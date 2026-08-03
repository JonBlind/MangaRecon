from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest

import backend.ingestion.mangaupdates_parser as parser_module
from backend.ingestion.records import CreatorCreditRecord


def make_payload() -> dict[str, Any]:
    return {
        "series_id": 51239621230,
        "title": "Berserk",
        "url": (
            "https://www.mangaupdates.com/"
            "series/njeqwry/berserk"
        ),
        "associated": [
            {
                "title": "ベルセルク",
            },
            {
                "title": "Berserk",
            },
            {
                "title": "  ベルセルク  ",
            },
            {
                "title": "   ",
            },
            "invalid",
        ],
        "description": "A dark fantasy manga.",
        "image": {
            "url": {
                "original": (
                    "https://cdn.mangaupdates.com/"
                    "image/i501230.png"
                ),
                "thumb": (
                    "https://cdn.mangaupdates.com/"
                    "image/thumb/i501230.png"
                ),
            },
            "height": 400,
            "width": 284,
        },
        "type": "Manga",
        "year": "1989",
        "bayesian_rating": 8.98,
        "rating_votes": 3722,
        "genres": [
            {
                "genre": "Action",
            },
            {
                "genre": "Seinen",
            },
            {
                "genre": "Fantasy",
            },
            {
                "genre": "action",
            },
        ],
        "categories": [
            {
                "category": "Dark Fantasy",
                "votes": 44,
            },
            {
                "category": "War",
                "votes": 0,
            },
            {
                "category": "dark fantasy",
                "votes": 1,
            },
        ],
        "authors": [
            {
                "name": "MIURA Kentaro",
                "author_id": 22635311083,
                "url": (
                    "https://www.mangaupdates.com/"
                    "author/aech9t7/miura-kentaro"
                ),
                "type": "Author",
            },
            {
                "name": "MIURA Kentaro",
                "author_id": 22635311083,
                "url": (
                    "https://www.mangaupdates.com/"
                    "author/aech9t7/miura-kentaro"
                ),
                "type": "Artist",
            },
            {
                "name": "Studio Gaga",
                "author_id": 58953789514,
                "url": (
                    "https://www.mangaupdates.com/"
                    "author/r2zkb4a/studio-gaga"
                ),
                "type": "Artist",
            },
        ],
        "last_updated": {
            "timestamp": 1784651704,
            "as_rfc3339": (
                "2026-07-21T09:35:04-07:00"
            ),
        },
    }


def test_parse_series_normalizes_expected_record() -> None:
    payload = make_payload()

    result = parser_module.parse_mangaupdates_series(payload)

    assert result.provider_key == "mangaupdates"
    assert result.external_id == "51239621230"
    assert result.source_url == payload["url"]
    assert result.source_updated_at == datetime(
        2026,
        7,
        21,
        9,
        35,
        4,
        tzinfo=timezone(
            timedelta(hours=-7)
        ),
    )

    assert len(result.payload_hash) == 64
    assert result.title == "Berserk"
    assert result.alternate_titles == (
        "ベルセルク",
    )
    assert result.description == (
        "A dark fantasy manga."
    )
    assert result.publication_year == 1989
    assert result.media_type == "Manga"

    assert result.external_average_rating == (
        Decimal("8.98")
    )
    assert result.external_rating_votes == 3722
    assert result.cover_image_url == (
        "https://cdn.mangaupdates.com/"
        "image/i501230.png"
    )

    assert result.genres == (
        "Action",
        "Fantasy",
    )
    assert result.demographics == (
        "Seinen",
    )
    assert result.tags == (
        "Dark Fantasy",
        "War",
    )

    assert result.creator_credits == (
        CreatorCreditRecord(
            provider_key="mangaupdates",
            external_id="22635311083",
            name="MIURA Kentaro",
            role="author",
            source_url=(
                "https://www.mangaupdates.com/"
                "author/aech9t7/miura-kentaro"
            ),
        ),
        CreatorCreditRecord(
            provider_key="mangaupdates",
            external_id="22635311083",
            name="MIURA Kentaro",
            role="artist",
            source_url=(
                "https://www.mangaupdates.com/"
                "author/aech9t7/miura-kentaro"
            ),
        ),
        CreatorCreditRecord(
            provider_key="mangaupdates",
            external_id="58953789514",
            name="Studio Gaga",
            role="artist",
            source_url=(
                "https://www.mangaupdates.com/"
                "author/r2zkb4a/studio-gaga"
            ),
        ),
    )


@pytest.mark.parametrize(
    "appendix",
    [
        "Note: Nominated for an award.",
        (
            "**Original Manga:** "
            "[Publisher](https://example.com/original)"
        ),
        (
            "**Official Translations:**  \n"
            "English: [Publisher](https://example.com/en)"
        ),
    ],
)
def test_description_excludes_source_and_appendix_metadata(
    appendix: str,
) -> None:
    payload = make_payload()
    payload["description"] = (
        "From Viz:  \n"
        "The actual synopsis.\n\n"
        f"{appendix}"
    )

    result = parser_module.parse_mangaupdates_series(payload)

    assert result.description == "The actual synopsis."


def test_zero_votes_normalizes_rating_to_none() -> None:
    payload = make_payload()
    payload["bayesian_rating"] = 0
    payload["rating_votes"] = 0

    result = parser_module.parse_mangaupdates_series(payload)

    assert result.external_average_rating is None
    assert result.external_rating_votes == 0


def test_thumbnail_is_used_when_original_is_missing() -> None:
    payload = make_payload()
    payload["image"]["url"]["original"] = " "

    result = parser_module.parse_mangaupdates_series(payload)

    assert result.cover_image_url == (
        "https://cdn.mangaupdates.com/"
        "image/thumb/i501230.png"
    )


