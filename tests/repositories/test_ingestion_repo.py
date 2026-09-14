from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.repositories import ingestion_repo


@pytest.mark.asyncio
async def test_find_existing_catalog_external_ids_returns_empty_without_query(
) -> None:
    db = MagicMock()
    db.scalars_all = AsyncMock()

    result = await ingestion_repo.find_existing_catalog_external_ids(
        db,
        provider_key="mangaupdates",
        external_ids=(),
    )

    assert result == set()
    db.scalars_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_find_uncached_catalog_covers_builds_bounded_query(
) -> None:
    query_result = MagicMock()
    query_result.all.return_value = [
        SimpleNamespace(
            manga_id=7,
            external_id="42",
            source_url=(
                "https://cdn.mangaupdates.com/image/i42.png"
            ),
        )
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=query_result)

    result = await ingestion_repo.find_uncached_catalog_covers(
        db,
        provider_key="mangaupdates",
        public_base_url="https://mangarecon.com/",
        limit=25,
    )

    assert result == (
        ingestion_repo.CatalogCoverCandidate(
            manga_id=7,
            external_id="42",
            source_url=(
                "https://cdn.mangaupdates.com/image/i42.png"
            ),
        ),
    )
    statement = db.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(compiled)
    assert "JOIN manga_external_source" in sql
    assert "JOIN data_provider" in sql
    assert "manga.cover_image_url IS NOT NULL" in sql
    assert "btrim(manga.cover_image_url)" in sql
    assert "manga.cover_image_url NOT LIKE" in sql
    assert "ORDER BY manga.manga_id" in sql
    assert "mangaupdates" in compiled.params.values()
    assert "https://mangarecon.com/covers/%" in (
        compiled.params.values()
    )
    assert 25 in compiled.params.values()


@pytest.mark.parametrize(
    ("limit", "public_base_url", "message"),
    [
        (0, "https://mangarecon.com", "limit"),
        (None, "   ", "public_base_url"),
    ],
)
@pytest.mark.asyncio
async def test_find_uncached_catalog_covers_rejects_invalid_input(
    limit: int | None,
    public_base_url: str,
    message: str,
) -> None:
    db = MagicMock()
    db.execute = AsyncMock()

    with pytest.raises(ValueError, match=message):
        await ingestion_repo.find_uncached_catalog_covers(
            db,
            provider_key="mangaupdates",
            public_base_url=public_base_url,
            limit=limit,
        )

    db.execute.assert_not_awaited()


@pytest.mark.parametrize(
    ("updated_id", "expected"),
    [(7, True), (None, False)],
)
@pytest.mark.asyncio
async def test_replace_catalog_cover_url_is_concurrency_guarded(
    updated_id: int | None,
    expected: bool,
) -> None:
    db = MagicMock()
    db.scalar_one_or_none = AsyncMock(return_value=updated_id)

    result = await ingestion_repo.replace_catalog_cover_url(
        db,
        manga_id=7,
        expected_source_url=(
            "https://cdn.mangaupdates.com/image/i42.png"
        ),
        stored_url=(
            "https://mangarecon.com/covers/mangaupdates/42/hash.png"
        ),
    )

    assert result is expected
    statement = db.scalar_one_or_none.await_args.args[0]
    compiled = statement.compile()
    sql = str(compiled)
    assert "UPDATE manga SET cover_image_url=" in sql
    assert "manga.manga_id =" in sql
    assert "manga.cover_image_url =" in sql
    assert "RETURNING manga.manga_id" in sql
    assert 7 in compiled.params.values()


@pytest.mark.parametrize(
    ("updated_id", "expected"),
    [(7, True), (None, False)],
)
@pytest.mark.asyncio
async def test_clear_catalog_cover_url_is_concurrency_guarded(
    updated_id: int | None,
    expected: bool,
) -> None:
    db = MagicMock()
    db.scalar_one_or_none = AsyncMock(return_value=updated_id)

    result = await ingestion_repo.clear_catalog_cover_url(
        db,
        manga_id=7,
        expected_source_url=(
            "https://cdn.mangaupdates.com/image/i42.png"
        ),
    )

    assert result is expected
    statement = db.scalar_one_or_none.await_args.args[0]
    compiled = statement.compile()
    sql = str(compiled)
    assert "UPDATE manga SET cover_image_url=" in sql
    assert "manga.manga_id =" in sql
    assert "manga.cover_image_url =" in sql
    assert "RETURNING manga.manga_id" in sql
    assert 7 in compiled.params.values()
    assert None in compiled.params.values()


@pytest.mark.asyncio
async def test_find_existing_catalog_external_ids_deduplicates_and_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = MagicMock()
    db.scalars_all = AsyncMock(
        side_effect=[
            ["10"],
            ["30"],
        ]
    )
    monkeypatch.setattr(
        ingestion_repo,
        "_EXTERNAL_ID_LOOKUP_BATCH_SIZE",
        2,
    )

    result = await ingestion_repo.find_existing_catalog_external_ids(
        db,
        provider_key="mangaupdates",
        external_ids=("10", "20", "10", "30"),
    )

    assert result == {"10", "30"}
    assert db.scalars_all.await_count == 2

    statements = [
        call.args[0]
        for call in db.scalars_all.await_args_list
    ]
    compiled_statements = [
        statement.compile()
        for statement in statements
    ]

    for statement in statements:
        sql = str(statement)
        assert "manga_external_source.external_id" in sql
        assert "JOIN data_provider" in sql
        assert "data_provider.provider_key" in sql

    bound_batches = [
        next(
            value
            for value in compiled.params.values()
            if isinstance(value, (list, tuple))
        )
        for compiled in compiled_statements
    ]
    assert bound_batches == [["10", "20"], ["30"]]

    for compiled in compiled_statements:
        assert "mangaupdates" in compiled.params.values()


@pytest.mark.asyncio
async def test_find_missing_cover_external_ids_builds_bounded_provider_query(
) -> None:
    db = MagicMock()
    db.scalars_all = AsyncMock(return_value=["10", "20"])

    result = await ingestion_repo.find_missing_cover_external_ids(
        db,
        provider_key="mangaupdates",
        limit=2,
    )

    assert result == ("10", "20")
    db.scalars_all.assert_awaited_once()

    statement = db.scalars_all.await_args.args[0]
    compiled = statement.compile()
    sql = str(compiled)

    assert "manga_external_source.external_id" in sql
    assert "JOIN data_provider" in sql
    assert "JOIN manga" in sql
    assert "data_provider.provider_key" in sql
    assert "manga.cover_image_url IS NULL" in sql
    assert "btrim(manga.cover_image_url)" in sql
    assert "ORDER BY manga.manga_id" in sql
    assert "mangaupdates" in compiled.params.values()
    assert 2 in compiled.params.values()


@pytest.mark.asyncio
async def test_find_missing_cover_external_ids_rejects_invalid_limit(
) -> None:
    db = MagicMock()
    db.scalars_all = AsyncMock()

    with pytest.raises(
        ValueError,
        match="limit must be greater than zero",
    ):
        await ingestion_repo.find_missing_cover_external_ids(
            db,
            provider_key="mangaupdates",
            limit=0,
        )

    db.scalars_all.assert_not_awaited()
