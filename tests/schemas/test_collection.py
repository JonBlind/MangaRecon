import pytest
from datetime import datetime
from pydantic import ValidationError

from backend.schemas.collection import (
    CollectionCreate,
    CollectionUpdate,
    CollectionRead,
)


# -------------------------
# CollectionCreate
# -------------------------

def test_collection_create_valid_minimal():
    obj = CollectionCreate(collection_name="Favorites")
    assert obj.collection_name == "Favorites"
    assert obj.description is None


def test_collection_create_valid_with_description():
    obj = CollectionCreate(
        collection_name="Favorites",
        description="My favorite manga"
    )
    assert obj.description == "My favorite manga"


@pytest.mark.parametrize("name", ["", " "])
def test_collection_create_rejects_empty_name(name: str):
    with pytest.raises(ValidationError):
        CollectionCreate(collection_name=name)


def test_collection_create_rejects_too_long_name():
    with pytest.raises(ValidationError):
        CollectionCreate(collection_name="a" * 256)


def test_collection_create_rejects_too_long_description():
    with pytest.raises(ValidationError):
        CollectionCreate(
            collection_name="Favorites",
            description="a" * 256
        )


# -------------------------
# CollectionUpdate
# -------------------------

def test_collection_update_allows_empty_payload():
    # All fields optional → empty update is valid
    obj = CollectionUpdate()
    assert obj.collection_name is None
    assert obj.description is None


def test_collection_update_valid_partial_update():
    obj = CollectionUpdate(collection_name="Updated Name")
    assert obj.collection_name == "Updated Name"
    assert obj.description is None


def test_collection_update_rejects_invalid_name():
    with pytest.raises(ValidationError):
        CollectionUpdate(collection_name="")


# -------------------------
# CollectionRead
# -------------------------

def test_collection_read_instantiates():
    now = datetime.now()
    obj = CollectionRead(
        collection_id=1,
        user_id="user-uuid",
        collection_name="Favorites",
        description=None,
        created_at=now,
    )

    assert obj.collection_id == 1
    assert obj.user_id == "user-uuid"
    assert obj.collection_name == "Favorites"
    assert obj.description is None
    assert obj.created_at == now


def test_collection_read_from_attributes():
    class DummyCollection:
        def __init__(self):
            self.collection_id = 1
            self.user_id = "user-uuid"
            self.collection_name = "Favorites"
            self.description = None
            self.created_at = datetime.now()

    dummy = DummyCollection()
    obj = CollectionRead.model_validate(dummy)

    assert obj.collection_id == dummy.collection_id
    assert obj.user_id == dummy.user_id
    assert obj.collection_name == dummy.collection_name
    assert obj.created_at == dummy.created_at
