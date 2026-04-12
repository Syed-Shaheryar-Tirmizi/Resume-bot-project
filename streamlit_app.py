import os
import re
from pathlib import Path
from typing import Optional

import httpx
import streamlit as st

from backend.config import settings
from streamlit_errors import format_api_error

DEFAULT_API = os.environ.get("RESUME_INSIGHT_API", "http://127.0.0.1:8000")


def api_base() -> str:
    return DEFAULT_API.rstrip("/")


@st.cache_data(ttl=15, show_spinner=False)
def fetch_ready_status(api_root: str) -> tuple[bool, list[str]]:
    root = (api_root or DEFAULT_API).rstrip("/")
    try:
        with httpx.Client(timeout=12.0) as client:
            r = client.get(f"{root}/ready")
            r.raise_for_status()
            data = r.json()
            if data.get("ready"):
                return True, []
            return False, list(data.get("messages") or ["The API reported it is not fully ready."])
    except httpx.HTTPStatusError as e:
        return False, [format_api_error(e)]
    except httpx.RequestError as e:
        return False, [format_api_error(e)]
    except Exception as e:
        return False, [format_api_error(e)]


def post_json(path: str, payload: dict) -> dict:
    with httpx.Client(timeout=120.0) as client:
        r = client.post(f"{api_base()}{path}", json=payload)
        r.raise_for_status()
        return r.json()


def post_file(path: str, field: str, file_bytes: bytes, filename: str) -> dict:
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            f"{api_base()}{path}",
            files={field: (filename, file_bytes)},
        )
        r.raise_for_status()
        return r.json()


def post_match_index_file(title: str, file_bytes: bytes, filename: str) -> dict:
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            f"{api_base()}/api/match/index-file",
            data={"title": title.strip()},
            files={"file": (filename or "resume.pdf", file_bytes)},
        )
        r.raise_for_status()
        return r.json()


def post_match_query_file(file_bytes: bytes, filename: str, top_k: int) -> dict:
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            f"{api_base()}/api/match/query-file",
            data={"top_k": str(int(top_k))},
            files={"file": (filename or "job.txt", file_bytes)},
        )
        r.raise_for_status()
        return r.json()


def get_json(path: str) -> dict:
    with httpx.Client(timeout=60.0) as client:
        r = client.get(f"{api_base()}{path}")
        r.raise_for_status()
        return r.json()


def delete_json(path: str) -> dict:
    with httpx.Client(timeout=120.0) as client:
        r = client.delete(f"{api_base()}{path}")
        r.raise_for_status()
        if r.content:
            return r.json()
        return {}


def post_export_docx(content: str) -> bytes:
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            f"{api_base()}/api/documents/export-resume-docx",
            json={"content": content},
        )
        r.raise_for_status()
        return r.content


def last_assistant_text() -> str:
    for m in reversed(st.session_state.chat_messages):
        if m["role"] == "assistant":
            return m["content"]
    return ""


def safe_resume_filename(title: str, index: int, ext: str) -> str:
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (title or "").strip()) or f"resume-{index}"
    return (base[:120] if len(base) > 120 else base) + ext


def index_title_for_resume_upload(
    uploaded_name: str,
    file_index: int,
    user_title: str,
    total_files: int,
) -> Optional[str]:
    """
    Build the resume title for the index API.
    One file: user_title must be non-empty (same as manual index).
    Several files: each title is filename stem, optionally prefixed by user_title.
    """
    user = user_title.strip()
    raw_stem = Path(uploaded_name or "").stem.strip()
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", raw_stem) or f"resume-{file_index}"
    if total_files == 1:
        if not user:
            return None
        return user[:256]
    if user:
        combined = f"{user} – {stem}"
    else:
        combined = stem
    return combined[:256]


