from __future__ import annotations

import asyncio
import io
import json
from unittest.mock import MagicMock

import pytest

from backend.ingestion.mangaupdates_backfill import (
    MangaUpdatesBackfillCheckpoint,
)
from backend.storage import catalog_checkpoint_store as storage


def test_load_returns_none_before_first_checkpoint() -> None:
    s3_client = MagicMock()
    s3_client.list_objects_v2.return_value = {}
    store = storage.S3CatalogCheckpointStore(
        bucket_name="covers",
        s3_client=s3_client,
    )

    assert asyncio.run(store.load()) is None
    s3_client.get_object.assert_not_called()


def test_save_and_load_checkpoint_json() -> None:
    checkpoint = (
        MangaUpdatesBackfillCheckpoint.initial(start_year=2026)
        .with_pending_recent_series_ids((10, 20))
        .with_pending_series_ids((30, 40))
    )
    s3_client = MagicMock()
    s3_client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": storage.CATALOG_CHECKPOINT_OBJECT_KEY}
        ]
    }
    s3_client.get_object.return_value = {
        "Body": io.BytesIO(
            json.dumps(checkpoint.to_dict()).encode("utf-8")
        )
    }
    store = storage.S3CatalogCheckpointStore(
        bucket_name="covers",
        s3_client=s3_client,
    )

    assert asyncio.run(store.load()) == checkpoint
    asyncio.run(store.save(checkpoint))

    s3_client.list_objects_v2.assert_called_once_with(
        Bucket="covers",
        Prefix=storage.CATALOG_CHECKPOINT_OBJECT_KEY,
        MaxKeys=1,
    )
    s3_client.get_object.assert_called_once_with(
        Bucket="covers",
        Key=storage.CATALOG_CHECKPOINT_OBJECT_KEY,
    )
    put_kwargs = s3_client.put_object.call_args.kwargs
    assert put_kwargs["Bucket"] == "covers"
    assert put_kwargs["Key"] == storage.CATALOG_CHECKPOINT_OBJECT_KEY
    assert put_kwargs["ContentType"] == "application/json"
    assert put_kwargs["CacheControl"] == "no-store"
    assert json.loads(put_kwargs["Body"].decode("utf-8")) == (
        checkpoint.to_dict()
    )


def test_load_rejects_invalid_checkpoint() -> None:
    s3_client = MagicMock()
    s3_client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": storage.CATALOG_CHECKPOINT_OBJECT_KEY}
        ]
    }
    s3_client.get_object.return_value = {
        "Body": io.BytesIO(b"not-json")
    }
    store = storage.S3CatalogCheckpointStore(
        bucket_name="covers",
        s3_client=s3_client,
    )

    with pytest.raises(
        storage.CatalogCheckpointStorageError,
        match="checkpoint is invalid",
    ):
        asyncio.run(store.load())


def test_factory_requires_bucket_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(storage, "ENV", "prod")
    monkeypatch.setattr(
        storage.settings,
        "cover_storage_bucket",
        None,
    )

    with pytest.raises(
        storage.CatalogCheckpointStorageError,
        match="requires COVER_STORAGE_BUCKET",
    ):
        storage.create_catalog_checkpoint_store_from_settings()


def test_factory_builds_configured_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_store = object()
    constructor = MagicMock(return_value=configured_store)
    monkeypatch.setattr(
        storage.settings,
        "cover_storage_bucket",
        " checkpoint-bucket ",
    )
    monkeypatch.setattr(
        storage,
        "S3CatalogCheckpointStore",
        constructor,
    )

    result = storage.create_catalog_checkpoint_store_from_settings()

    assert result is configured_store
    constructor.assert_called_once_with(
        bucket_name="checkpoint-bucket"
    )
