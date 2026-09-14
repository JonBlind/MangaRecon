from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Any, Protocol
from urllib.parse import urlsplit

from backend.config.settings import ENV, settings
from backend.ingestion.images import DownloadedCoverImage


_SAFE_KEY_COMPONENT = re.compile(r"\A[a-zA-Z0-9_-]+\Z")


class CoverStorageError(RuntimeError):
    """Raised when a validated cover cannot be stored."""


class CoverStorageConfigurationError(CoverStorageError):
    """Raised when cover storage configuration is incomplete."""


class CoverStore(Protocol):
    """Interface used by ingestion without coupling it to S3."""

    @property
    def public_base_url(self) -> str:
        """Return the public origin used for stored cover URLs."""

    async def store_cover(
        self,
        *,
        provider_key: str,
        external_id: str,
        image: DownloadedCoverImage,
    ) -> str:
        """Store a cover and return its public URL."""


class S3CoverStore:
    """Persist content-addressed covers in a private S3 bucket."""

    def __init__(
        self,
        *,
        bucket_name: str,
        public_base_url: str,
        s3_client: Any | None = None,
    ) -> None:
        normalized_bucket = bucket_name.strip()
        normalized_base_url = public_base_url.strip().rstrip("/")

        if not normalized_bucket:
            raise ValueError("bucket_name cannot be blank.")

        parsed_base_url = urlsplit(normalized_base_url)

        if (
            parsed_base_url.scheme != "https"
            or not parsed_base_url.netloc
            or parsed_base_url.query
            or parsed_base_url.fragment
        ):
            raise ValueError(
                "public_base_url must be an HTTPS URL without a query or fragment."
            )

        self._bucket_name = normalized_bucket
        self._public_base_url = normalized_base_url
        self._s3_client = s3_client

    @property
    def public_base_url(self) -> str:
        return self._public_base_url

    async def store_cover(
        self,
        *,
        provider_key: str,
        external_id: str,
        image: DownloadedCoverImage,
    ) -> str:
        normalized_provider = provider_key.strip()
        normalized_external_id = external_id.strip()

        for field_name, value in (
            ("provider_key", normalized_provider),
            ("external_id", normalized_external_id),
        ):
            if not _SAFE_KEY_COMPONENT.fullmatch(value):
                raise ValueError(
                    f"{field_name} contains unsupported characters."
                )

        digest = hashlib.sha256(image.content).hexdigest()
        object_key = (
            f"covers/{normalized_provider}/{normalized_external_id}/"
            f"{digest}.{image.extension}"
        )

        try:
            await asyncio.to_thread(
                self._put_object,
                object_key,
                image,
            )
        except Exception as exc:
            raise CoverStorageError(
                "Could not store the cover image."
            ) from exc

        return f"{self._public_base_url}/{object_key}"

    def _put_object(
        self,
        object_key: str,
        image: DownloadedCoverImage,
    ) -> None:
        self._get_s3_client().put_object(
            Bucket=self._bucket_name,
            Key=object_key,
            Body=image.content,
            ContentType=image.content_type,
            CacheControl="public,max-age=31536000,immutable",
        )

    def _get_s3_client(self):
        if self._s3_client is None:
            # Keep boto3 out of the request-serving import path. Cover storage
            # is used only by controlled ingestion and maintenance jobs.
            import boto3

            self._s3_client = boto3.client("s3")

        return self._s3_client


def create_cover_store_from_settings() -> S3CoverStore | None:
    """Build configured cover storage for an ingestion process."""
    bucket_name = (settings.cover_storage_bucket or "").strip()
    public_base_url = (settings.cover_public_base_url or "").strip()

    if bool(bucket_name) != bool(public_base_url):
        raise CoverStorageConfigurationError(
            "COVER_STORAGE_BUCKET and COVER_PUBLIC_BASE_URL must be "
            "configured together."
        )

    if not bucket_name:
        if ENV == "prod":
            raise CoverStorageConfigurationError(
                "Production ingestion requires configured cover storage."
            )

        return None

    return S3CoverStore(
        bucket_name=bucket_name,
        public_base_url=public_base_url,
    )
