from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from contextlib import aclosing

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch and ingest one MangaUpdates series."
        )
    )
    parser.add_argument(
        "series_id",
        type=_series_id,
        help="Positive MangaUpdates series ID.",
    )
    return parser


async def run_series_ingestion(
    series_id: int,
) -> MangaIngestionResult:
    """
    Ingest one series using the configured Manga write database.
    """
    try:
        async with aclosing(
            get_manga_write_db()
        ) as database_provider:
            manga_db = await anext(database_provider)

            async with (
                create_mangaupdates_client()
            ) as client:
                return await ingest_mangaupdates_series(
                    manga_db,
                    client=client,
                    series_id=series_id,
                )
    finally:
        await dispose_database_engines()


def _result_status(
    result: MangaIngestionResult,
) -> str:
    if result.created:
        return "created"

    if result.changed:
        return "updated"

    return "unchanged"


def main(
    argv: Sequence[str] | None = None,
) -> int:
    arguments = build_parser().parse_args(argv)

    try:
        validate_database_config()
        result = asyncio.run(
            run_series_ingestion(arguments.series_id)
        )
    except Exception as exc:
        print(
            f"Ingestion failed: {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        (
            f"MangaUpdates series {arguments.series_id} "
            f"{_result_status(result)}; "
            f"manga_id={result.manga_id}."
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())