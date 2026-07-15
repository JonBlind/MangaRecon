from pathlib import Path
import os
import subprocess
import sys
from unittest.mock import MagicMock

from backend.auth import config


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_isolated_config_import(
    *,
    tmp_path,
    environment: dict[str, str],
    code: str,
):
    """
    Import backend.auth.config in a separate Python process.

    A temporary working directory prevents the project's .env file from
    supplying AUTH_SECRET and interfering with import-time branch tests.
    """
    env = os.environ.copy()

    env.pop("AUTH_SECRET", None)
    env.pop("DEBUG", None)
    env.pop("MANGARECON_ENV", None)

    env.update(environment)

    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(PROJECT_ROOT)
        if not existing_pythonpath
        else os.pathsep.join(
            [
                str(PROJECT_ROOT),
                existing_pythonpath,
            ]
        )
    )

    return subprocess.run(
        [
            sys.executable,
            "-c",
            code,
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_settings_contains_auth_secret():
    assert config.settings.auth_secret is not None
    assert isinstance(
        config.settings.auth_secret,
        str,
    )
    assert config.settings.auth_secret


def test_cookie_transport_configuration_matches_settings():
    transport = config.cookie_transport

    assert transport.cookie_name == "auth"
    assert transport.cookie_max_age == 3600
    assert transport.cookie_secure is (
        not config.settings.debug
    )
    assert transport.cookie_samesite == "lax"


def test_get_jwt_strategy_returns_configured_strategy():
    strategy = config.get_jwt_strategy()

    assert strategy.secret == (
        config.settings.auth_secret
    )
    assert strategy.lifetime_seconds == 3600


def test_get_jwt_strategy_constructs_strategy_from_current_settings(
    monkeypatch,
):
    strategy = MagicMock()
    constructor = MagicMock(
        return_value=strategy
    )

    monkeypatch.setattr(
        config,
        "JWTStrategy",
        constructor,
    )
    monkeypatch.setattr(
        config.settings,
        "auth_secret",
        "updated-test-secret",
    )

    result = config.get_jwt_strategy()

    assert result is strategy

    constructor.assert_called_once_with(
        secret="updated-test-secret",
        lifetime_seconds=3600,
    )


def test_auth_backend_configuration():
    backend = config.auth_backend

    assert backend.name == "jwt"
    assert backend.transport is (
        config.cookie_transport
    )
    assert backend.get_strategy is (
        config.get_jwt_strategy
    )


def test_missing_secret_uses_test_fallback(
    tmp_path,
):
    result = run_isolated_config_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "test",
        },
        code=(
            "from backend.auth import config; "
            "assert config._ENV == 'test'; "
            "assert config.settings.auth_secret == "
            "'some-fake-secret-for-tests-NOT-4-USE'; "
            "print('fallback-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "fallback-ok" in result.stdout


def test_environment_name_is_normalized(
    tmp_path,
):
    result = run_isolated_config_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "  TeSt  ",
        },
        code=(
            "from backend.auth import config; "
            "assert config._ENV == 'test'; "
            "assert config.settings.auth_secret == "
            "'some-fake-secret-for-tests-NOT-4-USE'; "
            "print('normalized-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "normalized-ok" in result.stdout


def test_missing_secret_outside_test_environment_raises(
    tmp_path,
):
    result = run_isolated_config_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
        },
        code=(
            "from backend.auth import config"
        ),
    )

    assert result.returncode != 0
    assert (
        "AUTH_SECRET is required "
        "(set AUTH_SECRET or run with "
        "MANGARECON_ENV=test)."
        in result.stderr
    )


def test_explicit_secret_is_used_outside_test_environment(
    tmp_path,
):
    result = run_isolated_config_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
            "AUTH_SECRET": "production-test-secret",
            "DEBUG": "false",
        },
        code=(
            "from backend.auth import config; "
            "assert config._ENV == 'prod'; "
            "assert config.settings.auth_secret == "
            "'production-test-secret'; "
            "assert config.settings.debug is False; "
            "assert config.cookie_transport.cookie_secure "
            "is True; "
            "print('explicit-secret-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "explicit-secret-ok" in result.stdout


def test_debug_environment_disables_secure_cookie(
    tmp_path,
):
    result = run_isolated_config_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "dev",
            "AUTH_SECRET": "development-secret",
            "DEBUG": "true",
        },
        code=(
            "from backend.auth import config; "
            "assert config.settings.debug is True; "
            "assert config.cookie_transport.cookie_secure "
            "is False; "
            "print('debug-cookie-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "debug-cookie-ok" in result.stdout