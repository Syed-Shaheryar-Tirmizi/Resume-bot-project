from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.services import llm

router = APIRouter(prefix="/transform", tags=["transform"])

TRANSFORM_SYSTEM = """You are an expert career coach and resume editor.
Rewrite the given resume so it fits the target job domain.
Preserve truthful facts (employers, dates, degrees) but reframe skills, summary, and bullets using domain-relevant language.
Output the full revised resume in markdown format."""


class TransformRequest(BaseModel):
    resume_text: str = Field(..., min_length=20)
    target_domain: str = Field(..., min_length=2, max_length=200)


class TransformResponse(BaseModel):
    transformed_resume: str


@router.post("", response_model=TransformResponse)
def transform(req: TransformRequest) -> TransformResponse:
    user = (
        f"Target domain: {req.target_domain.strip()}\n\n"
        f"Current resume:\n{req.resume_text.strip()}"
    )
    out = llm.chat_completion([{"role": "user", "content": user}], system=TRANSFORM_SYSTEM)
    return TransformResponse(transformed_resume=out)
