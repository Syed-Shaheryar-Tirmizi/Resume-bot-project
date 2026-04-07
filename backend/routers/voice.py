from fastapi import APIRouter, File, UploadFile

from backend.services import llm

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    data = await audio.read()
    if not data:
        return {"text": "", "error": "empty file"}
    name = audio.filename or "audio.webm"
    text = llm.transcribe_audio(data, name)
    return {"text": text}
