from pathlib import Path
import os
import subprocess
import sys
import hashlib

from backend.config import settings as settings_module


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_isolated_settings_import(
    *,
    tmp_path,
    environment: dict[str, str],
    code: str,
):
    """
    Import backend.config.settings in an isolated Python process.

    This lets us test import-time environment and dotenv behavior without
    mutating the settings module already imported by the main pytest process.
    """
    env = os.environ.copy()

    for name in (
        "MANGARECON_ENV",
        "FRONTEND_ORIGINS",
        "DEBUG",
        "ORIGIN_VERIFY_HEADER_NAME",
        "ORIGIN_VERIFY_SECRET_DIGEST",
        "TRUSTED_CLIENT_ADDRESS_HEADER_NAME",
        "MANGAUPDATES_BASE_URL",
        "MANGAUPDATES_TIMEOUT_SECONDS",
        "MANGAUPDATES_MIN_REQUEST_INTERVAL_SECONDS",
        "MANGAUPDATES_USER_AGENT",
        "REDIS_CONNECT_TIMEOUT_SECONDS",
        "REDIS_OPERATION_TIMEOUT_SECONDS",
        "REDIS_READY_TIMEOUT_SECONDS",
        "REDIS_MAX_CONNECTIONS",
    ):
        env.pop(name, None)
        env.pop(name.lower(), None)

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


def test_settings_module_has_resolved_environment():
    assert isinstance(settings_module.ENV, str)
    assert settings_module.ENV


def test_settings_contains_frontend_origins():
    assert isinstance(
        settings_module.settings.frontend_origins,
        str,
    )
    assert settings_module.settings.frontend_origins


def test_origin_verification_settings_load_as_secrets(
    tmp_path,
):
    header_name = "X-Test-Origin"
    secret_digest = hashlib.sha256(
        b"test-only-origin-value"
    ).hexdigest()
    client_header_name = "X-Test-Client-Address"

    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
            "FRONTEND_ORIGINS": (
                "https://mangarecon.example"
            ),
            "ORIGIN_VERIFY_HEADER_NAME": header_name,
            "ORIGIN_VERIFY_SECRET_DIGEST": secret_digest,
            "TRUSTED_CLIENT_ADDRESS_HEADER_NAME": (
                client_header_name
            ),
        },
        code=(
            "from backend.config import settings; "
            "configured = settings.settings; "
            "assert configured."
            "origin_verify_header_name."
            "get_secret_value() "
            f"== '{header_name}'; "
            "assert configured."
            "origin_verify_secret_digest."
            "get_secret_value() "
            f"== '{secret_digest}'; "
            "assert configured."
            "trusted_client_address_header_name."
            "get_secret_value() "
            f"== '{client_header_name}'; "
            f"assert '{header_name}' "
            "not in repr(configured); "
            f"assert '{secret_digest}' "
            "not in repr(configured); "
            f"assert '{client_header_name}' "
            "not in repr(configured); "
            "print('origin-settings-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "origin-settings-ok" in result.stdout


def test_origins_are_split_and_trimmed():
    expected = [
        origin.strip()
        for origin in (
            settings_module.settings.frontend_origins.split(",")
        )
        if origin.strip()
    ]

    assert settings_module.origins == expected


def test_origins_contain_no_empty_values():
    assert all(settings_module.origins)

    assert all(
        origin == origin.strip()
        for origin in settings_module.origins
    )


def test_test_environment_loads_env_test_with_override(
    tmp_path,
):
    env_test = tmp_path / ".env.test"
    env_test.write_text(
        "\n".join(
            [
                "FRONTEND_ORIGINS=http://env-test.example",
                "DEBUG=true",
            ]
        ),
        encoding="utf-8",
    )

    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "test",
            "FRONTEND_ORIGINS": (
                "http://existing.example"
            ),
            "DEBUG": "false",
        },
        code=(
            "from backend.config import settings; "
            "assert settings.ENV == 'test'; "
            "assert settings.settings.frontend_origins == "
            "'http://env-test.example'; "
            "assert settings.settings.debug is True; "
            "assert settings.origins == "
            "['http://env-test.example']; "
            "print('test-env-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert "test-env-ok" in result.stdout


def test_non_test_environment_loads_env_without_override(
    tmp_path,
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "FRONTEND_ORIGINS=http://dotenv.example",
                "DEBUG=true",
            ]
        ),
        encoding="utf-8",
    )

    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
            "FRONTEND_ORIGINS": (
                "http://existing.example"
            ),
            "DEBUG": "false",
        },
        code=(
            "from backend.config import settings; "
            "assert settings.ENV == 'prod'; "
            "assert settings.settings.frontend_origins == "
            "'http://existing.example'; "
            "assert settings.settings.debug is False; "
            "assert settings.origins == "
            "['http://existing.example']; "
            "print('prod-env-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert "prod-env-ok" in result.stdout


def test_settings_accept_lowercase_environment_names(
    tmp_path,
):
    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "dev",
            "frontend_origins": (
                "http://lowercase.example"
            ),
            "debug": "true",
        },
        code=(
            "from backend.config import settings; "
            "assert settings.settings.frontend_origins == "
            "'http://lowercase.example'; "
            "assert settings.settings.debug is True; "
            "assert settings.origins == "
            "['http://lowercase.example']; "
            "print('lowercase-settings-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert "lowercase-settings-ok" in result.stdout


def test_settings_accept_uppercase_environment_names(
    tmp_path,
):
    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "dev",
            "FRONTEND_ORIGINS": (
                "http://uppercase.example"
            ),
            "DEBUG": "true",
        },
        code=(
            "from backend.config import settings; "
            "assert settings.settings.frontend_origins == "
            "'http://uppercase.example'; "
            "assert settings.settings.debug is True; "
            "assert settings.origins == "
            "['http://uppercase.example']; "
            "print('uppercase-settings-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert "uppercase-settings-ok" in result.stdout


def test_environment_name_is_lowercased(
    tmp_path,
):
    env_test = tmp_path / ".env.test"
    env_test.write_text(
        "FRONTEND_ORIGINS=http://test.example\n",
        encoding="utf-8",
    )

    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "TEST",
        },
        code=(
            "from backend.config import settings; "
            "assert settings.ENV == 'test'; "
            "print('lowercase-env-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert "lowercase-env-ok" in result.stdout


def test_invalid_environment_name_fails_import(
    tmp_path,
):
    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "staging",
            "FRONTEND_ORIGINS": (
                "http://example.com"
            ),
        },
        code=(
            "from backend.config import settings"
        ),
    )

    assert result.returncode != 0
    assert (
        "MANGARECON_ENV must be one of: "
        "dev, test, prod"
    ) in result.stderr


