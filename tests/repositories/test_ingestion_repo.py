from __future__ import annotations

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
