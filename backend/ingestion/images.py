from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DownloadedCoverImage:
    """Validated cover bytes ready for durable storage."""

    content: bytes
    content_type: str
    extension: str
