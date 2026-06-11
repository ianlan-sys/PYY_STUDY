# backend/database.py
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_db_dir = os.getenv("DB_DIR", "")
DB_PATH = (Path(_db_dir) / "app.db") if _db_dir else (Path(__file__).parent / "app.db")

DEFAULT_CHAT_BASE = (
    "你是一位耐心友善的 Python 编程老师，专门辅导中文学习者。\n"
    "当前学生水平：{level_text}。\n"
    "学生目前正在学习：{node_text}。\n"
    "请根据学生水平回答问题，语言通俗易懂，代码示例简洁。\n"
    "回复使用中文，代码用 Python。"
)
DEFAULT_CODE_SUFFIX = "请逐行解释代码的功能与执行逻辑，包含输出结果。"
DEFAULT_ERROR_SUFFIX = "请分析错误原因，给出修复建议，并附上正确示例代码。"


@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                openid TEXT PRIMARY KEY,
                nickname TEXT NOT NULL DEFAULT '学习者',
                avatar_url TEXT NOT NULL DEFAULT '',
                level TEXT NOT NULL DEFAULT 'beginner',
                points INTEGER NOT NULL DEFAULT 0,
                streak_days INTEGER NOT NULL DEFAULT 0,
                last_active_date TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                openid TEXT NOT NULL REFERENCES users(openid),
                node_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'locked',
                completed_at TEXT,
                UNIQUE(openid, node_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                openid TEXT NOT NULL REFERENCES users(openid),
                mode TEXT NOT NULL DEFAULT 'chat',
                first_question TEXT NOT NULL DEFAULT '',
                messages_json TEXT NOT NULL DEFAULT '[]',
                message_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                key TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                text TEXT NOT NULL,
                options_json TEXT NOT NULL,
                answer TEXT NOT NULL,
                difficulty INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                node_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                phase TEXT NOT NULL DEFAULT '入门',
                sections_json TEXT NOT NULL DEFAULT '[]',
                generated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                api_key TEXT NOT NULL,
                base_url TEXT NOT NULL DEFAULT 'https://api.deepseek.com',
                is_active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        _seed(conn)


DEFAULT_QUESTIONS = [
    (1, "variables", "以下哪个是合法的 Python 变量名？", '["A. 1name","B. name_1","C. name-1","D. name 1"]', "B", 1),
    (2, "variables", "x = 5; x = x + 3 执行后 x 的值是？", '["A. 5","B. 8","C. 3","D. 报错"]', "B", 2),
    (3, "loops",     "for i in range(3) 会循环几次？", '["A. 2次","B. 4次","C. 3次","D. 1次"]', "C", 1),
    (4, "loops",     "while True 语句中，退出循环的关键字是？", '["A. break","B. stop","C. exit","D. end"]', "A", 2),
    (5, "functions", "定义函数的关键字是？", '["A. function","B. func","C. define","D. def"]', "D", 1),
    (6, "functions", "def add(a, b): return a + b; print(add(2, 3)) 输出？", '["A. 23","B. 5","C. 报错","D. None"]', "B", 2),
    (7, "lists",     "lst = [1,2,3]; lst[0] 的值是？", '["A. 1","B. 2","C. 3","D. 报错"]', "A", 1),
    (8, "lists",     "lst = [1,2,3]; lst.append(4) 后 len(lst) 是？", '["A. 3","B. 5","C. 4","D. 报错"]', "C", 2),
    (9, "dicts",     "d = {\"a\": 1}; 访问 d[\"a\"] 的值是？", '["A. a","B. 1","C. None","D. 报错"]', "B", 1),
    (10, "dicts",    "d = {}; d[\"key\"] = \"val\"; d 中有几个键？", '["A. 0","B. 2","C. 报错","D. 1"]', "D", 2),
]


def _seed(conn: sqlite3.Connection) -> None:
    ts = now_iso()
    for qid, topic, text, options, answer, diff in DEFAULT_QUESTIONS:
        conn.execute(
            "INSERT OR IGNORE INTO questions (id, topic, text, options_json, answer, difficulty, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (qid, topic, text, options, answer, diff, ts),
        )
    conn.executemany(
        "INSERT OR IGNORE INTO prompts (key, content, updated_at) VALUES (?, ?, ?)",
        [
            ("chat_base", DEFAULT_CHAT_BASE, ts),
            ("code_suffix", DEFAULT_CODE_SUFFIX, ts),
            ("error_suffix", DEFAULT_ERROR_SUFFIX, ts),
        ],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
        [("ai_model", "deepseek-chat", ts)],
    )
