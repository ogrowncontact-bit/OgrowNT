"""SecretProvider — "PROMPT 13" §28-30, §92-94.

Only a BrokerAdapter's own __init__/connect() may ever call
SecretProvider.get() (§30: "Somente BrokerAdapter pode acessar
credentials. Agents/Strategies/LLM/Frontend: NO ACCESS") — enforced today
by the simple fact that PaperBrokerAdapter never calls this module at all
(it needs no credentials), and structurally proven by
tests/test_execution_red_team.py's AST walk confirming no agent/strategy/
research/LLM module imports packages.execution.secrets.

No real broker/exchange credentials exist anywhere in this deployment —
EnvSecretProvider exists so a future real adapter has a real, already-
credential-isolated place to read from, and so `is_broker_configured()` can
give the dashboard/API an honest True/False without ever exposing what (if
anything) is actually configured.
"""
from __future__ import annotations

import os
from typing import Protocol


class SecretProvider(Protocol):
    def is_configured(self, key: str) -> bool: ...
    def get(self, key: str) -> str | None: ...


class EnvSecretProvider:
    """Reads from process environment variables only — never a database
    column, never logged, never placed in an LLM prompt or returned to the
    frontend (§28)."""

    def is_configured(self, key: str) -> bool:
        return bool(os.environ.get(key))

    def get(self, key: str) -> str | None:
        return os.environ.get(key) or None


def mask(value: str | None) -> str:
    """Never returns the real value — for anywhere that needs to SHOW a
    credential exists without ever exposing it (dashboard, logs, an admin
    API response)."""
    if not value:
        return "not_configured"
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


def is_broker_configured(provider: SecretProvider, *, broker_name: str) -> bool:
    """§28-29 — a broker is "configured" iff its API-key env var is set;
    this never reads or returns the value itself, only a boolean."""
    return provider.is_configured(f"{broker_name.upper()}_API_KEY")
