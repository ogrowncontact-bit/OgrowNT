"""Reproducibility metadata — "PROMPT 7" §48. `get_code_version()` identifies
the exact code that produced a BacktestRun so results are auditable and
reproducible. Checks the `OGROWNT_CODE_VERSION` env var first — the
Dockerfiles never copy `.git` into an image (repo history has no business
being in a runtime container), so a real deployment sets this at build time
(e.g. `--build-arg`/`ENV OGROWNT_CODE_VERSION=<git sha>` baked in by CI) —
then falls back to a live `git rev-parse` for local/non-Docker development,
where `.git` genuinely is available. Returns `None` (never a fabricated
placeholder) when neither source is available.
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def get_code_version() -> str | None:
    env_version = os.environ.get("OGROWNT_CODE_VERSION")
    if env_version:
        return env_version
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None
