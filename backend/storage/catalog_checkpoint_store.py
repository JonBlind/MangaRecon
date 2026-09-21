from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol

from backend.config.settings import ENV, settings
from backend.ingestion.mangaupdates_backfill import (
    MangaUpdatesBackfillCheckpoint,
)


CATALOG_CHECKPOINT_OBJECT_KEY = (
    "catalog-sync/mangaupdates-backfill-v1.json"
)


class CatalogCheckpointStorageError(RuntimeError):
    """Raised when the catalog checkpoint cannot be read or stored."""


class CatalogCheckpointStore(Protocol):
    async def load(self) -> MangaUpdatesBackfillCheckpoint | None:
        """Load the saved checkpoint, or return None before the first run."""

    async def save(
        self,
        checkpoint: MangaUpdatesBackfillCheckpoint,
    ) -> None:
        """Persist the complete checkpoint atomically as one object."""


class S3CatalogCheckpointStore:
    """Persist the small catalog cursor in private S3 storage."""

    def __init__(
        self,
        *,
        bucket_name: str,
        object_key: str = CATALOG_CHECKPOINT_OBJECT_KEY,
        s3_client: Any | None = None,
    ) -> None:
        normalized_bucket = bucket_name.strip()
        normalized_key = object_key.strip().lstrip("/")

        if not normalized_bucket:
            raise ValueError("bucket_name cannot be blank.")

        if not normalized_key:
            raise ValueError("object_key cannot be blank.")

        self._bucket_name = normalized_bucket
        self._object_key = normalized_key
        self._s3_client = s3_client

    async def load(self) -> MangaUpdatesBackfillCheckpoint | None:
        try:
            payload = await asyncio.to_thread(self._get_object)
        except Exception as exc:
            error_code = (
                getattr(exc, "response", {})
                .get("Error", {})
                .get("Code")
            )

            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return None

            raise CatalogCheckpointStorageError(
                "Could not load the catalog checkpoint."
            ) from exc

        if payload is None:
            return None

        try:
            decoded = json.loads(payload.decode("utf-8"))
            return MangaUpdatesBackfillCheckpoint.from_dict(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise CatalogCheckpointStorageError(
                "The catalog checkpoint is invalid."
            ) from exc

    async def save(
        self,
        checkpoint: MangaUpdatesBackfillCheckpoint,
    ) -> None:
        payload = json.dumps(
            checkpoint.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        try:
            await asyncio.to_thread(self._put_object, payload)
        except Exception as exc:
            raise CatalogCheckpointStorageError(
                "Could not store the catalog checkpoint."
            ) from exc

    def _get_object(self) -> bytes | None:
        s3_client = self._get_s3_client()
        listing = s3_client.list_objects_v2(
            Bucket=self._bucket_name,
            Prefix=self._object_key,
            MaxKeys=1,
        )
        object_exists = any(
            item.get("Key") == self._object_key
            for item in listing.get("Contents", [])
            if isinstance(item, dict)
        )

        if not object_exists:
            return None

        response = s3_client.get_object(
            Bucket=self._bucket_name,
            Key=self._object_key,
        )
        body = response.get("Body")

        if body is None or not hasattr(body, "read"):
            raise CatalogCheckpointStorageError(
                "The catalog checkpoint response has no readable body."
            )

        payload = body.read()

        if not isinstance(payload, bytes):
            raise CatalogCheckpointStorageError(
                "The catalog checkpoint body must be bytes."
            )

        return payload

    def _put_object(self, payload: bytes) -> None:
        self._get_s3_client().put_object(
            Bucket=self._bucket_name,
            Key=self._object_key,
            Body=payload,
            ContentType="application/json",
            CacheControl="no-store",
        )

    def _get_s3_client(self):
        if self._s3_client is None:
            import boto3

            self._s3_client = boto3.client("s3")

        return self._s3_client


def create_catalog_checkpoint_store_from_settings(
) -> S3CatalogCheckpointStore | None:
    bucket_name = (settings.cover_storage_bucket or "").strip()

    if not bucket_name:
        if ENV == "prod":
            raise CatalogCheckpointStorageError(
                "Production catalog sync requires COVER_STORAGE_BUCKET."
            )

        return None

    return S3CatalogCheckpointStore(bucket_name=bucket_name)