def test_default_environment_is_prod(
    tmp_path,
):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FRONTEND_ORIGINS=http://prod.example\n",
        encoding="utf-8",
    )

    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={},
        code=(
            "from backend.config import settings; "
            "assert settings.ENV == 'prod'; "
            "assert settings.origins == "
            "['http://prod.example']; "
            "print('default-prod-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert "default-prod-ok" in result.stdout


def test_origins_remove_whitespace_and_empty_entries(
    tmp_path,
):
    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
            "FRONTEND_ORIGINS": (
                " http://one.example, ,"
                "http://two.example ,, "
            ),
        },
        code=(
            "from backend.config import settings; "
            "assert settings.origins == "
            "['http://one.example', "
            "'http://two.example']; "
            "print('origins-clean-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert "origins-clean-ok" in result.stdout


def test_debug_defaults_to_false(
    tmp_path,
):
    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
            "FRONTEND_ORIGINS": (
                "http://example.com"
            ),
        },
        code=(
            "from backend.config import settings; "
            "assert settings.settings.debug is False; "
            "print('debug-default-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    assert "debug-default-ok" in result.stdout


def test_production_environment_rejects_debug_mode(
    tmp_path,
):
    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
            "FRONTEND_ORIGINS": (
                "https://mangarecon.example"
            ),
            "DEBUG": "true",
        },
        code=(
            "from backend.config import settings"
        ),
    )

    assert result.returncode != 0
    assert (
        "MANGARECON_ENV=prod requires DEBUG=false."
        in result.stderr
    )


def test_import_fails_when_frontend_origins_is_missing(
    tmp_path,
):
    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
        },
        code=(
            "from backend.config import settings"
        ),
    )

    assert result.returncode != 0
    assert "FRONTEND_ORIGINS" in result.stderr


