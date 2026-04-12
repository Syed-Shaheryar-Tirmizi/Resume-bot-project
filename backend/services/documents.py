from io import BytesIO

from docx import Document
from pypdf import PdfReader


def extract_text_from_pdf(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "\n".join(parts).strip()


def extract_text_from_docx(data: bytes) -> str:
    doc = Document(BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text).strip()


def extract_text_from_upload(data: bytes, filename: str) -> str:
    """Extract plain text from PDF, DOCX, or TXT bytes. Raises ValueError on empty or unsupported type."""
    if not data:
        raise ValueError("empty file")
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(data)
    if name.endswith(".docx"):
        return extract_text_from_docx(data)
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="replace").strip()
    raise ValueError("unsupported file type; use .pdf, .docx, or .txt")
