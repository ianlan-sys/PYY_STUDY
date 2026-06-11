# backend/tests/test_database.py
from database import get_db, init_db


def test_tables_created(test_db):
    with get_db() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"users", "progress", "sessions", "prompts", "config"} <= tables


def test_prompts_seeded(test_db):
    with get_db() as conn:
        keys = {r["key"] for r in conn.execute("SELECT key FROM prompts").fetchall()}
    assert {"chat_base", "code_suffix", "error_suffix"} == keys


def test_seed_is_idempotent(test_db):
    init_db()
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
    assert count == 3
