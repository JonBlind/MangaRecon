from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text


DEFAULT_PASSWORD = "ValidPass123!"


@dataclass(frozen=True)
class RegisteredUser:
    email: str
    username: str
    displayname: str
    password: str = DEFAULT_PASSWORD


@dataclass(frozen=True)
class CatalogSeed:
    action_genre_id: int
    romance_genre_id: int
    adventure_tag_id: int
    drama_tag_id: int
    shonen_demographic_id: int
    seinen_demographic_id: int
    seed_manga_id: int
    similar_manga_id: int
    unrelated_manga_id: int


def make_user(*, suffix: str | None = None, password: str = DEFAULT_PASSWORD) -> RegisteredUser:
    """
    Build a user with values that are unique across repeated/local test runs.

    Passing a suffix keeps names readable. A random suffix is used when omitted.
    """
    resolved = suffix or uuid4().hex[:10]
    normalized = resolved.lower().replace("-", "_")

    return RegisteredUser(
        email=f"integration-{normalized}@example.com",
        username=f"user_{normalized}",
        displayname=f"User {resolved.replace('_', ' ').title()}",
        password=password,
    )


def assert_success(
    response: Response,
    *,
    status_code: int = 200,
    message: str | None = None,
) -> dict[str, Any]:
    """
    Validate MangaRecon's success envelope and return the decoded response body.
    """
    assert response.status_code == status_code, response.text

    body = response.json()
    assert body["status"] == "success"
    assert body["detail"] is None

    if message is not None:
        assert body["message"] == message

    return body


