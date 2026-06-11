# backend/routers/progress.py
from fastapi import APIRouter
from database import get_db, now_iso
from models import ProgressItem

router = APIRouter(tags=["progress"])


@router.get("/users/{openid}/progress", response_model=list[ProgressItem])
async def get_progress(openid: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT node_id, status, completed_at FROM progress WHERE openid = ?",
            (openid,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/users/{openid}/progress", response_model=ProgressItem)
async def upsert_progress(openid: str, body: ProgressItem):
    completed_at = now_iso() if body.status == "done" else body.completed_at
    with get_db() as conn:
        conn.execute(
            """INSERT INTO progress (openid, node_id, status, completed_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(openid, node_id) DO UPDATE SET
                 status = excluded.status,
                 completed_at = excluded.completed_at""",
            (openid, body.node_id, body.status, completed_at),
        )
        row = conn.execute(
            "SELECT node_id, status, completed_at FROM progress WHERE openid=? AND node_id=?",
            (openid, body.node_id),
        ).fetchone()
    return dict(row)
