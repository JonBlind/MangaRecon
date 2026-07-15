import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.routes import metadata_routes


def handler(function):
    return inspect.unwrap(function)


class FakeScalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeResult:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return FakeScalars(self.values)


@pytest.mark.parametrize(
    (
        "route_name",
        "model_name",
        "id_name",
        "value_id",
        "value_name",
        "expected_message",
    ),
    [
        (
            "get_all_genres",
            "Genre",
            "genre_id",
            1,
            "Action",
            "Genres successfully retrieved",
        ),
        (
            "get_all_tags",
            "Tag",
            "tag_id",
            2,
            "Psychological",
            "Tags successfully retrieved",
        ),
        (
            "get_all_demographics",
            "Demographic",
            "demographic_id",
            3,
            "Seinen",
            "Demographics successfully retrieved",
        ),
    ],
)
@pytest.mark.asyncio
async def test_metadata_routes_return_validated_items(
    route_name,
    model_name,
    id_name,
    value_id,
    value_name,
    expected_message,
):
    request = MagicMock()
    db = MagicMock()

    name_field = {
        "Genre": "genre_name",
        "Tag": "tag_name",
        "Demographic": "demographic_name",
    }[model_name]

    row = SimpleNamespace(
        **{
            id_name: value_id,
            name_field: value_name,
        }
    )

    db.execute = AsyncMock(
        return_value=FakeResult([row])
    )

    result = await handler(
        getattr(metadata_routes, route_name)
    )(
        request=request,
        db=db,
    )

    assert result["status"] == "success"
    assert result["message"] == expected_message
    assert result["data"]["total_results"] == 1
    assert len(result["data"]["items"]) == 1

    item = result["data"]["items"][0]
    assert getattr(item, id_name) == value_id
    assert getattr(item, name_field) == value_name

    statement = db.execute.await_args.args[0]
    sql = str(statement)

    assert "ORDER BY" in sql
    assert id_name in sql


@pytest.mark.parametrize(
    (
        "route_name",
        "expected_log_fragment",
    ),
    [
        (
            "get_all_genres",
            "Failed to get all genres",
        ),
        (
            "get_all_tags",
            "Failed to get all tags",
        ),
        (
            "get_all_demographics",
            "Failed to get all demographics",
        ),
    ],
)
@pytest.mark.asyncio
async def test_metadata_routes_log_and_reraise_errors(
    monkeypatch,
    route_name,
    expected_log_fragment,
):
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=RuntimeError("metadata failed")
    )

    log_error = MagicMock()
    monkeypatch.setattr(
        metadata_routes.logger,
        "error",
        log_error,
    )

    with pytest.raises(
        RuntimeError,
        match="metadata failed",
    ):
        await handler(
            getattr(metadata_routes, route_name)
        )(
            request=MagicMock(),
            db=db,
        )

    log_error.assert_called_once()
    assert expected_log_fragment in (
        log_error.call_args.args[0]
    )
    assert (
        log_error.call_args.kwargs["exc_info"]
        is True
    )