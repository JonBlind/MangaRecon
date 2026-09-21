from __future__ import annotations

from collections.abc import Callable, Sequence

from backend.config.bootstrap_runtime import load_runtime_secrets


def _load_sync_main() -> Callable[[Sequence[str] | None], int]:
    # Import after Secrets Manager populates the environment. The imported
    # modules construct application and database settings at import time.
    from backend.cli.sync_mangaupdates_catalog import main

    return main


def main(argv: Sequence[str] | None = None) -> int:
    """Load production runtime secrets, then execute the bounded sync."""
    load_runtime_secrets()
    return _load_sync_main()(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
