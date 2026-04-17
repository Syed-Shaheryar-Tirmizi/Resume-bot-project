"""Password hashing and JWT helpers."""

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from backend.config import settings

# bcrypt has a 72-byte limit on the password input (documented in API validators).
BCRYPT_MAX_PASSWORD_BYTES = 72


def hash_password(plain: str) -> str:
    pw = plain.encode("utf-8")
    if len(pw) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes.")
    digest = bcrypt.hashpw(pw, bcrypt.gensalt())
    return digest.decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def create_access_token(*, subject: str) -> str:
    exp_ts = int(
        (datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)).timestamp()
    )
    to_encode = {"sub": subject, "exp": exp_ts}
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        if isinstance(sub, str) and sub:
            return sub
    except JWTError:
        return None
    return None
