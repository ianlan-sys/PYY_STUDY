# backend/tests/test_assessment_router.py
import pytest

ALL_WRONG = [{"question_id": i, "answer": "Z"} for i in range(1, 11)]
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

@pytest.mark.asyncio
async def test_all_wrong_is_beginner(client):
    response = await client.post("/assessment/grade", json={"answers": ALL_WRONG})
    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "beginner"
    assert data["score"] == 0
    assert data["unlock_nodes"] == ["beginner_syntax_1"]

@pytest.mark.asyncio
async def test_all_correct_is_advanced(client):
    response = await client.post("/assessment/grade", json={"answers": ALL_CORRECT})
    assert response.status_code == 200
    data = response.json()
    assert data["level"] == "advanced"
    assert "beginner_syntax_3" in data["unlock_nodes"]
