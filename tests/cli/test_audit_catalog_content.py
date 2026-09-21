from __future__ import annotations

import csv
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.cli import audit_catalog_content as cli
from backend.dependencies import settings as database_settings


@pytest.mark.asyncio
async def test_inventory_counts_user_links_once_per_title() -> None:
    catalog_db = MagicMock()
    user_db = MagicMock()
    query_result = MagicMock()
    query_result.all.return_value = [
        SimpleNamespace(
            manga_id=10, title="Explicit",
            cover_image_url="https://mangarecon.com/covers/10.png",
            is_adult_content=True, genre_name="Hentai",
        ),
        SimpleNamespace(
            manga_id=10, title="Explicit",
            cover_image_url="https://mangarecon.com/covers/10.png",
            is_adult_content=True, genre_name="Smut",
        ),
        SimpleNamespace(
            manga_id=20, title="Mature work", cover_image_url=None,
            is_adult_content=True, genre_name="Adult",
        ),
        SimpleNamespace(
            manga_id=30, title="Flagged without genre", cover_image_url=None,
            is_adult_content=True, genre_name=None,
        ),
    ]
    catalog_db.execute = AsyncMock(return_value=query_result)
    user_db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(all=lambda: [(10, 3), (20, 1)]),
            SimpleNamespace(all=lambda: [(10, 2), (30, 1)]),
        ]
    )

    items = await cli.inventory_catalog_content(catalog_db, user_db)

    assert [(item.manga_id, item.category, item.ratings, item.collection_links)
            for item in items] == [
        (10, "explicit", 3, 2),
        (20, "adult_opt_in", 1, 0),
        (30, "classification_mismatch", 0, 1),
    ]
    assert items[0].matched_genres == ("Hentai", "Smut")
    catalog_sql = str(catalog_db.execute.await_args.args[0])
    assert "rating" not in catalog_sql
    assert "manga_collection" not in catalog_sql
    user_sql = [str(call.args[0]) for call in user_db.execute.await_args_list]
    assert len(user_sql) == 2
    assert "rating.manga_id" in user_sql[0]
    assert "manga_collection.manga_id" in user_sql[1]
    assert "manga." not in " ".join(user_sql)


@pytest.mark.asyncio
async def test_inventory_batches_user_link_counts_for_large_catalog() -> None:
    catalog_db = MagicMock()
    catalog_db.execute = AsyncMock(
        return_value=SimpleNamespace(
            all=lambda: [
                SimpleNamespace(
                    manga_id=manga_id,
                    title=f"Title {manga_id}",
                    cover_image_url=None,
                    is_adult_content=True,
                    genre_name="Adult",
                )
                for manga_id in range(1, 502)
            ]
        )
    )
    user_db = MagicMock()
    user_db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(all=lambda: [(1, 2)]),
            SimpleNamespace(all=lambda: []),
            SimpleNamespace(all=lambda: [(501, 3)]),
            SimpleNamespace(all=lambda: [(501, 4)]),
        ]
    )

    items = await cli.inventory_catalog_content(catalog_db, user_db)

    assert len(items) == 501
    assert (items[0].ratings, items[0].collection_links) == (2, 0)
    assert (items[-1].ratings, items[-1].collection_links) == (3, 4)
    assert user_db.execute.await_count == 4


def test_csv_output_quotes_provider_formula_titles(tmp_path) -> None:
    item = cli.CatalogContentImpact(
        manga_id=1, title="=DANGEROUS()", category="explicit",
        matched_genres=("Hentai",), ratings=2, collection_links=1,
        cover_url="https://mangarecon.com/covers/a.png", classified_adult=True,
    )
    path = tmp_path / "inventory.csv"

    cli.write_inventory_csv(path, (item,))

    with path.open(newline="", encoding="utf-8-sig") as source:
        rows = list(csv.DictReader(source))

    assert len(rows) == 1
    assert rows[0]["title"] == "'=DANGEROUS()"
    assert rows[0]["ratings"] == "2"
    assert rows[0]["hosted_cover"] == "True"


@pytest.mark.asyncio
async def test_tag_audit_counts_safe_and_adult_links() -> None:
    db = MagicMock()
    result = MagicMock()
    result.all.return_value = [
        SimpleNamespace(
            tag_id=1, tag_name="Sample", safe_titles=2, adult_titles=4
        ),
    ]
    db.execute = AsyncMock(return_value=result)

    tags = await cli.inventory_tag_visibility(db)

    assert tags == (cli.CatalogTagImpact(1, "Sample", 2, 4),)
    stmt = str(db.execute.await_args.args[0])
    assert "is_adult_content IS false" in stmt
    assert "is_adult_content IS true" in stmt


def test_main_uses_database_settings_and_runs_read_only_audit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.database_settings is database_settings
    monkeypatch.setattr(
        cli.database_settings,
        "manga_read",
        "postgresql+asyncpg://reader:secret@db.example.test/manga",
    )
    monkeypatch.setattr(
        cli.database_settings,
        "user_read",
        "postgresql+asyncpg://user_reader:secret@db.example.test/manga",
    )
    catalog_db, user_db = object(), object()

    async def fake_catalog_read_db():
        yield catalog_db

    async def fake_user_read_db():
        yield user_db

    inventory = AsyncMock(return_value=())
    dispose = AsyncMock()
    monkeypatch.setattr(cli, "get_manga_read_db", fake_catalog_read_db)
    monkeypatch.setattr(cli, "get_user_read_db", fake_user_read_db)
    monkeypatch.setattr(cli, "inventory_catalog_content", inventory)
    monkeypatch.setattr(cli, "dispose_database_engines", dispose)

    assert cli.main([]) == 0
    stdout = capsys.readouterr().out
    assert (
        "host=db.example.test database=manga "
        "catalog_user=reader user_data_user=user_reader"
    ) in stdout
    assert "secret" not in stdout
    assert "Read-only inventory: no records or covers were changed." in stdout
    inventory.assert_awaited_once_with(catalog_db, user_db)
    dispose.assert_awaited_once()


def test_main_without_read_database_exits_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli.database_settings, "manga_read", None)

    assert cli.main([]) == 1
    assert "MangaReaderDB and UserReaderDB must both be configured." in capsys.readouterr().err


def test_main_rejects_different_database_targets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli.database_settings,
        "manga_read",
        "postgresql+asyncpg://reader:secret@localhost/mangarecon",
    )
    monkeypatch.setattr(
        cli.database_settings,
        "user_read",
        "postgresql+asyncpg://user_reader:secret@db.example.test/mangarecon",
    )

    assert cli.main([]) == 1
    assert "must target the same host, port, and database" in capsys.readouterr().err
