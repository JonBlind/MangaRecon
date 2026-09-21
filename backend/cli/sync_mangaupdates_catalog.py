from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from contextlib import aclosing
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite

from backend.cli import ingest_mangaupdates as ingestion_cli
from backend.clients.mangaupdates_client import (
    MangaUpdatesRateLimitError,
    create_mangaupdates_client,
)
from backend.content_safety.policy import (
    RESTRICTED_INGESTION_GENRE_NAMES,
)
from backend.dependencies import (
    dispose_database_engines,
    get_manga_write_db,
    validate_database_config,
)
from backend.ingestion.mangaupdates_backfill import (
    DEFAULT_MINIMUM_PUBLICATION_YEAR,
    MangaUpdatesBackfillCheckpoint,
    advance_backfill_page,
)
from backend.ingestion.mangaupdates_discovery import (
    MAX_DISCOVERY_RESULTS,
    MangaUpdatesDiscoveryPage,
    MangaUpdatesDiscoveryRequest,
    MangaUpdatesDiscoveryState,
    discover_mangaupdates_catalog,
)
from backend.ingestion.mangaupdates_parser import (
    MANGAUPDATES_PROVIDER_KEY,
)
from backend.repositories.ingestion_repo import (
    find_existing_catalog_external_ids,
)
from backend.storage.catalog_checkpoint_store import (
    CatalogCheckpointStore,
    create_catalog_checkpoint_store_from_settings,
)


_DEFAULT_RECENT_DISCOVERY_LIMIT = 500
_DEFAULT_MAX_NEW = 400
_DEFAULT_MAX_RECENT = 300
_DEFAULT_HISTORICAL_PAGES = 5
_DEFAULT_PER_PAGE = 100
_DEFAULT_PROGRESS_INTERVAL = 25
_MAX_DAILY_INGESTION = 400
_MAX_HISTORICAL_PAGES = 20


@dataclass(frozen=True, slots=True)
class MangaCatalogSyncReport:
    """Recent discovery, historical progress, and ingestion results."""

    recent_discovered: int
    recent_pages: int
    recent_malformed: int
    historical_pages: int
    considered: int
    existing: int
    new: int
    selected_series_ids: tuple[int, ...]
    deferred: int
    checkpoint: MangaUpdatesBackfillCheckpoint
    ingestion: ingestion_cli.MangaBatchIngestionReport | None
    excluded_known: int = 0
    recent_candidates: int = 0
    historical_candidates: int = 0
    selected_recent_series_ids: tuple[int, ...] = ()
    selected_historical_series_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class _CatalogCandidateQueues:
    considered_series_ids: tuple[int, ...]
    recent_series_ids: tuple[int, ...]
    historical_series_ids: tuple[int, ...]
    existing: int
    excluded_known: int


def _bounded_integer(
    value: str,
    *,
    field_name: str,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"{field_name} must be an integer."
        ) from exc

    if not 1 <= parsed <= maximum:
        raise argparse.ArgumentTypeError(
            f"{field_name} must be between 1 and {maximum}."
        )

    return parsed


def _recent_discovery_limit(value: str) -> int:
    return _bounded_integer(
        value,
        field_name="recent discovery limit",
        maximum=MAX_DISCOVERY_RESULTS,
    )


def _max_new(value: str) -> int:
    return _bounded_integer(
        value,
        field_name="max new",
        maximum=_MAX_DAILY_INGESTION,
    )


def _max_recent(value: str) -> int:
    return _bounded_integer(
        value,
        field_name="max recent",
        maximum=_MAX_DAILY_INGESTION,
    )


def _historical_pages(value: str) -> int:
    return _bounded_integer(
        value,
        field_name="historical pages",
        maximum=_MAX_HISTORICAL_PAGES,
    )


def _per_page(value: str) -> int:
    return _bounded_integer(
        value,
        field_name="per-page",
        maximum=100,
    )


def _minimum_year(value: str) -> int:
    return _bounded_integer(
        value,
        field_name="minimum year",
        maximum=9999,
    )


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


