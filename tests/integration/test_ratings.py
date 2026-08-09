from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from .helpers import assert_error, assert_success, register_and_login, seed_catalog


def test_rating_create_read_update_list_delete_persists_real_rows(
    client: TestClient,
    manga_write_engine: Engine,
    user_write_engine: Engine,
) -> None:
    register_and_login(client, suffix="ratings")
    catalog = seed_catalog(manga_write_engine)

    created = assert_success(
        client.post(
            "/ratings",
            json={"manga_id": catalog.seed_manga_id, "personal_rating": 8},
        )
    )["data"]
    assert created["manga_id"] == catalog.seed_manga_id
    assert created["personal_rating"] == 8.0

    with user_write_engine.connect() as connection:
        persisted = connection.execute(
            text(
                "SELECT personal_rating FROM rating WHERE manga_id = :manga_id"
            ),
            {"manga_id": catalog.seed_manga_id},
        ).scalar_one()
    assert float(persisted) == 8.0

    single = assert_success(
        client.get("/ratings", params={"manga_id": catalog.seed_manga_id})
    )["data"]
    assert single["personal_rating"] == 8.0

    updated = assert_success(
        client.put(
            "/ratings",
            json={"manga_id": catalog.seed_manga_id, "personal_rating": 9.0},
        )
    )["data"]
    assert updated["personal_rating"] == 9.0

    listed = assert_success(client.get("/ratings"))["data"]
    assert listed["total_results"] == 1
    assert listed["items"][0]["personal_rating"] == 9.0

    deleted = assert_success(
        client.delete(f"/ratings/{catalog.seed_manga_id}")
    )["data"]
    assert deleted == {"manga_id": catalog.seed_manga_id}

    missing = client.get("/ratings", params={"manga_id": catalog.seed_manga_id})
    assert_error(missing, status_code=404, detail="RATING_NOT_FOUND")


def test_rating_create_rejects_missing_manga_and_does_not_persist(
    client: TestClient,
    user_write_engine: Engine,
) -> None:
    register_and_login(client, suffix="ratingmissing")

    response = client.post(
        "/ratings",
        json={"manga_id": 999999, "personal_rating": 7},
    )
    assert_error(response, status_code=404, detail="MANGA_NOT_FOUND")

    with user_write_engine.connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM rating")).scalar_one()
    assert count == 0


def test_rating_update_requires_existing_rating(
    client: TestClient,
    manga_write_engine: Engine,
) -> None:
    register_and_login(client, suffix="ratingupdate")
    catalog = seed_catalog(manga_write_engine)

    response = client.put(
        "/ratings",
        json={"manga_id": catalog.seed_manga_id, "personal_rating": 6.0},
    )
    assert_error(response, status_code=404, detail="RATING_NOT_FOUND")


def test_rating_delete_requires_existing_rating(client: TestClient) -> None:
    register_and_login(client, suffix="ratingdelete")

    response = client.delete("/ratings/123456")
    assert_error(response, status_code=404, detail="RATING_NOT_FOUND")


def test_rating_schema_enforces_integer_scores_from_one_to_ten(
    client: TestClient,
) -> None:
    register_and_login(client, suffix="ratingvalidation")

    too_high = client.post(
        "/ratings",
        json={"manga_id": 1, "personal_rating": 11},
    )
    fractional = client.post(
        "/ratings",
        json={"manga_id": 1, "personal_rating": 7.5},
    )
    zero = client.post(
        "/ratings",
        json={"manga_id": 1, "personal_rating": 0},
    )

    assert_error(too_high, status_code=422)
    assert_error(fractional, status_code=422)
    assert_error(zero, status_code=422)


def test_rating_changes_recalculate_internal_manga_average(
    client_factory,
    manga_write_engine: Engine,
) -> None:
    first_user = client_factory()
    second_user = client_factory()
    register_and_login(first_user, suffix="ratingaverageone")
    register_and_login(second_user, suffix="ratingaveragetwo")
    catalog = seed_catalog(manga_write_engine)

    def current_average() -> float | None:
        with manga_write_engine.connect() as connection:
            value = connection.execute(
                text(
                    "SELECT average_rating FROM manga WHERE manga_id = :manga_id"
                ),
                {"manga_id": catalog.seed_manga_id},
            ).scalar_one()
        return None if value is None else float(value)

    assert_success(
        first_user.post(
            "/ratings",
            json={"manga_id": catalog.seed_manga_id, "personal_rating": 8.0},
        )
    )
    assert current_average() == 8.0

    assert_success(
        second_user.post(
            "/ratings",
            json={"manga_id": catalog.seed_manga_id, "personal_rating": 9.0},
        )
    )
    assert current_average() == 8.5

    assert_success(
        first_user.post(
            "/ratings",
            json={"manga_id": catalog.seed_manga_id, "personal_rating": 10.0},
        )
    )
    assert current_average() == 9.5

    assert_success(second_user.delete(f"/ratings/{catalog.seed_manga_id}"))
    assert current_average() == 10.0

    assert_success(first_user.delete(f"/ratings/{catalog.seed_manga_id}"))
    assert current_average() is None
