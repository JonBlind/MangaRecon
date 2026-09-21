from __future__ import annotations

from unittest.mock import Mock

from backend.cli import run_scheduled_mangaupdates as cli


def test_main_loads_runtime_secrets_before_sync(
    monkeypatch,
) -> None:
    calls: list[str] = []
    sync_main = Mock(return_value=7)

    def load_secrets() -> None:
        calls.append("secrets")

    def load_sync():
        calls.append("sync_import")
        return sync_main

    monkeypatch.setattr(
        cli,
        "load_runtime_secrets",
        load_secrets,
    )
    monkeypatch.setattr(cli, "_load_sync_main", load_sync)

    assert cli.main(["--preview"]) == 7
    assert calls == ["secrets", "sync_import"]
    sync_main.assert_called_once_with(["--preview"])
