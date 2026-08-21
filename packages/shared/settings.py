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
    # Below this 0-100 score (packages/data/quality.py), /api/market/data-quality
    # and the dashboard mark an asset DATA_UNSAFE rather than silently degraded.
    market_data_quality_unsafe_threshold: int = 50
    # Strategy evaluation cadence — docs/blueprint/05-event-flow.md §Cadência (15 min).
    strategy_interval_seconds: int = 900

    news_provider: str = "mock"
    # News Intelligence Agent cadence — independent of strategy_interval_seconds.
    news_interval_seconds: int = 900

    macro_calendar_provider: str = "mock"
    # MacroCalendarWorker cadence (packages/data/connectors/macro) — slower
    # than news_interval_seconds since a macro calendar changes far less
    # often than headlines do.
    macro_calendar_interval_seconds: int = 1800
    # SentimentWorker's aggregate SENTIMENT_SHIFT cadence (packages/quant/
    # news/sentiment.py's compute_sentiment_shift) — a per-asset rollup, not
    # per-item, so it runs on its own cadence rather than per ingested item.
    sentiment_shift_interval_seconds: int = 900

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

    # apps/backtest_worker/main.py's poll cadence -- separate process from
    # apps/worker (see that module's docstring for why), short enough that
    # a queued backtest/Monte Carlo/stress-test job feels responsive in the
    # Strategy Lab UI without hammering Postgres between jobs.
    backtest_job_poll_interval_seconds: int = 5

    # apps/research_worker/main.py's poll cadence -- "PROMPT 10" §59's
    # compute isolation, a THIRD separate process from both apps/worker and
    # apps/backtest_worker. Slower than the backtest worker's on purpose:
    # research_queue items (hypothesis generation, experiments, genetic
    # search) are inherently heavier and less latency-sensitive than a
    # human waiting on a Strategy Lab job in the dashboard.
    research_job_poll_interval_seconds: int = 15

    # "PROMPT 8" §69-71: how often packages/portfolio/reconciliation.py
    # re-derives cash from first principles. Frequent — an accounting
    # mismatch pauses trading, so catching one quickly matters more than the
    # (cheap, SQL-aggregate-only) cost of running it often.
    reconciliation_interval_seconds: int = 300

    # "PROMPT 8" §62-66: how often a SystemHealth snapshot row is written —
    # the historical record GET /api/system/health's on-demand view doesn't
    # keep.
    health_snapshot_interval_seconds: int = 300

    # "PROMPT 11" §92's UniverseWorker cadence — how often
    # packages/market/universe.py's MarketUniverseManager re-evaluates every
    # asset's data-quality/liquidity/status. Slower than scan_interval_seconds
    # since liquidity/quality standing changes far less often than price does.
    universe_interval_seconds: int = 300
    # "PROMPT 11" §92's MarketScannerWorker/OpportunityWorker/AnomalyWorker/
    # VolatilityWorker/MarketStructureWorker/WatchlistWorker cadence — one
    # combined pass (apps/worker/market_intelligence.py) since they're
    # sequential stages of the same fast-scan -> deep-scan-on-the-top-N
    # pipeline, the same "single process, multiple cadences" pattern as
    # every other agent in apps/worker/main.py. Not the prompt's literal
    # 1s/5s ideal (§29) -- a private, modest-scale paper system has no need
    # to scan sub-minute, and the mock provider ticks once a minute anyway.
    market_intelligence_interval_seconds: int = 120

    # "PROMPT 12" §107-108's Risk Event Timeline / periodic risk reports --
    # how often apps/worker/capital_defense.py runs AdvancedRiskEngine
    # (packages/risk/advanced_engine.py) and persists a RiskAssessment row,
    # independent of the strategy cycle so a quiet market still has a
    # continuous risk-state history. Faster than universe_interval_seconds
    # (capital defense state can matter on a shorter horizon than asset
    # liquidity/quality standing) but not as fast as scan_interval_seconds
    # (a full portfolio-wide assessment is heavier than a price scan).
    capital_defense_interval_seconds: int = 120

    # "PROMPT 8" §66 crash-loop protection (SystemState.worker_restart_count):
    # more worker-process restarts than this within restart_window_seconds
    # auto-pauses trading rather than letting a silently crash-looping
    # process keep trading "on" underneath the flapping.
    max_worker_restarts_per_window: int = 5
    restart_window_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