def test_timestamp_is_used_when_rfc3339_is_invalid() -> None:
    payload = make_payload()
    payload["last_updated"] = {
        "timestamp": 1700000000,
        "as_rfc3339": "invalid",
    }

    result = parser_module.parse_mangaupdates_series(payload)

    assert result.source_updated_at == (
        datetime.fromtimestamp(
            1700000000,
            tz=timezone.utc,
        )
    )


def test_malformed_optional_fields_are_ignored() -> None:
    payload = make_payload()
    payload.update(
        {
            "description": 123,
            "image": {
                "url": {
                    "original": 123,
                    "thumb": "",
                }
            },
            "type": "x" * 51,
            "year": "Unknown",
            "bayesian_rating": "NaN",
            "rating_votes": -1,
            "associated": [
                {
                    "title": "x" * 256,
                },
                {
                    "missing": "title",
                },
                123,
            ],
            "genres": [
                {
                    "genre": "",
                },
                {
                    "genre": "x" * 256,
                },
                123,
            ],
            "categories": [
                {
                    "category": "",
                },
                {
                    "category": "x" * 256,
                },
                123,
            ],
            "authors": [
                {
                    "name": "Unknown",
                    "author_id": 1,
                    "type": "Editor",
                },
                {
                    "name": "",
                    "author_id": 2,
                    "type": "Author",
                },
                {
                    "name": "Creator",
                    "author_id": 0,
                    "type": "Artist",
                },
                123,
            ],
            "last_updated": {
                "timestamp": "invalid",
                "as_rfc3339": "invalid",
            },
        }
    )

    result = parser_module.parse_mangaupdates_series(payload)

    assert result.description is None
    assert result.cover_image_url is None
    assert result.media_type is None
    assert result.publication_year is None
    assert result.external_average_rating is None
    assert result.external_rating_votes is None
    assert result.alternate_titles == ()
    assert result.genres == ()
    assert result.demographics == ()
    assert result.tags == ()
    assert result.creator_credits == ()
    assert result.source_updated_at is None


def test_creator_without_external_id_is_preserved() -> None:
    payload = make_payload()
    payload["authors"] = [
        {
            "name": "DISCIPLES (Redice Studio)",
            "author_id": None,
            "url": None,
            "type": "Artist",
        },
        {
            "name": "disciples (redice studio)",
            "type": "Artist",
        },
    ]

    result = parser_module.parse_mangaupdates_series(payload)

    assert result.creator_credits == (
        CreatorCreditRecord(
            provider_key="mangaupdates",
            external_id=None,
            name="DISCIPLES (Redice Studio)",
            role="artist",
            source_url=None,
        ),
    )


@pytest.mark.parametrize(
    "rating",
    [
        -1,
        11,
        True,
        None,
        "not-a-number",
    ],
)
def test_invalid_ratings_are_ignored(
    rating: Any,
) -> None:
    payload = make_payload()
    payload["bayesian_rating"] = rating
    payload["rating_votes"] = 1

    result = parser_module.parse_mangaupdates_series(payload)

    assert result.external_average_rating is None


def test_payload_hash_is_independent_of_object_key_order() -> None:
    payload = make_payload()
    reordered = dict(
        reversed(
            list(payload.items())
        )
    )

    first = parser_module.parse_mangaupdates_series(payload)
    second = parser_module.parse_mangaupdates_series(reordered)

    assert first.payload_hash == second.payload_hash


def test_payload_hash_changes_when_payload_changes() -> None:
    first_payload = make_payload()
    second_payload = deepcopy(first_payload)
    second_payload["description"] = "Updated description."

    first = parser_module.parse_mangaupdates_series(
        first_payload
    )
    second = parser_module.parse_mangaupdates_series(
        second_payload
    )

    assert first.payload_hash != second.payload_hash


def test_payload_hash_changes_when_normalization_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = make_payload()
    first = parser_module.parse_mangaupdates_series(payload)
    next_version = (
        parser_module._MANGAUPDATES_NORMALIZATION_VERSION
        + 1
    )

    monkeypatch.setattr(
        parser_module,
        "_MANGAUPDATES_NORMALIZATION_VERSION",
        next_version,
    )

    second = parser_module.parse_mangaupdates_series(payload)

    assert first.payload_hash != second.payload_hash


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("series_id", None),
        ("series_id", 0),
        ("series_id", True),
        ("series_id", "invalid"),
        ("title", None),
        ("title", ""),
        ("title", "x" * 256),
        ("url", None),
        ("url", "   "),
    ],
)
def test_required_identity_fields_are_validated(
    field_name: str,
    value: Any,
) -> None:
    payload = make_payload()
    payload[field_name] = value

    with pytest.raises(
        parser_module.MangaUpdatesParseError,
        match=field_name,
    ):
        parser_module.parse_mangaupdates_series(payload)


def test_payload_must_be_an_object() -> None:
    with pytest.raises(
        parser_module.MangaUpdatesParseError,
        match="must be an object",
    ):
        parser_module.parse_mangaupdates_series(
            []  # type: ignore[arg-type]
        )


def test_external_string_ids_are_canonicalized() -> None:
    payload = make_payload()
    payload["series_id"] = "000123"
    payload["authors"] = [
        {
            "name": "Creator",
            "author_id": "00042",
            "type": "Author",
        }
    ]

    result = parser_module.parse_mangaupdates_series(payload)

    assert result.external_id == "123"
    assert result.creator_credits[0].external_id == "42"
