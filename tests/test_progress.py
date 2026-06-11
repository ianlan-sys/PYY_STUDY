# backend/tests/test_progress.py
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def openid(client):
    await client.post("/users/init", json={"openid": "prog_uid", "nickname": "进度用户"})
    return "prog_uid"


@pytest.mark.asyncio
async def test_get_empty_progress(client, openid):
    resp = await client.get(f"/users/{openid}/progress")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_add_progress_node(client, openid):
    resp = await client.post(
        f"/users/{openid}/progress",
        json={"node_id": "beginner_syntax_1", "status": "learning"},
    )
    assert resp.status_code == 200
    assert resp.json()["node_id"] == "beginner_syntax_1"
    assert resp.json()["status"] == "learning"


@pytest.mark.asyncio
async def test_upsert_updates_status(client, openid):
    await client.post(f"/users/{openid}/progress",
                      json={"node_id": "beginner_syntax_1", "status": "learning"})
    await client.post(f"/users/{openid}/progress",
                      json={"node_id": "beginner_syntax_1", "status": "done"})
    resp = await client.get(f"/users/{openid}/progress")
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "done"
