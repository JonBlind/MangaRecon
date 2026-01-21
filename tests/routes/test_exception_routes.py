import pytest

from tests.db.factories import make_manga


@pytest.mark.asyncio
async def test_get_collection_mangas_missing_collection_returns_404(async_client):
    # GET /collections/{id}/mangas should preserve 404 when collection doesn't exist.
    missing_collection_id = 999999

    resp = await async_client.get(f"/collections/{missing_collection_id}/mangas?page=1&size=20")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_update_rating_missing_returns_404(async_client, db_session):
    # PUT /ratings/ should 404 when the user has no rating for the given manga_id.

    manga = await make_manga(db_session)

    resp = await async_client.put(
        "/ratings/",
        json={"manga_id": manga.manga_id, "personal_rating": 7.0},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_delete_rating_missing_returns_404(async_client, db_session):
    # DELETE /ratings/{manga_id} should 404 when no rating exists for that manga.

    manga = await make_manga(db_session)

    resp = await async_client.delete(f"/ratings/{manga.manga_id}")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_get_single_rating_missing_returns_404(async_client, db_session):
    # GET /ratings/?manga_id=... should 404 when the user has no rating for that manga.

    manga = await make_manga(db_session)

    resp = await async_client.get(f"/ratings/?manga_id={manga.manga_id}")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_get_recommendations_missing_collection_returns_404(async_client):
    # GET /recommendations/{collection_id} should preserve 404 when collection doesn't exist.

    missing_collection_id = 999999

    resp = await async_client.get(f"/recommendations/{missing_collection_id}?page=1&size=20")
    assert resp.status_code == 404, resp.text
