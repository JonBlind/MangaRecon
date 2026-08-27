import json
import os
from unittest.mock import MagicMock

import pytest

from backend.config import bootstrap_runtime


def _valid_secret_payload() -> dict[str, str]:
    return {
        key: f"value-for-{key}"
        for key in bootstrap_runtime.REQUIRED_SECRET_KEYS
    }


def test_load_runtime_secrets_is_noop_without_secret_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_factory = MagicMock()
    monkeypatch.delenv(
        bootstrap_runtime.SECRET_ID_ENV,
        raising=False,
    )
    monkeypatch.setattr(
        bootstrap_runtime.boto3,
        "client",
        client_factory,
    )

    bootstrap_runtime.load_runtime_secrets()

    client_factory.assert_not_called()


def test_load_runtime_secrets_loads_expected_environment_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _valid_secret_payload()
    secrets_client = MagicMock()
    secrets_client.get_secret_value.return_value = {
        "SecretString": json.dumps(payload)
    }

    monkeypatch.setenv(
        bootstrap_runtime.SECRET_ID_ENV,
        "mangarecon/prod/runtime",
    )
    monkeypatch.setattr(
        bootstrap_runtime.boto3,
        "client",
        MagicMock(return_value=secrets_client),
    )

    bootstrap_runtime.load_runtime_secrets()

    secrets_client.get_secret_value.assert_called_once_with(
        SecretId="mangarecon/prod/runtime"
    )
    for key, value in payload.items():
        assert os.environ[key] == value


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"AUTH_SECRET": "present"},
            "missing required keys",
        ),
        (
            {
                **_valid_secret_payload(),
                "UNEXPECTED": "value",
            },
            "unexpected keys",
        ),
        (
            {
                **_valid_secret_payload(),
                "AUTH_SECRET": "",
            },
            "empty or non-string values",
        ),
        (
            {
                **_valid_secret_payload(),
                "AUTH_SECRET": 123,
            },
            "empty or non-string values",
        ),
    ],
)
def test_parse_secret_payload_rejects_invalid_fields(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        bootstrap_runtime._parse_secret_payload(
            json.dumps(payload)
        )


@pytest.mark.parametrize(
    "secret_string",
    [
        "not-json",
        json.dumps(["not", "an", "object"]),
    ],
)
def test_parse_secret_payload_rejects_invalid_json_shape(
    secret_string: str,
) -> None:
    with pytest.raises(RuntimeError, match="valid JSON object|JSON object"):
        bootstrap_runtime._parse_secret_payload(secret_string)


def test_load_runtime_secrets_requires_secret_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secrets_client = MagicMock()
    secrets_client.get_secret_value.return_value = {
        "SecretBinary": b"not-supported"
    }

    monkeypatch.setenv(
        bootstrap_runtime.SECRET_ID_ENV,
        "mangarecon/prod/runtime",
    )
    monkeypatch.setattr(
        bootstrap_runtime.boto3,
        "client",
        MagicMock(return_value=secrets_client),
    )

    with pytest.raises(RuntimeError, match="SecretString JSON"):
        bootstrap_runtime.load_runtime_secrets()


def test_load_runtime_secrets_wraps_aws_errors_without_secret_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client_factory = MagicMock(
        side_effect=RuntimeError("provider failure")
    )

    monkeypatch.setenv(
        bootstrap_runtime.SECRET_ID_ENV,
        "mangarecon/prod/runtime",
    )
    monkeypatch.setattr(
        bootstrap_runtime.boto3,
        "client",
        client_factory,
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to load MangaRecon runtime secrets",
    ) as exc_info:
        bootstrap_runtime.load_runtime_secrets()

    assert "provider failure" not in str(exc_info.value)


def test_main_loads_secrets_before_replacing_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def load() -> None:
        calls.append("load")

    def execv(executable: str, command: list[str]) -> None:
        calls.append("exec")
        assert executable == command[0]
        assert command[1:] == [
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
        ]
        raise RuntimeError("exec intercepted")

    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setattr(
        bootstrap_runtime,
        "load_runtime_secrets",
        load,
    )
    monkeypatch.setattr(
        bootstrap_runtime.os,
        "execv",
        execv,
    )

    with pytest.raises(RuntimeError, match="exec intercepted"):
        bootstrap_runtime.main()

    assert calls == ["load", "exec"]
