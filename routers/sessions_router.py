# backend/routers/sessions_router.py
import json
from fastapi import APIRouter, HTTPException
from database import get_db, now_iso
from models import SessionSave, SessionSummary, SessionDetail

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionSummary)
async def save_session(body: SessionSave):
    messages_json = json.dumps(
        [m.model_dump() for m in body.messages], ensure_ascii=False
    )
    ts = now_iso()
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO sessions
               (openid, mode, first_question, messages_json, message_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (body.openid, body.mode, body.first_question, messages_json, body.message_count, ts),
        )
        sid = cur.lastrowid
    return {"id": sid, "mode": body.mode, "first_question": body.first_question,
            "message_count": body.message_count, "created_at": ts}


@router.get("/users/{openid}/sessions", response_model=list[SessionSummary])
async def list_sessions(openid: str):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, mode, first_question, message_count, created_at
               FROM sessions WHERE openid = ?
               ORDER BY created_at DESC LIMIT 20""",
            (openid,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    data = dict(row)
    data["messages"] = json.loads(data.pop("messages_json"))
    return data
