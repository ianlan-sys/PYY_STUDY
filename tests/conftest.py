# backend/tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    import database
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.init_db()
    yield db_path


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
