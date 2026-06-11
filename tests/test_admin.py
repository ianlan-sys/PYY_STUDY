# backend/tests/test_admin.py
import os
import pytest
import bcrypt as _bcrypt
from httpx import AsyncClient, ASGITransport
from main import app

# Setup env before import
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD_HASH", _bcrypt.hashpw(b"admin123", _bcrypt.gensalt()).decode())


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_headers(client):
    resp = await client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_login_success(client):
    resp = await client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    resp = await client.post("/admin/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_token(client):
    resp = await client.get("/admin/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_username(client, auth_headers):
    resp = await client.get("/admin/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_stats_requires_auth(client):
    resp = await client.get("/admin/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stats_returns_counts(client, auth_headers):
    resp = await client.get("/admin/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "total_sessions" in data
    assert "active_7d" in data
    assert "estimated_tokens" in data


@pytest.mark.asyncio
async def test_users_list(client, auth_headers):
    resp = await client.get("/admin/users", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_sessions_list(client, auth_headers):
    resp = await client.get("/admin/sessions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_get_prompts(client, auth_headers):
    resp = await client.get("/admin/prompts", headers=auth_headers)
    assert resp.status_code == 200
    keys = {p["key"] for p in resp.json()}
    assert {"chat_base", "code_suffix", "error_suffix"} <= keys


@pytest.mark.asyncio
async def test_update_prompt(client, auth_headers):
    new_content = "新的 system prompt 内容"
    resp = await client.put("/admin/prompts/chat_base",
                             json={"content": new_content},
                             headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["content"] == new_content


@pytest.mark.asyncio
async def test_get_config(client, auth_headers):
    resp = await client.get("/admin/config", headers=auth_headers)
    assert resp.status_code == 200
    keys = {c["key"] for c in resp.json()}
    assert "ai_model" in keys


@pytest.mark.asyncio
async def test_update_config(client, auth_headers):
    resp = await client.put("/admin/config/ai_model",
                             json={"value": "deepseek-reasoner"},
                             headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["value"] == "deepseek-reasoner"


@pytest.mark.asyncio
async def test_get_session_detail(client, auth_headers):
    # create user and session first
    await client.post("/users/init", json={"openid": "admin_test_uid", "nickname": "测试"})
    save_resp = await client.post("/sessions", json={
        "openid": "admin_test_uid", "mode": "chat",
        "first_question": "测试问题", "messages": [{"role": "user", "content": "测试"}],
        "message_count": 1,
    })
    sid = save_resp.json()["id"]
    resp = await client.get(f"/admin/sessions/{sid}", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json()["messages"], list)
