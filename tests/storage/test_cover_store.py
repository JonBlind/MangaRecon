from __future__ import annotations

import asyncio
import hashlib
from unittest.mock import MagicMock

import pytest

from backend.ingestion.images import DownloadedCoverImage
from backend.storage import cover_store


def _image() -> DownloadedCoverImage:
    return DownloadedCoverImage(
        content=b"\x89PNG\r\n\x1a\ncover-data",
        content_type="image/png",
        extension="png",
    )


@pytest.mark.parametrize(
    ("bucket_name", "public_base_url", "message"),
    [
        ("   ", "https://mangarecon.com", "bucket_name"),
        ("covers", "http://mangarecon.com", "HTTPS URL"),
        (
            "covers",
            "https://mangarecon.com?query=true",
            "without a query",
        ),
    ],
)
def test_constructor_rejects_invalid_configuration(
    bucket_name: str,
    public_base_url: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        cover_store.S3CoverStore(
            bucket_name=bucket_name,
            public_base_url=public_base_url,
        )


def test_store_cover_writes_content_addressed_immutable_object(
) -> None:
    s3_client = MagicMock()
    store = cover_store.S3CoverStore(
        bucket_name="mangarecon-covers",
        public_base_url="https://mangarecon.com/",
        s3_client=s3_client,
    )
    image = _image()

    result = asyncio.run(
        store.store_cover(
            provider_key="mangaupdates",
            external_id="42",
            image=image,
        )
    )

    digest = hashlib.sha256(image.content).hexdigest()
    object_key = f"covers/mangaupdates/42/{digest}.png"
    assert result == f"https://mangarecon.com/{object_key}"
    assert store.public_base_url == "https://mangarecon.com"
    s3_client.put_object.assert_called_once_with(
        Bucket="mangarecon-covers",
        Key=object_key,
        Body=image.content,
        ContentType="image/png",
        CacheControl="public,max-age=31536000,immutable",
    )


def test_store_cover_rejects_unsafe_key_components_before_s3(
) -> None:
    s3_client = MagicMock()
    store = cover_store.S3CoverStore(
        bucket_name="mangarecon-covers",
        public_base_url="https://mangarecon.com",
        s3_client=s3_client,
    )

    with pytest.raises(
        ValueError,
        match="provider_key contains unsupported characters",
    ):
        asyncio.run(
            store.store_cover(
                provider_key="../unsafe",
                external_id="42",
                image=_image(),
            )
        )

    s3_client.put_object.assert_not_called()


def test_store_cover_wraps_provider_failure() -> None:
    failure = RuntimeError("provider details")
    s3_client = MagicMock()
    s3_client.put_object.side_effect = failure
    store = cover_store.S3CoverStore(
        bucket_name="mangarecon-covers",
        public_base_url="https://mangarecon.com",
        s3_client=s3_client,
    )

    with pytest.raises(
        cover_store.CoverStorageError,
        match="Could not store the cover image",
    ) as exc_info:
        asyncio.run(
            store.store_cover(
                provider_key="mangaupdates",
                external_id="42",
                image=_image(),
            )
        )

    assert exc_info.value.__cause__ is failure
    assert "provider details" not in str(exc_info.value)


def test_factory_returns_none_outside_production_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cover_store, "ENV", "test")
    monkeypatch.setattr(
        cover_store.settings,
        "cover_storage_bucket",
        None,
    )
    monkeypatch.setattr(
        cover_store.settings,
        "cover_public_base_url",
        None,
    )

    assert cover_store.create_cover_store_from_settings() is None


@pytest.mark.parametrize(
    ("bucket_name", "public_base_url"),
    [
        ("covers", None),
        (None, "https://mangarecon.com"),
    ],
)
def test_factory_rejects_partial_configuration(
    monkeypatch: pytest.MonkeyPatch,
    bucket_name: str | None,
    public_base_url: str | None,
) -> None:
    monkeypatch.setattr(
        cover_store.settings,
        "cover_storage_bucket",
        bucket_name,
    )
    monkeypatch.setattr(
        cover_store.settings,
        "cover_public_base_url",
        public_base_url,
    )

    with pytest.raises(
        cover_store.CoverStorageConfigurationError,
        match="must be configured together",
    ):
        cover_store.create_cover_store_from_settings()


def test_factory_requires_configuration_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cover_store, "ENV", "prod")
    monkeypatch.setattr(
        cover_store.settings,
        "cover_storage_bucket",
        None,
    )
    monkeypatch.setattr(
        cover_store.settings,
        "cover_public_base_url",
        None,
    )

    with pytest.raises(
        cover_store.CoverStorageConfigurationError,
        match="Production ingestion requires",
    ):
        cover_store.create_cover_store_from_settings()


def test_factory_builds_configured_s3_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_store = object()
    constructor = MagicMock(return_value=configured_store)
    monkeypatch.setattr(
        cover_store.settings,
        "cover_storage_bucket",
        " configured-bucket ",
    )
    monkeypatch.setattr(
        cover_store.settings,
        "cover_public_base_url",
        " https://mangarecon.com ",
    )
    monkeypatch.setattr(
        cover_store,
        "S3CoverStore",
        constructor,
    )

    result = cover_store.create_cover_store_from_settings()

    assert result is configured_store
    constructor.assert_called_once_with(
        bucket_name="configured-bucket",
        public_base_url="https://mangarecon.com",
    )
