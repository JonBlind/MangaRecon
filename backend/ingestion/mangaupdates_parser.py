from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.ingestion.records import (
    CreatorCreditRecord,
    CreatorRole,
    MangaIngestionRecord,
)

MANGAUPDATES_PROVIDER_KEY = "mangaupdates"

_MANGAUPDATES_NORMALIZATION_VERSION = 2

_DESCRIPTION_SOURCE_PREFIX = re.compile(
    r"\AFrom[ \t]+[^:\r\n]{1,100}:"
    r"[ \t]*(?:\r?\n)?[ \t]*",
    re.IGNORECASE,
)

_DESCRIPTION_APPENDIX_HEADING = re.compile(
    r"\A(?:\*\*)?"
    r"(?:notes?|original(?:[ \t]+[^:\r\n]+)?|"
    r"official(?:[ \t]+[^:\r\n]+)?)"
    r":(?:\*\*)?",
    re.IGNORECASE,
)

_DESCRIPTION_PARAGRAPH_BREAK = re.compile(
    r"\r?\n[ \t]*\r?\n"
)

_DEMOGRAPHIC_NAMES = {
    "josei": "Josei",
    "seinen": "Seinen",
    "shoujo": "Shoujo",
    "shounen": "Shounen",
}

_CREATOR_ROLES: dict[str, CreatorRole] = {
    "author": "author",
    "artist": "artist",
}


class MangaUpdatesParseError(ValueError):
    """
    Raised when required MangaUpdates series data is invalid.
    """


def parse_mangaupdates_series(
    payload: Mapping[str, Any],
) -> MangaIngestionRecord:
    """
    Convert one MangaUpdates series-detail payload into a normalized record.

    Required identity fields cause a parse error when invalid. Malformed
    optional metadata is ignored so one dirty field does not prevent the
    entire series from being ingested.
    """
    if not isinstance(payload, Mapping):
        raise MangaUpdatesParseError(
            "MangaUpdates payload must be an object."
        )

    external_id = _required_external_id(
        payload.get("series_id"),
        field_name="series_id",
    )
    title = _required_text(
        payload.get("title"),
        field_name="title",
        max_length=255,
    )
    source_url = _required_text(
        payload.get("url"),
        field_name="url",
    )

    rating_votes = _optional_nonnegative_int(
        payload.get("rating_votes")
    )

    genres, demographics = _parse_genres(
        payload.get("genres")
    )

    return MangaIngestionRecord(
        provider_key=MANGAUPDATES_PROVIDER_KEY,
        external_id=external_id,
        source_url=source_url,
        source_updated_at=_parse_source_updated_at(
            payload.get("last_updated")
        ),
        payload_hash=_calculate_payload_hash(payload),
        title=title,
        alternate_titles=_parse_alternate_titles(
            payload.get("associated"),
            primary_title=title,
        ),
        description=_parse_description(
            payload.get("description")
        ),
        publication_year=_parse_year(
            payload.get("year")
        ),
        media_type=_optional_text(
            payload.get("type"),
            max_length=50,
        ),
        external_average_rating=_parse_rating(
            payload.get("bayesian_rating"),
            rating_votes=rating_votes,
        ),
        external_rating_votes=rating_votes,
        cover_image_url=_parse_cover_image_url(
            payload.get("image")
        ),
        genres=genres,
        tags=_parse_named_items(
            payload.get("categories"),
            field_name="category",
            max_length=50,
        ),
        demographics=demographics,
        creator_credits=_parse_creator_credits(
            payload.get("authors")
        ),
    )


def _required_external_id(
    value: Any,
    *,
    field_name: str,
) -> str:
    external_id = _optional_external_id(value)

    if external_id is None:
        raise MangaUpdatesParseError(
            f"MangaUpdates payload has invalid {field_name}."
        )

    return external_id


def _optional_external_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        if value < 1:
            return None

        return str(value)

    if isinstance(value, str):
        normalized = value.strip()

        if not normalized.isdecimal():
            return None

        numeric_value = int(normalized)

        if numeric_value < 1:
            return None

        return str(numeric_value)

    return None


def _required_text(
    value: Any,
    *,
    field_name: str,
    max_length: int | None = None,
) -> str:
    normalized = _optional_text(
        value,
        max_length=max_length,
    )

    if normalized is None:
        raise MangaUpdatesParseError(
            f"MangaUpdates payload has invalid {field_name}."
        )

    return normalized


def _optional_text(
    value: Any,
    *,
    max_length: int | None = None,
) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip()

    if not normalized:
        return None

    if (
        max_length is not None
        and len(normalized) > max_length
    ):
        return None

    return normalized

def _parse_description(value: Any) -> str | None:
    description = _optional_text(value)

    if description is None:
        return None

    description = _DESCRIPTION_SOURCE_PREFIX.sub(
        "",
        description,
        count=1,
    ).strip()

    synopsis_paragraphs = []

    for paragraph in _DESCRIPTION_PARAGRAPH_BREAK.split(
        description
    ):
        normalized = paragraph.strip()

        if not normalized:
            continue

        if _DESCRIPTION_APPENDIX_HEADING.match(
            normalized
        ):
            break

        synopsis_paragraphs.append(normalized)

    return _optional_text(
        "\n\n".join(synopsis_paragraphs)
    )


