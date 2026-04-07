from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from backend.services import llm

router = APIRouter(prefix="/chat", tags=["chat"])

RESUME_BOT_SYSTEM = """You are Resume Insight AI, a professional resume-writing assistant.
Help the user build or refine their resume through conversation.
Ask concise follow-up questions when information is missing.
When the user asks for a full resume, output a clear, structured resume using markdown:
- One top-level heading (#) for the person's name or document title
- ## for section titles: Summary, Skills, Experience, Education, etc.
- ### for employer or school names where helpful
- Bullet lines starting with - for skills and achievement bullets
- Use **bold** sparingly for role titles or keywords
Stay factual; do not invent employers or degrees."""


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    msgs = [{"role": m.role, "content": m.content} for m in req.messages]
    reply = llm.chat_completion(msgs, system=RESUME_BOT_SYSTEM)
    return ChatResponse(reply=reply)
