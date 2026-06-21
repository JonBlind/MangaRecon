from uuid import uuid4
from sqlalchemy import create_engine, text
from backend.dependencies import settings

def unique_user_payload():
    unique = uuid4().hex[:8]
    return {
        "email": f"test_{unique}@example.com",
        "password": "password123",
        "username": f"user{unique}",
        "displayname": f"User {unique}",
    }

def register_and_login(client):
    payload = unique_user_payload()

    register_response = client.post("/auth/register", json=payload)
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/jwt/login",
        data={
            "username": payload["email"],
            "password": payload["password"],
        },
    )
    assert login_response.status_code == 204

    return payload

def create_collection(client, name="Favorites", description="My favorite manga"):
    response = client.post(
        "/collections",
        json={
            "collection_name": name,
            "description": description,
        },
    )

    assert response.status_code == 200
    return response.json()["data"]

def create_test_manga(title=None):
    unique = uuid4().hex[:8]
    manga_title = title or f"Test Manga {unique}"

    sync_url = settings.user_write.replace(
        "postgresql+asyncpg://",
        "postgresql://",
    )

    engine = create_engine(sync_url)

    with engine.begin() as conn:
        author_id = conn.execute(
            text("""
                INSERT INTO author (author_name)
                VALUES (:author_name)
                RETURNING author_id
            """),
            {"author_name": f"Test Author {unique}"},
        ).scalar_one()

        manga_id = conn.execute(
            text("""
                INSERT INTO manga (
                    title,
                    author_id,
                    description,
                    external_average_rating,
                    average_rating
                )
                VALUES (
                    :title,
                    :author_id,
                    :description,
                    :external_average_rating,
                    :average_rating
                )
                RETURNING manga_id
            """),
            {
                "title": manga_title,
                "author_id": author_id,
                "description": "Test manga description",
                "external_average_rating": 4.5,
                "average_rating": 4.0,
            },
        ).scalar_one()

    engine.dispose()

    return {
        "manga_id": manga_id,
        "title": manga_title,
        "author_id": author_id,
    }