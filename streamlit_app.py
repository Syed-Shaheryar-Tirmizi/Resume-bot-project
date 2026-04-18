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


def auth_headers() -> dict[str, str]:
    token = st.session_state.get("auth_token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


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
        r = client.post(f"{api_base()}{path}", json=payload, headers=auth_headers())
        r.raise_for_status()
        return r.json()


def post_auth_login(email: str, password: str) -> dict:
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            f"{api_base()}/api/auth/login",
            json={"email": email, "password": password},
        )
        r.raise_for_status()
        return r.json()


def post_auth_register(email: str, password: str) -> dict:
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            f"{api_base()}/api/auth/register",
            json={"email": email, "password": password},
        )
        r.raise_for_status()
        return r.json()


def post_file(path: str, field: str, file_bytes: bytes, filename: str) -> dict:
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            f"{api_base()}{path}",
            files={field: (filename, file_bytes)},
            headers=auth_headers(),
        )
        r.raise_for_status()
        return r.json()


def post_match_index_file(title: str, file_bytes: bytes, filename: str) -> dict:
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            f"{api_base()}/api/match/index-file",
            data={"title": title.strip()},
            files={"file": (filename or "resume.pdf", file_bytes)},
            headers=auth_headers(),
        )
        r.raise_for_status()
        return r.json()


def post_match_query_file(file_bytes: bytes, filename: str, top_k: int) -> dict:
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            f"{api_base()}/api/match/query-file",
            data={"top_k": str(int(top_k))},
            files={"file": (filename or "job.txt", file_bytes)},
            headers=auth_headers(),
        )
        r.raise_for_status()
        return r.json()


def get_json(path: str) -> dict:
    with httpx.Client(timeout=60.0) as client:
        r = client.get(f"{api_base()}{path}", headers=auth_headers())
        r.raise_for_status()
        return r.json()


def delete_json(path: str) -> dict:
    with httpx.Client(timeout=120.0) as client:
        r = client.delete(f"{api_base()}{path}", headers=auth_headers())
        r.raise_for_status()
        if r.content:
            return r.json()
        return {}


