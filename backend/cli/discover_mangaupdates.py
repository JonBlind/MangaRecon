from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from math import isfinite
from pathlib import Path

from backend.clients.mangaupdates_client import (
    MANGAUPDATES_SERIES_FILTERS,
    MANGAUPDATES_SERIES_ORDER_FIELDS,
    MANGAUPDATES_SERIES_TYPES,
    create_mangaupdates_client,
)
from backend.ingestion.mangaupdates_discovery import (
    MAX_DISCOVERY_RESULTS,
    MangaUpdatesDiscoveryError,
    MangaUpdatesDiscoveryRequest,
    MangaUpdatesDiscoveryState,
    discover_mangaupdates_catalog,
)


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
            (
                f"{field_name} must be between 1 and "
                f"{maximum}."
            )
        )

    return parsed


def _limit(value: str) -> int:
    return _bounded_integer(
        value,
        field_name="limit",
        maximum=MAX_DISCOVERY_RESULTS,
    )


def _per_page(value: str) -> int:
    return _bounded_integer(
        value,
        field_name="per-page",
        maximum=100,
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
            "Discover MangaUpdates series into a reviewable, "
            "resumable manifest without changing the database."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("mangaupdates-discovery.json"),
        help=(
            "JSON manifest/checkpoint path. Defaults to "
            "mangaupdates-discovery.json."
        ),
    )
    parser.add_argument(
        "--ids-output",
        type=Path,
        help=(
            "Text ID-list path for the ingestion command. Defaults "
            "to the manifest path with a .txt suffix."
        ),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Resume the next uncompleted page from an existing "
            "manifest."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Fetch and display candidates without writing a "
            "manifest or ID list."
        ),
    )
    parser.add_argument(
        "--limit",
        type=_limit,
        default=None,
        help=(
            "Maximum deduplicated IDs to discover (1-10000; "
            "default 100)."
        ),
    )
    parser.add_argument(
        "--per-page",
        type=_per_page,
        default=None,
        help=(
            "Requested MangaUpdates page size (1-100; "
            "default 100)."
        ),
    )
    parser.add_argument(
        "--query",
        type=_nonblank,
        default=None,
        help="Optional title-search text.",
    )
    parser.add_argument(
        "--type",
        dest="series_types",
        action="append",
        choices=MANGAUPDATES_SERIES_TYPES,
        default=None,
        help=(
            "MangaUpdates media type. Repeat to include multiple "
            "types."
        ),
    )
    parser.add_argument(
        "--year",
        type=_nonblank,
        default=None,
        help=(
            "Optional MangaUpdates year filter/partition value."
        ),
    )
    parser.add_argument(
        "--genre",
        dest="genres",
        action="append",
        type=_nonblank,
        default=None,
        help="Genre to include. Repeat for multiple genres.",
    )
    parser.add_argument(
        "--exclude-genre",
        dest="exclude_genres",
        action="append",
        type=_nonblank,
        default=None,
        help="Genre to exclude. Repeat for multiple genres.",
    )
    parser.add_argument(
        "--filter",
        dest="filters",
        action="append",
        choices=MANGAUPDATES_SERIES_FILTERS,
        default=None,
        help=(
            "Structured MangaUpdates filter. Repeat for multiple "
            "filters."
        ),
    )
    parser.add_argument(
        "--order-by",
        choices=MANGAUPDATES_SERIES_ORDER_FIELDS,
        default=None,
        help=(
            "MangaUpdates result ordering (default rating)."
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


def _deduplicate(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _request_from_arguments(
    arguments: argparse.Namespace,
    *,
    base: MangaUpdatesDiscoveryRequest | None = None,
) -> MangaUpdatesDiscoveryRequest:
    def scalar(
        argument_name: str,
        initial_default,
    ):
        supplied = getattr(arguments, argument_name)

        if supplied is not None:
            return supplied

        if base is not None:
            return getattr(base, argument_name)

        return initial_default

    def values(argument_name: str) -> tuple[str, ...]:
        supplied = getattr(arguments, argument_name)

        if supplied is not None:
            return _deduplicate(supplied)

        if base is not None:
            return getattr(base, argument_name)

        return ()

    return MangaUpdatesDiscoveryRequest(
        limit=scalar("limit", 100),
        per_page=scalar("per_page", 100),
        query=scalar("query", None),
        series_types=values("series_types"),
        year=scalar("year", None),
        genres=values("genres"),
        exclude_genres=values("exclude_genres"),
        filters=values("filters"),
        order_by=scalar("order_by", "rating"),
    )


def _ids_output_path(
    manifest_path: Path,
    configured_path: Path | None,
) -> Path:
    if configured_path is not None:
        return configured_path

    return manifest_path.with_suffix(".txt")


def _paths_are_same(first: Path, second: Path) -> bool:
    return first.resolve(strict=False) == second.resolve(
        strict=False
    )


def _atomic_write_text(
    path: Path,
    contents: str,
) -> None:
    parent = path.parent

    if not parent.exists():
        raise OSError(
            f"Output directory does not exist: {parent}"
        )

    temporary_name: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(contents)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_name = temporary_file.name

        os.replace(temporary_name, path)
    except BaseException:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)

        raise


def _write_manifest(
    path: Path,
    state: MangaUpdatesDiscoveryState,
) -> None:
    _atomic_write_text(
        path,
        json.dumps(
            state.to_dict(),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
    )


def _load_manifest(
    path: Path,
) -> MangaUpdatesDiscoveryState:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as exc:
        raise MangaUpdatesDiscoveryError(
            f"Could not read discovery manifest {path}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise MangaUpdatesDiscoveryError(
            f"Discovery manifest {path} is invalid JSON: {exc}"
        ) from exc

    return MangaUpdatesDiscoveryState.from_dict(payload)


def _write_ids(
    path: Path,
    *,
    manifest_path: Path,
    state: MangaUpdatesDiscoveryState,
) -> None:
    if state.status != "complete":
        raise MangaUpdatesDiscoveryError(
            "Cannot write IDs before discovery completes."
        )

    header = (
        "# MangaUpdates series IDs discovered by MangaRecon\n"
        f"# Manifest: {manifest_path.name}\n"
        f"# Count: {len(state.series)}\n"
    )
    body = "".join(
        f"{item.series_id}\n" for item in state.series
    )
    _atomic_write_text(path, header + body)


async def run_discovery(
    state: MangaUpdatesDiscoveryState,
    *,
    min_request_interval_seconds: float | None = None,
    checkpoint_path: Path | None = None,
) -> MangaUpdatesDiscoveryState:
    client_options: dict[str, float] = {}

    if min_request_interval_seconds is not None:
        client_options[
            "min_request_interval_seconds"
        ] = min_request_interval_seconds

    checkpoint = None

    if checkpoint_path is not None:
        checkpoint = lambda current: _write_manifest(
            checkpoint_path,
            current,
        )

    async with create_mangaupdates_client(
        **client_options
    ) as client:
        return await discover_mangaupdates_catalog(
            client,
            state=state,
            checkpoint=checkpoint,
        )


def _print_dry_run(
    state: MangaUpdatesDiscoveryState,
) -> None:
    for item in state.series:
        print(f"{item.series_id}\t{item.title}")

    print(
        (
            f"Dry-run summary: discovered={len(state.series)}; "
            f"pages={state.pages_completed}; "
            f"skipped_malformed={len(state.issues)}."
        )
    )


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    manifest_path = arguments.manifest
    ids_output_path = _ids_output_path(
        manifest_path,
        arguments.ids_output,
    )

    if arguments.resume and arguments.dry_run:
        parser.error("--resume and --dry-run cannot be combined.")

    if _paths_are_same(manifest_path, ids_output_path):
        parser.error(
            "--manifest and --ids-output must be different paths."
        )

    try:
        if arguments.resume:
            if not manifest_path.is_file():
                raise MangaUpdatesDiscoveryError(
                    (
                        "Cannot resume because the manifest does "
                        f"not exist: {manifest_path}"
                    )
                )

            state = _load_manifest(manifest_path)
            requested = _request_from_arguments(
                arguments,
                base=state.request,
            )

            if requested != state.request:
                raise MangaUpdatesDiscoveryError(
                    (
                        "Resume options do not match the request "
                        "stored in the manifest."
                    )
                )

            if (
                state.status != "complete"
                and ids_output_path.exists()
            ):
                raise MangaUpdatesDiscoveryError(
                    (
                        "ID output already exists for an incomplete "
                        f"manifest: {ids_output_path}"
                    )
                )
        else:
            request = _request_from_arguments(arguments)
            state = MangaUpdatesDiscoveryState(
                request=request
            )

            if not arguments.dry_run:
                if manifest_path.exists():
                    raise MangaUpdatesDiscoveryError(
                        (
                            "Manifest already exists; use --resume "
                            f"or choose another path: {manifest_path}"
                        )
                    )

                if ids_output_path.exists():
                    raise MangaUpdatesDiscoveryError(
                        (
                            "ID output already exists; choose "
                            f"another path: {ids_output_path}"
                        )
                    )

                _write_manifest(manifest_path, state)

        if state.status != "complete":
            state = asyncio.run(
                run_discovery(
                    state,
                    min_request_interval_seconds=(
                        arguments.min_request_interval_seconds
                    ),
                    checkpoint_path=(
                        None
                        if arguments.dry_run
                        else manifest_path
                    ),
                )
            )

        if arguments.dry_run:
            _print_dry_run(state)
            return 0

        if not ids_output_path.exists():
            _write_ids(
                ids_output_path,
                manifest_path=manifest_path,
                state=state,
            )
    except Exception as exc:
        print(f"Discovery failed: {exc}", file=sys.stderr)
        return 1

    print(
        (
            f"Discovery complete: series={len(state.series)}; "
            f"pages={state.pages_completed}; "
            f"skipped_malformed={len(state.issues)}."
        )
    )
    print(f"Manifest: {manifest_path}")
    print(f"ID list: {ids_output_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