def test_redis_connection_settings_use_bounded_defaults(
    tmp_path,
):
    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
            "FRONTEND_ORIGINS": (
                "https://mangarecon.example"
            ),
        },
        code=(
            "from backend.config import settings; "
            "configured = settings.settings; "
            "assert configured.redis_connect_timeout_seconds == 3.0; "
            "assert configured.redis_operation_timeout_seconds == 3.0; "
            "assert configured.redis_ready_timeout_seconds == 5.0; "
            "assert configured.redis_max_connections == 4; "
            "print('redis-defaults-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "redis-defaults-ok" in result.stdout


def test_redis_connection_settings_accept_environment_overrides(
    tmp_path,
):
    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
            "FRONTEND_ORIGINS": (
                "https://mangarecon.example"
            ),
            "REDIS_CONNECT_TIMEOUT_SECONDS": "1.5",
            "REDIS_OPERATION_TIMEOUT_SECONDS": "2.5",
            "REDIS_READY_TIMEOUT_SECONDS": "4.5",
            "REDIS_MAX_CONNECTIONS": "7",
        },
        code=(
            "from backend.config import settings; "
            "configured = settings.settings; "
            "assert configured.redis_connect_timeout_seconds == 1.5; "
            "assert configured.redis_operation_timeout_seconds == 2.5; "
            "assert configured.redis_ready_timeout_seconds == 4.5; "
            "assert configured.redis_max_connections == 7; "
            "print('redis-overrides-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "redis-overrides-ok" in result.stdout

def test_mangaupdates_settings_use_safe_defaults(
    tmp_path,
):
    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
            "FRONTEND_ORIGINS": (
                "http://example.com"
            ),
        },
        code=(
            "from backend.config import settings; "
            "configured = settings.settings; "
            "assert configured.mangaupdates_base_url == "
            "'https://api.mangaupdates.com/v1'; "
            "assert configured."
            "mangaupdates_timeout_seconds == 10.0; "
            "assert configured."
            "mangaupdates_min_request_interval_seconds "
            "== 1.0; "
            "assert configured.mangaupdates_user_agent "
            "== 'MangaRecon/0.1'; "
            "print('mangaupdates-defaults-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert (
        "mangaupdates-defaults-ok"
        in result.stdout
    )


def test_mangaupdates_settings_accept_environment_overrides(
    tmp_path,
):
    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
            "FRONTEND_ORIGINS": (
                "http://example.com"
            ),
            "MANGAUPDATES_BASE_URL": (
                "https://configured.example/v1"
            ),
            "MANGAUPDATES_TIMEOUT_SECONDS": "7.5",
            (
                "MANGAUPDATES_"
                "MIN_REQUEST_INTERVAL_SECONDS"
            ): "0.25",
            "MANGAUPDATES_USER_AGENT": (
                "MangaRecon-Test/1.0"
            ),
        },
        code=(
            "from backend.config import settings; "
            "configured = settings.settings; "
            "assert configured.mangaupdates_base_url == "
            "'https://configured.example/v1'; "
            "assert configured."
            "mangaupdates_timeout_seconds == 7.5; "
            "assert configured."
            "mangaupdates_min_request_interval_seconds "
            "== 0.25; "
            "assert configured.mangaupdates_user_agent "
            "== 'MangaRecon-Test/1.0'; "
            "print('mangaupdates-overrides-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert (
        "mangaupdates-overrides-ok"
        in result.stdout
    )

def test_origin_verification_settings_load_as_secrets(
    tmp_path,
):
    header_name = "X-Test-Origin"
    secret_digest = hashlib.sha256(
        b"test-only-origin-value"
    ).hexdigest()
    client_header_name = "X-Test-Client-Address"

    result = run_isolated_settings_import(
        tmp_path=tmp_path,
        environment={
            "MANGARECON_ENV": "prod",
            "FRONTEND_ORIGINS": (
                "https://mangarecon.example"
            ),
            "ORIGIN_VERIFY_HEADER_NAME": header_name,
            "ORIGIN_VERIFY_SECRET_DIGEST": secret_digest,
            "TRUSTED_CLIENT_ADDRESS_HEADER_NAME": (
                client_header_name
            ),
        },
        code=(
            "from backend.config import settings; "
            "configured = settings.settings; "
            "assert configured."
            "origin_verify_header_name."
            "get_secret_value() "
            f"== '{header_name}'; "
            "assert configured."
            "origin_verify_secret_digest."
            "get_secret_value() "
            f"== '{secret_digest}'; "
            "assert configured."
            "trusted_client_address_header_name."
            "get_secret_value() "
            f"== '{client_header_name}'; "
            f"assert '{header_name}' "
            "not in repr(configured); "
            f"assert '{secret_digest}' "
            "not in repr(configured); "
            f"assert '{client_header_name}' "
            "not in repr(configured); "
            "print('origin-settings-ok')"
        ),
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "origin-settings-ok" in result.stdout
