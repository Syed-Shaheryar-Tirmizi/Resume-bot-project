import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.services import vector_store

router = APIRouter(prefix="/match", tags=["match"])


class IndexRequest(BaseModel):
    title: str = Field(default="", max_length=256)
    content: str = Field(..., min_length=20)


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


class DeleteRequest(BaseModel):
    resume_id: str = Field(..., min_length=1, max_length=128)


_STORE = "weaviate"


@router.post("/index", response_model=IndexResponse)
def index_resume(req: IndexRequest) -> IndexResponse:
    rid = str(uuid.uuid4())
    rid = vector_store.index_resume(rid, req.title.strip(), req.content.strip())
    return IndexResponse(resume_id=rid, store=_STORE)


@router.post("/query", response_model=MatchResponse)
def match_job(req: MatchRequest) -> MatchResponse:
    results = vector_store.match_job(req.job_description.strip(), top_k=req.top_k)
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


@router.delete("/{resume_id}")
def delete_resume(resume_id: str) -> dict:
    vector_store.remove_resume(resume_id)
    return {"ok": True, "resume_id": resume_id}
