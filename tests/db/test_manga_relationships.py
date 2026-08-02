from sqlalchemy import inspect

from backend.db.models.manga import Manga


def test_manga_does_not_implicitly_load_collection_links():
    relationship = inspect(Manga).relationships[
        "manga_collection_links"
    ]

    assert relationship.lazy == "raise"
    assert relationship.passive_deletes is True