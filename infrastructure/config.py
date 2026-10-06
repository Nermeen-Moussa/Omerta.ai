"""Application configuration loaded from environment variables.

Secrets are never hard-coded; values come from the environment (optionally via
a local .env file, which is git-ignored). Settings consumed in later phases
(LLM, vector store) are declared here so the contract stays stable.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_file=(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- PostgreSQL ---
    # Host port 15432 avoids clashing with native PostgreSQL installs (5432+).
    database_url: str = "postgresql+asyncpg://omerta:omerta_dev_password@localhost:15432/omerta"
    test_database_url: str = (
        "postgresql+asyncpg://omerta:omerta_dev_password@localhost:15432/omerta_test"
    )

    # --- Neo4j (derived graph projection; PostgreSQL stays source of truth) ---
    neo4j_uri: str = "bolt://localhost:17687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "omerta_dev_password"  # local dev default; override via .env
    neo4j_database: str = "neo4j"
    # Namespace property stamped on every projected node; lets tests and dev
    # data coexist safely in one (community-edition) Neo4j instance.
    graph_projection: str = "dev"

    # --- LLM, provider-agnostic (consumed in later phases) ---
    llm_provider: str | None = None  # openai | gemini | groq | ollama
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None

    # --- Vector store (consumed in later phases) ---
    vector_db_url: str | None = None

    # --- Risk subsystem ---
    # Only 'mock' exists in Phase 7; the future ML engine will add its own.
    risk_provider: str = "mock"

    # --- Security (Phase 17) ---
    # API keys: unset => auth disabled (local dev/test default). Set to enable
    # mandatory X-API-Key auth with role-based access. Never commit real keys.
    api_key_analyst: str | None = None
    api_key_admin: str | None = None
    # Rate limiting (requests per minute per key/IP; 0 disables).
    rate_limit_per_minute: int = 0
    rate_limit_burst: int | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
