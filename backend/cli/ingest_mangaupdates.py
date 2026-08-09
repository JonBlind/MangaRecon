from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from contextlib import aclosing
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from backend.clients.mangaupdates_client import (
    create_mangaupdates_client,
)
from backend.dependencies import (
    dispose_database_engines,
    get_manga_write_db,
    validate_database_config,
)
from backend.services.ingestion_service import (
    MangaIngestionResult,
    ingest_mangaupdates_series,
)


@dataclass(frozen=True, slots=True)
class MangaIngestionAttempt:
    """
    Successful result or isolated failure for one batch item.
    """

    series_id: int
    result: MangaIngestionResult | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.error is None):
            raise ValueError(
                "Exactly one of result or error must be set."
            )


def _series_id(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "series ID must be an integer."
        ) from exc

    if parsed < 1:
        raise argparse.ArgumentTypeError(
            "series ID must be greater than zero."
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
            "Fetch and ingest one or more MangaUpdates series."
        )
    )
    parser.add_argument(
        "series_ids",
        nargs="*",
        type=_series_id,
        metavar="SERIES_ID",
        help=(
            "Positive MangaUpdates series ID. Provide more than "
            "one ID to run a batch."
        ),
    )
    parser.add_argument(
        "--file",
        dest="input_file",
        type=Path,
        help=(
            "UTF-8 text file containing one series ID per line. "
            "Blank lines and lines beginning with # are ignored."
        ),
    )
    parser.add_argument(
        "--min-request-interval-seconds",
        type=_request_interval,
        default=None,
        help=(
            "Override the configured minimum delay between API "
            "request start times for this job."
        ),
    )
    return parser


def _load_series_ids(path: Path) -> list[int]:
    try:
        contents = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError(
            f"Could not read series ID file {path}: {exc}"
        ) from exc

    series_ids: list[int] = []

    for line_number, raw_line in enumerate(
        contents.splitlines(),
        start=1,
    ):
        value = raw_line.partition("#")[0].strip()

        if not value:
            continue

        try:
            series_ids.append(_series_id(value))
        except argparse.ArgumentTypeError as exc:
            raise ValueError(
                f"{path}:{line_number}: {exc}"
            ) from exc

    if not series_ids:
        raise ValueError(
            f"Series ID file {path} contains no series IDs."
        )

    return series_ids


def _deduplicate_series_ids(
    series_ids: Sequence[int],
) -> tuple[int, ...]:
    return tuple(dict.fromkeys(series_ids))


def _collect_series_ids(
    positional_ids: Sequence[int],
    input_file: Path | None,
) -> tuple[int, ...]:
    combined_ids = list(positional_ids)

    if input_file is not None:
        combined_ids.extend(_load_series_ids(input_file))

    if not combined_ids:
        raise ValueError(
            "Provide at least one SERIES_ID or use --file."
        )

    return _deduplicate_series_ids(combined_ids)


def _client_options(
    min_request_interval_seconds: float | None,
) -> dict[str, float]:
    if min_request_interval_seconds is None:
        return {}

    return {
        "min_request_interval_seconds": (
            min_request_interval_seconds
        )
    }


async def run_series_ingestion(
    series_id: int,
    *,
    min_request_interval_seconds: float | None = None,
) -> MangaIngestionResult:
    """
    Ingest one series using the configured Manga write database.
    """
    try:
        async with aclosing(
            get_manga_write_db()
        ) as database_provider:
            manga_db = await anext(database_provider)

            async with create_mangaupdates_client(
                **_client_options(
                    min_request_interval_seconds
                )
            ) as client:
                return await ingest_mangaupdates_series(
                    manga_db,
                    client=client,
                    series_id=series_id,
                )
    finally:
        await dispose_database_engines()


async def run_batch_ingestion(
    series_ids: Sequence[int],
    *,
    min_request_interval_seconds: float | None = None,
) -> tuple[MangaIngestionAttempt, ...]:
    """
    Ingest a batch while isolating individual series failures.

    The database provider and HTTP client are reused for the entire job.
    The ingestion service owns the transaction boundary for each series.
    """
    if not series_ids:
        raise ValueError(
            "series_ids must contain at least one series ID."
        )

    attempts: list[MangaIngestionAttempt] = []

    try:
        async with aclosing(
            get_manga_write_db()
        ) as database_provider:
            manga_db = await anext(database_provider)

            async with create_mangaupdates_client(
                **_client_options(
                    min_request_interval_seconds
                )
            ) as client:
                for series_id in series_ids:
                    try:
                        result = await ingest_mangaupdates_series(
                            manga_db,
                            client=client,
                            series_id=series_id,
                        )
                    except Exception as exc:
                        error = str(exc).strip()

                        attempts.append(
                            MangaIngestionAttempt(
                                series_id=series_id,
                                error=(
                                    error
                                    or type(exc).__name__
                                ),
                            )
                        )
                    else:
                        attempts.append(
                            MangaIngestionAttempt(
                                series_id=series_id,
                                result=result,
                            )
                        )
    finally:
        await dispose_database_engines()

    return tuple(attempts)


def _result_status(
    result: MangaIngestionResult,
) -> str:
    if result.created:
        return "created"

    if result.changed:
        return "updated"

    return "unchanged"


def _print_success(
    series_id: int,
    result: MangaIngestionResult,
) -> None:
    print(
        (
            f"MangaUpdates series {series_id} "
            f"{_result_status(result)}; "
            f"manga_id={result.manga_id}."
        )
    )


def _print_batch_results(
    attempts: Sequence[MangaIngestionAttempt],
) -> int:
    counts = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "failed": 0,
    }

    for attempt in attempts:
        if attempt.result is None:
            counts["failed"] += 1
            print(
                (
                    f"MangaUpdates series "
                    f"{attempt.series_id} failed: "
                    f"{attempt.error}"
                ),
                file=sys.stderr,
            )
            continue

        status = _result_status(attempt.result)
        counts[status] += 1
        _print_success(
            attempt.series_id,
            attempt.result,
        )

    print(
        (
            f"Summary: total={len(attempts)}; "
            f"created={counts['created']}; "
            f"updated={counts['updated']}; "
            f"unchanged={counts['unchanged']}; "
            f"failed={counts['failed']}."
        )
    )

    if counts["failed"]:
        return 1

    return 0


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        series_ids = _collect_series_ids(
            arguments.series_ids,
            arguments.input_file,
        )
    except ValueError as exc:
        parser.error(str(exc))

    run_options = _client_options(
        arguments.min_request_interval_seconds
    )
    single_series_mode = (
        arguments.input_file is None
        and len(arguments.series_ids) == 1
    )

    try:
        validate_database_config()

        if single_series_mode:
            result = asyncio.run(
                run_series_ingestion(
                    series_ids[0],
                    **run_options,
                )
            )
        else:
            attempts = asyncio.run(
                run_batch_ingestion(
                    series_ids,
                    **run_options,
                )
            )
    except Exception as exc:
        print(
            f"Ingestion failed: {exc}",
            file=sys.stderr,
        )
        return 1

    if single_series_mode:
        _print_success(series_ids[0], result)
        return 0

    return _print_batch_results(attempts)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
