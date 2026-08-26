"""Application settings, loaded from environment variables.

Single source of truth for configuration across api, worker, and CLI
entrypoints. Secrets never get default values so a misconfigured deploy
fails loudly at startup instead of silently running unauthenticated.
"""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "ci", "production"] = "local"
    log_level: str = "INFO"

    # Data stores
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://repopilot:repopilot@localhost:5432/repopilot"
    )
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")

    # GitHub App
    github_app_id: str = ""
    github_app_private_key: SecretStr = SecretStr("")
    github_webhook_secret: SecretStr = SecretStr("")

    # Internal API key — shared secret the Next.js BFF presents on every
    # dashboard request. When set, the API rejects unauthenticated callers.
    internal_api_key: SecretStr = SecretStr("")

    # LLM providers
    groq_api_key: SecretStr = SecretStr("")
    google_api_key: SecretStr = SecretStr("")
    anthropic_api_key: SecretStr = SecretStr("")
    cohere_api_key: SecretStr = SecretStr("")

    # Observability
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = "https://cloud.langfuse.com"

    # Cost controls
    max_cost_per_run_usd: float = 0.02

    # Abuse / cost-DoS budget
    max_runs_per_install_per_day: int = 500

    # CORS — the Next.js origin that is allowed to reach the API.
    web_origin: str = "http://localhost:3000"

    # OpenTelemetry → Grafana Cloud (OTLP over HTTPS)
    # Leave empty to disable (local/CI). Set via Fly secrets in production.
    otel_exporter_otlp_endpoint: str = ""
    otel_exporter_otlp_headers: SecretStr = SecretStr("")
    otel_service_name: str = "repopilot"


@lru_cache
def get_settings() -> Settings:
    return Settings()
