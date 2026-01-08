import pytest
import uuid
from datetime import datetime, timezone
from pydantic import ValidationError

from backend.schemas.user import UserCreate, UserRead, UserUpdate, ChangePassword


def test_user_create_valid():
    obj = UserCreate(
        email="test@example.com",
        password="password123",
        username="testuser",
        displayname="Test User",
    )
    assert obj.email == "test@example.com"
    assert obj.username == "testuser"
    assert obj.displayname == "Test User"


@pytest.mark.parametrize("bad_username", ["", "a", "abc"])
def test_user_create_rejects_short_username(bad_username: str):
    with pytest.raises(ValidationError):
        UserCreate(
            email="test@example.com",
            password="password123",
            username=bad_username,
            displayname="Test User",
        )


@pytest.mark.parametrize("bad_displayname", ["", "a", "abc"])
def test_user_create_rejects_short_displayname(bad_displayname: str):
    with pytest.raises(ValidationError):
        UserCreate(
            email="test@example.com",
            password="password123",
            username="testuser",
            displayname=bad_displayname,
        )


def test_user_create_rejects_long_displayname():
    with pytest.raises(ValidationError):
        UserCreate(
            email="test@example.com",
            password="password123",
            username="testuser",
            displayname="a" * 65,
        )


def test_user_create_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserCreate(
            email="not-an-email",
            password="password123",
            username="testuser",
            displayname="Test User",
        )


def test_user_update_allows_empty_payload():
    obj = UserUpdate()
    assert obj.email is None
    assert obj.password is None
    assert obj.displayname is None


def test_user_update_rejects_short_displayname_if_provided():
    with pytest.raises(ValidationError):
        UserUpdate(displayname="abc")


def test_change_password_requires_fields():
    with pytest.raises(ValidationError):
        ChangePassword()  # type: ignore


def test_user_read_instantiates():
    now = datetime.now(timezone.utc)
    user_id = uuid.uuid4()

    obj = UserRead(
        id=user_id,
        email="test@example.com",
        username="testuser",
        displayname="Test User",
        is_active=True,
        is_superuser=False,
        is_verified=False,
        created_at=now,
        last_login=None,
    )

    assert obj.id == user_id
    assert obj.email == "test@example.com"
    assert obj.last_login is None


def test_user_read_from_attributes():
    class DummyUser:
        def __init__(self):
            self.id = uuid.uuid4()
            self.email = "test@example.com"
            self.username = "testuser"
            self.displayname = "Test User"
            self.is_active = True
            self.is_superuser = False
            self.is_verified = True
            self.created_at = datetime.now(timezone.utc)
            self.last_login = None

    dummy = DummyUser()
    obj = UserRead.model_validate(dummy)

    assert obj.id == dummy.id
    assert obj.email == dummy.email
    assert obj.is_verified is True
