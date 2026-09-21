from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.engine import make_url

from backend.cli import cleanup_explicit_catalog as cli


def _target(
    manga_id: int = 1,
    *,
    cover: bool = True,
) -> cli.ExplicitCatalogTarget:
    cover_key = (
        f"covers/mangaupdates/{manga_id}/hash.jpg"
        if cover else None
    )
    return cli.ExplicitCatalogTarget(
        manga_id=manga_id,
        title=f"Title {manga_id}",
        matched_genres=("Hentai",),
        cover_url=(
            f"https://mangarecon.com/{cover_key}"
            if cover_key else None
        ),
        cover_key=cover_key,
    )


@pytest.mark.asyncio
async def test_select_targets_uses_only_explicit_genres() -> None:
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        manga_id=7,
                        title="Explicit",
                        cover_image_url=(
                            "https://mangarecon.com/covers/"
                            "mangaupdates/7/hash.jpg"
                        ),
                    )
                ]
            ),
            SimpleNamespace(all=lambda: [(7, "Hentai"), (7, "Smut")]),
        ]
    )

    targets = await cli.select_explicit_catalog_targets(
        db,
        public_base_url="https://mangarecon.com",
        lock=True,
    )

    assert targets == (
        cli.ExplicitCatalogTarget(
            manga_id=7,
            title="Explicit",
            matched_genres=("Hentai", "Smut"),
            cover_url=(
                "https://mangarecon.com/covers/mangaupdates/7/hash.jpg"
            ),
            cover_key="covers/mangaupdates/7/hash.jpg",
        ),
    )
    first_sql = str(db.execute.await_args_list[0].args[0])
    assert "FOR UPDATE" in first_sql
    assert "adult" not in first_sql.casefold()


@pytest.mark.asyncio
async def test_user_link_counts_are_batched() -> None:
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalar_one=lambda: 2),
            SimpleNamespace(scalar_one=lambda: 3),
            SimpleNamespace(scalar_one=lambda: 5),
            SimpleNamespace(scalar_one=lambda: 7),
        ]
    )

    counts = await cli.count_user_links(db, tuple(range(1, 502)))

    assert counts == cli.UserLinkCounts(ratings=7, collection_links=10)
    assert db.execute.await_count == 4


def test_manifest_round_trip_and_database_guard(tmp_path) -> None:
    path = tmp_path / "cleanup.json"
    database_url = make_url(
        "postgresql+asyncpg://reader:secret@db.example.test/mangarecon"
    )
    targets = (_target(),)

    cli.write_manifest(
        path,
        database_url=database_url,
        bucket_name="covers-bucket",
        public_base_url="https://mangarecon.com",
        targets=targets,
    )

    assert cli.load_manifest(
        path,
        database_url=database_url,
        bucket_name="covers-bucket",
        public_base_url="https://mangarecon.com",
    ) == targets

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["policy_genres"] == [
        "Hentai", "Lolicon", "Shotacon", "Smut"
    ]

    with pytest.raises(
        cli.ExplicitCatalogCleanupError,
        match="different database target",
    ):
        cli.load_manifest(
            path,
            database_url=make_url(
                "postgresql+asyncpg://writer:secret@other.test/mangarecon"
            ),
            bucket_name="covers-bucket",
            public_base_url="https://mangarecon.com",
        )

    with pytest.raises(
        cli.ExplicitCatalogCleanupError,
        match="different cover storage",
    ):
        cli.load_manifest(
            path,
            database_url=database_url,
            bucket_name="wrong-bucket",
            public_base_url="https://mangarecon.com",
        )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://mangarecon.com/covers/mangaupdates/1/hash.jpg",
            "covers/mangaupdates/1/hash.jpg",
        ),
        ("https://example.com/covers/mangaupdates/1/hash.jpg", None),
        ("https://mangarecon.com/covers/other/1/hash.jpg", None),
        (
            "https://mangarecon.com/covers/mangaupdates/../secret",
            None,
        ),
    ],
)
def test_cover_key_accepts_only_managed_urls(
    url: str,
    expected: str | None,
) -> None:
    assert cli._cover_key(url, "https://mangarecon.com") == expected


