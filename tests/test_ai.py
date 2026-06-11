# backend/tests/test_ai.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from main import app


async def fake_chat_stream(messages):
    for chunk in ["你好", "，", "我是AI助手"]:
        yield chunk


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_chat_streams_response(client):
    with patch("routers.ai.chat_stream", side_effect=fake_chat_stream):
        resp = await client.post("/ai/chat", json={
            "messages": [{"role": "user", "content": "什么是变量？"}],
            "user_level": "beginner",
            "current_node": "beginner_syntax_1",
        })
    assert resp.status_code == 200
    assert "你好" in resp.text


@pytest.mark.asyncio
async def test_chat_builds_system_prompt(client):
    captured = []

    async def capturing_stream(messages):
        captured.extend(messages)
        yield "ok"

    with patch("routers.ai.chat_stream", side_effect=capturing_stream):
        await client.post("/ai/chat", json={
            "messages": [{"role": "user", "content": "test"}],
            "user_level": "intermediate",
            "current_node": "beginner_syntax_2",
        })

    assert captured[0]["role"] == "system"
    assert "循环" in captured[0]["content"]
    assert captured[1]["role"] == "user"


@pytest.mark.asyncio
async def test_chat_invalid_level_rejected(client):
    resp = await client.post("/ai/chat", json={
        "messages": [{"role": "user", "content": "hi"}],
        "user_level": "expert",
        "current_node": "beginner_syntax_1",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_code_mode_appends_suffix(client):
    captured = []

    async def capturing_stream(messages):
        captured.extend(messages)
        yield "ok"

    with patch("routers.ai.chat_stream", side_effect=capturing_stream):
        await client.post("/ai/chat", json={
            "messages": [{"role": "user", "content": "for i in range(3): print(i)"}],
            "user_level": "beginner",
            "current_node": "beginner_syntax_1",
            "mode": "code",
        })

    assert "逐行解释" in captured[0]["content"]
