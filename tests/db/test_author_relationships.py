from sqlalchemy import inspect

from backend.db.models.creator import Creator
from backend.db.models.manga_creator import MangaCreator
from backend.db.models.manga import Manga


def test_manga_creator_is_the_only_creator_storage_path():
    assert "author_id" not in Manga.__table__.columns
    assert {
        column.name
        for column in MangaCreator.__table__.primary_key.columns
    } == {
        "manga_id",
        "creator_id",
        "role",
    }


def test_creator_and_manga_use_manga_creator_association_model():
    manga_relationship_targets = {
        relationship.mapper.class_
        for relationship in inspect(Manga).relationships
    }
    creator_relationship_targets = {
        relationship.mapper.class_
        for relationship in inspect(Creator).relationships
    }

    assert MangaCreator in manga_relationship_targets
    assert MangaCreator in creator_relationship_targets