def _nonblank(value: str) -> str:
    normalized = value.strip()

    if not normalized:
        raise argparse.ArgumentTypeError(
            "value cannot be blank."
        )

    return normalized


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest newly added MangaUpdates series and resume a "
            "checkpointed historical catalog backfill."
        )
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help=(
            "Discover candidates without storing the checkpoint, "
            "fetching details, downloading covers, or changing records."
        ),
    )
    parser.add_argument(
        "--recent-discovery-limit",
        type=_recent_discovery_limit,
        default=_DEFAULT_RECENT_DISCOVERY_LIMIT,
        help=(
            "Newest MangaUpdates results inspected on every run "
            f"(default {_DEFAULT_RECENT_DISCOVERY_LIMIT})."
        ),
    )
    parser.add_argument(
        "--max-new",
        type=_max_new,
        default=_DEFAULT_MAX_NEW,
        help=(
            "Maximum candidate attempts across recent and historical "
            f"candidates (default {_DEFAULT_MAX_NEW})."
        ),
    )
    parser.add_argument(
        "--max-recent",
        type=_max_recent,
        default=_DEFAULT_MAX_RECENT,
        help=(
            "Maximum recent candidate attempts; unused capacity flows "
            "to historical backfill "
            f"(default {_DEFAULT_MAX_RECENT})."
        ),
    )
    parser.add_argument(
        "--historical-pages",
        type=_historical_pages,
        default=_DEFAULT_HISTORICAL_PAGES,
        help=(
            "Maximum historical search pages inspected when the deferred "
            f"queue needs replenishing (default {_DEFAULT_HISTORICAL_PAGES})."
        ),
    )
    parser.add_argument(
        "--per-page",
        type=_per_page,
        default=_DEFAULT_PER_PAGE,
        help=(
            "MangaUpdates discovery page size "
            f"(default {_DEFAULT_PER_PAGE})."
        ),
    )
    parser.add_argument(
        "--minimum-year",
        type=_minimum_year,
        default=DEFAULT_MINIMUM_PUBLICATION_YEAR,
        help=(
            "Oldest publication year included in historical backfill "
            f"(default {DEFAULT_MINIMUM_PUBLICATION_YEAR})."
        ),
    )
    parser.add_argument(
        "--exclude-genre",
        dest="exclude_genres",
        action="append",
        type=_nonblank,
        default=None,
        help=(
            "Genre excluded from recent and historical discovery. "
            "Repeat for multiple genres."
        ),
    )
    parser.add_argument(
        "--min-request-interval-seconds",
        type=_request_interval,
        default=None,
        help=(
            "Override the configured minimum delay between MangaUpdates "
            "request start times."
        ),
    )
    return parser


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


async def _load_existing_series_ids(
    series_ids: Sequence[int],
) -> set[str]:
    """Bulk-load known provider IDs without fetching series details."""
    try:
        async with aclosing(
            get_manga_write_db()
        ) as database_provider:
            manga_db = await anext(database_provider)
            return await find_existing_catalog_external_ids(
                manga_db,
                provider_key=MANGAUPDATES_PROVIDER_KEY,
                external_ids=tuple(
                    str(series_id) for series_id in series_ids
                ),
            )
    finally:
        await dispose_database_engines()


async def _discover_recent(
    client,
    *,
    limit: int,
    per_page: int,
    exclude_genres: Sequence[str],
) -> MangaUpdatesDiscoveryState:
    state = MangaUpdatesDiscoveryState(
        request=MangaUpdatesDiscoveryRequest(
            limit=limit,
            per_page=per_page,
            exclude_genres=tuple(exclude_genres),
            order_by="date_added",
        )
    )
    return await discover_mangaupdates_catalog(
        client,
        state=state,
    )


