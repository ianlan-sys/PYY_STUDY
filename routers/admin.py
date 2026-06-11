# backend/routers/admin.py
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from admin.auth import create_token, require_admin, verify_password
from database import get_db, now_iso
from services.deepseek import chat_once

router = APIRouter(prefix="/admin", tags=["admin"])


class LoginRequest(BaseModel):
    username: str
    password: str


class PromptUpdate(BaseModel):
    content: str


class ConfigUpdate(BaseModel):
    value: str


class LessonCreate(BaseModel):
    node_id: str
    title: str
    phase: str = "入门"


class QuestionCreate(BaseModel):
    topic: str
    text: str
    options: list[str]
    answer: str
    difficulty: int = 1


class QuestionUpdate(BaseModel):
    topic: str | None = None
    text: str | None = None
    options: list[str] | None = None
    answer: str | None = None
    difficulty: int | None = None


class ModelCreate(BaseModel):
    display_name: str
    model_name: str
    api_key: str
    base_url: str = "https://api.deepseek.com"


class ModelUpdate(BaseModel):
    display_name: str | None = None
    model_name: str | None = None
    api_key: str | None = None
    base_url: str | None = None


@router.post("/login")
async def login(body: LoginRequest):
    expected_user = os.getenv("ADMIN_USERNAME", "admin")
    password_hash = os.getenv("ADMIN_PASSWORD_HASH", "")
    if body.username != expected_user or not verify_password(body.password, password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {"access_token": create_token(body.username), "token_type": "bearer"}


@router.get("/me")
async def me(username: str = Depends(require_admin)):
    return {"username": username}


@router.get("/stats")
async def stats(_: str = Depends(require_admin)):
    with get_db() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()[:10]
        active_7d = conn.execute(
            "SELECT COUNT(DISTINCT openid) FROM sessions WHERE created_at >= ?", (cutoff,)
        ).fetchone()[0]
        all_messages = conn.execute("SELECT messages_json FROM sessions").fetchall()
    total_chars = sum(len(row[0]) for row in all_messages)
    return {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "active_7d": active_7d,
        "estimated_tokens": total_chars // 4,
    }


@router.get("/users")
async def list_users(
    page: int = 1,
    q: Optional[str] = None,
    _: str = Depends(require_admin),
):
    offset = (page - 1) * 20
    with get_db() as conn:
        if q:
            where = "WHERE u.nickname LIKE ?"
            params_total = (f"%{q}%",)
            params_items = (f"%{q}%", offset)
        else:
            where = ""
            params_total = ()
            params_items = (offset,)
        total = conn.execute(
            f"SELECT COUNT(*) FROM users u {where}", params_total
        ).fetchone()[0]
        rows = conn.execute(
            f"""SELECT u.openid, u.nickname, u.level, u.points, u.created_at,
                       (SELECT COUNT(*) FROM sessions s WHERE s.openid = u.openid) AS session_count
                FROM users u {where}
                ORDER BY u.created_at DESC LIMIT 20 OFFSET ?""",
            params_items,
        ).fetchall()
    return {"total": total, "page": page, "items": [dict(r) for r in rows]}


@router.get("/sessions")
async def list_sessions(
    page: int = 1,
    mode: Optional[str] = None,
    _: str = Depends(require_admin),
):
    offset = (page - 1) * 20
    with get_db() as conn:
        if mode:
            where = "WHERE s.mode = ?"
            params_total = (mode,)
            params_items = (mode, offset)
        else:
            where = ""
            params_total = ()
            params_items = (offset,)
        total = conn.execute(
            f"SELECT COUNT(*) FROM sessions s {where}", params_total
        ).fetchone()[0]
        rows = conn.execute(
            f"""SELECT s.id, u.nickname, s.mode, s.first_question, s.message_count, s.created_at
                FROM sessions s
                LEFT JOIN users u ON u.openid = s.openid
                {where}
                ORDER BY s.created_at DESC LIMIT 20 OFFSET ?""",
            params_items,
        ).fetchall()
    return {"total": total, "page": page, "items": [dict(r) for r in rows]}


@router.get("/sessions/{session_id}")
async def get_admin_session(session_id: int, _: str = Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    data = dict(row)
    data["messages"] = json.loads(data.pop("messages_json"))
    return data


@router.get("/prompts")
async def get_prompts(_: str = Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute("SELECT key, content, updated_at FROM prompts").fetchall()
    return [dict(r) for r in rows]


@router.put("/prompts/{key}")
async def update_prompt(key: str, body: PromptUpdate, _: str = Depends(require_admin)):
    ts = now_iso()
    with get_db() as conn:
        conn.execute(
            "UPDATE prompts SET content = ?, updated_at = ? WHERE key = ?",
            (body.content, ts, key),
        )
        row = conn.execute("SELECT key, content, updated_at FROM prompts WHERE key = ?", (key,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Prompt key not found")
    return dict(row)


@router.get("/config")
async def get_config(_: str = Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute("SELECT key, value, updated_at FROM config").fetchall()
    return [dict(r) for r in rows]


@router.put("/config/{key}")
async def update_config(key: str, body: ConfigUpdate, _: str = Depends(require_admin)):
    ts = now_iso()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO config (key, value, updated_at) VALUES (?, ?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, body.value, ts),
        )
        row = conn.execute("SELECT key, value, updated_at FROM config WHERE key = ?", (key,)).fetchone()
    return dict(row)


NODE_META = {
    "beginner_syntax_1": {"title": "变量与数据类型", "phase": "入门"},
    "beginner_syntax_2": {"title": "条件与循环",     "phase": "入门"},
    "beginner_syntax_3": {"title": "函数",           "phase": "入门"},
}

LESSON_PROMPT = """你是 Python 编程老师，请为以下课程节点生成教学内容，面向零基础中文学习者。

节点：{title}

请严格按照如下 JSON 格式返回，不要有任何额外文字，只返回 JSON 数组：
[
  {{"heading": "小节标题", "body": "文字讲解（100字以内）", "code": "Python 示例代码（可为空字符串）"}},
  ...
]
要求：
- 共 3 个小节
- body 用中文，语言通俗
- code 每段不超过 10 行，用真实可运行的 Python 代码
- heading、body、code 均为字符串"""


@router.get("/lessons")
async def list_lessons(_: str = Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT node_id, title, phase, generated_at FROM lessons ORDER BY generated_at"
        ).fetchall()
    db_map = {r["node_id"]: dict(r) for r in rows}
    result = []
    # built-in nodes first
    for node_id, meta in NODE_META.items():
        entry = {"node_id": node_id, **meta, "generated_at": None, "builtin": True}
        if node_id in db_map:
            entry["generated_at"] = db_map[node_id]["generated_at"]
        result.append(entry)
    # custom nodes from DB not in NODE_META
    for node_id, row in db_map.items():
        if node_id not in NODE_META:
            result.append({**row, "builtin": False})
    return result


async def _generate_and_save(node_id: str, title: str, phase: str) -> dict:
    prompt = LESSON_PROMPT.format(title=title)
    raw = await chat_once([
        {"role": "system", "content": "你是 Python 编程老师，只返回合法 JSON，不返回任何其他内容。"},
        {"role": "user",   "content": prompt},
    ])
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        sections = json.loads(raw[start:end])
    except Exception:
        raise HTTPException(status_code=502, detail=f"AI 返回格式错误: {raw[:200]}")
    ts = now_iso()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO lessons (node_id, title, phase, sections_json, generated_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(node_id) DO UPDATE SET"
            "   title=excluded.title, phase=excluded.phase,"
            "   sections_json=excluded.sections_json, generated_at=excluded.generated_at",
            (node_id, title, phase, json.dumps(sections, ensure_ascii=False), ts),
        )
    return {"node_id": node_id, "title": title, "phase": phase, "sections": sections, "generated_at": ts}


@router.post("/lessons")
async def create_lesson(body: LessonCreate, _: str = Depends(require_admin)):
    node_id = body.node_id.strip().replace(" ", "_")
    if not node_id:
        raise HTTPException(status_code=400, detail="node_id 不能为空")
    return await _generate_and_save(node_id, body.title.strip(), body.phase.strip())


@router.post("/lessons/generate/{node_id}")
async def generate_lesson(node_id: str, _: str = Depends(require_admin)):
    meta = NODE_META.get(node_id)
    if meta:
        title, phase = meta["title"], meta["phase"]
    else:
        with get_db() as conn:
            row = conn.execute("SELECT title, phase FROM lessons WHERE node_id=?", (node_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="节点不存在")
        title, phase = row["title"], row["phase"]
    return await _generate_and_save(node_id, title, phase)


QUESTION_GEN_PROMPT = """请为 Python 测评生成一道{topic}主题的选择题，面向初学者。
严格按以下 JSON 格式返回，不要有任何其他文字：
{{"text":"题目","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"正确选项字母(A/B/C/D)","difficulty":1或2}}
difficulty: 1=简单, 2=中等"""


@router.get("/questions")
async def admin_list_questions(_: str = Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, topic, text, options_json, answer, difficulty, created_at FROM questions ORDER BY id"
        ).fetchall()
    return [
        {**dict(r), "options": json.loads(r["options_json"])}
        for r in rows
    ]


@router.post("/questions")
async def admin_create_question(body: QuestionCreate, _: str = Depends(require_admin)):
    ts = now_iso()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO questions (topic, text, options_json, answer, difficulty, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (body.topic, body.text, json.dumps(body.options, ensure_ascii=False),
             body.answer.upper(), body.difficulty, ts),
        )
        qid = cur.lastrowid
    return {"id": qid, "topic": body.topic, "text": body.text,
            "options": body.options, "answer": body.answer.upper(),
            "difficulty": body.difficulty, "created_at": ts}


@router.post("/questions/generate")
async def admin_generate_question(
    topic: str = "variables", _: str = Depends(require_admin)
):
    prompt = QUESTION_GEN_PROMPT.format(topic=topic)
    raw = await chat_once([
        {"role": "system", "content": "只返回合法 JSON，不返回任何其他内容。"},
        {"role": "user",   "content": prompt},
    ])
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        q = json.loads(raw[start:end])
    except Exception:
        raise HTTPException(status_code=502, detail=f"AI 返回格式错误: {raw[:200]}")
    ts = now_iso()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO questions (topic, text, options_json, answer, difficulty, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (topic, q["text"], json.dumps(q["options"], ensure_ascii=False),
             q["answer"].upper(), q.get("difficulty", 1), ts),
        )
        qid = cur.lastrowid
    return {"id": qid, "topic": topic, **q, "created_at": ts}


@router.put("/questions/{qid}")
async def admin_update_question(qid: int, body: QuestionUpdate, _: str = Depends(require_admin)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "options" in updates:
        updates["options_json"] = json.dumps(updates.pop("options"), ensure_ascii=False)
    if "answer" in updates:
        updates["answer"] = updates["answer"].upper()
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with get_db() as conn:
            conn.execute(f"UPDATE questions SET {set_clause} WHERE id = ?",
                         [*updates.values(), qid])
    with get_db() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")
    data = dict(row)
    data["options"] = json.loads(data.pop("options_json"))
    return data


@router.delete("/questions/{qid}")
async def admin_delete_question(qid: int, _: str = Depends(require_admin)):
    with get_db() as conn:
        conn.execute("DELETE FROM questions WHERE id = ?", (qid,))
    return {"deleted": qid}


@router.get("/models")
async def list_models(_: str = Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, display_name, model_name, api_key, base_url, is_active, created_at FROM models ORDER BY id"
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        key = d["api_key"]
        d["api_key_masked"] = ("*" * (len(key) - 4) + key[-4:]) if len(key) >= 4 else "****"
        result.append(d)
    return result


@router.post("/models")
async def create_model(body: ModelCreate, _: str = Depends(require_admin)):
    ts = now_iso()
    with get_db() as conn:
        # 若当前无激活模型，新建时自动激活
        has_active = conn.execute("SELECT 1 FROM models WHERE is_active = 1").fetchone()
        is_active = 0 if has_active else 1
        cur = conn.execute(
            "INSERT INTO models (display_name, model_name, api_key, base_url, is_active, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (body.display_name.strip(), body.model_name.strip(),
             body.api_key.strip(), body.base_url.strip(), is_active, ts),
        )
        mid = cur.lastrowid
    return {"id": mid, "display_name": body.display_name, "model_name": body.model_name,
            "base_url": body.base_url, "is_active": is_active, "created_at": ts}


@router.put("/models/{mid}")
async def update_model(mid: int, body: ModelUpdate, _: str = Depends(require_admin)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with get_db() as conn:
            conn.execute(f"UPDATE models SET {set_clause} WHERE id = ?", [*updates.values(), mid])
    with get_db() as conn:
        row = conn.execute("SELECT * FROM models WHERE id = ?", (mid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Model not found")
    d = dict(row)
    key = d["api_key"]
    d["api_key_masked"] = ("*" * (len(key) - 4) + key[-4:]) if len(key) >= 4 else "****"
    return d


@router.delete("/models/{mid}")
async def delete_model(mid: int, _: str = Depends(require_admin)):
    with get_db() as conn:
        row = conn.execute("SELECT is_active FROM models WHERE id = ?", (mid,)).fetchone()
        if row and row["is_active"]:
            raise HTTPException(status_code=400, detail="不能删除当前激活的模型，请先切换到其他模型")
        conn.execute("DELETE FROM models WHERE id = ?", (mid,))
    return {"deleted": mid}


@router.post("/models/{mid}/activate")
async def activate_model(mid: int, _: str = Depends(require_admin)):
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM models WHERE id = ?", (mid,)).fetchone():
            raise HTTPException(status_code=404, detail="Model not found")
        conn.execute("UPDATE models SET is_active = 0")
        conn.execute("UPDATE models SET is_active = 1 WHERE id = ?", (mid,))
    return {"activated": mid}


@router.delete("/lessons/{node_id}")
async def delete_lesson(node_id: str, _: str = Depends(require_admin)):
    if node_id in NODE_META:
        raise HTTPException(status_code=400, detail="内置节点不能删除，只能重新生成")
    with get_db() as conn:
        conn.execute("DELETE FROM lessons WHERE node_id = ?", (node_id,))
    return {"deleted": node_id}
