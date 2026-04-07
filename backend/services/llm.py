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
    logger.exception("Unexpected error during OpenAI chat/audio call")
    return ServiceError(502, "openai_unexpected", str(exc) or "Unexpected OpenAI error.")


def get_client() -> OpenAI:
    settings.require_openai_key()
    return OpenAI(api_key=settings.openai_api_key)


def chat_completion(messages: list[dict], system: str | None = None) -> str:
    client = get_client()
    msgs: list[dict] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)
    try:
        r = client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=msgs,
            temperature=0.4,
        )
        return (r.choices[0].message.content or "").strip()
    except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as e:
        raise _openai_service_error(e) from e


def transcribe_audio(file_bytes: bytes, filename: str) -> str:
    client = get_client()
    try:
        r = client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, file_bytes),
        )
        return (r.text or "").strip()
    except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as e:
        raise _openai_service_error(e) from e