async def _discover_historical(
    client,
    *,
    checkpoint: MangaUpdatesBackfillCheckpoint,
    max_pages: int,
    per_page: int,
    queue_target: int,
    exclude_genres: Sequence[str],
) -> tuple[
    MangaUpdatesBackfillCheckpoint,
    tuple[int, ...],
    int,
]:
    discovered_ids: list[int] = []
    pages = 0

    while (
        not checkpoint.complete
        and pages < max_pages
        and len(checkpoint.pending_series_ids)
        + len(discovered_ids)
        < queue_target
    ):
        series_types = (
            (checkpoint.series_type,)
            if checkpoint.series_type is not None
            else ()
        )
        payload = await client.discover_series_page(
            page=checkpoint.page,
            per_page=per_page,
            series_types=series_types,
            year=str(checkpoint.current_year),
            exclude_genres=exclude_genres,
            order_by="date_added",
        )
        page = MangaUpdatesDiscoveryPage.from_payload(
            payload,
            expected_page=checkpoint.page,
        )
        checkpoint, page_ids = advance_backfill_page(
            checkpoint,
            page,
        )
        discovered_ids.extend(page_ids)
        pages += 1

    return checkpoint, tuple(discovered_ids), pages


def _candidate_queues(
    *,
    recent_ids: Sequence[int],
    pending_recent_ids: Sequence[int],
    pending_historical_ids: Sequence[int],
    historical_ids: Sequence[int],
    existing_ids: set[str],
    excluded_recent_ids: set[int],
) -> _CatalogCandidateQueues:
    recent_considered = tuple(
        dict.fromkeys((*pending_recent_ids, *recent_ids))
    )
    recent_considered_set = set(recent_considered)
    historical_considered = tuple(
        series_id
        for series_id in dict.fromkeys(
            (*pending_historical_ids, *historical_ids)
        )
        if series_id not in recent_considered_set
    )
    considered = (*recent_considered, *historical_considered)
    existing = sum(
        str(series_id) in existing_ids
        for series_id in considered
    )
    excluded_known = sum(
        str(series_id) not in existing_ids
        and series_id in excluded_recent_ids
        for series_id in recent_considered
    )
    recent_candidates = tuple(
        series_id
        for series_id in recent_considered
        if str(series_id) not in existing_ids
        and series_id not in excluded_recent_ids
    )
    historical_candidates = tuple(
        series_id
        for series_id in historical_considered
        if str(series_id) not in existing_ids
    )

    return _CatalogCandidateQueues(
        considered_series_ids=considered,
        recent_series_ids=recent_candidates,
        historical_series_ids=historical_candidates,
        existing=existing,
        excluded_known=excluded_known,
    )


def _completed_ingestion_ids(
    report: ingestion_cli.MangaBatchIngestionReport,
) -> set[int]:
    completed = set(report.skipped_existing_series_ids)
    completed.update(
        attempt.series_id
        for attempt in report.attempts
        if attempt.result is not None or attempt.excluded_reason is not None
    )
    return completed


