async def test_healthz(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    payload = r.json()
    assert isinstance(payload, dict)