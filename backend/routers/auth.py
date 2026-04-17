from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db import get_db
from backend.errors import auth_not_configured, email_already_registered, invalid_credentials
from backend.models import User
from backend.security import (
    BCRYPT_MAX_PASSWORD_BYTES,
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_rules(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Password cannot be only whitespace.")
        if len(v.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes (bcrypt limit)."
            )
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, v: str) -> str:
        if len(v.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes (bcrypt limit)."
            )
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


def _require_auth_enabled() -> None:
    if not settings.enable_auth or not settings.jwt_secret_key:
        raise auth_not_configured()


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    _require_auth_enabled()
    existing = db.scalars(select(User).where(User.email == req.email.lower())).first()
    if existing is not None:
        raise email_already_registered()
    user = User(
        email=req.email.lower(),
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token, email=user.email)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    _require_auth_enabled()
    user = db.scalars(select(User).where(User.email == req.email.lower())).first()
    if user is None or not verify_password(req.password, user.hashed_password):
        raise invalid_credentials()
    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token, email=user.email)
