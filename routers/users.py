# backend/routers/users.py
from fastapi import APIRouter, HTTPException
from database import get_db, now_iso
from models import UserInit, UserUpdate, UserProfile

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/init", response_model=UserProfile)
async def init_user(body: UserInit):
    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE openid = ?", (body.openid,)
        ).fetchone()
        if existing:
            return dict(existing)
        ts = now_iso()
        conn.execute(
            """INSERT INTO users
               (openid, nickname, avatar_url, level, points, streak_days, last_active_date, created_at)
               VALUES (?, ?, ?, 'beginner', 0, 0, ?, ?)""",
            (body.openid, body.nickname, body.avatar_url, ts[:10], ts),
        )
    return {
        "openid": body.openid, "nickname": body.nickname, "avatar_url": body.avatar_url,
        "level": "beginner", "points": 0, "streak_days": 0,
        "last_active_date": ts[:10], "created_at": ts,
    }


@router.get("/{openid}", response_model=UserProfile)
async def get_user(openid: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE openid = ?", (openid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


@router.patch("/{openid}", response_model=UserProfile)
async def update_user(openid: str, body: UserUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with get_db() as conn:
            conn.execute(
                f"UPDATE users SET {set_clause} WHERE openid = ?",
                [*updates.values(), openid],
            )
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE openid = ?", (openid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)
