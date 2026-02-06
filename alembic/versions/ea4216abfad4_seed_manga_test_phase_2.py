"""seed manga (test phase 2)

Revision ID: ea4216abfad4
Revises: 72c324a3ded1
Create Date: 2025-08-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "ea4216abfad4"
down_revision: Union[str, Sequence[str], None] = "72c324a3ded1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


AUTHOR_SEED = {
    "author_name": "MR Seed Author"
}

MANGA_SEED = [
    {
        "title": "MR Seed — Crimson Blade",
        "description": "A wandering swordsman gets pulled into a rebellion against a corrupt empire.",
        "published_date": "2011-04-03",
        "external_average_rating": 8.4,
        "average_rating": None,
        "cover_image_url": "https://placehold.co/400x600?text=Crimson+Blade",
        "genres": ["Action", "Drama"],
        "tags": ["Reincarnation"],
        "demographics": ["Shounen"],
    },
    {
        "title": "MR Seed — Clockwork Heart",
        "description": "A quiet romance unfolds when time slips begin to rewrite two students’ lives.",
        "published_date": "2016-09-12",
        "external_average_rating": 8.1,
        "average_rating": None,
        "cover_image_url": "https://placehold.co/400x600?text=Clockwork+Heart",
        "genres": ["Romance", "Drama"],
        "tags": ["Time Travel"],
        "demographics": ["Shoujo"],
    },
    {
        "title": "MR Seed — Otherworld Hostel",
        "description": "A broke college kid wakes up in a fantasy hostel for lost travelers from other worlds.",
        "published_date": "2019-01-20",
        "external_average_rating": 7.9,
        "average_rating": None,
        "cover_image_url": "https://placehold.co/400x600?text=Otherworld+Hostel",
        "genres": ["Fantasy", "Comedy"],
        "tags": ["Isekai"],
        "demographics": ["Seinen"],
    },
    {
        "title": "MR Seed — Witch’s Contract",
        "description": "A skeptical investigator signs a contract with a witch to solve impossible cases.",
        "published_date": "2014-06-07",
        "external_average_rating": 8.0,
        "average_rating": None,
        "cover_image_url": "https://placehold.co/400x600?text=Witchs+Contract",
        "genres": ["Fantasy", "Drama"],
        "tags": ["Magic"],
        "demographics": ["Seinen"],
    },
    {
        "title": "MR Seed — Laughing Storm",
        "description": "A chaotic comedy about a club that accidentally becomes the school’s problem-solver.",
        "published_date": "2013-02-11",
        "external_average_rating": 7.3,
        "average_rating": None,
        "cover_image_url": "https://placehold.co/400x600?text=Laughing+Storm",
        "genres": ["Comedy"],
        "tags": [],
        "demographics": ["Shounen"],
    },
]


def _fetch_id_by_name(conn, table: str, id_col: str, name_col: str, name: str) -> int:
    row = conn.execute(
        sa.text(f"SELECT {id_col} FROM {table} WHERE {name_col} = :name ORDER BY {id_col} LIMIT 1"),
        {"name": name},
    ).fetchone()
    if not row:
        raise RuntimeError(f"Missing {table} row for name='{name}'")
    return int(row[0])


def upgrade() -> None:
    conn = op.get_bind()

    # -------------------------
    # 1) Seed author (no ON CONFLICT)
    # -------------------------
    select_author_id = sa.text("""
        SELECT author_id
        FROM author
        WHERE author_name = :author_name
        ORDER BY author_id
        LIMIT 1
    """)

    insert_author = sa.text("""
        INSERT INTO author (author_name)
        VALUES (:author_name)
        RETURNING author_id
    """)

    existing_author = conn.execute(select_author_id, AUTHOR_SEED).fetchone()
    if existing_author and existing_author[0]:
        author_id = int(existing_author[0])
    else:
        author_id = int(conn.execute(insert_author, AUTHOR_SEED).scalar_one())

    # -------------------------
    # 2) Metadata ID lookups
    # -------------------------
    genre_id = lambda n: _fetch_id_by_name(conn, "genre", "genre_id", "genre_name", n)
    tag_id = lambda n: _fetch_id_by_name(conn, "tag", "tag_id", "tag_name", n)
    demo_id = lambda n: _fetch_id_by_name(conn, "demographic", "demographic_id", "demographic_name", n)

    # -------------------------
    # 3) Manga seed (no ON CONFLICT)
    # -------------------------
    select_manga_id = sa.text("""
        SELECT manga_id
        FROM manga
        WHERE title = :title
        ORDER BY manga_id
        LIMIT 1
    """)

    insert_manga = sa.text("""
        INSERT INTO manga (
            title,
            description,
            published_date,
            external_average_rating,
            average_rating,
            author_id,
            cover_image_url
        )
        VALUES (
            :title,
            :description,
            :published_date,
            :external_average_rating,
            :average_rating,
            :author_id,
            :cover_image_url
        )
        RETURNING manga_id
    """)

    # -------------------------
    # 4) Join table inserts (no ON CONFLICT)
    # -------------------------
    select_manga_genre = sa.text("""
        SELECT 1 FROM manga_genre
        WHERE manga_id = :manga_id AND genre_id = :genre_id
        LIMIT 1
    """)
    insert_manga_genre = sa.text("""
        INSERT INTO manga_genre (manga_id, genre_id)
        VALUES (:manga_id, :genre_id)
    """)

    select_manga_tag = sa.text("""
        SELECT 1 FROM manga_tag
        WHERE manga_id = :manga_id AND tag_id = :tag_id
        LIMIT 1
    """)
    insert_manga_tag = sa.text("""
        INSERT INTO manga_tag (manga_id, tag_id)
        VALUES (:manga_id, :tag_id)
    """)

    select_manga_demo = sa.text("""
        SELECT 1 FROM manga_demographic
        WHERE manga_id = :manga_id AND demographic_id = :demographic_id
        LIMIT 1
    """)
    insert_manga_demo = sa.text("""
        INSERT INTO manga_demographic (manga_id, demographic_id)
        VALUES (:manga_id, :demographic_id)
    """)

    # -------------------------
    # 5) Apply seeds
    # -------------------------
    for m in MANGA_SEED:
        payload = dict(m)
        payload["author_id"] = author_id

        existing_manga = conn.execute(select_manga_id, {"title": payload["title"]}).fetchone()
        if existing_manga and existing_manga[0]:
            manga_id = int(existing_manga[0])
        else:
            manga_id = int(conn.execute(insert_manga, payload).scalar_one())

        # Genres
        for g in m["genres"]:
            params = {"manga_id": manga_id, "genre_id": genre_id(g)}
            exists = conn.execute(select_manga_genre, params).fetchone()
            if not exists:
                conn.execute(insert_manga_genre, params)

        # Tags
        for t in m["tags"]:
            params = {"manga_id": manga_id, "tag_id": tag_id(t)}
            exists = conn.execute(select_manga_tag, params).fetchone()
            if not exists:
                conn.execute(insert_manga_tag, params)

        # Demographics
        for d in m["demographics"]:
            params = {"manga_id": manga_id, "demographic_id": demo_id(d)}
            exists = conn.execute(select_manga_demo, params).fetchone()
            if not exists:
                conn.execute(insert_manga_demo, params)


def downgrade() -> None:
    conn = op.get_bind()

    titles = [m["title"] for m in MANGA_SEED]

    rows = conn.execute(
        sa.text("""
            SELECT manga_id
            FROM manga
            WHERE title = ANY(:titles)
        """),
        {"titles": titles},
    ).fetchall()

    manga_ids = [int(r[0]) for r in rows]

    if manga_ids:
        conn.execute(sa.text("DELETE FROM manga_tag WHERE manga_id = ANY(:ids)"), {"ids": manga_ids})
        conn.execute(sa.text("DELETE FROM manga_genre WHERE manga_id = ANY(:ids)"), {"ids": manga_ids})
        conn.execute(sa.text("DELETE FROM manga_demographic WHERE manga_id = ANY(:ids)"), {"ids": manga_ids})
        conn.execute(sa.text("DELETE FROM manga WHERE manga_id = ANY(:ids)"), {"ids": manga_ids})

    conn.execute(
        sa.text("DELETE FROM author WHERE author_name = :author_name"),
        AUTHOR_SEED
    )
