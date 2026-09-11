"""Small, non-sensitive performance markers for production diagnostics."""

from __future__ import annotations

import time
from typing import Literal


TimingOutcome = Literal[
    "error",
    "ready",
    "skipped",
    "success",
    "unavailable",
]


def emit_elapsed(
    stage: str,
    started_at: float,
    *,
    outcome: TimingOutcome = "success",
) -> None:
    """Write one structured duration marker without request or secret data."""
    duration_ms = max(0.0, (time.perf_counter() - started_at) * 1000)
    print(
        "MANGARECON_TIMING "
        f"stage={stage} "
        f"duration_ms={duration_ms:.2f} "
        f"outcome={outcome}",
        flush=True,
    )
