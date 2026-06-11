# backend/tests/test_sessions_router.py
import pytest
from httpx import AsyncClient, ASGITransport
from main import app

SAMPLE = {
    "openid": "sess_uid",
    "mode": "chat",
    "first_question": "什么是列表推导式？",
    "messages": [
        {"role": "user", "content": "什么是列表推导式？"},
        {"role": "assistant", "content": "列表推导式是简洁创建列表的语法…"},
    ],
    "message_count": 2,
}


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/users/init", json={"openid": "sess_uid", "nickname": "会话用户"})
        yield c


@pytest.mark.asyncio
async def test_save_session(client):
    resp = await client.post("/sessions", json=SAMPLE)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["message_count"] == 2


@pytest.mark.asyncio
async def test_list_sessions(client):
    await client.post("/sessions", json=SAMPLE)
    await client.post("/sessions", json={**SAMPLE, "mode": "code"})
    resp = await client.get("/users/sess_uid/sessions")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_session_detail(client):
    save_resp = await client.post("/sessions", json=SAMPLE)
    sid = save_resp.json()["id"]
    resp = await client.get(f"/sessions/{sid}")
    assert resp.status_code == 200
    assert len(resp.json()["messages"]) == 2


@pytest.mark.asyncio
async def test_list_sessions_max_20(client):
    for i in range(25):
        await client.post("/sessions", json={**SAMPLE, "first_question": f"问题{i}"})
    resp = await client.get("/users/sess_uid/sessions")
    assert len(resp.json()) <= 20
