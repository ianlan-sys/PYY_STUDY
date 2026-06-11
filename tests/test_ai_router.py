# backend/tests/test_ai_router.py
import pytest
from unittest.mock import patch, AsyncMock

async def fake_stream(messages):
    for chunk in ["Hello", " World"]:
        yield chunk

@pytest.mark.asyncio
async def test_chat_streams_response(client):
    with patch("routers.ai.chat_stream", side_effect=fake_stream):
        response = await client.post(
            "/ai/chat",
            json={
                "messages": [{"role": "user", "content": "什么是变量？"}],
                "user_level": "beginner",
                "current_node": "beginner_syntax_1",
            },
        )
    assert response.status_code == 200
    assert "Hello" in response.text
    assert "World" in response.text

@pytest.mark.asyncio
async def test_chat_missing_field(client):
    response = await client.post("/ai/chat", json={"messages": []})
    assert response.status_code == 422