def _select_candidate_ids(
    *,
    recent_ids: Sequence[int],
    historical_ids: Sequence[int],
    max_new: int,
    max_recent: int,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    selected_recent = tuple(recent_ids[:max_recent])
    historical_capacity = max_new - len(selected_recent)
    selected_historical = tuple(
        historical_ids[:historical_capacity]
    )
    return selected_recent, selected_historical


async def run_catalog_sync(
    *,
    checkpoint_store: CatalogCheckpointStore,
    preview: bool = False,
    recent_discovery_limit: int = _DEFAULT_RECENT_DISCOVERY_LIMIT,
    max_new: int = _DEFAULT_MAX_NEW,
    max_recent: int = _DEFAULT_MAX_RECENT,
    historical_pages: int = _DEFAULT_HISTORICAL_PAGES,
    per_page: int = _DEFAULT_PER_PAGE,
    minimum_year: int = DEFAULT_MINIMUM_PUBLICATION_YEAR,
    exclude_genres: Sequence[str] = (),
    min_request_interval_seconds: float | None = None,
    initial_year: int | None = None,
) -> MangaCatalogSyncReport:
    """Catch recent additions and advance a resumable historical scan."""
    if not 1 <= recent_discovery_limit <= MAX_DISCOVERY_RESULTS:
        raise ValueError(
            "recent_discovery_limit must be between 1 and 10000."
        )

    if not 1 <= max_new <= _MAX_DAILY_INGESTION:
        raise ValueError(
            f"max_new must be between 1 and {_MAX_DAILY_INGESTION}."
        )

    if not 1 <= max_recent <= max_new:
        raise ValueError(
            "max_recent must be between 1 and max_new."
        )

    if not 1 <= historical_pages <= _MAX_HISTORICAL_PAGES:
        raise ValueError(
            (
                "historical_pages must be between 1 and "
                f"{_MAX_HISTORICAL_PAGES}."
            )
        )

    if not 1 <= per_page <= 100:
        raise ValueError("per_page must be between 1 and 100.")

    resolved_initial_year = initial_year or datetime.now(
        timezone.utc
    ).year

    if minimum_year > resolved_initial_year:
        raise ValueError(
            "minimum_year cannot be later than the initial year."
        )

    excluded_genres = tuple(
        dict.fromkeys(
            (*sorted(RESTRICTED_INGESTION_GENRE_NAMES), *exclude_genres)
        )
    )
    checkpoint = await checkpoint_store.load()

    if checkpoint is None:
        checkpoint = MangaUpdatesBackfillCheckpoint.initial(
            start_year=resolved_initial_year,
            minimum_year=minimum_year,
        )
    elif checkpoint.minimum_year != minimum_year:
        raise ValueError(
            (
                "The saved checkpoint minimum year does not match "
                "the configured minimum year."
            )
        )

    async with create_mangaupdates_client(
        **_client_options(min_request_interval_seconds)
    ) as client:
        recent_state = await _discover_recent(
            client,
            limit=recent_discovery_limit,
            per_page=per_page,
            exclude_genres=excluded_genres,
        )
        recent_ids = tuple(item.series_id for item in recent_state.series)
        recent_id_set = set(recent_ids)
        checkpoint = checkpoint.with_excluded_recent_series_ids(
            tuple(
                series_id
                for series_id in checkpoint.excluded_recent_series_ids
                if series_id in recent_id_set
            )
        )
        checkpoint, historical_ids, historical_page_count = (
            await _discover_historical(
                client,
                checkpoint=checkpoint,
                max_pages=historical_pages,
                per_page=per_page,
                queue_target=max_new,
                exclude_genres=excluded_genres,
            )
        )

    considered_ids = tuple(
        dict.fromkeys(
            (
                *checkpoint.pending_recent_series_ids,
                *recent_ids,
                *checkpoint.pending_series_ids,
                *historical_ids,
            )
        )
    )
    existing_ids = await _load_existing_series_ids(
        considered_ids
    )
    queues = _candidate_queues(
        recent_ids=recent_ids,
        pending_recent_ids=(
            checkpoint.pending_recent_series_ids
        ),
        pending_historical_ids=checkpoint.pending_series_ids,
        historical_ids=historical_ids,
        existing_ids=existing_ids,
        excluded_recent_ids=set(
            checkpoint.excluded_recent_series_ids
        ),
    )
    selected_recent_ids, selected_historical_ids = (
        _select_candidate_ids(
            recent_ids=queues.recent_series_ids,
            historical_ids=queues.historical_series_ids,
            max_new=max_new,
            max_recent=max_recent,
        )
    )
    selected_ids = (
        *selected_recent_ids,
        *selected_historical_ids,
    )
    ingestion = None
    checkpoint = checkpoint.with_pending_recent_series_ids(
        queues.recent_series_ids
    ).with_pending_series_ids(queues.historical_series_ids)

    if not preview:
        await checkpoint_store.save(checkpoint)

        if selected_ids:
            ingestion = await ingestion_cli.run_batch_ingestion(
                selected_ids,
                min_request_interval_seconds=(
                    min_request_interval_seconds
                ),
                progress_callback=(
                    ingestion_cli._print_batch_progress
                ),
                progress_interval=_DEFAULT_PROGRESS_INTERVAL,
            )
            completed_ids = _completed_ingestion_ids(ingestion)
            excluded_in_batch = {
                attempt.series_id for attempt in ingestion.attempts
                if attempt.excluded_reason is not None
            }
            checkpoint = checkpoint.with_pending_series_ids(
                tuple(
                    series_id
                    for series_id in checkpoint.pending_series_ids
                    if series_id not in completed_ids
                )
            )
            checkpoint = checkpoint.with_pending_recent_series_ids(
                tuple(
                    series_id
                    for series_id in (
                        checkpoint.pending_recent_series_ids
                    )
                    if series_id not in completed_ids
                )
            )
            new_recent_exclusions = (
                series_id for series_id in selected_recent_ids
                if series_id in excluded_in_batch
            )
            checkpoint = checkpoint.with_excluded_recent_series_ids(
                tuple(dict.fromkeys((
                    *checkpoint.excluded_recent_series_ids,
                    *new_recent_exclusions,
                )))
            )
            await checkpoint_store.save(checkpoint)

    return MangaCatalogSyncReport(
        recent_discovered=len(recent_ids),
        recent_pages=recent_state.pages_completed,
        recent_malformed=len(recent_state.issues),
        historical_pages=historical_page_count,
        considered=len(queues.considered_series_ids),
        existing=queues.existing,
        new=(
            len(queues.recent_series_ids)
            + len(queues.historical_series_ids)
        ),
        selected_series_ids=selected_ids,
        deferred=(
            len(queues.recent_series_ids)
            + len(queues.historical_series_ids)
            - len(selected_ids)
        ),
        checkpoint=checkpoint,
        ingestion=ingestion,
        excluded_known=queues.excluded_known,
        recent_candidates=len(queues.recent_series_ids),
        historical_candidates=len(queues.historical_series_ids),
        selected_recent_series_ids=selected_recent_ids,
        selected_historical_series_ids=selected_historical_ids,
    )


def _print_discovery_summary(
    report: MangaCatalogSyncReport,
    *,
    preview: bool,
) -> None:
    label = "Catalog preview" if preview else "Catalog discovery"
    print(
        (
            f"{label}: recent_discovered={report.recent_discovered}; "
            f"recent_pages={report.recent_pages}; "
            f"recent_malformed={report.recent_malformed}; "
            f"historical_pages={report.historical_pages}; "
            f"considered={report.considered}; "
            f"existing={report.existing}; "
            f"excluded_known={report.excluded_known}; new={report.new}; "
            f"recent_new={report.recent_candidates}; "
            f"historical_new={report.historical_candidates}; "
            "recent_selected="
            f"{len(report.selected_recent_series_ids)}; "
            "historical_selected="
            f"{len(report.selected_historical_series_ids)}; "
            f"selected={len(report.selected_series_ids)}; "
            f"deferred={report.deferred}; "
            f"checkpoint={report.checkpoint.partition_label}; "
            "checkpoint_recent_pending="
            f"{len(report.checkpoint.pending_recent_series_ids)}; "
            "checkpoint_historical_pending="
            f"{len(report.checkpoint.pending_series_ids)}."
        )
    )


def _print_report(
    report: MangaCatalogSyncReport,
    *,
    preview: bool,
) -> int:
    _print_discovery_summary(report, preview=preview)

    if preview:
        print(
            "No checkpoint, series details, covers, or records were changed."
        )
        return 0

    if report.ingestion is None:
        print(
            "No new MangaUpdates series were found in this run."
        )
        return 0

    return ingestion_cli._print_batch_results(report.ingestion)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        validate_database_config()
        checkpoint_store = (
            create_catalog_checkpoint_store_from_settings()
        )

        if checkpoint_store is None:
            raise RuntimeError(
                "Catalog checkpoint storage is not configured."
            )

        report = asyncio.run(
            run_catalog_sync(
                checkpoint_store=checkpoint_store,
                preview=arguments.preview,
                recent_discovery_limit=(
                    arguments.recent_discovery_limit
                ),
                max_new=arguments.max_new,
                max_recent=arguments.max_recent,
                historical_pages=arguments.historical_pages,
                per_page=arguments.per_page,
                minimum_year=arguments.minimum_year,
                exclude_genres=arguments.exclude_genres or (),
                min_request_interval_seconds=(
                    arguments.min_request_interval_seconds
                ),
            )
        )
    except KeyboardInterrupt:
        print(
            (
                "MangaUpdates catalog sync interrupted. Completed records "
                "remain committed and will be skipped next time."
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
                "MangaUpdates catalog sync stopped after HTTP 429; "
                f"no further requests were sent.{retry_after}"
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            f"MangaUpdates catalog sync failed: {exc}",
            file=sys.stderr,
        )
        return 1

    return _print_report(report, preview=arguments.preview)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
