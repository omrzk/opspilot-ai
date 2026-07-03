"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProviderName = Literal["anthropic", "openrouter", "ollama", "openai_compatible"]
EmbeddingProviderName = Literal["ollama", "openai_compatible"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    secret_key: str = Field(
        default="dev-only-secret-do-not-use-in-production-7f3a", alias="OPSPILOT_SECRET_KEY"
    )
    environment: str = Field(default="development", alias="OPSPILOT_ENVIRONMENT")
    cors_origins: str = Field(default="http://localhost:3000", alias="OPSPILOT_CORS_ORIGINS")
    access_token_expire_minutes: int = 60 * 12
    upload_dir: str = Field(default="/data/uploads", alias="OPSPILOT_UPLOAD_DIR")
    max_upload_mb: int = 200

    # Demo mode: one-click ephemeral sessions with seeded data, auto-reset via TTL.
    # Registration is disabled and per-session AI usage is capped while enabled.
    demo_mode: bool = Field(default=False, alias="OPSPILOT_DEMO_MODE")
    demo_session_ttl_minutes: int = Field(default=45, alias="OPSPILOT_DEMO_TTL_MINUTES")
    demo_max_analyses: int = Field(default=5, alias="OPSPILOT_DEMO_MAX_ANALYSES")
    demo_max_chat_messages: int = Field(default=40, alias="OPSPILOT_DEMO_MAX_CHAT_MESSAGES")
    demo_max_upload_mb: int = Field(default=5, alias="OPSPILOT_DEMO_MAX_UPLOAD_MB")

    # Database
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="opspilot", alias="POSTGRES_USER")
    postgres_password: str = Field(default="opspilot", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="opspilot", alias="POSTGRES_DB")

    # Redis / Celery
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # LLM
    llm_provider: LLMProviderName = Field(default="anthropic", alias="LLM_PROVIDER")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-5", alias="ANTHROPIC_MODEL")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="anthropic/claude-sonnet-5", alias="OPENROUTER_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1:8b", alias="OLLAMA_MODEL")
    openai_compatible_base_url: str = Field(default="", alias="OPENAI_COMPATIBLE_BASE_URL")
    openai_compatible_api_key: str = Field(default="", alias="OPENAI_COMPATIBLE_API_KEY")
    openai_compatible_model: str = Field(default="", alias="OPENAI_COMPATIBLE_MODEL")
    llm_timeout_seconds: float = 180.0
    llm_max_output_tokens: int = 4096

    # Embeddings / RAG
    embedding_provider: EmbeddingProviderName = Field(default="ollama", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="nomic-embed-text", alias="EMBEDDING_MODEL")
    embedding_dim: int = Field(default=768, alias="EMBEDDING_DIM")
    rag_chunk_size: int = 1200
    rag_chunk_overlap: int = 150
    rag_top_k: int = 6

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """URL for Alembic (runs through the sync psycopg-style dialect via asyncpg driver)."""
        return self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
