def test_get_all_genres(client):
    response = client.get("/metadata/genres")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "success"

    data = body["data"]
    assert "total_results" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_get_all_tags(client):
    response = client.get("/metadata/tags")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "success"

    data = body["data"]
    assert "total_results" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_get_all_demographics(client):
    response = client.get("/metadata/demographics")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "success"

    data = body["data"]
    assert "total_results" in data
    assert "items" in data
    assert isinstance(data["items"], list)