def _inject_app_theme_css() -> None:
    """Polish beyond theme colors; hide Streamlit sidebar (no sidebar UI)."""
    st.markdown(
        """
        <style>
            .stApp {
                background: linear-gradient(165deg, #0b1120 0%, #0f172a 40%, #111827 100%);
            }
            [data-testid="stSidebar"],
            [data-testid="collapsedControl"] {
                display: none !important;
            }
            [data-testid="stAppViewContainer"] > .main {
                margin-left: 0 !important;
            }
            [data-testid="stHeader"] {
                background: rgba(15, 23, 42, 0.92);
                border-bottom: 1px solid rgba(45, 212, 191, 0.12);
            }
            .stTabs [data-baseweb="tab-list"] {
                gap: 0.5rem;
                background-color: rgba(30, 41, 59, 0.6);
                border-radius: 0.5rem;
                padding: 0.25rem 0.35rem;
            }
            .stTabs [aria-selected="true"] {
                background: rgba(45, 212, 191, 0.15) !important;
                border-radius: 0.35rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="Resume Insight AI",
    layout="wide",
    initial_sidebar_state="collapsed",
)
_inject_app_theme_css()
st.title("Resume Insight AI")
st.caption(
    "AI resume creation and semantic matching (Weaviate required)."
    + (
        " Domain transform and voice input are disabled in this build."
        if not (settings.enable_cv_domain_transform or settings.enable_voice_input)
        else ""
    )
)

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "export_docx" not in st.session_state:
    st.session_state.export_docx = None

ready_ok, ready_msgs = fetch_ready_status(api_base())
if not ready_ok:
    for msg in ready_msgs:
        st.error(msg)
else:
    st.caption("API status: ready (OpenAI key set, Weaviate connected).")

_tab_labels = ["Resume chatbot"]
if settings.enable_cv_domain_transform:
    _tab_labels.append("Domain transform")
_tab_labels.append("Semantic matching")
_tab_labels.append("Stored resumes")
if settings.enable_voice_input:
    _tab_labels.append("Voice (Whisper)")
_tab_widgets = st.tabs(_tab_labels)
_i = 0
tab_chat = _tab_widgets[_i]
_i += 1
tab_xform = None
if settings.enable_cv_domain_transform:
    tab_xform = _tab_widgets[_i]
    _i += 1
tab_match = _tab_widgets[_i]
_i += 1
tab_stored = _tab_widgets[_i]
_i += 1
tab_voice = None
if settings.enable_voice_input:
    tab_voice = _tab_widgets[_i]

with tab_chat:
    st.subheader("Conversational resume creation")
    for m in st.session_state.chat_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    prompt = st.chat_input("Describe your background or ask to draft your resume")
    if prompt:
        st.session_state.export_docx = None
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        try:
            payload = {"messages": st.session_state.chat_messages}
            data = post_json("/api/chat", payload)
            reply = data.get("reply", "")
            st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            st.error(format_api_error(e))
        except Exception as e:
            st.error(format_api_error(e))
        st.rerun()
    if st.button("Clear conversation"):
        st.session_state.chat_messages = []
        st.session_state.export_docx = None
        st.rerun()

    st.divider()
    st.markdown("**Download formatted resume** — builds a Word file from the **latest AI reply**.")
    dc1, dc2 = st.columns(2)
    with dc1:
        if st.button("Build Word document (.docx)"):
            t = last_assistant_text().strip()
            if len(t) < 10:
                st.warning("Ask the chatbot to draft your resume first.")
            else:
                try:
                    st.session_state.export_docx = post_export_docx(t)
                    st.success("Document ready — download below.")
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    st.error(format_api_error(e))
                except Exception as e:
                    st.error(format_api_error(e))
    with dc2:
        if st.session_state.export_docx:
            st.download_button(
                label="Download resume.docx",
                data=st.session_state.export_docx,
                file_name="resume.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="download_resume_docx",
            )

if tab_xform is not None:
    with tab_xform:
        st.subheader("Cross-domain resume transformation")
        resume_text = st.text_area("Paste resume text", height=220, placeholder="Full resume…")
        target = st.text_input("Target domain", placeholder="e.g. Digital Marketing")
        if st.button("Transform"):
            if len(resume_text.strip()) < 20 or not target.strip():
                st.warning("Provide resume text (20+ chars) and a target domain.")
            else:
                try:
                    out = post_json(
                        "/api/transform",
                        {"resume_text": resume_text, "target_domain": target.strip()},
                    )
                    st.markdown(out.get("transformed_resume", ""))
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    st.error(format_api_error(e))
                except Exception as e:
                    st.error(format_api_error(e))

with tab_match:
    st.subheader("Upload resume & job description, then match")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Your resume**")
        up_resume = st.file_uploader(
            "Upload one or more resumes (PDF, DOCX, or TXT) — indexed directly on the server (no separate extract step)",
            type=["pdf", "docx", "txt"],
            key="up_resume",
            accept_multiple_files=True,
        )
        title = st.text_input(
            "Title / name (required for a single file; optional prefix when uploading several)",
            key="idx_title",
        )
        if up_resume:
            n_files = len(up_resume)
            btn_label = (
                "Index from uploaded file"
                if n_files == 1
                else f"Index all uploaded files ({n_files})"
            )
            if n_files > 1:
                st.caption(
                    "With multiple files, each resume is titled using its file name (without extension). "
                    "If you enter text in the field above, it is added as a prefix for every file."
                )
            if st.button(btn_label, key="btn_index_resume_file"):
                if n_files == 1 and not title.strip():
                    st.warning(
                        "Please enter a title or name for this resume. It is used to label your resume in match results."
                    )
                else:
                    ok = 0
                    store = None
                    errs = []
                    for i, uf in enumerate(up_resume, start=1):
                        t = index_title_for_resume_upload(uf.name or "", i, title, n_files)
                        if t is None:
                            st.warning(
                                "Please enter a title or name for this resume. It is used to label your resume in match results."
                            )
                            break
                        try:
                            res = post_match_index_file(
                                t,
                                uf.getvalue(),
                                uf.name or "resume.pdf",
                            )
                            ok += 1
                            store = res.get("store")
                        except (httpx.HTTPStatusError, httpx.RequestError) as e:
                            errs.append(f"{uf.name or 'file'}: {format_api_error(e)}")
                        except Exception as e:
                            errs.append(f"{uf.name or 'file'}: {format_api_error(e)}")
                    if ok and not errs:
                        st.success(
                            f"Indexed {ok} resume(s) successfully"
                            + (f" (store: {store})." if store else ".")
                        )
                    elif ok and errs:
                        st.success(f"Indexed {ok} resume(s) (store: {store}). Some files failed:")
                        for err in errs:
                            st.error(err)
                    elif errs:
                        for err in errs:
                            st.error(err)
        body = st.text_area(
            "Or paste resume text here and use “Index from text”",
            height=180,
            key="idx_body",
        )
        if st.button("Index from text"):
            if not title.strip():
                st.warning(
                    "Please enter a title or name for this resume. It is used to label your resume in match results."
                )
            elif len(body.strip()) < 20:
                st.warning("Resume content should be at least 20 characters.")
            else:
                try:
                    res = post_json(
                        "/api/match/index",
                        {"title": title.strip(), "content": body.strip()},
                    )
                    st.success(f"Resume indexed successfully (store: {res.get('store')}).")
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    st.error(format_api_error(e))
                except Exception as e:
                    st.error(format_api_error(e))
    with c2:
        st.markdown("**Job description**")
        up_jd = st.file_uploader(
            "Upload job description (PDF, DOCX, or TXT) — matched directly on the server (no separate extract step)",
            type=["pdf", "docx", "txt"],
            key="up_jd",
        )
        if up_jd is not None:
            if st.button("Run semantic match from uploaded file", key="btn_match_jd_file"):
                try:
                    tk = int(st.session_state.get("match_top_k", 5))
                    res = post_match_query_file(
                        up_jd.getvalue(),
                        up_jd.name or "job.txt",
                        tk,
                    )
                    for k in list(st.session_state.keys()):
                        if isinstance(k, str) and k.startswith("match_docx_"):
                            del st.session_state[k]
                    st.session_state["last_match_result"] = res
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    st.error(format_api_error(e))
                except Exception as e:
                    st.error(format_api_error(e))
        top_k = st.number_input("Top K", min_value=1, max_value=20, value=5, key="match_top_k")
        jd = st.text_area(
            "Or paste job description here and use “Run semantic match (from text)”",
            height=180,
            key="jd",
        )
        if st.button("Run semantic match (from text)"):
            if len(jd.strip()) < 20:
                st.warning("Job description should be at least 20 characters.")
            else:
                try:
                    res = post_json(
                        "/api/match/query",
                        {"job_description": jd.strip(), "top_k": int(top_k)},
                    )
                    for k in list(st.session_state.keys()):
                        if isinstance(k, str) and k.startswith("match_docx_"):
                            del st.session_state[k]
                    st.session_state["last_match_result"] = res
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    st.error(format_api_error(e))
                except Exception as e:
                    st.error(format_api_error(e))

    match_res = st.session_state.get("last_match_result")
    if match_res:
        st.divider()
        mr1, mr2 = st.columns([4, 1])
        with mr1:
            st.markdown("**Match results**")
        with mr2:
            if st.button("Clear results", key="btn_clear_match_results"):
                del st.session_state["last_match_result"]
                for k in list(st.session_state.keys()):
                    if isinstance(k, str) and k.startswith("match_docx_"):
                        del st.session_state[k]
                st.rerun()
        st.caption(
            f"Vector store: {match_res.get('store')} — text in each result may be truncated by the server (up to ~8k characters)."
        )
        for i, row in enumerate(match_res.get("results") or [], start=1):
            title = (row.get("title") or "").strip() or "Untitled"
            rid = row.get("resume_id") or ""
            content = row.get("content") or ""
            with st.expander(f"#{i} — {title}"):
                docx_key = f"match_docx_{rid}_{i}"
                dl1, dl2 = st.columns(2)
                with dl1:
                    st.download_button(
                        label="Download .txt",
                        data=content.encode("utf-8"),
                        file_name=safe_resume_filename(title, i, ".txt"),
                        mime="text/plain",
                        key=f"match_dl_txt_{i}_{rid}",
                    )
                with dl2:
                    if docx_key in st.session_state:
                        st.download_button(
                            label="Download Word (.docx)",
                            data=st.session_state[docx_key],
                            file_name=safe_resume_filename(title, i, ".docx"),
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"match_dl_docx_{i}_{rid}",
                        )
                    elif st.button(
                        "Build Word (.docx)",
                        key=f"match_prep_docx_{i}_{rid}",
                        help="Creates a formatted Word file from this match result.",
                    ):
                        try:
                            st.session_state[docx_key] = post_export_docx(content)
                        except (httpx.HTTPStatusError, httpx.RequestError) as e:
                            st.error(format_api_error(e))
                        except Exception as e:
                            st.error(format_api_error(e))
                        else:
                            st.rerun()
                st.text(content[:4000] + ("…" if len(content) > 4000 else ""))

with tab_stored:
    st.subheader("Stored resumes")
    st.caption(
        "Indexed resumes used for semantic matching. Delete entries you no longer need, or clear the whole list."
    )
    if not ready_ok:
        st.info("When the API is ready (see status above), you can view and manage indexed resumes here.")
    else:
        head_a, head_b = st.columns([1, 2])
        with head_a:
            st.button("Refresh list", key="btn_refresh_stored", help="Reload from the vector store")
        with head_b:
            confirm_all = st.checkbox(
                "I understand that deleting all stored resumes cannot be undone.",
                key="chk_delete_all_stored",
            )
            if st.button("Delete all stored resumes", disabled=not confirm_all, key="btn_delete_all_stored"):
                try:
                    cleared = delete_json("/api/match/resumes")
                    n = int(cleared.get("deleted", 0))
                    st.success(f"Removed {n} resume(s) from the store ({cleared.get('store', '')}).")
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    st.error(format_api_error(e))
                except Exception as e:
                    st.error(format_api_error(e))

        try:
            listing = get_json("/api/match/resumes")
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            st.error(format_api_error(e))
            listing = None
        except Exception as e:
            st.error(format_api_error(e))
            listing = None
        if listing is not None:
            rows = listing.get("resumes") or []
            st.caption(f"Vector store: {listing.get('store', '')} — {len(rows)} resume(s).")
            if not rows:
                st.info("No resumes indexed yet. Add one under **Semantic matching**.")
            else:
                for item in rows:
                    rid = item.get("resume_id") or ""
                    title = (item.get("title") or "").strip() or "Untitled"
                    excerpt = item.get("content_excerpt") or ""
                    col_l, col_r = st.columns([5, 1])
                    with col_l:
                        st.markdown(f"**{title}**")
                        if excerpt:
                            st.caption(excerpt)
                    with col_r:
                        if rid and st.button("Delete", key=f"del_stored_{rid}"):
                            try:
                                delete_json(f"/api/match/{rid}")
                                st.rerun()
                            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                                st.error(format_api_error(e))
                            except Exception as e:
                                st.error(format_api_error(e))
                    st.divider()

if tab_voice is not None:
    with tab_voice:
        st.subheader("Speech to text (OpenAI Whisper via API)")
        up = st.file_uploader("Upload audio (mp3, wav, m4a, webm, …)", type=None)
        if up and st.button("Transcribe"):
            raw = up.getvalue()
            try:
                data = post_file("/api/voice/transcribe", "audio", raw, up.name or "clip.webm")
                st.text_area("Transcript", value=data.get("text", ""), height=200)
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                st.error(format_api_error(e))
            except Exception as e:
                st.error(format_api_error(e))