def _parse_year(value: Any) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        year = value
    elif isinstance(value, str):
        normalized = value.strip()

        if (
            len(normalized) != 4
            or not normalized.isdecimal()
        ):
            return None

        year = int(normalized)
    else:
        return None

    if not 1000 <= year <= 9999:
        return None

    return year


def _optional_nonnegative_int(
    value: Any,
) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value >= 0 else None

    if isinstance(value, str):
        normalized = value.strip()

        if normalized.isdecimal():
            return int(normalized)

    return None


def _parse_rating(
    value: Any,
    *,
    rating_votes: int | None,
) -> Decimal | None:
    if rating_votes == 0:
        return None

    if value is None or isinstance(value, bool):
        return None

    try:
        rating = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None

    if not rating.is_finite():
        return None

    if not Decimal("0") <= rating <= Decimal("10"):
        return None

    return rating


def _parse_cover_image_url(
    value: Any,
) -> str | None:
    if not isinstance(value, Mapping):
        return None

    urls = value.get("url")

    if not isinstance(urls, Mapping):
        return None

    original = _optional_text(
        urls.get("original")
    )

    if original is not None:
        return original

    return _optional_text(
        urls.get("thumb")
    )


def _parse_alternate_titles(
    value: Any,
    *,
    primary_title: str,
) -> tuple[str, ...]:
    titles = []

    for item in _mapping_items(value):
        title = _optional_text(
            item.get("title"),
            max_length=255,
        )

        if title is not None:
            titles.append(title)

    return _ordered_unique(
        titles,
        excluded={primary_title.casefold()},
    )


def _parse_genres(
    value: Any,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    genres = []
    demographics = []

    for item in _mapping_items(value):
        name = _optional_text(
            item.get("genre"),
            max_length=50,
        )

        if name is None:
            continue

        demographic = _DEMOGRAPHIC_NAMES.get(
            name.casefold()
        )

        if demographic is not None:
            demographics.append(demographic)
        else:
            genres.append(name)

    return (
        _ordered_unique(genres),
        _ordered_unique(demographics),
    )


def _parse_named_items(
    value: Any,
    *,
    field_name: str,
    max_length: int,
) -> tuple[str, ...]:
    names = []

    for item in _mapping_items(value):
        name = _optional_text(
            item.get(field_name),
            max_length=max_length,
        )

        if name is not None:
            names.append(name)

    return _ordered_unique(names)


def _parse_creator_credits(
    value: Any,
) -> tuple[CreatorCreditRecord, ...]:
    credits = []
    seen = set()

    for item in _mapping_items(value):
        raw_external_id = item.get("author_id")
        external_id = _optional_external_id(
            raw_external_id
        )
        name = _optional_text(
            item.get("name"),
            max_length=255,
        )
        raw_role = _optional_text(
            item.get("type")
        )

        if (
            name is None
            or raw_role is None
            or (
                raw_external_id is not None
                and external_id is None
            )
        ):
            continue

        role = _CREATOR_ROLES.get(
            raw_role.casefold()
        )

        if role is None:
            continue

        if external_id is None:
            identity = (
                "name",
                name.casefold(),
                role,
            )
        else:
            identity = (
                "external_id",
                external_id,
                role,
            )

        if identity in seen:
            continue

        seen.add(identity)

        credits.append(
            CreatorCreditRecord(
                provider_key=MANGAUPDATES_PROVIDER_KEY,
                external_id=external_id,
                name=name,
                role=role,
                source_url=_optional_text(
                    item.get("url")
                ),
            )
        )

    return tuple(credits)


def _parse_source_updated_at(
    value: Any,
) -> datetime | None:
    if not isinstance(value, Mapping):
        return None

    rfc3339 = _optional_text(
        value.get("as_rfc3339")
    )

    if rfc3339 is not None:
        normalized = rfc3339

        if normalized.endswith(("Z", "z")):
            normalized = (
                f"{normalized[:-1]}+00:00"
            )

        try:
            parsed = datetime.fromisoformat(
                normalized
            )
        except ValueError:
            parsed = None

        if (
            parsed is not None
            and parsed.tzinfo is not None
        ):
            return parsed

    timestamp = _optional_nonnegative_int(
        value.get("timestamp")
    )

    if timestamp is None:
        return None

    try:
        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )
    except (OSError, OverflowError, ValueError):
        return None


def _calculate_payload_hash(
    payload: Mapping[str, Any],
) -> str:
    try:
        canonical_payload = json.dumps(
            dict(payload),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise MangaUpdatesParseError(
            "MangaUpdates payload is not valid JSON data."
        ) from exc

    fingerprint_input = (
        f"{_MANGAUPDATES_NORMALIZATION_VERSION}\0"
        f"{canonical_payload}"
    )

    return hashlib.sha256(
        fingerprint_input.encode("utf-8")
    ).hexdigest()

def _mapping_items(
    value: Any,
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()

    return tuple(
        item
        for item in value
        if isinstance(item, Mapping)
    )


def _ordered_unique(
    values: Iterable[str],
    *,
    excluded: set[str] | None = None,
) -> tuple[str, ...]:
    seen = set() if excluded is None else set(excluded)
    result = []

    for value in values:
        identity = value.casefold()

        if identity in seen:
            continue

        seen.add(identity)
        result.append(value)

    return tuple(result)
