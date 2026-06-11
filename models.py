# backend/models.py
from pydantic import BaseModel
from typing import Literal, Optional

class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    user_level: Literal["beginner", "intermediate", "advanced"]
    current_node: str  # e.g. "beginner_syntax_1"
    mode: Literal["chat", "code", "error"] = "chat"

class AssessmentAnswer(BaseModel):
    question_id: int
    answer: str  # "A" | "B" | "C" | "D"

class AssessmentRequest(BaseModel):
    answers: list[AssessmentAnswer]  # 10 items

class AssessmentResult(BaseModel):
    level: Literal["beginner", "intermediate", "advanced"]
    score: int  # 0-15 (easy=1pt, hard=2pt per question)
    unlock_nodes: list[str]

class UserInit(BaseModel):
    openid: str
    nickname: str = "学习者"
    avatar_url: str = ""

class UserUpdate(BaseModel):
    level: Optional[Literal["beginner", "intermediate", "advanced"]] = None
    points: Optional[int] = None

class UserProfile(BaseModel):
    openid: str
    nickname: str
    avatar_url: str
    level: str
    points: int
    streak_days: int
    last_active_date: Optional[str] = None
    created_at: str

class ProgressItem(BaseModel):
    node_id: str
    status: Literal["locked", "learning", "done"]
    completed_at: Optional[str] = None

class SessionSave(BaseModel):
    openid: str
    mode: Literal["chat", "code", "error"]
    first_question: str
    messages: list[Message]
    message_count: int

class SessionSummary(BaseModel):
    id: int
    mode: str
    first_question: str
    message_count: int
    created_at: str

class SessionDetail(SessionSummary):
    openid: str
    messages: list[Message]
