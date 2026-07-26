from sqlalchemy import Engine, inspect


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
