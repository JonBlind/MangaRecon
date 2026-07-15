import pytest
from sqlalchemy.dialects import postgresql

from backend.utils.ordering import get_ordering_clause


@pytest.mark.parametrize(
    ("field", "direction", "expected_sql"),
    [
        ("title", "asc", "manga.title ASC"),
        ("title", "desc", "manga.title DESC"),
        ("published_date", "asc", "manga.published_date ASC"),
        ("published_date", "desc", "manga.published_date DESC"),
        (
            "external_average_rating",
            "asc",
            "manga.external_average_rating ASC",
        ),
        (
            "external_average_rating",
            "desc",
            "manga.external_average_rating DESC",
        ),
    ],
)
def test_get_ordering_clause_returns_expected_sql(
    field,
    direction,
    expected_sql,
):
    clause = get_ordering_clause(
        field=field,
        direction=direction,
    )

    compiled = str(
        clause.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert compiled == expected_sql


@pytest.mark.parametrize(
    "field",
    [
        "",
        "score",
        "author",
        "manga_id",
        "TITLE",
        None,
    ],
)
def test_get_ordering_clause_rejects_unsupported_field(
    field,
):
    with pytest.raises(
        ValueError,
        match=f"Unsupported sort field: {field}",
    ):
        get_ordering_clause(
            field=field,
            direction="asc",
        )


@pytest.mark.parametrize(
    "direction",
    [
        "",
        "ascending",
        "descending",
        "ASC",
        "DESC",
        None,
    ],
)
def test_get_ordering_clause_rejects_unsupported_direction(
    direction,
):
    with pytest.raises(
        ValueError,
        match=f"Unsupported sort direction: {direction}",
    ):
        get_ordering_clause(
            field="title",
            direction=direction,
        )