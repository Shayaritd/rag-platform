"""
Centralized config, loaded once from environment variables.
Using pydantic-settings so every setting is typed and validated at boot
instead of failing deep inside a request handler.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    ENV: str = "local"
    API_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"

    # Postgres (Supabase-compatible: just point this at your Supabase
    # connection string, e.g. postgresql://postgres:[pwd]@db.xxxx.supabase.co:5432/postgres)
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/rag_platform"

    # Auth
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Vector DB
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_PREFIX: str = "tenant"

    # Embeddings (local-first to keep cost near zero)
    EMBEDDING_PROVIDER: str = "local"          # "local" | "gemini"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384

    # LLM providers
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    LLAMA_BASE_URL: str = "http://localhost:11434"   # e.g. local Ollama
    LLAMA_MODEL: str = "llama3"
    LLM_TIMEOUT_SECONDS: float = 90.0
    LLM_MAX_RETRIES: int = 2

    # Rate limiting / quotas
    DEFAULT_DAILY_QUERY_QUOTA: int = 200
    RATE_LIMIT_PER_MINUTE: int = 30

    # File storage
    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_MB: int = 25

    # Caching
    QUERY_CACHE_TTL_SECONDS: int = 3600

    # Monitoring
    PROMETHEUS_METRICS_PATH: str = "/metrics"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.DATABASE_URL.startswith("postgresql+psycopg://"):
        settings.DATABASE_URL = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)
    return settings
