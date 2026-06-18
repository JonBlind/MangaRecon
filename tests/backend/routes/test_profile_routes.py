from tests.backend.routes.helpers import unique_user_payload

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


def test_profiles_me_requires_auth(client):
    response = client.get("/profiles/me")

    assert response.status_code == 401


def test_logged_in_user_can_read_profile(client):
    payload = register_and_login(client)

    response = client.get("/profiles/me")

    assert response.status_code == 200

    body = response.json()
    profile = body["data"]

    assert profile["email"] == payload["email"]
    assert profile["username"] == payload["username"]
    assert profile["displayname"] == payload["displayname"]


def test_logged_in_user_can_update_displayname(client):
    register_and_login(client)

    response = client.patch(
        "/profiles/me",
        json={"displayname": "Updated Name"},
    )

    assert response.status_code == 200

    body = response.json()
    profile = body["data"]

    assert profile["displayname"] == "Updated Name"


def test_update_displayname_rejects_blank_value(client):
    register_and_login(client)

    response = client.patch(
        "/profiles/me",
        json={"displayname": ""},
    )

    assert response.status_code in {400, 422}

def test_update_displayname_persists_to_profiles_me(client):
    register_and_login(client)

    update_response = client.patch(
        "/profiles/me",
        json={"displayname": "Updated Name"},
    )

    assert update_response.status_code == 200

    read_response = client.get("/profiles/me")
    assert read_response.status_code == 200

    profile = read_response.json()["data"]
    assert profile["displayname"] == "Updated Name"

def test_update_profile_requires_auth(client):
    response = client.patch(
        "/profiles/me",
        json={"displayname": "Should Fail"},
    )

    assert response.status_code == 401