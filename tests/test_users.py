# backend/tests/test_users.py
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_init_creates_user(client):
    resp = await client.post("/users/init", json={
        "openid": "uid_1", "nickname": "测试用户", "avatar_url": "",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["openid"] == "uid_1"
    assert data["level"] == "beginner"
    assert data["points"] == 0


@pytest.mark.asyncio
async def test_init_is_idempotent(client):
    body = {"openid": "uid_2", "nickname": "用户"}
    await client.post("/users/init", json=body)
    resp = await client.post("/users/init", json=body)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_user(client):
    await client.post("/users/init", json={"openid": "uid_3", "nickname": "用户3"})
    resp = await client.get("/users/uid_3")
    assert resp.status_code == 200
    assert resp.json()["nickname"] == "用户3"


@pytest.mark.asyncio
async def test_get_nonexistent_user_returns_404(client):
    resp = await client.get("/users/no_such_user")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_user_level_and_points(client):
    await client.post("/users/init", json={"openid": "uid_4", "nickname": "用户4"})
    resp = await client.patch("/users/uid_4", json={"level": "advanced", "points": 50})
    assert resp.status_code == 200
    assert resp.json()["level"] == "advanced"
    assert resp.json()["points"] == 50
