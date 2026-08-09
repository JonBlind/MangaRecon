from __future__ import annotations

import json
from unittest.mock import AsyncMock

from backend.cli import discover_mangaupdates as cli
from backend.cli.ingest_mangaupdates import _load_series_ids
from backend.ingestion.mangaupdates_discovery import (
    MangaUpdatesDiscoveredSeries,
    MangaUpdatesDiscoveryRequest,
    MangaUpdatesDiscoveryState,
)


def discovered(
    series_id: int,
    title: str,
) -> MangaUpdatesDiscoveredSeries:
    return MangaUpdatesDiscoveredSeries(
        series_id=series_id,
        title=title,
        media_type="Manga",
        year="2020",
        source_url=(
            "https://www.mangaupdates.com/series/"
            f"{series_id}"
        ),
        source_updated_at="2026-08-01T12:00:00Z",
    )


def complete_state(
    state: MangaUpdatesDiscoveryState,
    *,
    items: list[MangaUpdatesDiscoveredSeries],
) -> MangaUpdatesDiscoveryState:
    state.series = items
    state.status = "complete"
    state.next_page = None
    state.pages_completed = 1
    state.reported_total_hits = len(items)
    state.last_error = None
    return state


def test_main_writes_review_manifest_and_ingestion_compatible_ids(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    manifest = tmp_path / "pilot.json"
    ids_output = tmp_path / "pilot.txt"

    async def fake_run(state, **options):
        assert options["checkpoint_path"] == manifest
        result = complete_state(
            state,
            items=[
                discovered(10, "Ten"),
                discovered(20, "Twenty"),
            ],
        )
        cli._write_manifest(manifest, result)
        return result

    monkeypatch.setattr(cli, "run_discovery", fake_run)

    exit_code = cli.main(
        [
            "--manifest",
            str(manifest),
            "--ids-output",
            str(ids_output),
            "--limit",
            "2",
            "--type",
            "Manga",
            "--exclude-genre",
            "Hentai",
        ]
    )

    assert exit_code == 0
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert payload["series_count"] == 2
    assert payload["request"]["series_types"] == ["Manga"]
    assert payload["request"]["exclude_genres"] == ["Hentai"]
    assert [item["title"] for item in payload["series"]] == [
        "Ten",
        "Twenty",
    ]
    assert _load_series_ids(ids_output) == [10, 20]
    assert "Discovery complete: series=2" in capsys.readouterr().out


def test_dry_run_fetches_without_writing_files(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    manifest = tmp_path / "dry-run.json"
    ids_output = tmp_path / "dry-run.txt"

    async def fake_run(state, **options):
        assert options["checkpoint_path"] is None
        return complete_state(
            state,
            items=[discovered(10, "Ten")],
        )

    monkeypatch.setattr(cli, "run_discovery", fake_run)

    exit_code = cli.main(
        [
            "--dry-run",
            "--manifest",
            str(manifest),
            "--ids-output",
            str(ids_output),
            "--limit",
            "1",
        ]
    )

    assert exit_code == 0
    assert not manifest.exists()
    assert not ids_output.exists()
    assert capsys.readouterr().out == (
        "10\tTen\n"
        "Dry-run summary: discovered=1; pages=1; "
        "skipped_malformed=0.\n"
    )


def test_resume_uses_saved_request_and_next_page(
    monkeypatch,
    tmp_path,
) -> None:
    manifest = tmp_path / "resume.json"
    ids_output = tmp_path / "resume.txt"
    saved = MangaUpdatesDiscoveryState(
        request=MangaUpdatesDiscoveryRequest(
            limit=2,
            per_page=1,
            series_types=("Manga",),
            order_by="title",
        ),
        status="failed",
        next_page=2,
        pages_completed=1,
        reported_total_hits=2,
        series=[discovered(10, "Ten")],
        last_error="temporary failure",
    )
    cli._write_manifest(manifest, saved)

    async def fake_run(state, **options):
        assert state.next_page == 2
        assert state.request == saved.request
        state.series.append(discovered(20, "Twenty"))
        state.status = "complete"
        state.next_page = None
        state.pages_completed = 2
        state.last_error = None
        cli._write_manifest(manifest, state)
        return state

    monkeypatch.setattr(cli, "run_discovery", fake_run)

    exit_code = cli.main(
        [
            "--resume",
            "--manifest",
            str(manifest),
            "--ids-output",
            str(ids_output),
        ]
    )

    assert exit_code == 0
    assert _load_series_ids(ids_output) == [10, 20]
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["pages_completed"] == 2
    assert payload["status"] == "complete"


def test_resume_rejects_changed_filter_partition(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    manifest = tmp_path / "resume.json"
    saved = MangaUpdatesDiscoveryState(
        request=MangaUpdatesDiscoveryRequest(
            series_types=("Manga",)
        ),
        status="failed",
        next_page=2,
        pages_completed=1,
        reported_total_hits=200,
        last_error="temporary failure",
    )
    cli._write_manifest(manifest, saved)
    run = AsyncMock()
    monkeypatch.setattr(cli, "run_discovery", run)

    exit_code = cli.main(
        [
            "--resume",
            "--manifest",
            str(manifest),
            "--type",
            "Manhwa",
        ]
    )

    assert exit_code == 1
    assert "Resume options do not match" in capsys.readouterr().err
    run.assert_not_awaited()


def test_resume_of_complete_manifest_preserves_existing_id_list(
    monkeypatch,
    tmp_path,
) -> None:
    manifest = tmp_path / "complete.json"
    ids_output = tmp_path / "complete.txt"
    state = complete_state(
        MangaUpdatesDiscoveryState(
            request=MangaUpdatesDiscoveryRequest(limit=1)
        ),
        items=[discovered(10, "Ten")],
    )
    cli._write_manifest(manifest, state)
    existing_contents = (
        "# already reviewed\n"
        "10\n"
    )
    ids_output.write_text(
        existing_contents,
        encoding="utf-8",
    )
    run = AsyncMock()
    monkeypatch.setattr(cli, "run_discovery", run)

    exit_code = cli.main(
        [
            "--resume",
            "--manifest",
            str(manifest),
            "--ids-output",
            str(ids_output),
        ]
    )

    assert exit_code == 0
    assert ids_output.read_text(encoding="utf-8") == (
        existing_contents
    )
    run.assert_not_awaited()


def test_main_refuses_to_overwrite_existing_manifest(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    manifest = tmp_path / "existing.json"
    manifest.write_text("keep me", encoding="utf-8")
    run = AsyncMock()
    monkeypatch.setattr(cli, "run_discovery", run)

    exit_code = cli.main(
        ["--manifest", str(manifest)]
    )

    assert exit_code == 1
    assert manifest.read_text(encoding="utf-8") == "keep me"
    assert "Manifest already exists" in capsys.readouterr().err
    run.assert_not_awaited()
