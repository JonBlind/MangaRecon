import pytest
from sqlalchemy.sql.elements import UnaryExpression

from backend.utils.ordering import (
    get_ordering_clause,
    MANGA_SORT_OPTIONS,
)


@pytest.mark.parametrize("field", list(MANGA_SORT_OPTIONS.keys()))
def test_get_ordering_clause_returns_asc(field: str):
    clause = get_ordering_clause(field, "asc")

    # ORDER BY expression
    assert isinstance(clause, UnaryExpression)

    # Ascending direction
    assert clause.modifier.__name__ == "asc_op"

    # Correct column (compare by column name)
    assert getattr(clause.element, "name", None) == field


@pytest.mark.parametrize("field", list(MANGA_SORT_OPTIONS.keys()))
def test_get_ordering_clause_returns_desc(field: str):
    clause = get_ordering_clause(field, "desc")

    assert isinstance(clause, UnaryExpression)
    assert clause.modifier.__name__ == "desc_op"
    assert getattr(clause.element, "name", None) == field


def test_get_ordering_clause_invalid_field():
    with pytest.raises(ValueError, match="Unsupported sort field"):
        get_ordering_clause("invalid_field", "asc")


def test_get_ordering_clause_invalid_direction():
    with pytest.raises(ValueError, match="Unsupported sort direction"):
        get_ordering_clause("title", "up") 