from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.schemas.collection import (
    BulkMangaAddFailure,
    BulkMangaInCollectionRequest,
    BulkMangaInCollectionResponse,
    CollectionCreate,
    CollectionRead,
    CollectionUpdate,
    MangaInCollectionRequest,
)


def test_collection_create_accepts_valid_payload():
    payload = CollectionCreate(
        collection_name="Favorites",
        description="My favorite manga",
    )

    assert payload.collection_name == "Favorites"
    assert payload.description == "My favorite manga"


def test_collection_create_allows_missing_description():
    payload = CollectionCreate(
        collection_name="Favorites",
    )

    assert payload.collection_name == "Favorites"
    assert payload.description is None


def test_collection_create_preserves_surrounding_whitespace():
    payload = CollectionCreate(
        collection_name="  Favorites  ",
    )

    assert payload.collection_name == "  Favorites  "


@pytest.mark.parametrize(
    "collection_name",
    [
        "",
        " ",
        "   ",
        "\t",
        "\n",
        " \t\n ",
    ],
)
def test_collection_create_rejects_empty_or_whitespace_name(
    collection_name,
):
    with pytest.raises(ValidationError) as exc_info:
        CollectionCreate(
            collection_name=collection_name,
        )

    errors = exc_info.value.errors()

    assert any(
        error["loc"] == ("collection_name",)
        for error in errors
    )


def test_collection_create_accepts_name_at_maximum_length():
    name = "a" * 255

    payload = CollectionCreate(
        collection_name=name,
    )

    assert payload.collection_name == name


def test_collection_create_rejects_name_over_maximum_length():
    with pytest.raises(ValidationError):
        CollectionCreate(
            collection_name="a" * 256,
        )


def test_collection_create_accepts_description_at_maximum_length():
    description = "a" * 255

    payload = CollectionCreate(
        collection_name="Favorites",
        description=description,
    )

    assert payload.description == description


def test_collection_create_rejects_description_over_maximum_length():
    with pytest.raises(ValidationError):
        CollectionCreate(
            collection_name="Favorites",
            description="a" * 256,
        )


def test_collection_update_accepts_empty_payload():
    payload = CollectionUpdate()

    assert payload.collection_name is None
    assert payload.description is None
    assert payload.model_dump(exclude_unset=True) == {}


def test_collection_update_accepts_name_only():
    payload = CollectionUpdate(
        collection_name="Completed",
    )

    assert payload.collection_name == "Completed"
    assert payload.description is None
    assert payload.model_dump(exclude_unset=True) == {
        "collection_name": "Completed",
    }


def test_collection_update_accepts_description_only():
    payload = CollectionUpdate(
        description="Finished series",
    )

    assert payload.collection_name is None
    assert payload.description == "Finished series"
    assert payload.model_dump(exclude_unset=True) == {
        "description": "Finished series",
    }


def test_collection_update_allows_explicit_null_values():
    payload = CollectionUpdate(
        collection_name=None,
        description=None,
    )

    assert payload.model_dump(exclude_unset=True) == {
        "collection_name": None,
        "description": None,
    }


@pytest.mark.parametrize(
    "collection_name",
    [
        "",
        " ",
        "\t",
        "\n",
        " \t\n ",
    ],
)
def test_collection_update_rejects_empty_or_whitespace_name(
    collection_name,
):
    with pytest.raises(ValidationError):
        CollectionUpdate(
            collection_name=collection_name,
        )


def test_collection_update_rejects_name_over_maximum_length():
    with pytest.raises(ValidationError):
        CollectionUpdate(
            collection_name="a" * 256,
        )


def test_collection_update_rejects_description_over_maximum_length():
    with pytest.raises(ValidationError):
        CollectionUpdate(
            description="a" * 256,
        )


def test_collection_read_accepts_dictionary_data():
    created_at = datetime(
        2026,
        1,
        2,
        3,
        4,
        tzinfo=timezone.utc,
    )

    collection = CollectionRead(
        collection_id=10,
        collection_name="Favorites",
        description=None,
        created_at=created_at,
    )

    assert collection.collection_id == 10
    assert collection.collection_name == "Favorites"
    assert collection.description is None
    assert collection.created_at == created_at


def test_collection_read_supports_from_attributes():
    created_at = datetime(
        2026,
        1,
        2,
        3,
        4,
        tzinfo=timezone.utc,
    )

    orm_collection = SimpleNamespace(
        collection_id=10,
        collection_name="Favorites",
        description="My favorites",
        created_at=created_at,
    )

    collection = CollectionRead.model_validate(
        orm_collection
    )

    assert collection.collection_id == 10
    assert collection.collection_name == "Favorites"
    assert collection.description == "My favorites"
    assert collection.created_at == created_at


def test_manga_in_collection_request_accepts_manga_id():
    payload = MangaInCollectionRequest(
        manga_id=25,
    )

    assert payload.manga_id == 25


def test_manga_in_collection_request_requires_manga_id():
    with pytest.raises(ValidationError):
        MangaInCollectionRequest()


def test_bulk_manga_request_accepts_one_id():
    payload = BulkMangaInCollectionRequest(
        manga_ids=[1],
    )

    assert payload.manga_ids == [1]


def test_bulk_manga_request_accepts_one_hundred_ids():
    manga_ids = list(range(1, 101))

    payload = BulkMangaInCollectionRequest(
        manga_ids=manga_ids,
    )

    assert payload.manga_ids == manga_ids


def test_bulk_manga_request_rejects_empty_list():
    with pytest.raises(ValidationError):
        BulkMangaInCollectionRequest(
            manga_ids=[],
        )


def test_bulk_manga_request_rejects_more_than_one_hundred_ids():
    with pytest.raises(ValidationError):
        BulkMangaInCollectionRequest(
            manga_ids=list(range(101)),
        )


@pytest.mark.parametrize(
    "reason",
    [
        "ALREADY_EXISTS",
        "COLLECTION_NOT_FOUND",
        "MANGA_NOT_FOUND",
        "UNKNOWN",
    ],
)
def test_bulk_manga_add_failure_accepts_supported_reasons(
    reason,
):
    failure = BulkMangaAddFailure(
        manga_id=25,
        reason=reason,
    )

    assert failure.manga_id == 25
    assert failure.reason == reason


def test_bulk_manga_add_failure_rejects_unknown_reason():
    with pytest.raises(ValidationError):
        BulkMangaAddFailure(
            manga_id=25,
            reason="INVALID_REASON",
        )


def test_bulk_manga_response_accepts_complete_payload():
    response = BulkMangaInCollectionResponse(
        collection_id=10,
        added_count=2,
        failed_count=1,
        added_ids=[1, 2],
        failed=[
            BulkMangaAddFailure(
                manga_id=3,
                reason="ALREADY_EXISTS",
            )
        ],
    )

    assert response.collection_id == 10
    assert response.added_count == 2
    assert response.failed_count == 1
    assert response.added_ids == [1, 2]

    assert response.failed == [
        BulkMangaAddFailure(
            manga_id=3,
            reason="ALREADY_EXISTS",
        )
    ]


def test_bulk_manga_response_parses_nested_failure_dicts():
    response = BulkMangaInCollectionResponse(
        collection_id=10,
        added_count=0,
        failed_count=1,
        added_ids=[],
        failed=[
            {
                "manga_id": 3,
                "reason": "COLLECTION_NOT_FOUND",
            }
        ],
    )

    assert isinstance(
        response.failed[0],
        BulkMangaAddFailure,
    )
    assert response.failed[0].manga_id == 3