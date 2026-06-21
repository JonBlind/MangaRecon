from helpers import create_test_manga
from uuid import uuid4

def test_get_manga_by_id(client):
    manga = create_test_manga()

    response = client.get(f"/mangas/{manga['manga_id']}")

    assert response.status_code == 200

    data = response.json()["data"]
    assert data["manga_id"] == manga["manga_id"]
    assert data["title"] == manga["title"]


def test_get_missing_manga_returns_404(client):
    response = client.get("/mangas/999999999")

    assert response.status_code == 404


def test_list_manga_default_page(client):
    response = client.get("/mangas/")

    assert response.status_code == 200

    data = response.json()["data"]
    assert "items" in data
    assert "page" in data
    assert "size" in data
    assert "total_results" in data


def test_filter_manga_by_title(client):
    unique = uuid4().hex[:8]

    manga = create_test_manga(
        title=f"Unique Test Manga {unique}"
    )

    response = client.get(
        "/mangas/",
        params={"title": unique},
    )

    assert any(
        item["manga_id"] == manga["manga_id"]
        for item in response.json()["data"]["items"]
    )

def test_invalid_page_returns_422(client):
    response = client.get("/mangas/", params={"page": 0})

    assert response.status_code == 422


def test_invalid_size_returns_422(client):
    response = client.get("/mangas/", params={"size": 101})

    assert response.status_code == 422