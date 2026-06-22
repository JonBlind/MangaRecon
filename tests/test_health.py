def test_healthz_returns_running_message(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"message": "MangaRecon API is running."}


def test_readyz_returns_503_when_rate_limit_storage_not_ready(app, client):
    app.state.rate_limit_storage_ready = False

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "data": {},
        "message": "Service unavailable.",
        "detail": "TEMPORARILY_UNAVAILABLE",
    }
    assert response.headers["Retry-After"] == "15"

def test_readyz_returns_ready_when_rate_limit_storage_ready(app, client):
    app.state.rate_limit_storage_ready = True

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"message": "MangaRecon API is ready."}