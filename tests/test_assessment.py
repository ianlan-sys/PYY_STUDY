# backend/tests/test_assessment.py
import pytest
from httpx import AsyncClient, ASGITransport
from main import app

# correct answers from routers/assessment.py ANSWER_KEY
ALL_CORRECT = [
    {"question_id": 1, "answer": "A"},
    {"question_id": 2, "answer": "B"},
    {"question_id": 3, "answer": "C"},
    {"question_id": 4, "answer": "A"},
    {"question_id": 5, "answer": "D"},
    {"question_id": 6, "answer": "B"},
    {"question_id": 7, "answer": "A"},
    {"question_id": 8, "answer": "C"},
    {"question_id": 9, "answer": "B"},
    {"question_id": 10, "answer": "D"},
]

ALL_WRONG = [
    {"question_id": i, "answer": "Z"} for i in range(1, 11)
]


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_grade_all_correct_returns_advanced(client):
    resp = await client.post("/assessment/grade", json={"answers": ALL_CORRECT})
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == "advanced"
    assert data["score"] >= 10
    assert "beginner_syntax_1" in data["unlock_nodes"]
    assert "beginner_syntax_3" in data["unlock_nodes"]


@pytest.mark.asyncio
async def test_grade_all_wrong_returns_beginner(client):
    resp = await client.post("/assessment/grade", json={"answers": ALL_WRONG})
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == "beginner"
    assert data["score"] == 0
    assert data["unlock_nodes"] == ["beginner_syntax_1"]


@pytest.mark.asyncio
async def test_grade_intermediate_score(client):
    # answer half correctly (questions 1-5 all correct = easy*5 + hard*0 or mix)
    partial = ALL_CORRECT[:5] + ALL_WRONG[5:]
    resp = await client.post("/assessment/grade", json={"answers": partial})
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] in ("beginner", "intermediate", "advanced")
    assert "level" in data
    assert "unlock_nodes" in data


@pytest.mark.asyncio
async def test_grade_empty_answers(client):
    resp = await client.post("/assessment/grade", json={"answers": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["level"] == "beginner"
    assert data["score"] == 0
