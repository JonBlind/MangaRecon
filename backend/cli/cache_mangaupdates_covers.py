from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from contextlib import aclosing
from dataclasses import dataclass
from math import isfinite

from backend.clients.mangaupdates_client import (
    MangaUpdatesTransportError,
    MangaUpdatesRateLimitError,
    MangaUpdatesUnavailableError,
    create_mangaupdates_client,
)
from backend.dependencies import (
    dispose_database_engines,
    get_manga_write_db,
    validate_database_config,
)
from backend.ingestion.mangaupdates_parser import (
    MANGAUPDATES_PROVIDER_KEY,
)
from backend.repositories.ingestion_repo import (
    CatalogCoverCandidate,
    find_uncached_catalog_covers,
)
from backend.services.cover_service import cache_catalog_cover
from backend.storage.cover_store import (
    CoverStorageConfigurationError,
    CoverStorageError,
    create_cover_store_from_settings,
)


_DEFAULT_PROGRESS_INTERVAL = 25


@dataclass(frozen=True, slots=True)
class CoverCacheAttempt:
    candidate: CatalogCoverCandidate
    cached: bool = False
    skipped_changed: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CoverCacheReport:
    selected: int
    attempts: tuple[CoverCacheAttempt, ...]


def _positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "value must be an integer."
        ) from exc

    if parsed < 1:
        raise argparse.ArgumentTypeError(
            "value must be greater than zero."
        )

    return parsed


def _request_interval(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "request interval must be a number."
        ) from exc

    if not isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError(
            "request interval must be a finite nonnegative number."
        )

    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Copy externally hosted MangaUpdates covers into durable "
            "MangaRecon storage. Completed records are skipped on reruns."
        )
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help=(
            "Report how many covers need caching without downloading, "
            "uploading, or changing the database."
        ),
    )
    parser.add_argument(
        "--limit",
        type=_positive_integer,
        default=None,
        help=(
            "Process at most this many covers in stable catalog order. "
            "Omit to process every selected cover."
        ),
    )
    parser.add_argument(
        "--min-request-interval-seconds",
        type=_request_interval,
        default=None,
        help=(
            "Override the configured minimum delay between MangaUpdates "
            "image request start times."
        ),
    )
    return parser


def _client_options(
    min_request_interval_seconds: float | None,
) -> dict[str, float]:
    if min_request_interval_seconds is None:
        return {}

    return {
        "min_request_interval_seconds": min_request_interval_seconds,
    }


async def run_cover_cache(
    *,
    preview: bool = False,
    limit: int | None = None,
    min_request_interval_seconds: float | None = None,
    progress_interval: int = _DEFAULT_PROGRESS_INTERVAL,
) -> CoverCacheReport:
    """Run one resumable cover-cache batch against the manga database."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than zero.")

    if progress_interval < 1:
        raise ValueError("progress_interval must be greater than zero.")

    cover_store = create_cover_store_from_settings()

    if cover_store is None:
        raise CoverStorageConfigurationError(
            "Cover storage is not configured."
        )

    attempts: list[CoverCacheAttempt] = []

    try:
        async with aclosing(
            get_manga_write_db()
        ) as database_provider:
            manga_db = await anext(database_provider)
            candidates = await find_uncached_catalog_covers(
                manga_db,
                provider_key=MANGAUPDATES_PROVIDER_KEY,
                public_base_url=cover_store.public_base_url,
                limit=limit,
            )

            if preview or not candidates:
                return CoverCacheReport(
                    selected=len(candidates),
                    attempts=(),
                )

            async with create_mangaupdates_client(
                **_client_options(
                    min_request_interval_seconds
                )
            ) as client:
                for candidate in candidates:
                    try:
                        result = await cache_catalog_cover(
                            manga_db,
                            candidate=candidate,
                            client=client,
                            cover_store=cover_store,
                        )
                    except MangaUpdatesRateLimitError:
                        raise
                    except (
                        MangaUpdatesTransportError,
                        MangaUpdatesUnavailableError,
                        CoverStorageError,
                    ):
                        # These failures normally affect the whole job. Stop
                        # after the first one so the source or S3 is not
                        # repeatedly contacted while unavailable.
                        raise
                    except Exception as exc:
                        error = str(exc).strip() or type(exc).__name__
                        attempts.append(
                            CoverCacheAttempt(
                                candidate=candidate,
                                error=error,
                            )
                        )
                        print(
                            (
                                "Cover cache failed: manga_id="
                                f"{candidate.manga_id}; series_id="
                                f"{candidate.external_id}; error={error}"
                            ),
                            file=sys.stderr,
                            flush=True,
                        )
                    else:
                        attempts.append(
                            CoverCacheAttempt(
                                candidate=candidate,
                                cached=result.database_updated,
                                skipped_changed=(
                                    not result.database_updated
                                ),
                            )
                        )

                    if len(attempts) % progress_interval == 0:
                        _print_progress(
                            len(attempts),
                            len(candidates),
                            attempts,
                        )
    finally:
        await dispose_database_engines()

    return CoverCacheReport(
        selected=len(candidates),
        attempts=tuple(attempts),
    )


def _attempt_counts(
    attempts: Sequence[CoverCacheAttempt],
) -> tuple[int, int, int]:
    cached = sum(attempt.cached for attempt in attempts)
    skipped_changed = sum(
        attempt.skipped_changed for attempt in attempts
    )
    failed = sum(attempt.error is not None for attempt in attempts)
    return cached, skipped_changed, failed


def _print_progress(
    processed: int,
    selected: int,
    attempts: Sequence[CoverCacheAttempt],
) -> None:
    cached, skipped_changed, failed = _attempt_counts(attempts)
    print(
        (
            f"Cover-cache progress: processed={processed}/{selected}; "
            f"cached={cached}; skipped_changed={skipped_changed}; "
            f"failed={failed}."
        ),
        flush=True,
    )


def _print_report(
    report: CoverCacheReport,
    *,
    preview: bool,
    limit: int | None,
) -> int:
    selected_limit = "all" if limit is None else str(limit)

    if preview:
        print(
            (
                "Cover-cache preview: "
                f"selected={report.selected}; limit={selected_limit}. "
                "No images were downloaded and no records were changed."
            )
        )
        return 0

    cached, skipped_changed, failed = _attempt_counts(
        report.attempts
    )
    print(
        (
            f"Cover-cache summary: selected={report.selected}; "
            f"cached={cached}; skipped_changed={skipped_changed}; "
            f"failed={failed}."
        )
    )
    return 1 if failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        validate_database_config()
        report = asyncio.run(
            run_cover_cache(
                preview=arguments.preview,
                limit=arguments.limit,
                min_request_interval_seconds=(
                    arguments.min_request_interval_seconds
                ),
            )
        )
    except KeyboardInterrupt:
        print(
            (
                "Cover caching interrupted. Completed records remain "
                "stored and will be skipped when the command is rerun."
            ),
            file=sys.stderr,
        )
        return 130
    except MangaUpdatesRateLimitError as exc:
        retry_after = (
            f" Retry-After={exc.retry_after}."
            if exc.retry_after
            else ""
        )
        print(
            (
                "Cover caching stopped after MangaUpdates returned HTTP "
                f"429; no further requests were sent.{retry_after}"
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"Cover caching failed: {exc}", file=sys.stderr)
        return 1

    return _print_report(
        report,
        preview=arguments.preview,
        limit=arguments.limit,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