def post_export_docx(content: str) -> bytes:
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            f"{api_base()}/api/documents/export-resume-docx",
            json={"content": content},
            headers=auth_headers(),
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
    st.markdown(
        """
        <style>
            .stApp { background: #F8FAFC; }

            [data-testid="stSidebar"],
            [data-testid="collapsedControl"] { display: none !important; }

            /* ══════════════════════════════
               HEADER — navy bar + amber underline
            ══════════════════════════════ */
            [data-testid="stHeader"] {
                background: #1E3A5F !important;
                border-bottom: 3px solid #F59E0B !important;
            }
            /* Streamlit injects a Deploy button area — keep it visible */
            [data-testid="stHeader"] button,
            [data-testid="stHeader"] a { color: #F1F5F9 !important; }

            /* ── Title and caption that appear below the header ── */
            .stApp .stMarkdown h1,
            .stApp h1 {
                color: #1E3A5F !important;
                font-size: 26px;
                font-weight: 700;
                border-left: 4px solid #F59E0B;
                padding-left: 12px;
                margin-bottom: 4px;
            }
            .stApp .stCaption p,
            .stCaption {
                color: #64748B !important;
                font-size: 12px;
            }

            /* ══════════════════════════════
               TABS
            ══════════════════════════════ */
            .stTabs [data-baseweb="tab-list"] {
                gap: 4px;
                background: #1E3A5F;
                border: 1px solid #2D4F7A;
                border-radius: 12px;
                padding: 5px;
            }
            .stTabs [data-baseweb="tab"] {
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
                color: #93B4D4 !important;
                padding: 9px 22px;
                background: transparent !important;
            }
            .stTabs [aria-selected="true"] {
                background: #F59E0B !important;
                color: #1C1400 !important;
                font-weight: 600 !important;
                border-radius: 8px !important;
                border: none !important;
                box-shadow: 0 2px 8px rgba(245,158,11,0.35) !important;
            }
            .stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {
                background: rgba(255,255,255,0.1) !important;
                color: #E2EEF9 !important;
            }
            .stTabs [data-baseweb="tab-highlight"],
            .stTabs [data-baseweb="tab-border"] { display: none; }

            /* ══════════════════════════════
               CHAT — container + bubbles
            ══════════════════════════════ */

            /* Outer chat wrapper */
            [data-testid="stChatMessageContainer"] {
                border: 2px solid #1E3A5F !important;
                border-radius: 14px !important;
                background: #EFF4FA !important;
                padding: 12px !important;
            }

            /* Input bar at bottom of chat */
            [data-testid="stChatInput"] {
                border: 2px solid #1E3A5F !important;
                border-top: 2px solid #1E3A5F !important;
                border-radius: 10px !important;
                background: #ffffff !important;
            }
            [data-testid="stChatInput"] textarea {
                background: #ffffff !important;
                font-size: 13px;
                color: #0F172A;
            }

            /* USER bubble */
            [data-testid="stChatMessage"][data-testid*="user"],
            div[data-testid="stChatMessage"]:has(img[alt="user avatar"]) {
                background: #1E3A5F !important;
                border: 1.5px solid #2D4F7A !important;
                border-radius: 12px !important;
                border-top-right-radius: 3px !important;
                padding: 12px 14px !important;
                margin-left: auto;
                margin-right: 0;
                max-width: 80%;
                color: #F1F5F9 !important;
            }
            [data-testid="stChatMessage"]:has(img[alt="user avatar"]) * {
                color: #F1F5F9 !important;
            }

            /* ASSISTANT bubble */
            [data-testid="stChatMessage"]:has(img[alt="assistant avatar"]),
            [data-testid="stChatMessage"]:not(:has(img[alt="user avatar"])) {
                background: #ffffff !important;
                border: 1.5px solid #B8CFEA !important;
                border-radius: 12px !important;
                border-top-left-radius: 3px !important;
                padding: 12px 14px !important;
                margin-right: auto;
                max-width: 80%;
            }

            /* Fallback: alternate rows if :has() not supported */
            [data-testid="stChatMessage"]:nth-child(odd) {
                background: #ffffff;
                border: 1.5px solid #B8CFEA;
                border-radius: 12px;
                margin-bottom: 10px;
            }
            [data-testid="stChatMessage"]:nth-child(even) {
                background: #1E3A5F;
                border: 1.5px solid #2D4F7A;
                border-radius: 12px;
                margin-bottom: 10px;
                color: #F1F5F9;
            }
            [data-testid="stChatMessage"]:nth-child(even) * {
                color: #F1F5F9 !important;
            }

            /* ══════════════════════════════
               BUTTONS
            ══════════════════════════════ */
            button[kind="primary"],
            .stButton > button[kind="primary"] {
                background: #1E3A5F !important;
                color: #F1F5F9 !important;
                border: none;
                border-radius: 9px;
                font-weight: 500;
            }
            .stButton > button {
                background: #ffffff;
                color: #1E3A5F;
                border: 1.5px solid #B8CFEA;
                border-radius: 9px;
                font-size: 13px;
                font-weight: 500;
                white-space: nowrap;
                padding: 0.45rem 0.9rem;
                min-height: 2.25rem;
            }
            .stButton > button:hover { background: #EEF3F9; }
            /* Avoid clipping buttons in horizontal layouts (e.g. title + Log out) */
            [data-testid="stHorizontalBlock"] > [data-testid="column"] {
                overflow: visible !important;
            }
            .stDownloadButton > button {
                background: #F0FDF4 !important;
                border: 1.5px solid #BBF7D0 !important;
                color: #166534 !important;
                border-radius: 9px;
            }

            /* ══════════════════════════════
               INPUTS / FORMS
            ══════════════════════════════ */
            .stTextInput input,
            .stTextArea textarea,
            .stNumberInput input {
                background: #ffffff;
                border: 1.5px solid #B8CFEA !important;
                border-radius: 9px;
                font-size: 13px;
                color: #0F172A;
            }
            .stTextInput input:focus,
            .stTextArea textarea:focus {
                border-color: #1E3A5F !important;
                box-shadow: 0 0 0 3px rgba(30,58,95,0.1) !important;
            }
            [data-testid="stFileUploader"] {
                border: 1.5px dashed #B8CFEA !important;
                border-radius: 10px;
                background: #F0F5FA;
            }
            .streamlit-expanderHeader {
                border: 1.5px solid #B8CFEA !important;
                border-radius: 10px;
            }
            .streamlit-expanderContent {
                border: 1.5px solid #B8CFEA !important;
                border-top: none !important;
                border-radius: 0 0 10px 10px;
            }

            hr { border-color: #DBEAFE; border-width: 1px; }
            /* Extra top space so the first row (title / actions) is not clipped by the fixed Streamlit header */
            .block-container { padding-top: 2.75rem; padding-bottom: 2rem; max-width: 1100px; }
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

if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None

if settings.enable_auth and not st.session_state.auth_token:
    st.title("Resume Insight AI")
    st.caption("Sign in or register to continue. The API must run with PostgreSQL auth enabled.")
    tab_login, tab_reg = st.tabs(["Log in", "Register"])
    with tab_login:
        le = st.text_input("Email", key="wall_login_email", autocomplete="email")
        lp = st.text_input("Password", type="password", key="wall_login_password")
        if st.button("Log in", key="wall_btn_login", type="primary"):
            if not (le or "").strip() or not lp:
                st.warning("Enter email and password.")
            else:
                try:
                    data = post_auth_login((le or "").strip(), lp)
                    st.session_state.auth_token = data.get("access_token")
                    st.session_state.user_email = data.get("email")
                    st.rerun()
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    st.error(format_api_error(e))
                except Exception as e:
                    st.error(format_api_error(e))
    with tab_reg:
        re = st.text_input("Email", key="wall_reg_email", autocomplete="email")
        rp = st.text_input("Password", type="password", key="wall_reg_password")
        rp2 = st.text_input("Confirm password", type="password", key="wall_reg_password2")
        st.caption("Password must be at least 8 characters.")
        if st.button("Create account", key="wall_btn_register", type="primary"):
            e = (re or "").strip()
            if not e or not rp:
                st.warning("Enter email and password.")
            elif rp != rp2:
                st.warning("Passwords do not match.")
            elif len(rp) < 8:
                st.warning("Password must be at least 8 characters.")
            else:
                try:
                    data = post_auth_register(e, rp)
                    st.session_state.auth_token = data.get("access_token")
                    st.session_state.user_email = data.get("email")
                    st.rerun()
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    st.error(format_api_error(e))
                except Exception as e:
                    st.error(format_api_error(e))
    st.stop()

st.title("Resume Insight AI")
# Log out on its own row below the title so it stays below the fixed app header (same row was clipped at the top).
if settings.enable_auth and st.session_state.auth_token:
    _spacer, _logout_col = st.columns([6, 2])
    with _logout_col:
        if st.button("Log out", key="btn_logout", use_container_width=True):
            st.session_state.auth_token = None
            st.session_state.user_email = None
            st.rerun()

st.caption(
    "AI resume creation and semantic matching (Weaviate required)."
    + (
        " Domain transform and voice input are disabled in this build."
        if not (settings.enable_cv_domain_transform or settings.enable_voice_input)
        else ""
    )
)
if settings.enable_auth and st.session_state.user_email:
    st.caption(f"Signed in as {st.session_state.user_email}.")

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
