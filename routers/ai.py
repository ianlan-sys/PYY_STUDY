# backend/routers/ai.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from models import ChatRequest
from services.deepseek import chat_stream
from services.prompts import build_chat_system_prompt

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat")
async def chat(request: ChatRequest):
    system_prompt = build_chat_system_prompt(
        request.user_level, request.current_node, request.mode
    )
    messages = [{"role": "system", "content": system_prompt}]
    messages += [m.model_dump() for m in request.messages]

    async def generate():
        async for chunk in chat_stream(messages):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
