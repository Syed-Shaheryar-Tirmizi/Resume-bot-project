import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.errors import ServiceError, service_error_handler
from backend.routers import chat, documents, match, transform, voice
from backend.services import vector_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required. Set it in .env or the environment before starting the server."
        )
    logger.info("Initializing Weaviate (required vector store)…")
    await asyncio.to_thread(vector_store.init_weaviate)
    logger.info("Weaviate ready; API startup complete.")
    yield
    logger.info("Shutting down Weaviate client…")
    await asyncio.to_thread(vector_store.shutdown_weaviate)


app = FastAPI(title="Resume Insight AI", version="0.1.0", lifespan=lifespan)
app.add_exception_handler(ServiceError, service_error_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
if settings.enable_cv_domain_transform:
    app.include_router(transform.router, prefix="/api")
app.include_router(match.router, prefix="/api")
if settings.enable_voice_input:
    app.include_router(voice.router, prefix="/api")
app.include_router(documents.router, prefix="/api")


@app.get("/health")
def health() -> dict:
    """Liveness: process is running."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    """Readiness: configuration and vector DB connection."""
    checks = {
        "openai_api_key_configured": bool(settings.openai_api_key),
        "weaviate_connected": vector_store.is_connected(),
    }
    ok = all(checks.values())
    messages: list[str] = []
    if not checks["openai_api_key_configured"]:
        messages.append("OPENAI_API_KEY is missing on the server.")
    if not checks["weaviate_connected"]:
        messages.append("Weaviate is not connected; restart the API after fixing the vector database.")
    return {"ready": ok, "checks": checks, "messages": messages}
