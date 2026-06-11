# backend/tests/test_deepseek.py
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from services.deepseek import chat_stream, chat_once

FAKE_MESSAGES = [{"role": "user", "content": "什么是变量？"}]

@pytest.mark.asyncio
async def test_chat_stream_yields_text():
    chunks = [
        "data: " + json.dumps({"choices": [{"delta": {"content": "变量"}}]}) + "\n",
        "data: " + json.dumps({"choices": [{"delta": {"content": "是容器"}}]}) + "\n",
        "data: [DONE]\n",
    ]

    async def fake_aiter_lines():
        for c in chunks:
            yield c.strip()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = fake_aiter_lines

    mock_stream_cm = MagicMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_stream_cm)

    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("services.deepseek.httpx.AsyncClient", return_value=mock_client_cm):
        collected = []
        async for chunk in chat_stream(FAKE_MESSAGES):
            collected.append(chunk)

    assert collected == ["变量", "是容器"]


@pytest.mark.asyncio
async def test_chat_once_returns_string():
    fake_resp_json = {
        "choices": [{"message": {"content": "变量是存储数据的容器"}}]
    }
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=fake_resp_json)

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("services.deepseek.httpx.AsyncClient", return_value=mock_client_cm):
        result = await chat_once(FAKE_MESSAGES)

    assert result == "变量是存储数据的容器"
