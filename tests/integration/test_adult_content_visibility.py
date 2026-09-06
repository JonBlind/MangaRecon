from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from .helpers import (
    add_manga_to_collection,
    assert_error,
    assert_success,
    count_rows,
    create_collection,
    create_rating,
    list_collection_mangas,
    register_and_login,
)


ADULT_MANGA_ID = 901
ADULT_GENRE_ID = 901


def seed_adult_title(manga_write_engine: Engine) -> None:
    with manga_write_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO genre (genre_id, genre_name)
                VALUES (:genre_id, 'Adult')
                """
            ),
            {"genre_id": ADULT_GENRE_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO manga (
                    manga_id,
                    title,
                    description,
                    publication_year,
                    external_average_rating,
                    is_adult_content
                )
                VALUES (
                    :manga_id,
                    'Restricted Example',
                    'Adult-content visibility fixture.',
                    2026,
                    8.0,
                    TRUE
                )
                """
            ),
            {"manga_id": ADULT_MANGA_ID},
        )
        connection.execute(
            text(
                """
                INSERT INTO manga_genre (manga_id, genre_id)
                VALUES (:manga_id, :genre_id)
                """
            ),
            {
                "manga_id": ADULT_MANGA_ID,
                "genre_id": ADULT_GENRE_ID,
            },
        )


def search_for_adult_title(client: TestClient) -> dict:
    return assert_success(
        client.get(
            "/mangas/",
            params={"title": "Restricted Example"},
        )
    )["data"]


def test_adult_content_is_safe_by_default_and_preserved_when_disabled(
    client: TestClient,
    manga_write_engine: Engine,
    user_write_engine: Engine,
) -> None:
    seed_adult_title(manga_write_engine)

    assert search_for_adult_title(client)["total_results"] == 0
    assert_error(
        client.get(f"/mangas/{ADULT_MANGA_ID}"),
        status_code=404,
        detail="MANGA_NOT_FOUND",
    )
    anonymous_genres = assert_success(
        client.get("/metadata/genres")
    )["data"]
    assert anonymous_genres["items"] == []

    register_and_login(client, suffix="adult_visibility")
    initial_profile = assert_success(
        client.get("/profiles/me")
    )["data"]
    assert initial_profile["show_adult_content"] is False

    collection = create_collection(
        client,
        name="Adult visibility",
    )
    collection_id = collection["collection_id"]
    assert_error(
        client.post(
            f"/collections/{collection_id}/mangas",
            json={"manga_id": ADULT_MANGA_ID},
        ),
        status_code=404,
        detail="MANGA_NOT_FOUND",
    )
    assert_error(
        client.post(
            "/ratings",
            json={
                "manga_id": ADULT_MANGA_ID,
                "personal_rating": 8,
            },
        ),
        status_code=404,
        detail="MANGA_NOT_FOUND",
    )

    missing_confirmation = client.patch(
        "/profiles/me",
        json={"show_adult_content": True},
    )
    assert_error(
        missing_confirmation,
        status_code=400,
        detail="ADULT_CONTENT_AGE_CONFIRMATION_REQUIRED",
    )

    opted_in = assert_success(
        client.patch(
            "/profiles/me",
            json={
                "show_adult_content": True,
                "confirm_adult_content_age": True,
            },
        )
    )["data"]
    assert opted_in["show_adult_content"] is True
    assert search_for_adult_title(client)["total_results"] == 1
    assert_success(client.get(f"/mangas/{ADULT_MANGA_ID}"))

    opted_in_genres = assert_success(
        client.get("/metadata/genres")
    )["data"]
    assert [
        item["genre_name"]
        for item in opted_in_genres["items"]
    ] == ["Adult"]

    add_manga_to_collection(
        client,
        collection_id=collection_id,
        manga_id=ADULT_MANGA_ID,
    )
    create_rating(
        client,
        manga_id=ADULT_MANGA_ID,
        personal_rating=8,
    )

    disabled = assert_success(
        client.patch(
            "/profiles/me",
            json={"show_adult_content": False},
        )
    )["data"]
    assert disabled["show_adult_content"] is False

    hidden_collection = list_collection_mangas(
        client,
        collection_id=collection_id,
    )
    assert hidden_collection["total_results"] == 0
    assert hidden_collection["items"] == []

    hidden_ratings = assert_success(client.get("/ratings"))["data"]
    assert hidden_ratings["total_results"] == 0
    assert hidden_ratings["items"] == []
    hidden_rating = assert_success(
        client.get(
            "/ratings",
            params={"manga_id": ADULT_MANGA_ID},
        )
    )["data"]
    assert hidden_rating is None

    assert count_rows(user_write_engine, "manga_collection") == 1
    assert count_rows(user_write_engine, "rating") == 1

    assert_success(
        client.patch(
            "/profiles/me",
            json={
                "show_adult_content": True,
                "confirm_adult_content_age": True,
            },
        )
    )

    visible_collection = list_collection_mangas(
        client,
        collection_id=collection_id,
    )
    assert visible_collection["total_results"] == 1
    assert visible_collection["items"][0]["manga_id"] == ADULT_MANGA_ID

    visible_ratings = assert_success(client.get("/ratings"))["data"]
    assert visible_ratings["total_results"] == 1
    assert visible_ratings["items"][0]["manga_id"] == ADULT_MANGA_ID
