import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from backend.services import documents as doc_svc
from backend.services import vector_store
from backend.routers.deps import require_current_user_email

router = APIRouter(prefix="/match", tags=["match"])


class IndexRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=20)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("title must not be empty or whitespace only")
        return s


class IndexResponse(BaseModel):
    resume_id: str
    store: str


class MatchRequest(BaseModel):
    job_description: str = Field(..., min_length=20)
    top_k: int = Field(default=5, ge=1, le=50)


class MatchItem(BaseModel):
    resume_id: str
    title: str
    content: str
    score: float


class MatchResponse(BaseModel):
    results: list[MatchItem]
    store: str


class StoredResumeItem(BaseModel):
    resume_id: str
    title: str
    content_excerpt: str


class ListResumesResponse(BaseModel):
    resumes: list[StoredResumeItem]
    store: str


_STORE = "weaviate"


def _build_match_response(job_description: str, top_k: int, user_email: str) -> MatchResponse:
    results = vector_store.match_job(job_description.strip(), user_email=user_email, top_k=top_k)
    return MatchResponse(
        results=[
            MatchItem(
                resume_id=r.resume_id,
                title=r.title,
                content=r.content[:8000] if len(r.content) > 8000 else r.content,
                score=round(r.score, 6),
            )
            for r in results
        ],
        store=_STORE,
    )


@router.post("/index", response_model=IndexResponse)
def index_resume(
    req: IndexRequest,
    user_email: str = Depends(require_current_user_email),
) -> IndexResponse:
    rid = str(uuid.uuid4())
    rid = vector_store.index_resume(rid, req.title.strip(), req.content.strip(), user_email=user_email)
    return IndexResponse(resume_id=rid, store=_STORE)


@router.post("/index-file", response_model=IndexResponse)
async def index_resume_file(
    title: str = Form(..., min_length=1, max_length=256),
    file: UploadFile = File(...),
    user_email: str = Depends(require_current_user_email),
) -> IndexResponse:
    """Upload a resume file (PDF/DOCX/TXT); text is extracted on the server and indexed in one step."""
    data = await file.read()
    try:
        text = doc_svc.extract_text_from_upload(data, file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    title_clean = title.strip()
    if not title_clean:
        raise HTTPException(status_code=422, detail="title must not be empty")
    content = text.strip()
    if len(content) < 20:
        raise HTTPException(
            status_code=422,
            detail="extracted text must be at least 20 characters",
        )
    rid = str(uuid.uuid4())
    rid = vector_store.index_resume(rid, title_clean, content, user_email=user_email)
    return IndexResponse(resume_id=rid, store=_STORE)


@router.get("/resumes", response_model=ListResumesResponse)
def list_resumes(user_email: str = Depends(require_current_user_email)) -> ListResumesResponse:
    rows = vector_store.list_stored_resumes(user_email=user_email)
    return ListResumesResponse(
        resumes=[
            StoredResumeItem(
                resume_id=r.resume_id,
                title=r.title,
                content_excerpt=r.content_excerpt,
            )
            for r in rows
        ],
        store=_STORE,
    )


@router.delete("/resumes")
def delete_all_resumes(user_email: str = Depends(require_current_user_email)) -> dict:
    n = vector_store.clear_all_resumes(user_email=user_email)
    return {"ok": True, "deleted": n, "store": _STORE}


@router.post("/query", response_model=MatchResponse)
def match_job(
    req: MatchRequest,
    user_email: str = Depends(require_current_user_email),
) -> MatchResponse:
    return _build_match_response(req.job_description, req.top_k, user_email)


@router.post("/query-file", response_model=MatchResponse)
async def match_job_file(
    top_k: int = Form(5, ge=1, le=50),
    file: UploadFile = File(...),
    user_email: str = Depends(require_current_user_email),
) -> MatchResponse:
    """Upload a job description file (PDF/DOCX/TXT); text is extracted on the server and used for semantic match."""
    data = await file.read()
    try:
        text = doc_svc.extract_text_from_upload(data, file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    jd = text.strip()
    if len(jd) < 20:
        raise HTTPException(
            status_code=422,
            detail="extracted job description must be at least 20 characters",
        )
    return _build_match_response(jd, top_k, user_email)


@router.delete("/{resume_id}")
def delete_resume(
    resume_id: str,
    user_email: str = Depends(require_current_user_email),
) -> dict:
    vector_store.remove_resume(resume_id, user_email=user_email)
    return {"ok": True, "resume_id": resume_id}
