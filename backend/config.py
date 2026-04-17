from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o"
    openai_embed_model: str = "text-embedding-3-small"

    # Local Weaviate (default): host + ports. Ignored if weaviate_url is set.
    weaviate_http_host: str = "localhost"
    weaviate_http_port: int = 8080
    weaviate_grpc_port: int = 50051
    # Weaviate Cloud / custom cluster (optional). If set, API key is required.
    weaviate_url: str = ""
    weaviate_api_key: str = ""
    # Cloud gRPC init default is 2s in the client — too low for many networks; increase if startup fails.
    weaviate_timeout_init: float = 90.0
    # If gRPC is blocked by firewall but REST works, set WEAVIATE_SKIP_INIT_CHECKS=true (not ideal; prefer opening gRPC).
    weaviate_skip_init_checks: bool = False

    # Off by default (~40% scope): cross-domain CV transformer + voice (Whisper STT).
    enable_cv_domain_transform: bool = False
    enable_voice_input: bool = False

    google_application_credentials: str | None = None

    # Auth (PostgreSQL + JWT). When enable_auth is true, DATABASE_URL and JWT_SECRET_KEY are required.
    enable_auth: bool = False
    database_url: str = ""
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    @field_validator("openai_api_key", "weaviate_url", "weaviate_api_key", "database_url", mode="before")
    @classmethod
    def strip_str(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def strip_jwt_secret(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    def require_openai_key(self) -> None:
        if not self.openai_api_key:
            from backend.errors import missing_openai_key

            raise missing_openai_key()

    def weaviate_cloud_mode(self) -> bool:
        return bool(self.weaviate_url)

    def weaviate_cluster_url(self) -> str:
        """Full HTTPS URL for Weaviate Cloud (adds scheme if host-only)."""
        u = self.weaviate_url.strip()
        if not u:
            return u
        if u.startswith(("http://", "https://")):
            return u
        return f"https://{u}"


settings = Settings()
