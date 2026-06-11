# backend/services/deepseek.py
import os
import json
from typing import AsyncGenerator
import httpx


def _get_model_config() -> dict:
    """每次调用时动态读取激活模型配置，fallback 到环境变量。"""
    try:
        from database import get_db
        with get_db() as conn:
            row = conn.execute(
                "SELECT model_name, api_key, base_url FROM models WHERE is_active = 1"
            ).fetchone()
            if row and row["api_key"]:
                return {
                    "model": row["model_name"],
                    "api_key": row["api_key"],
                    "base_url": row["base_url"],
                }
            # 无激活模型时读 config 表的 ai_model key
            model_row = conn.execute(
                "SELECT value FROM config WHERE key = 'ai_model'"
            ).fetchone()
            model = model_row["value"] if model_row else "deepseek-chat"
    except Exception:
        model = "deepseek-chat"
    return {
        "model": model,
        "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    }


async def chat_stream(messages: list[dict]) -> AsyncGenerator[str, None]:
    cfg = _get_model_config()
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    body = {
        "model": cfg["model"],
        "messages": messages,
        "stream": True,
        "max_tokens": 1024,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            f"{cfg['base_url']}/v1/chat/completions",
            headers=headers,
            json=body,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                data = json.loads(payload)
                delta = data["choices"][0]["delta"].get("content", "")
                if delta:
                    yield delta


async def chat_once(messages: list[dict]) -> str:
    cfg = _get_model_config()
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    body = {
        "model": cfg["model"],
        "messages": messages,
        "stream": False,
        "max_tokens": 512,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{cfg['base_url']}/v1/chat/completions",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
