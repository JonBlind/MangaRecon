from unittest.mock import MagicMock

from backend.auth import passwords


def test_hash_password_delegates_to_password_helper(monkeypatch):
    helper = MagicMock()
    helper.hash.return_value = "hashed-password"

    monkeypatch.setattr(
        passwords,
        "_password_helper",
        helper,
    )

    result = passwords.hash_password("plain-password")

    assert result == "hashed-password"
    helper.hash.assert_called_once_with("plain-password")


def test_verify_password_returns_true_for_valid_password(monkeypatch):
    helper = MagicMock()
    helper.verify_and_update.return_value = (
        True,
        None,
    )

    monkeypatch.setattr(
        passwords,
        "_password_helper",
        helper,
    )

    result = passwords.verify_password(
        "plain-password",
        "hashed-password",
    )

    assert result is True
    helper.verify_and_update.assert_called_once_with(
        "plain-password",
        "hashed-password",
    )


def test_verify_password_returns_false_for_invalid_password(monkeypatch):
    helper = MagicMock()
    helper.verify_and_update.return_value = (
        False,
        None,
    )

    monkeypatch.setattr(
        passwords,
        "_password_helper",
        helper,
    )

    result = passwords.verify_password(
        "wrong-password",
        "hashed-password",
    )

    assert result is False
    helper.verify_and_update.assert_called_once_with(
        "wrong-password",
        "hashed-password",
    )


def test_verify_password_ignores_updated_hash(monkeypatch):
    helper = MagicMock()
    helper.verify_and_update.return_value = (
        True,
        "replacement-hash",
    )

    monkeypatch.setattr(
        passwords,
        "_password_helper",
        helper,
    )

    result = passwords.verify_password(
        "plain-password",
        "old-hash",
    )

    assert result is True