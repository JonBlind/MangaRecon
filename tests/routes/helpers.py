from uuid import uuid4
from fastapi_users.jwt import generate_jwt
from sqlalchemy import create_engine, text
from backend.auth.user_manager import UserManager
from backend.dependencies import settings

def unique_user_payload():
    unique = uuid4().hex[:8]
    return {
        "email": f"test_{unique}@example.com",
        "password": "password123",
        "username": f"user{unique}",
        "displayname": f"User {unique}",
    }


def verify_registered_user(client, *, user_id, email):
    token = generate_jwt(
        {
            "sub": str(user_id),
            "email": email,
            "aud": UserManager.verification_token_audience,
        },
        UserManager.verification_token_secret,
        UserManager.verification_token_lifetime_seconds,
    )
    response = client.post(
        "/auth/verify",
        json={"token": token},
    )
    assert response.status_code == 200
    return response.json()

def register_and_login(client):
    payload = unique_user_payload()

    register_response = client.post("/auth/register", json=payload)
    assert register_response.status_code == 201
    verify_registered_user(
        client,
        user_id=register_response.json()["id"],
        email=payload["email"],
    )

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
        "postgresql+psycopg://"
    )

    engine = create_engine(sync_url)

    with engine.begin() as conn:
        creator_id = conn.execute(
            text("""
                INSERT INTO creator (creator_name)
                VALUES (:creator_name)
                RETURNING creator_id
            """),
            {"creator_name": f"Test Creator {unique}"},
        ).scalar_one()

        manga_id = conn.execute(
            text("""
                INSERT INTO manga (
                    title,
                    description,
                    external_average_rating,
                    average_rating
                )
                VALUES (
                    :title,
                    :description,
                    :external_average_rating,
                    :average_rating
                )
                RETURNING manga_id
            """),
            {
                "title": manga_title,
                "description": "Test manga description",
                "external_average_rating": 4.5,
                "average_rating": 4.0,
            },
        ).scalar_one()

        conn.execute(
            text("""
                INSERT INTO manga_creator (
                    manga_id,
                    creator_id,
                    role
                )
                VALUES (
                    :manga_id,
                    :creator_id,
                    'author'
                )
            """),
            {
                "manga_id": manga_id,
                "creator_id": creator_id,
            },
        )

    engine.dispose()

    return {
        "manga_id": manga_id,
        "title": manga_title,
        "creator_credits": [
            {
                "creator_id": creator_id,
                "creator_name": f"Test Creator {unique}",
                "role": "author",
            }
        ],
    }