def assert_error(
    response: Response,
    *,
    status_code: int,
    detail: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """
    Validate MangaRecon's error envelope and return the decoded response body.
    """
    assert response.status_code == status_code, response.text

    body = response.json()
    assert body["status"] == "error"

    if detail is not None:
        assert body["detail"] == detail

    if message is not None:
        assert body["message"] == message

    return body


def success_data(
    response: Response,
    *,
    status_code: int = 200,
    message: str | None = None,
) -> Any:
    """
    Validate a success response and return only its data field.
    """
    return assert_success(
        response,
        status_code=status_code,
        message=message,
    )["data"]


def register_user(
    client: TestClient,
    user: RegisteredUser,
) -> dict[str, Any]:
    response = client.post(
        "/auth/register",
        json={
            "email": user.email,
            "password": user.password,
            "username": user.username,
            "displayname": user.displayname,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login_user(
    client: TestClient,
    user: RegisteredUser,
) -> None:
    response = client.post(
        "/auth/jwt/login",
        data={
            "username": user.email,
            "password": user.password,
        },
    )
    assert response.status_code == 204, response.text
    assert "auth" in client.cookies


def logout_user(client: TestClient) -> None:
    response = client.post("/auth/jwt/logout")
    assert response.status_code == 204, response.text
    assert "auth" not in client.cookies


def register_and_login(
    client: TestClient,
    *,
    suffix: str | None = None,
    password: str = DEFAULT_PASSWORD,
) -> RegisteredUser:
    user = make_user(
        suffix=suffix,
        password=password,
    )
    register_user(client, user)
    login_user(client, user)
    return user


def get_my_profile(client: TestClient) -> dict[str, Any]:
    return success_data(client.get("/profiles/me"))


def update_my_profile(
    client: TestClient,
    **changes: Any,
) -> dict[str, Any]:
    return success_data(
        client.patch(
            "/profiles/me",
            json=changes,
        )
    )


def change_password(
    client: TestClient,
    *,
    current_password: str,
    new_password: str,
) -> dict[str, Any]:
    return assert_success(
        client.post(
            "/profiles/me/change-password",
            json={
                "current_password": current_password,
                "new_password": new_password,
            },
        )
    )


def create_collection(
    client: TestClient,
    *,
    name: str = "Favorites",
    description: str | None = "Integration test collection",
) -> dict[str, Any]:
    return success_data(
        client.post(
            "/collections",
            json={
                "collection_name": name,
                "description": description,
            },
        )
    )


def get_collection(
    client: TestClient,
    collection_id: int,
) -> dict[str, Any]:
    return success_data(
        client.get(f"/collections/{collection_id}")
    )


def update_collection(
    client: TestClient,
    collection_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    if name is not None:
        payload["collection_name"] = name

    if description is not None:
        payload["description"] = description

    return success_data(
        client.put(
            f"/collections/{collection_id}",
            json=payload,
        )
    )


def delete_collection(
    client: TestClient,
    collection_id: int,
) -> dict[str, Any]:
    return success_data(
        client.delete(f"/collections/{collection_id}")
    )


def add_manga_to_collection(
    client: TestClient,
    *,
    collection_id: int,
    manga_id: int,
) -> dict[str, Any]:
    return success_data(
        client.post(
            f"/collections/{collection_id}/mangas",
            json={"manga_id": manga_id},
        )
    )


def add_mangas_to_collection_bulk(
    client: TestClient,
    *,
    collection_id: int,
    manga_ids: list[int],
) -> dict[str, Any]:
    return success_data(
        client.post(
            f"/collections/{collection_id}/mangas/bulk",
            json={"manga_ids": manga_ids},
        )
    )


def list_collection_mangas(
    client: TestClient,
    *,
    collection_id: int,
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    return success_data(
        client.get(
            f"/collections/{collection_id}/mangas",
            params={
                "page": page,
                "size": size,
            },
        )
    )


def remove_manga_from_collection(
    client: TestClient,
    *,
    collection_id: int,
    manga_id: int,
) -> dict[str, Any]:
    return success_data(
        client.delete(
            f"/collections/{collection_id}/mangas/{manga_id}"
        )
    )


def create_rating(
    client: TestClient,
    *,
    manga_id: int,
    personal_rating: float,
) -> dict[str, Any]:
    return success_data(
        client.post(
            "/ratings",
            json={
                "manga_id": manga_id,
                "personal_rating": personal_rating,
            },
        )
    )


def get_rating(
    client: TestClient,
    *,
    manga_id: int,
) -> dict[str, Any]:
    return success_data(
        client.get(
            "/ratings",
            params={"manga_id": manga_id},
        )
    )


def update_rating(
    client: TestClient,
    *,
    manga_id: int,
    personal_rating: float,
) -> dict[str, Any]:
    return success_data(
        client.put(
            "/ratings",
            json={
                "manga_id": manga_id,
                "personal_rating": personal_rating,
            },
        )
    )


def delete_rating(
    client: TestClient,
    *,
    manga_id: int,
) -> dict[str, Any]:
    return success_data(
        client.delete(f"/ratings/{manga_id}")
    )


def get_collection_recommendations(
    client: TestClient,
    *,
    collection_id: int,
    order_by: str = "score",
    order_dir: str = "desc",
    page: int = 1,
    size: int = 20,
) -> dict[str, Any]:
    return success_data(
        client.get(
            f"/recommendations/{collection_id}",
            params={
                "order_by": order_by,
                "order_dir": order_dir,
                "page": page,
                "size": size,
            },
        )
    )


def get_query_list_recommendations(
    client: TestClient,
    *,
    manga_ids: list[int],
    order_by: str = "score",
    order_dir: str = "desc",
) -> dict[str, Any]:
    return success_data(
        client.post(
            "/recommendations/query-list",
            params={
                "order_by": order_by,
                "order_dir": order_dir,
            },
            json={"manga_ids": manga_ids},
        )
    )


def fetch_scalar(
    engine: Engine,
    statement: str,
    parameters: dict[str, Any] | None = None,
) -> Any:
    """
    Execute a read-only scalar SQL assertion against a test database.
    """
    with engine.connect() as connection:
        return connection.execute(
            text(statement),
            parameters or {},
        ).scalar_one()


def count_rows(
    engine: Engine,
    table_name: str,
    *,
    where: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> int:
    """
    Count rows in a known test table.

    Only call this with hard-coded table/where values from tests. The table name
    and optional WHERE fragment are interpolated because SQL parameters cannot
    represent SQL identifiers.
    """
    statement = f'SELECT count(*) FROM "{table_name}"'

    if where:
        statement += f" WHERE {where}"

    return int(fetch_scalar(engine, statement, parameters))


def seed_catalog(engine: Engine) -> CatalogSeed:
    """
    Insert a small deterministic manga catalog containing:

    - one seed manga;
    - one similar recommendation candidate;
    - one unrelated candidate;
    - two values for each metadata category.
    """
    values = CatalogSeed(
        action_genre_id=1,
        romance_genre_id=2,
        adventure_tag_id=1,
        drama_tag_id=2,
        shonen_demographic_id=1,
        seinen_demographic_id=2,
        seed_manga_id=101,
        similar_manga_id=102,
        unrelated_manga_id=103,
    )

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO author (author_id, author_name)
                VALUES
                    (1, 'Seed Author'),
                    (2, 'Other Author')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO genre (genre_id, genre_name)
                VALUES
                    (:action_id, 'Action'),
                    (:romance_id, 'Romance')
                """
            ),
            {
                "action_id": values.action_genre_id,
                "romance_id": values.romance_genre_id,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO tag (tag_id, tag_name)
                VALUES
                    (:adventure_id, 'Adventure'),
                    (:drama_id, 'Drama')
                """
            ),
            {
                "adventure_id": values.adventure_tag_id,
                "drama_id": values.drama_tag_id,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO demographic (demographic_id, demographic_name)
                VALUES
                    (:shonen_id, 'Shonen'),
                    (:seinen_id, 'Seinen')
                """
            ),
            {
                "shonen_id": values.shonen_demographic_id,
                "seinen_id": values.seinen_demographic_id,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO manga (
                    manga_id,
                    title,
                    author_id,
                    description,
                    published_date,
                    external_average_rating,
                    average_rating,
                    cover_image_url
                )
                VALUES
                    (
                        :seed_id,
                        'Alpha Quest',
                        1,
                        'The seed manga.',
                        :seed_date,
                        8.5,
                        8.0,
                        'https://example.com/alpha.jpg'
                    ),
                    (
                        :similar_id,
                        'Beta Quest',
                        1,
                        'A similar recommendation candidate.',
                        :similar_date,
                        8.0,
                        7.5,
                        'https://example.com/beta.jpg'
                    ),
                    (
                        :unrelated_id,
                        'Romance Story',
                        2,
                        'An unrelated title.',
                        :unrelated_date,
                        7.0,
                        6.5,
                        'https://example.com/romance.jpg'
                    )
                """
            ),
            {
                "seed_id": values.seed_manga_id,
                "similar_id": values.similar_manga_id,
                "unrelated_id": values.unrelated_manga_id,
                "seed_date": date(2020, 1, 1),
                "similar_date": date(2021, 1, 1),
                "unrelated_date": date(2010, 1, 1),
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO manga_genre (manga_id, genre_id)
                VALUES
                    (:seed_id, :action_id),
                    (:similar_id, :action_id),
                    (:unrelated_id, :romance_id)
                """
            ),
            {
                "seed_id": values.seed_manga_id,
                "similar_id": values.similar_manga_id,
                "unrelated_id": values.unrelated_manga_id,
                "action_id": values.action_genre_id,
                "romance_id": values.romance_genre_id,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO manga_tag (manga_id, tag_id)
                VALUES
                    (:seed_id, :adventure_id),
                    (:similar_id, :adventure_id),
                    (:unrelated_id, :drama_id)
                """
            ),
            {
                "seed_id": values.seed_manga_id,
                "similar_id": values.similar_manga_id,
                "unrelated_id": values.unrelated_manga_id,
                "adventure_id": values.adventure_tag_id,
                "drama_id": values.drama_tag_id,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO manga_demographic (manga_id, demographic_id)
                VALUES
                    (:seed_id, :shonen_id),
                    (:similar_id, :shonen_id),
                    (:unrelated_id, :seinen_id)
                """
            ),
            {
                "seed_id": values.seed_manga_id,
                "similar_id": values.similar_manga_id,
                "unrelated_id": values.unrelated_manga_id,
                "shonen_id": values.shonen_demographic_id,
                "seinen_id": values.seinen_demographic_id,
            },
        )

    return values