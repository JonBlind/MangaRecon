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
    finished_at: float | None = None,
    outcome: TimingOutcome = "success",
) -> None:
    """Write one structured duration marker without request or secret data.

    A captured ``finished_at`` keeps logging time out of adjacent measurements.
    """
    resolved_finished_at = (
        time.perf_counter()
        if finished_at is None
        else finished_at
    )
    duration_ms = max(
        0.0,
        (resolved_finished_at - started_at) * 1000,
    )
    print(
        "MANGARECON_TIMING "
        f"stage={stage} "
        f"duration_ms={duration_ms:.2f} "
        f"outcome={outcome}",
        flush=True,
    )
