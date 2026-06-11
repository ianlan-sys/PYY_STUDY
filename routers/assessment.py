# backend/routers/assessment.py
import json
from fastapi import APIRouter
from models import AssessmentRequest, AssessmentResult
from database import get_db

router = APIRouter(prefix="/assessment", tags=["assessment"])

NODE_UNLOCK_RULES = {
    "beginner":     ["beginner_syntax_1"],
    "intermediate": ["beginner_syntax_1", "beginner_syntax_2"],
    "advanced":     ["beginner_syntax_1", "beginner_syntax_2", "beginner_syntax_3"],
}


def _get_answer_key() -> dict:
    with get_db() as conn:
        rows = conn.execute("SELECT id, answer, difficulty FROM questions").fetchall()
    return {r["id"]: {"answer": r["answer"], "difficulty": r["difficulty"]} for r in rows}


@router.get("/questions")
async def get_questions():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, topic, text, options_json FROM questions ORDER BY id"
        ).fetchall()
    return [
        {"id": r["id"], "topic": r["topic"], "text": r["text"],
         "options": json.loads(r["options_json"])}
        for r in rows
    ]


@router.post("/grade", response_model=AssessmentResult)
async def grade_assessment(request: AssessmentRequest):
    answer_key = _get_answer_key()
    max_score = sum(v["difficulty"] for v in answer_key.values())
    score = sum(
        answer_key[a.question_id]["difficulty"]
        for a in request.answers
        if a.question_id in answer_key and a.answer == answer_key[a.question_id]["answer"]
    )
    if max_score > 0 and score >= max_score * 2 / 3:
        level = "advanced"
    elif max_score > 0 and score >= max_score / 3:
        level = "intermediate"
    else:
        level = "beginner"

    # unlock nodes from DB lessons, fall back to static rules
    with get_db() as conn:
        lesson_ids = [r["node_id"] for r in conn.execute(
            "SELECT node_id FROM lessons ORDER BY generated_at"
        ).fetchall()]
    unlock = lesson_ids if lesson_ids else NODE_UNLOCK_RULES.get(level, [])
    if level == "beginner" and lesson_ids:
        unlock = lesson_ids[:1]
    elif level == "intermediate" and lesson_ids:
        unlock = lesson_ids[:2]

    return AssessmentResult(level=level, score=score, unlock_nodes=unlock)
