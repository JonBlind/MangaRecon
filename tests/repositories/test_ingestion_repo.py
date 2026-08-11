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
