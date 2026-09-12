from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from .helpers import assert_error, assert_success, seed_catalog


def test_metadata_endpoints_read_real_seeded_rows(
    client: TestClient,
    manga_write_engine: Engine,
) -> None:
    seed_catalog(manga_write_engine)

    genres = assert_success(client.get("/metadata/genres"))["data"]
    tags = assert_success(client.get("/metadata/tags"))["data"]
    demographics = assert_success(client.get("/metadata/demographics"))["data"]

    assert genres["total_results"] == 2
    assert [item["genre_name"] for item in genres["items"]] == ["Action", "Romance"]
    assert tags["total_results"] == 2
    assert [item["tag_name"] for item in tags["items"]] == ["Adventure", "Drama"]
    assert demographics["total_results"] == 2
    assert [item["demographic_name"] for item in demographics["items"]] == ["Shonen", "Seinen"]


def test_manga_detail_returns_attached_metadata(
    client: TestClient,
    manga_write_engine: Engine,
) -> None:
    catalog = seed_catalog(manga_write_engine)

    data = assert_success(client.get(f"/mangas/{catalog.seed_manga_id}"))["data"]

    assert data["manga_id"] == catalog.seed_manga_id
    assert data["title"] == "Alpha Quest"
    assert data["creator_credits"] == [
        {
            "creator_id": 1,
            "creator_name": "Seed Creator",
            "role": "author",
        }
    ]
    assert data["genres"] == [{"genre_id": 1, "genre_name": "Action"}]
    assert data["tags"] == [{"tag_id": 1, "tag_name": "Adventure"}]
    assert data["demographics"] == [
        {"demographic_id": 1, "demographic_name": "Shonen"}
    ]


def test_manga_detail_returns_domain_404_for_missing_row(client: TestClient) -> None:
    response = client.get("/mangas/999999")
    assert_error(response, status_code=404, detail="MANGA_NOT_FOUND")


def test_manga_search_filters_orders_and_paginates_real_rows(
    client: TestClient,
    manga_write_engine: Engine,
) -> None:
    catalog = seed_catalog(manga_write_engine)

    title_response = client.get(
        "/mangas/",
        params={"title": "quest", "order_by": "title", "order_dir": "desc"},
    )
    title_data = assert_success(title_response)["data"]
    assert title_data["total_results"] == 2
    assert [item["title"] for item in title_data["items"]] == ["Beta Quest", "Alpha Quest"]

    with manga_write_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO manga_alternate_title (manga_id, title)
                VALUES (:manga_id, 'The Great Romance')
                """
            ),
            {"manga_id": catalog.unrelated_manga_id},
        )

    alternate_title_data = assert_success(
        client.get("/mangas/", params={"title": "great romance"})
    )["data"]
    assert alternate_title_data["total_results"] == 1
    assert [item["manga_id"] for item in alternate_title_data["items"]] == [
        catalog.unrelated_manga_id
    ]

    genre_response = client.get(
        "/mangas/",
        params=[("genre_ids", str(catalog.action_genre_id)), ("size", "1")],
    )
    genre_data = assert_success(genre_response)["data"]
    assert genre_data["total_results"] == 2
    assert genre_data["page"] == 1
    assert genre_data["size"] == 1
    assert len(genre_data["items"]) == 1
    assert genre_data["items"][0]["genres"][0]["genre_name"] == "Action"

    excluded_response = client.get(
        "/mangas/",
        params={"exclude_genres": catalog.action_genre_id},
    )
    excluded_data = assert_success(excluded_response)["data"]
    assert [item["manga_id"] for item in excluded_data["items"]] == [catalog.unrelated_manga_id]

    out_of_range_data = assert_success(
        client.get(
            "/mangas/",
            params={"title": "quest", "page": 99, "size": 1},
        )
    )["data"]
    assert out_of_range_data["total_results"] == 2
    assert out_of_range_data["items"] == []


def test_manga_search_rejects_invalid_pagination(client: TestClient) -> None:
    response = client.get("/mangas/", params={"page": 0, "size": 101})
    assert_error(response, status_code=422)


def test_manga_search_supports_global_and_or_metadata_matching(
    client: TestClient,
    manga_write_engine: Engine,
) -> None:
    catalog = seed_catalog(manga_write_engine)

    with manga_write_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO manga_genre (manga_id, genre_id)
                VALUES (:manga_id, :genre_id)
                """
            ),
            {
                "manga_id": catalog.seed_manga_id,
                "genre_id": catalog.romance_genre_id,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO manga_tag (manga_id, tag_id)
                VALUES (:manga_id, :tag_id)
                """
            ),
            {
                "manga_id": catalog.seed_manga_id,
                "tag_id": catalog.drama_tag_id,
            },
        )

    and_response = client.get(
        "/mangas/",
        params=[
            ("genre_ids", str(catalog.action_genre_id)),
            ("genre_ids", str(catalog.romance_genre_id)),
            ("tag_ids", str(catalog.drama_tag_id)),
        ],
    )
    and_data = assert_success(and_response)["data"]
    assert [item["manga_id"] for item in and_data["items"]] == [
        catalog.seed_manga_id
    ]

    or_response = client.get(
        "/mangas/",
        params=[
            ("genre_ids", str(catalog.action_genre_id)),
            ("tag_ids", str(catalog.drama_tag_id)),
            ("demo_ids", str(catalog.seinen_demographic_id)),
            ("match_mode", "or"),
            ("order_by", "title"),
        ],
    )
    or_data = assert_success(or_response)["data"]
    assert [item["manga_id"] for item in or_data["items"]] == [
        catalog.seed_manga_id,
        catalog.similar_manga_id,
        catalog.unrelated_manga_id,
    ]

    titled_or_data = assert_success(
        client.get(
            "/mangas/",
            params=[
                ("genre_ids", str(catalog.action_genre_id)),
                ("demo_ids", str(catalog.seinen_demographic_id)),
                ("match_mode", "or"),
                ("title", "beta"),
            ],
        )
    )["data"]
    assert [item["manga_id"] for item in titled_or_data["items"]] == [
        catalog.similar_manga_id
    ]

    excluded_or_data = assert_success(
        client.get(
            "/mangas/",
            params=[
                ("genre_ids", str(catalog.action_genre_id)),
                ("demo_ids", str(catalog.seinen_demographic_id)),
                ("exclude_genres", str(catalog.action_genre_id)),
                ("match_mode", "or"),
            ],
        )
    )["data"]
    assert [item["manga_id"] for item in excluded_or_data["items"]] == [
        catalog.unrelated_manga_id
    ]


def test_manga_search_rejects_invalid_match_mode(client: TestClient) -> None:
    response = client.get("/mangas/", params={"match_mode": "xor"})
    assert_error(response, status_code=422)
