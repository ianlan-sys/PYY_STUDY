# backend/routers/lessons.py
import json
from fastapi import APIRouter, HTTPException
from database import get_db

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.get("/nodes")
async def get_lesson_nodes():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT node_id, title, phase FROM lessons ORDER BY generated_at"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{node_id}")
async def get_lesson(node_id: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT node_id, title, phase, sections_json, generated_at FROM lessons WHERE node_id = ?",
            (node_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Lesson not yet generated")
    data = dict(row)
    data["sections"] = json.loads(data.pop("sections_json"))
    return data
