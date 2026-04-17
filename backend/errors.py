"""Application errors with stable codes for clients and UI."""

from fastapi import Request, status
from fastapi.responses import JSONResponse


class ServiceError(Exception):
    """Maps to JSON: {\"detail\": {\"error\": code, \"message\": message}}."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


async def service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"error": exc.code, "message": exc.message}},
        headers=exc.headers,
    )


def missing_openai_key() -> ServiceError:
    return ServiceError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "missing_openai_key",
        "OPENAI_API_KEY is not set or empty. Add it to the server environment or .env file.",
    )


def weaviate_unavailable(message: str) -> ServiceError:
    return ServiceError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "weaviate_unavailable",
        message,
    )


def auth_not_configured() -> ServiceError:
    return ServiceError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "auth_not_configured",
        "Authentication is not enabled or not fully configured on the server.",
    )


def email_already_registered() -> ServiceError:
    return ServiceError(
        status.HTTP_409_CONFLICT,
        "email_taken",
        "An account with this email already exists.",
    )


def invalid_credentials() -> ServiceError:
    return ServiceError(
        status.HTTP_401_UNAUTHORIZED,
        "invalid_credentials",
        "Incorrect email or password.",
    )
