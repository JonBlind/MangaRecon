"""remove test catalog seed

Revision ID: d8e3f0a6c1b4
Revises: a4d91c7e5b2f
Create Date: 2026-07-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8e3f0a6c1b4"
down_revision: Union[str, Sequence[str], None] = "a4d91c7e5b2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_CREATOR_NAME = "MR Seed Author"

MANGA_SEED = (
    {
        "title": "MR Seed — Crimson Blade",
        "description": (
            "A wandering swordsman gets pulled into a rebellion against "
            "a corrupt empire."
        ),
        "published_date": "2011-04-03",
        "external_average_rating": 8.4,
        "average_rating": None,
        "cover_image_url": (
            "https://placehold.co/400x600?text=Crimson+Blade"
        ),
        "genres": ("Action", "Drama"),
        "tags": ("Reincarnation",),
        "demographics": ("Shounen",),
    },
    {
        "title": "MR Seed — Clockwork Heart",
        "description": (
            "A quiet romance unfolds when time slips begin to rewrite "
            "two students’ lives."
        ),
        "published_date": "2016-09-12",
        "external_average_rating": 8.1,
        "average_rating": None,
        "cover_image_url": (
            "https://placehold.co/400x600?text=Clockwork+Heart"
        ),
        "genres": ("Romance", "Drama"),
        "tags": ("Time Travel",),
        "demographics": ("Shoujo",),
    },
    {
        "title": "MR Seed — Otherworld Hostel",
        "description": (
            "A broke college kid wakes up in a fantasy hostel for lost "
            "travelers from other worlds."
        ),
        "published_date": "2019-01-20",
        "external_average_rating": 7.9,
        "average_rating": None,
        "cover_image_url": (
            "https://placehold.co/400x600?text=Otherworld+Hostel"
        ),
        "genres": ("Fantasy", "Comedy"),
        "tags": ("Isekai",),
        "demographics": ("Seinen",),
    },
    {
        "title": "MR Seed — Witch’s Contract",
        "description": (
            "A skeptical investigator signs a contract with a witch to "
            "solve impossible cases."
        ),
        "published_date": "2014-06-07",
        "external_average_rating": 8.0,
        "average_rating": None,
        "cover_image_url": (
            "https://placehold.co/400x600?text=Witchs+Contract"
        ),
        "genres": ("Fantasy", "Drama"),
        "tags": ("Magic",),
        "demographics": ("Seinen",),
    },
    {
        "title": "MR Seed — Laughing Storm",
        "description": (
            "A chaotic comedy about a club that accidentally becomes "
            "the school’s problem-solver."
        ),
        "published_date": "2013-02-11",
        "external_average_rating": 7.3,
        "average_rating": None,
        "cover_image_url": (
            "https://placehold.co/400x600?text=Laughing+Storm"
        ),
        "genres": ("Comedy",),
        "tags": (),
        "demographics": ("Shounen",),
    },
)


def _fetch_metadata_id(
    connection,
    table_name: str,
    id_column: str,
    name_column: str,
    name: str,
) -> int:
    value = connection.execute(
        sa.text(
            f"""
            SELECT {id_column}
            FROM {table_name}
            WHERE {name_column} = :name
            ORDER BY {id_column}
            LIMIT 1
            """
        ),
        {"name": name},
    ).scalar_one_or_none()

    if value is None:
        raise RuntimeError(
            f"Cannot restore test seed: missing {table_name} row "
            f"for {name_column}={name!r}"
        )

    return int(value)


def upgrade() -> None:
    """Remove the exact catalog records created by the old test migration."""

    connection = op.get_bind()
    titles = [manga["title"] for manga in MANGA_SEED]

    # Foreign-key cascades remove metadata, creator, rating, and collection
    # associations for these explicitly test-only manga records.
    connection.execute(
        sa.text(
            """
            DELETE FROM manga
            WHERE title = ANY(:titles)
            """
        ),
        {"titles": titles},
    )

    # Do not remove the seed creator if another manga now references it.
    connection.execute(
        sa.text(
            """
            DELETE FROM creator AS seed_creator
            WHERE seed_creator.creator_name = :creator_name
              AND NOT EXISTS (
                  SELECT 1
                  FROM manga_creator
                  WHERE manga_creator.creator_id
                      = seed_creator.creator_id
              )
            """
        ),
        {"creator_name": SEED_CREATOR_NAME},
    )


def downgrade() -> None:
    """Restore the old test catalog using the current creator-credit schema."""

    connection = op.get_bind()

    creator_id = connection.execute(
        sa.text(
            """
            SELECT creator_id
            FROM creator
            WHERE creator_name = :creator_name
            ORDER BY creator_id
            LIMIT 1
            """
        ),
        {"creator_name": SEED_CREATOR_NAME},
    ).scalar_one_or_none()

    if creator_id is None:
        creator_id = connection.execute(
            sa.text(
                """
                INSERT INTO creator (creator_name)
                VALUES (:creator_name)
                RETURNING creator_id
                """
            ),
            {"creator_name": SEED_CREATOR_NAME},
        ).scalar_one()

    genre_id = lambda name: _fetch_metadata_id(
        connection,
        "genre",
        "genre_id",
        "genre_name",
        name,
    )
    tag_id = lambda name: _fetch_metadata_id(
        connection,
        "tag",
        "tag_id",
        "tag_name",
        name,
    )
    demographic_id = lambda name: _fetch_metadata_id(
        connection,
        "demographic",
        "demographic_id",
        "demographic_name",
        name,
    )

    for manga in MANGA_SEED:
        manga_id = connection.execute(
            sa.text(
                """
                SELECT manga_id
                FROM manga
                WHERE title = :title
                ORDER BY manga_id
                LIMIT 1
                """
            ),
            {"title": manga["title"]},
        ).scalar_one_or_none()

        if manga_id is None:
            manga_id = connection.execute(
                sa.text(
                    """
                    INSERT INTO manga (
                        title,
                        description,
                        published_date,
                        external_average_rating,
                        average_rating,
                        cover_image_url
                    )
                    VALUES (
                        :title,
                        :description,
                        :published_date,
                        :external_average_rating,
                        :average_rating,
                        :cover_image_url
                    )
                    RETURNING manga_id
                    """
                ),
                {
                    key: value
                    for key, value in manga.items()
                    if key
                    not in {"genres", "tags", "demographics"}
                },
            ).scalar_one()

        connection.execute(
            sa.text(
                """
                INSERT INTO manga_creator (
                    manga_id,
                    creator_id,
                    role
                )
                VALUES (:manga_id, :creator_id, 'author')
                ON CONFLICT (manga_id, creator_id, role) DO NOTHING
                """
            ),
            {
                "manga_id": manga_id,
                "creator_id": creator_id,
            },
        )

        for name in manga["genres"]:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO manga_genre (manga_id, genre_id)
                    VALUES (:manga_id, :genre_id)
                    ON CONFLICT (manga_id, genre_id) DO NOTHING
                    """
                ),
                {
                    "manga_id": manga_id,
                    "genre_id": genre_id(name),
                },
            )

        for name in manga["tags"]:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO manga_tag (manga_id, tag_id)
                    VALUES (:manga_id, :tag_id)
                    ON CONFLICT (manga_id, tag_id) DO NOTHING
                    """
                ),
                {
                    "manga_id": manga_id,
                    "tag_id": tag_id(name),
                },
            )

        for name in manga["demographics"]:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO manga_demographic (
                        manga_id,
                        demographic_id
                    )
                    VALUES (:manga_id, :demographic_id)
                    ON CONFLICT (
                        manga_id,
                        demographic_id
                    ) DO NOTHING
                    """
                ),
                {
                    "manga_id": manga_id,
                    "demographic_id": demographic_id(name),
                },
            )
