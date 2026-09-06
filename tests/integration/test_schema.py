import pytest
from sqlalchemy import Engine, inspect


@pytest.mark.parametrize(
    ("table_name", "related_id_column"),
    [
        ("manga_genre", "genre_id"),
        ("manga_tag", "tag_id"),
        ("manga_demographic", "demographic_id"),
    ],
)
def test_metadata_association_schema_matches_many_to_many_models(
    manga_write_engine: Engine,
    table_name: str,
    related_id_column: str,
) -> None:
    inspector = inspect(manga_write_engine)

    columns = {
        column["name"]: column
        for column in inspector.get_columns(table_name)
    }
    assert columns["manga_id"]["nullable"] is False
    assert columns[related_id_column]["nullable"] is False

    primary_key = inspector.get_pk_constraint(table_name)
    assert primary_key["constrained_columns"] == [
        "manga_id",
        related_id_column,
    ]


def test_creator_schema_matches_role_aware_many_to_many_model(
    manga_write_engine: Engine,
) -> None:
    inspector = inspect(manga_write_engine)

    manga_columns = {
        column["name"]: column
        for column in inspector.get_columns("manga")
    }
    assert "author_id" not in manga_columns

    manga_creator_columns = {
        column["name"]: column
        for column in inspector.get_columns("manga_creator")
    }
    assert manga_creator_columns["manga_id"]["nullable"] is False
    assert manga_creator_columns["creator_id"]["nullable"] is False
    assert manga_creator_columns["role"]["nullable"] is False

    primary_key = inspector.get_pk_constraint("manga_creator")
    assert set(primary_key["constrained_columns"]) == {
        "manga_id",
        "creator_id",
        "role",
    }

    indexes = inspector.get_indexes("manga_creator")
    assert any(
        index["column_names"] == ["creator_id"]
        for index in indexes
    )


def test_adult_content_columns_are_non_nullable_and_safe_by_default(
    manga_write_engine: Engine,
    user_write_engine: Engine,
) -> None:
    manga_columns = {
        column["name"]: column
        for column in inspect(manga_write_engine).get_columns("manga")
    }
    user_columns = {
        column["name"]: column
        for column in inspect(user_write_engine).get_columns("user")
    }

    assert manga_columns["is_adult_content"]["nullable"] is False
    assert "false" in str(
        manga_columns["is_adult_content"]["default"]
    ).casefold()
    assert user_columns["show_adult_content"]["nullable"] is False
    assert "false" in str(
        user_columns["show_adult_content"]["default"]
    ).casefold()
