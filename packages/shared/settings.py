"""Shared runtime settings for apps/api and apps/worker.

Values are read from environment variables (see .env.example). Nothing here
should be hardcoded that a deployer would reasonably need to change.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ogrownt:ogrownt@localhost:5432/ogrownt"

    admin_email: str = "admin@example.com"
    admin_password: str = "change-me"
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
