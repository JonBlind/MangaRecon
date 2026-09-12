from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from contextlib import aclosing
from math import isfinite

from backend.cli import ingest_mangaupdates as ingestion_cli
from backend.dependencies import (
    dispose_database_engines,
    get_manga_write_db,
    validate_database_config,
)
from backend.ingestion.mangaupdates_parser import (
    MANGAUPDATES_PROVIDER_KEY,
)
from backend.repositories.ingestion_repo import (
    find_missing_cover_external_ids,
)


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
            (
                "request interval must be a finite number "
                "greater than or equal to zero."
            )
        )

    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh selected existing MangaUpdates catalog records."
        )
    )
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument(
        "--missing-covers",
        action="store_true",
        help=(
            "Refresh existing MangaUpdates records whose stored cover "
            "URL is null or blank. All changed canonical metadata for "
            "the selected records is refreshed."
        ),
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help=(
            "Report the number of selected records without contacting "
            "MangaUpdates or changing the database."
        ),
    )
    parser.add_argument(
        "--limit",
        type=_positive_integer,
        default=None,
        help=(
            "Process at most this many selected records. Useful for a "
            "small production pilot."
        ),
    )
    parser.add_argument(
        "--min-request-interval-seconds",
        type=_request_interval,
        default=None,
        help=(
            "Override the configured minimum delay between API request "
            "start times for this job."
        ),
    )
    return parser


def _stored_series_id(value: str) -> int:
    try:
        series_id = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "The catalog contains an invalid MangaUpdates external ID."
        ) from exc

    if series_id < 1:
        raise RuntimeError(
            "The catalog contains an invalid MangaUpdates external ID."
        )

    return series_id


async def load_missing_cover_series_ids(
    *,
    limit: int | None = None,
) -> tuple[int, ...]:
    """Load the existing MangaUpdates IDs selected for cover refresh."""
    try:
        async with aclosing(
            get_manga_write_db()
        ) as database_provider:
            manga_db = await anext(database_provider)
            external_ids = await find_missing_cover_external_ids(
                manga_db,
                provider_key=MANGAUPDATES_PROVIDER_KEY,
                limit=limit,
            )

        return tuple(
            _stored_series_id(external_id)
            for external_id in external_ids
        )
    finally:
        await dispose_database_engines()


def _print_preview(
    series_ids: Sequence[int],
    *,
    limit: int | None,
) -> None:
    selected_limit = "all" if limit is None else str(limit)
    print(
        (
            "Missing-cover refresh preview: "
            f"selected={len(series_ids)}; "
            f"limit={selected_limit}. "
            "No records were changed."
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        validate_database_config()
        series_ids = asyncio.run(
            load_missing_cover_series_ids(
                limit=arguments.limit,
            )
        )

        if arguments.preview:
            _print_preview(
                series_ids,
                limit=arguments.limit,
            )
            return 0

        if not series_ids:
            print(
                "No MangaUpdates manga with missing covers were found."
            )
            return 0

        report = asyncio.run(
            ingestion_cli.run_batch_ingestion(
                series_ids,
                min_request_interval_seconds=(
                    arguments.min_request_interval_seconds
                ),
                refresh_existing=True,
                progress_callback=(
                    ingestion_cli._print_batch_progress
                ),
            )
        )
    except KeyboardInterrupt:
        print(
            (
                "Refresh interrupted by user. Already completed records "
                "remain committed; rerun the same command to continue."
            ),
            file=sys.stderr,
        )
        return 130
    except ingestion_cli.MangaUpdatesRateLimitError as exc:
        retry_after = (
            f" Retry-After={exc.retry_after}."
            if exc.retry_after
            else ""
        )
        print(
            (
                "Refresh stopped after MangaUpdates returned HTTP 429; "
                "no further requests were sent."
                f"{retry_after} Rerun later to continue."
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"Refresh failed: {exc}", file=sys.stderr)
        return 1

    return ingestion_cli._print_batch_results(report)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
