from fastapi import Header, status

from backend.config import settings
from backend.errors import ServiceError, auth_not_configured
from backend.security import decode_token


def require_current_user_email(
    authorization: str | None = Header(default=None),
) -> str:
    if not settings.enable_auth:
        return "public@local"
    if not settings.jwt_secret_key:
        raise auth_not_configured()
    if not authorization:
        raise ServiceError(
            status.HTTP_401_UNAUTHORIZED,
            "missing_token",
            "Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ServiceError(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_token",
            "Authorization must be in the format: Bearer <token>.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email = decode_token(token.strip())
    if not email:
        raise ServiceError(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_token",
            "Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return email.lower()
