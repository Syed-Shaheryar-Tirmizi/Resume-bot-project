import logging

from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError

from backend.config import settings
from backend.errors import ServiceError

logger = logging.getLogger(__name__)


def _openai_service_error(exc: Exception) -> ServiceError:
    if isinstance(exc, AuthenticationError):
        return ServiceError(
            401,
            "openai_authentication_failed",
            "OpenAI rejected the API key. Check OPENAI_API_KEY is correct and active.",
        )
    if isinstance(exc, RateLimitError):
        return ServiceError(
            429,
            "openai_rate_limited",
            "OpenAI rate limit reached. Wait a moment and try again.",
        )
    if isinstance(exc, APIConnectionError):
        return ServiceError(
            503,
            "openai_unreachable",
            "Cannot reach OpenAI. Check your network, firewall, or proxy settings.",
        )
    if isinstance(exc, APIError):
        return ServiceError(
            502,
            "openai_api_error",
            getattr(exc, "message", None) or str(exc) or "OpenAI API returned an error.",
        )
    logger.exception("Unexpected error during OpenAI embeddings call")
    return ServiceError(502, "openai_unexpected", str(exc) or "Unexpected OpenAI error.")


def get_client() -> OpenAI:
    settings.require_openai_key()
    return OpenAI(api_key=settings.openai_api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = get_client()
    try:
        r = client.embeddings.create(model=settings.openai_embed_model, input=texts)
        return [d.embedding for d in r.data]
    except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as e:
        raise _openai_service_error(e) from e
