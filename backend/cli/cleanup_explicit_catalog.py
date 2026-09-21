"""Preview or remove catalog titles carrying explicitly rejected genres."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from contextlib import aclosing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.engine import URL, make_url

from backend.config.settings import settings as application_settings
from backend.content_safety.policy import (
    EXPLICIT_GENRE_NAMES,
    NORMALIZED_EXPLICIT_GENRE_NAMES,
)
from backend.db.client_db import ClientReadDatabase, ClientWriteDatabase
from backend.db.models.genre import Genre
from backend.db.models.join_tables import manga_genre
from backend.db.models.manga import Manga
from backend.db.models.manga_collection import MangaCollection
from backend.db.models.rating import Rating
from backend.dependencies import (
    dispose_database_engines,
    get_manga_read_db,
    get_manga_write_db,
    get_user_read_db,
    settings as database_settings,
)


_MANIFEST_SCHEMA_VERSION = 1
_USER_LINK_BATCH_SIZE = 500
_S3_DELETE_BATCH_SIZE = 1_000
_MANAGED_COVER_PREFIX = "covers/mangaupdates/"


class ExplicitCatalogCleanupError(RuntimeError):
    """Raised when cleanup cannot continue without risking unrelated data."""


@dataclass(frozen=True, slots=True)
class ExplicitCatalogTarget:
    manga_id: int
    title: str
    matched_genres: tuple[str, ...]
    cover_url: str | None
    cover_key: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "manga_id": self.manga_id,
            "title": self.title,
            "matched_genres": list(self.matched_genres),
            "cover_url": self.cover_url,
            "cover_key": self.cover_key,
        }


@dataclass(frozen=True, slots=True)
class UserLinkCounts:
    ratings: int
    collection_links: int

    @property
    def total(self) -> int:
        return self.ratings + self.collection_links


def _positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected count must be an integer."
        ) from exc

    if parsed < 1:
        raise argparse.ArgumentTypeError(
            "expected count must be greater than zero."
        )

    return parsed


def _nonblank(value: str) -> str:
    normalized = value.strip()

    if not normalized:
        raise argparse.ArgumentTypeError("value cannot be blank.")

    return normalized


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Delete the exact manifest targets, then delete their hosted "
            "covers and invalidate the cover cache."
        ),
    )
    action.add_argument(
        "--assets-only",
        action="store_true",
        help=(
            "Retry only the idempotent S3 deletion and CloudFront "
            "invalidation from an existing manifest."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help=(
            "JSON manifest written during preview and required for any "
            "destructive action."
        ),
    )
    parser.add_argument(
        "--expected-count",
        type=_positive_integer,
        help="Required destructive-action guard matching the manifest count.",
    )
    parser.add_argument(
        "--cloudfront-distribution-id",
        type=_nonblank,
        help=(
            "Distribution invalidated after hosted covers are removed; "
            "required when the manifest contains hosted covers."
        ),
    )
    return parser


def _database_identity(url: URL) -> dict[str, Any]:
    return {
        "host": (url.host or "").casefold(),
        "port": url.port or 5432,
        "database": url.database,
    }


def _same_database(first: URL, second: URL) -> bool:
    return _database_identity(first) == _database_identity(second)


def _cover_key(url: str | None, public_base_url: str) -> str | None:
    if not url:
        return None

    parsed = urlsplit(url)
    base = urlsplit(public_base_url.rstrip("/"))

    if (
        parsed.scheme.casefold() != base.scheme.casefold()
        or parsed.netloc.casefold() != base.netloc.casefold()
        or parsed.query
        or parsed.fragment
    ):
        return None

    key = parsed.path.lstrip("/")

    if (
        not key.startswith(_MANAGED_COVER_PREFIX)
        or ".." in key.split("/")
        or key.endswith("/")
    ):
        return None

    return key


async def select_explicit_catalog_targets(
    db: ClientReadDatabase,
    *,
    public_base_url: str,
    lock: bool = False,
) -> tuple[ExplicitCatalogTarget, ...]:
    """Select only titles carrying one of the four rejected genres."""
    normalized_genre = func.lower(func.btrim(Genre.genre_name))
    explicit_match = (
        select(1)
        .select_from(
            manga_genre.join(
                Genre,
                manga_genre.c.genre_id == Genre.genre_id,
            )
        )
        .where(
            manga_genre.c.manga_id == Manga.manga_id,
            normalized_genre.in_(NORMALIZED_EXPLICIT_GENRE_NAMES),
        )
        .exists()
    )
    manga_stmt = (
        select(
            Manga.manga_id,
            Manga.title,
            Manga.cover_image_url,
        )
        .where(explicit_match)
        .order_by(Manga.manga_id)
    )

    if lock:
        manga_stmt = manga_stmt.with_for_update(of=Manga)

    manga_rows = (await db.execute(manga_stmt)).all()

    if not manga_rows:
        return ()

    manga_ids = tuple(int(row.manga_id) for row in manga_rows)
    genre_rows = (
        await db.execute(
            select(manga_genre.c.manga_id, Genre.genre_name)
            .select_from(
                manga_genre.join(
                    Genre,
                    manga_genre.c.genre_id == Genre.genre_id,
                )
            )
            .where(
                manga_genre.c.manga_id.in_(manga_ids),
                normalized_genre.in_(NORMALIZED_EXPLICIT_GENRE_NAMES),
            )
            .order_by(manga_genre.c.manga_id, Genre.genre_name)
        )
    ).all()
    matched_genres: dict[int, list[str]] = {
        manga_id: [] for manga_id in manga_ids
    }

    for manga_id, genre_name in genre_rows:
        matched_genres[int(manga_id)].append(genre_name.strip())

    return tuple(
        ExplicitCatalogTarget(
            manga_id=int(row.manga_id),
            title=row.title,
            matched_genres=tuple(matched_genres[int(row.manga_id)]),
            cover_url=row.cover_image_url,
            cover_key=_cover_key(row.cover_image_url, public_base_url),
        )
        for row in manga_rows
    )


async def count_user_links(
    db: ClientReadDatabase,
    manga_ids: Sequence[int],
) -> UserLinkCounts:
    ratings = 0
    collection_links = 0

    for start in range(0, len(manga_ids), _USER_LINK_BATCH_SIZE):
        batch = manga_ids[start:start + _USER_LINK_BATCH_SIZE]
        rating_result = await db.execute(
            select(func.count())
            .select_from(Rating)
            .where(Rating.manga_id.in_(batch))
        )
        ratings += int(rating_result.scalar_one())
        collection_result = await db.execute(
            select(func.count())
            .select_from(MangaCollection)
            .where(MangaCollection.manga_id.in_(batch))
        )
        collection_links += int(collection_result.scalar_one())

    return UserLinkCounts(
        ratings=ratings,
        collection_links=collection_links,
    )


def _manifest_payload(
    *,
    database_url: URL,
    bucket_name: str,
    public_base_url: str,
    targets: Sequence[ExplicitCatalogTarget],
) -> dict[str, Any]:
    return {
        "schema_version": _MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": _database_identity(database_url),
        "cover_storage": {
            "bucket": bucket_name,
            "public_base_url": public_base_url,
        },
        "policy_genres": sorted(EXPLICIT_GENRE_NAMES),
        "targets": [target.to_dict() for target in targets],
    }


def write_manifest(
    path: Path,
    *,
    database_url: URL,
    bucket_name: str,
    public_base_url: str,
    targets: Sequence[ExplicitCatalogTarget],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.tmp")
    temporary_path.write_text(
        json.dumps(
            _manifest_payload(
                database_url=database_url,
                bucket_name=bucket_name,
                public_base_url=public_base_url,
                targets=targets,
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def load_manifest(
    path: Path,
    *,
    database_url: URL,
    bucket_name: str,
    public_base_url: str,
) -> tuple[ExplicitCatalogTarget, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExplicitCatalogCleanupError(
            f"Could not read cleanup manifest: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise ExplicitCatalogCleanupError(
            "Cleanup manifest must contain a JSON object."
        )

    if payload.get("schema_version") != _MANIFEST_SCHEMA_VERSION:
        raise ExplicitCatalogCleanupError(
            "Unsupported cleanup manifest schema version."
        )

    if payload.get("database") != _database_identity(database_url):
        raise ExplicitCatalogCleanupError(
            "Cleanup manifest belongs to a different database target."
        )

    if payload.get("cover_storage") != {
        "bucket": bucket_name,
        "public_base_url": public_base_url,
    }:
        raise ExplicitCatalogCleanupError(
            "Cleanup manifest belongs to different cover storage."
        )

    if payload.get("policy_genres") != sorted(EXPLICIT_GENRE_NAMES):
        raise ExplicitCatalogCleanupError(
            "Cleanup manifest does not match the current explicit policy."
        )

    raw_targets = payload.get("targets")

    if not isinstance(raw_targets, list):
        raise ExplicitCatalogCleanupError(
            "Cleanup manifest targets must be an array."
        )

    targets: list[ExplicitCatalogTarget] = []
    seen_ids: set[int] = set()

    for raw_target in raw_targets:
        if not isinstance(raw_target, dict):
            raise ExplicitCatalogCleanupError(
                "Each cleanup manifest target must be an object."
            )

        manga_id = raw_target.get("manga_id")
        title = raw_target.get("title")
        matched_genres = raw_target.get("matched_genres")
        cover_url = raw_target.get("cover_url")
        cover_key = raw_target.get("cover_key")

        if (
            isinstance(manga_id, bool)
            or not isinstance(manga_id, int)
            or manga_id < 1
            or manga_id in seen_ids
            or not isinstance(title, str)
            or not isinstance(matched_genres, list)
            or not matched_genres
            or any(not isinstance(name, str) for name in matched_genres)
            or (cover_url is not None and not isinstance(cover_url, str))
            or (cover_key is not None and not isinstance(cover_key, str))
        ):
            raise ExplicitCatalogCleanupError(
                "Cleanup manifest contains an invalid target."
            )

        normalized_genres = {
            name.strip().casefold() for name in matched_genres
        }

        if not normalized_genres.issubset(
            NORMALIZED_EXPLICIT_GENRE_NAMES
        ):
            raise ExplicitCatalogCleanupError(
                "Cleanup manifest contains a non-explicit genre target."
            )

        expected_cover_key = _cover_key(cover_url, public_base_url)

        if cover_key != expected_cover_key:
            raise ExplicitCatalogCleanupError(
                "Cleanup manifest contains an invalid hosted-cover key."
            )

        targets.append(
            ExplicitCatalogTarget(
                manga_id=manga_id,
                title=title,
                matched_genres=tuple(matched_genres),
                cover_url=cover_url,
                cover_key=cover_key,
            )
        )
        seen_ids.add(manga_id)

    return tuple(targets)


def _assert_expected_count(
    targets: Sequence[ExplicitCatalogTarget],
    expected_count: int,
) -> None:
    if len(targets) != expected_count:
        raise ExplicitCatalogCleanupError(
            f"Expected {expected_count} targets, but the manifest contains "
            f"{len(targets)}."
        )


async def preview_cleanup(
    *,
    public_base_url: str,
) -> tuple[tuple[ExplicitCatalogTarget, ...], UserLinkCounts]:
    try:
        async with aclosing(get_manga_read_db()) as catalog_provider:
            catalog_db = await anext(catalog_provider)
            targets = await select_explicit_catalog_targets(
                catalog_db,
                public_base_url=public_base_url,
            )
        async with aclosing(get_user_read_db()) as user_provider:
            user_db = await anext(user_provider)
            links = await count_user_links(
                user_db,
                tuple(target.manga_id for target in targets),
            )
        return targets, links
    finally:
        await dispose_database_engines()


async def delete_manifest_targets(
    manifest_targets: tuple[ExplicitCatalogTarget, ...],
    *,
    public_base_url: str,
) -> UserLinkCounts:
    """Lock, revalidate, and transactionally delete exact manifest rows."""
    try:
        async with aclosing(get_manga_write_db()) as catalog_provider:
            catalog_db = await anext(catalog_provider)

            try:
                live_targets = await select_explicit_catalog_targets(
                    catalog_db,
                    public_base_url=public_base_url,
                    lock=True,
                )

                if live_targets != manifest_targets:
                    raise ExplicitCatalogCleanupError(
                        "Live explicit targets changed after preview; create "
                        "and review a new manifest."
                    )

                manga_ids = tuple(
                    target.manga_id for target in live_targets
                )
                async with aclosing(
                    get_user_read_db()
                ) as user_provider:
                    user_db = await anext(user_provider)
                    links = await count_user_links(user_db, manga_ids)

                if links.total:
                    raise ExplicitCatalogCleanupError(
                        "Cleanup refused because targets now have "
                        f"ratings={links.ratings} and "
                        f"collection_links={links.collection_links}."
                    )

                result = await catalog_db.execute(
                    delete(Manga)
                    .where(Manga.manga_id.in_(manga_ids))
                    .returning(Manga.manga_id)
                )
                deleted_ids = tuple(sorted(int(value) for value in result.scalars()))

                if deleted_ids != tuple(sorted(manga_ids)):
                    raise ExplicitCatalogCleanupError(
                        "Database did not delete the exact manifest target set."
                    )

                await catalog_db.commit()
                return links
            except Exception:
                await catalog_db.rollback()
                raise
    finally:
        await dispose_database_engines()


def delete_manifest_assets(
    targets: Sequence[ExplicitCatalogTarget],
    *,
    bucket_name: str,
    cloudfront_distribution_id: str,
    s3_client: Any | None = None,
    cloudfront_client: Any | None = None,
) -> tuple[int, str | None]:
    cover_keys = tuple(
        dict.fromkeys(
            target.cover_key
            for target in targets
            if target.cover_key is not None
        )
    )

    if not cover_keys:
        return 0, None

    if any(
        not key.startswith(_MANAGED_COVER_PREFIX)
        or ".." in key.split("/")
        for key in cover_keys
    ):
        raise ExplicitCatalogCleanupError(
            "Refusing to delete a cover outside the managed prefix."
        )

    if s3_client is None or cloudfront_client is None:
        import boto3

        s3_client = s3_client or boto3.client("s3")
        cloudfront_client = cloudfront_client or boto3.client("cloudfront")

    for start in range(0, len(cover_keys), _S3_DELETE_BATCH_SIZE):
        batch = cover_keys[start:start + _S3_DELETE_BATCH_SIZE]
        response = s3_client.delete_objects(
            Bucket=bucket_name,
            Delete={
                "Objects": [{"Key": key} for key in batch],
                "Quiet": True,
            },
        )
        errors = response.get("Errors", [])

        if errors:
            failed_keys = ", ".join(
                str(error.get("Key", "unknown")) for error in errors[:5]
            )
            raise ExplicitCatalogCleanupError(
                "S3 did not delete all manifest covers; failed keys: "
                f"{failed_keys}. Re-run --assets-only with this manifest."
            )

    response = cloudfront_client.create_invalidation(
        DistributionId=cloudfront_distribution_id,
        InvalidationBatch={
            "Paths": {
                "Quantity": 1,
                "Items": ["/covers/*"],
            },
            "CallerReference": (
                f"mangarecon-explicit-cleanup-{uuid4()}"
            ),
        },
    )
    invalidation_id = response.get("Invalidation", {}).get("Id")
    return len(cover_keys), invalidation_id


def _configured_cover_storage() -> tuple[str, str]:
    bucket_name = (application_settings.cover_storage_bucket or "").strip()
    public_base_url = (
        application_settings.cover_public_base_url or ""
    ).strip().rstrip("/")

    if not bucket_name or not public_base_url:
        raise ExplicitCatalogCleanupError(
            "COVER_STORAGE_BUCKET and COVER_PUBLIC_BASE_URL must both be "
            "configured for explicit-content cleanup."
        )

    return bucket_name, public_base_url


def _print_target_summary(
    targets: Sequence[ExplicitCatalogTarget],
    links: UserLinkCounts,
) -> None:
    hosted_covers = sum(
        target.cover_key is not None for target in targets
    )
    print(
        "Explicit cleanup selection: "
        f"titles={len(targets)}; ratings={links.ratings}; "
        f"collection_links={links.collection_links}; "
        f"hosted_covers={hosted_covers}."
    )
    print(
        "Policy: delete Hentai/Lolicon/Shotacon/Smut; retain Adult-only "
        "titles behind the existing opt-in toggle."
    )


def _validate_action_arguments(
    parser: argparse.ArgumentParser,
    arguments: argparse.Namespace,
) -> None:
    destructive = arguments.execute or arguments.assets_only

    if destructive and arguments.manifest is None:
        parser.error("--manifest is required with destructive actions.")

    if destructive and arguments.expected_count is None:
        parser.error("--expected-count is required with destructive actions.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    _validate_action_arguments(parser, arguments)

    try:
        bucket_name, public_base_url = _configured_cover_storage()

        if arguments.assets_only:
            if not database_settings.manga_write:
                raise ExplicitCatalogCleanupError(
                    "MangaWriterDB must be configured."
                )

            database_url = make_url(database_settings.manga_write)
            targets = load_manifest(
                arguments.manifest,
                database_url=database_url,
                bucket_name=bucket_name,
                public_base_url=public_base_url,
            )
            _assert_expected_count(targets, arguments.expected_count)

            if any(target.cover_key for target in targets) and not (
                arguments.cloudfront_distribution_id
            ):
                raise ExplicitCatalogCleanupError(
                    "--cloudfront-distribution-id is required when the "
                    "manifest contains hosted covers."
                )

            deleted, invalidation_id = delete_manifest_assets(
                targets,
                bucket_name=bucket_name,
                cloudfront_distribution_id=(
                    arguments.cloudfront_distribution_id or ""
                ),
            )
            print(
                f"Asset cleanup complete: covers_deleted={deleted}; "
                f"cloudfront_invalidation={invalidation_id or 'not_needed'}."
            )
            return 0

        if arguments.execute:
            if not database_settings.manga_write or not database_settings.user_read:
                raise ExplicitCatalogCleanupError(
                    "MangaWriterDB and UserReaderDB must both be configured."
                )

            database_url = make_url(database_settings.manga_write)
            user_url = make_url(database_settings.user_read)

            if not _same_database(database_url, user_url):
                raise ExplicitCatalogCleanupError(
                    "MangaWriterDB and UserReaderDB must target the same "
                    "host, port, and database."
                )

            targets = load_manifest(
                arguments.manifest,
                database_url=database_url,
                bucket_name=bucket_name,
                public_base_url=public_base_url,
            )
            _assert_expected_count(targets, arguments.expected_count)

            if any(target.cover_key for target in targets) and not (
                arguments.cloudfront_distribution_id
            ):
                raise ExplicitCatalogCleanupError(
                    "--cloudfront-distribution-id is required when the "
                    "manifest contains hosted covers."
                )

            print(
                "Destructive database target: "
                f"host={database_url.host} database={database_url.database} "
                f"user={database_url.username}"
            )
            links = asyncio.run(
                delete_manifest_targets(
                    targets,
                    public_base_url=public_base_url,
                )
            )
            _print_target_summary(targets, links)
            print(f"Deleted {len(targets)} explicit catalog titles.")

            try:
                deleted, invalidation_id = delete_manifest_assets(
                    targets,
                    bucket_name=bucket_name,
                    cloudfront_distribution_id=(
                        arguments.cloudfront_distribution_id or ""
                    ),
                )
            except Exception:
                print(
                    "Database deletion committed, but asset cleanup did not "
                    "finish. Preserve the manifest and retry with "
                    "--assets-only.",
                    file=sys.stderr,
                )
                raise

            print(
                f"Asset cleanup complete: covers_deleted={deleted}; "
                f"cloudfront_invalidation={invalidation_id or 'not_needed'}."
            )
            return 0

        if not database_settings.manga_read or not database_settings.user_read:
            raise ExplicitCatalogCleanupError(
                "MangaReaderDB and UserReaderDB must both be configured."
            )

        database_url = make_url(database_settings.manga_read)
        user_url = make_url(database_settings.user_read)

        if not _same_database(database_url, user_url):
            raise ExplicitCatalogCleanupError(
                "MangaReaderDB and UserReaderDB must target the same host, "
                "port, and database."
            )

        print(
            "Read-only database target: "
            f"host={database_url.host} database={database_url.database} "
            f"catalog_user={database_url.username} "
            f"user_data_user={user_url.username}"
        )
        targets, links = asyncio.run(
            preview_cleanup(
                public_base_url=public_base_url,
            )
        )
        _print_target_summary(targets, links)
        print("Preview only: no records or covers were changed.")

        if arguments.manifest:
            write_manifest(
                arguments.manifest,
                database_url=database_url,
                bucket_name=bucket_name,
                public_base_url=public_base_url,
                targets=targets,
            )
            print(f"Wrote cleanup manifest to {arguments.manifest}.")

        return 0
    except ExplicitCatalogCleanupError as exc:
        print(f"Explicit catalog cleanup failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Explicit catalog cleanup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