def test_asset_cleanup_batches_deletes_and_invalidates_all_cover_paths() -> None:
    targets = tuple(_target(manga_id) for manga_id in range(1, 1_002))
    s3_client = MagicMock()
    s3_client.delete_objects.side_effect = [{}, {}]
    cloudfront_client = MagicMock()
    cloudfront_client.create_invalidation.return_value = {
        "Invalidation": {"Id": "INV123"}
    }

    deleted, invalidation_id = cli.delete_manifest_assets(
        targets,
        bucket_name="covers-bucket",
        cloudfront_distribution_id="DIST123",
        s3_client=s3_client,
        cloudfront_client=cloudfront_client,
    )

    assert deleted == 1_001
    assert invalidation_id == "INV123"
    assert s3_client.delete_objects.call_count == 2
    assert len(
        s3_client.delete_objects.call_args_list[0]
        .kwargs["Delete"]["Objects"]
    ) == 1_000
    assert len(
        s3_client.delete_objects.call_args_list[1]
        .kwargs["Delete"]["Objects"]
    ) == 1
    cloudfront_client.create_invalidation.assert_called_once()
    invalidation = cloudfront_client.create_invalidation.call_args.kwargs
    assert invalidation["DistributionId"] == "DIST123"
    assert invalidation["InvalidationBatch"]["Paths"] == {
        "Quantity": 1,
        "Items": ["/covers/*"],
    }


@pytest.mark.asyncio
async def test_delete_revalidates_and_commits_exact_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = (_target(),)
    catalog_db = MagicMock()
    catalog_db.execute = AsyncMock(
        return_value=SimpleNamespace(scalars=lambda: [1])
    )
    catalog_db.commit = AsyncMock()
    catalog_db.rollback = AsyncMock()
    user_db = MagicMock()

    async def manga_provider():
        yield catalog_db

    async def user_provider():
        yield user_db

    monkeypatch.setattr(cli, "get_manga_write_db", manga_provider)
    monkeypatch.setattr(cli, "get_user_read_db", user_provider)
    monkeypatch.setattr(
        cli,
        "select_explicit_catalog_targets",
        AsyncMock(return_value=targets),
    )
    monkeypatch.setattr(
        cli,
        "count_user_links",
        AsyncMock(return_value=cli.UserLinkCounts(0, 0)),
    )
    dispose = AsyncMock()
    monkeypatch.setattr(cli, "dispose_database_engines", dispose)

    links = await cli.delete_manifest_targets(
        targets,
        public_base_url="https://mangarecon.com",
    )

    assert links == cli.UserLinkCounts(0, 0)
    catalog_db.commit.assert_awaited_once()
    catalog_db.rollback.assert_not_awaited()
    dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_refuses_any_user_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = (_target(),)
    catalog_db = MagicMock()
    catalog_db.execute = AsyncMock()
    catalog_db.commit = AsyncMock()
    catalog_db.rollback = AsyncMock()
    user_db = MagicMock()

    async def manga_provider():
        yield catalog_db

    async def user_provider():
        yield user_db

    monkeypatch.setattr(cli, "get_manga_write_db", manga_provider)
    monkeypatch.setattr(cli, "get_user_read_db", user_provider)
    monkeypatch.setattr(
        cli,
        "select_explicit_catalog_targets",
        AsyncMock(return_value=targets),
    )
    monkeypatch.setattr(
        cli,
        "count_user_links",
        AsyncMock(return_value=cli.UserLinkCounts(1, 0)),
    )
    monkeypatch.setattr(
        cli,
        "dispose_database_engines",
        AsyncMock(),
    )

    with pytest.raises(
        cli.ExplicitCatalogCleanupError,
        match="targets now have ratings=1",
    ):
        await cli.delete_manifest_targets(
            targets,
            public_base_url="https://mangarecon.com",
        )

    catalog_db.execute.assert_not_awaited()
    catalog_db.commit.assert_not_awaited()
    catalog_db.rollback.assert_awaited_once()
