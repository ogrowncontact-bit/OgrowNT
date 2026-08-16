"""Shared runtime settings for apps/api and apps/worker.

Values are read from environment variables (see .env.example). Nothing here
should be hardcoded that a deployer would reasonably need to change.
"""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The exact placeholder strings shipped in .env.example. Publicly known, so
# an unconfigured deployment would let anyone forge an admin JWT
# (jwt_secret signs it) or log in directly (admin_password) — refused at
# startup below rather than silently running insecurely.
_INSECURE_DEFAULT_JWT_SECRET = "change-me-to-a-long-random-string"
_INSECURE_DEFAULT_ADMIN_PASSWORD = "change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ogrownt:ogrownt@localhost:5432/ogrownt"

    admin_email: str = "admin@example.com"
    admin_password: str = _INSECURE_DEFAULT_ADMIN_PASSWORD
    jwt_secret: str = _INSECURE_DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    # Origins allowed to call the API from a browser (CORS). Comma-separated.
    # Defaults to the dashboard's own dev/docker-compose origins — a private
    # single-user deployment has exactly one legitimate frontend, so "*" here
    # would only ever help an attacker (any webpage the operator's browser
    # visits could otherwise read API responses cross-origin).
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @model_validator(mode="after")
    def _reject_insecure_defaults(self) -> "Settings":
        if self.jwt_secret == _INSECURE_DEFAULT_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET is still the placeholder from .env.example — set a real, "
                "random secret before starting (anyone who knows this value can forge "
                "an admin token)."
            )
        if self.admin_password == _INSECURE_DEFAULT_ADMIN_PASSWORD:
            raise ValueError(
                "ADMIN_PASSWORD is still the placeholder from .env.example — set a "
                "real password before starting."
            )
        return self

    initial_paper_capital: float = 10000.0

    market_data_provider: str = "mock"
    scan_interval_seconds: int = 60
    # Strategy evaluation cadence — docs/blueprint/05-event-flow.md §Cadência (15 min).
    strategy_interval_seconds: int = 900

    news_provider: str = "mock"
    # News Intelligence Agent cadence — independent of strategy_interval_seconds.
    news_interval_seconds: int = 900

    # Research Agent cadence (packages/quant/learning/research.py) — scans
    # pattern_performance/strategy_performance for underperformers and
    # proposes+validates learned_rules. Deliberately much longer than the
    # other cadences: it reasons over data that only changes as slowly as
    # trades close, not per scan/news tick.
    research_interval_seconds: int = 3600

    # packages/llm — required for real News Intelligence interpretation.
    # Left empty means "no LLM configured": the worker logs it and skips
    # interpretation rather than faking one (docs/blueprint/00-overview.md's
    # "no hallucinated data" rule applies to LLM output too).
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5"

    # packages/notifications — alert delivery channels (Phase 7). Each is
    # independently optional; an empty value means that channel is not
    # configured, the same honest-degradation convention as anthropic_api_key
    # above (alerts still land in the `alerts` table and the dashboard either
    # way — these only control whether they're also pushed out).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    alert_email_to: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # How often apps/worker/alerts.py attempts to deliver not-yet-delivered
    # Alert rows to whatever channels are configured. Short on purpose —
    # alerts (kill switch, safety belt changes) are time-sensitive.
    alert_delivery_interval_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
