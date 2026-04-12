from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.services import documents as doc_svc
from backend.services.resume_docx import build_resume_docx

router = APIRouter(prefix="/documents", tags=["documents"])


class ResumeExportRequest(BaseModel):
    content: str = Field(..., min_length=10, description="Resume text (markdown-style from chatbot)")


@router.post("/export-resume-docx")
def export_resume_docx(req: ResumeExportRequest) -> Response:
    buf = build_resume_docx(req.content)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="resume.docx"'},
    )


@router.post("/extract")
async def extract_text(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        text = doc_svc.extract_text_from_upload(data, file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"text": text, "filename": file.filename}
