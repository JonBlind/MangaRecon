from datetime import datetime, timezone
import uuid

import pytest
from pydantic import ValidationError

from backend.schemas.user import (
    ChangePassword,
    UserCreate,
    UserRead,
    UserUpdate,
)


def valid_user_create_data():
    return {
        "email": "reader@example.com",
        "password": "password123",
        "username": "reader",
        "displayname": "Manga Reader",
    }


def test_user_create_accepts_valid_payload():
    payload = UserCreate(
        **valid_user_create_data()
    )

    assert payload.email == "reader@example.com"
    assert payload.password == "password123"
    assert payload.username == "reader"
    assert payload.displayname == "Manga Reader"


def test_user_create_accepts_minimum_field_lengths():
    payload = UserCreate(
        email="reader@example.com",
        password="12345678",
        username="user",
        displayname="name",
    )

    assert payload.password == "12345678"
    assert payload.username == "user"
    assert payload.displayname == "name"


def test_user_create_accepts_displayname_at_maximum_length():
    displayname = "a" * 64

    payload = UserCreate(
        **{
            **valid_user_create_data(),
            "displayname": displayname,
        }
    )

    assert payload.displayname == displayname


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("password", "1234567"),
        ("username", "abc"),
        ("displayname", "abc"),
    ],
)
def test_user_create_rejects_fields_below_minimum_length(
    field,
    value,
):
    data = valid_user_create_data()
    data[field] = value

    with pytest.raises(ValidationError):
        UserCreate(**data)


def test_user_create_rejects_displayname_over_maximum_length():
    with pytest.raises(ValidationError):
        UserCreate(
            **{
                **valid_user_create_data(),
                "displayname": "a" * 65,
            }
        )


@pytest.mark.parametrize(
    "email",
    [
        "not-an-email",
        "reader@",
        "@example.com",
        "reader.example.com",
    ],
)
def test_user_create_rejects_invalid_email(
    email,
):
    with pytest.raises(ValidationError):
        UserCreate(
            **{
                **valid_user_create_data(),
                "email": email,
            }
        )


def test_user_update_accepts_empty_payload():
    payload = UserUpdate()

    assert payload.model_dump(exclude_unset=True) == {}


def test_user_update_accepts_displayname():
    payload = UserUpdate(
        displayname="Updated Reader",
    )

    assert payload.displayname == "Updated Reader"
    assert payload.model_dump(exclude_unset=True) == {
        "displayname": "Updated Reader",
    }


def test_user_update_accepts_username():
    payload = UserUpdate(
        username="updated-reader",
    )

    assert payload.username == "updated-reader"
    assert payload.model_dump(exclude_unset=True) == {
        "username": "updated-reader",
    }


def test_user_update_accepts_inherited_email_and_password_fields():
    payload = UserUpdate(
        email="updated@example.com",
        password="new-password",
    )

    dumped = payload.model_dump(
        exclude_unset=True
    )

    assert dumped["email"] == "updated@example.com"
    assert dumped["password"] == "new-password"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("username", "abc"),
        ("displayname", "abc"),
        ("displayname", "a" * 65),
    ],
)
def test_user_update_rejects_invalid_profile_field_lengths(
    field,
    value,
):
    with pytest.raises(ValidationError):
        UserUpdate(
            **{
                field: value,
            }
        )


def test_user_update_allows_explicit_null_profile_fields():
    payload = UserUpdate(
        username=None,
        displayname=None,
    )

    assert payload.model_dump(
        exclude_unset=True
    ) == {
        "username": None,
        "displayname": None,
    }


def test_user_read_accepts_complete_payload():
    user_id = uuid.uuid4()
    created_at = datetime(
        2026,
        1,
        2,
        3,
        4,
        tzinfo=timezone.utc,
    )
    last_login = datetime(
        2026,
        2,
        3,
        4,
        5,
        tzinfo=timezone.utc,
    )

    user = UserRead(
        id=user_id,
        email="reader@example.com",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        username="reader",
        displayname="Manga Reader",
        created_at=created_at,
        last_login=last_login,
    )

    assert user.id == user_id
    assert user.email == "reader@example.com"
    assert user.is_active is True
    assert user.is_superuser is False
    assert user.is_verified is True
    assert user.username == "reader"
    assert user.displayname == "Manga Reader"
    assert user.created_at == created_at
    assert user.last_login == last_login


def test_user_read_allows_missing_last_login():
    user = UserRead(
        id=uuid.uuid4(),
        email="reader@example.com",
        is_active=True,
        is_superuser=False,
        is_verified=False,
        username="reader",
        displayname="Manga Reader",
        created_at=datetime.now(
            timezone.utc
        ),
    )

    assert user.last_login is None


def test_user_read_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserRead(
            id=uuid.uuid4(),
            email="not-an-email",
            is_active=True,
            is_superuser=False,
            is_verified=False,
            username="reader",
            displayname="Manga Reader",
            created_at=datetime.now(
                timezone.utc
            ),
        )


def test_change_password_accepts_valid_payload():
    payload = ChangePassword(
        current_password="old-password",
        new_password="new-password",
    )

    assert payload.current_password == "old-password"
    assert payload.new_password == "new-password"


def test_change_password_accepts_one_character_current_password():
    payload = ChangePassword(
        current_password="x",
        new_password="12345678",
    )

    assert payload.current_password == "x"
    assert payload.new_password == "12345678"


@pytest.mark.parametrize(
    "current_password",
    [
        "",
    ],
)
def test_change_password_rejects_empty_current_password(
    current_password,
):
    with pytest.raises(ValidationError):
        ChangePassword(
            current_password=current_password,
            new_password="12345678",
        )


@pytest.mark.parametrize(
    "new_password",
    [
        "",
        "1",
        "1234567",
    ],
)
def test_change_password_rejects_short_new_password(
    new_password,
):
    with pytest.raises(ValidationError):
        ChangePassword(
            current_password="old-password",
            new_password=new_password,
        )


def test_change_password_requires_both_fields():
    with pytest.raises(ValidationError):
        ChangePassword(
            current_password="old-password",
        )

    with pytest.raises(ValidationError):
        ChangePassword(
            new_password="new-password",
        )