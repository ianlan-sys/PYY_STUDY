# backend/database.py
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_db_dir = os.getenv("DB_DIR", "")
DB_PATH = (Path(_db_dir) / "app.db") if _db_dir else (Path(__file__).parent / "app.db")

# 微信云托管自动注入 MYSQL_* 环境变量；存在 MYSQL_ADDRESS 即走 MySQL，否则走本地 SQLite。
MYSQL_ADDRESS = os.getenv("MYSQL_ADDRESS", "")          # host:port
MYSQL_USERNAME = os.getenv("MYSQL_USERNAME", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "wixi_app")


def use_mysql() -> bool:
    return bool(MYSQL_ADDRESS)


DEFAULT_CHAT_BASE = (
    "你是一位耐心友善的 Python 编程老师，专门辅导中文学习者。\n"
    "当前学生水平：{level_text}。\n"
    "学生目前正在学习：{node_text}。\n"
    "请根据学生水平回答问题，语言通俗易懂，代码示例简洁。\n"
    "回复使用中文，代码用 Python。"
)
DEFAULT_CODE_SUFFIX = "请逐行解释代码的功能与执行逻辑，包含输出结果。"
DEFAULT_ERROR_SUFFIX = "请分析错误原因，给出修复建议，并附上正确示例代码。"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# SQLite -> MySQL 方言翻译与兼容层
# 目标：让 routers/services 里原样的 SQLite SQL（? 占位符、INSERT OR IGNORE、
# ON CONFLICT...DO UPDATE、sqlite3.Row 行访问）无需改动即可跑在 MySQL 上。
# --------------------------------------------------------------------------
_RE_INSERT_OR_IGNORE = re.compile(r"INSERT\s+OR\s+IGNORE", re.IGNORECASE)
_RE_INSERT_OR_REPLACE = re.compile(r"INSERT\s+OR\s+REPLACE", re.IGNORECASE)
_RE_ON_CONFLICT = re.compile(r"ON\s+CONFLICT\s*\([^)]*\)\s+DO\s+UPDATE\s+SET", re.IGNORECASE)
_RE_EXCLUDED = re.compile(r"\bexcluded\.(\w+)", re.IGNORECASE)
# 仅给小写列名 key 加反引号（KEY 是 MySQL 保留字）。大小写敏感，避免误伤生成的
# "ON DUPLICATE KEY UPDATE" 里的大写 KEY；\b 保证不匹配 api_key 等。
_RE_KEY_COL = re.compile(r"\bkey\b")


def translate_sql(sql: str) -> str:
    sql = _RE_INSERT_OR_IGNORE.sub("INSERT IGNORE", sql)
    sql = _RE_INSERT_OR_REPLACE.sub("REPLACE", sql)
    sql = _RE_ON_CONFLICT.sub("ON DUPLICATE KEY UPDATE", sql)
    sql = _RE_EXCLUDED.sub(r"VALUES(\1)", sql)
    sql = _RE_KEY_COL.sub("`key`", sql)
    sql = sql.replace("?", "%s")
    return sql


class _Row:
    """兼容 sqlite3.Row：同时支持 row[0] 索引和 row['col'] 键名，dict(row) 可转字典。"""
    __slots__ = ("_d", "_vals")

    def __init__(self, d):
        self._d = d
        self._vals = list(d.values())

    def __getitem__(self, k):
        if isinstance(k, int):
            return self._vals[k]
        return self._d[k]

    def keys(self):
        return list(self._d.keys())

    def get(self, k, default=None):
        return self._d.get(k, default)

    def __iter__(self):
        return iter(self._vals)

    def __len__(self):
        return len(self._vals)

    def __contains__(self, k):
        return k in self._d


class _MySQLCursor:
    def __init__(self, cur):
        self._cur = cur

    def fetchone(self):
        r = self._cur.fetchone()
        return _Row(r) if r is not None else None

    def fetchall(self):
        return [_Row(r) for r in self._cur.fetchall()]

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount


class _MySQLConn:
    """包装 pymysql 连接，提供 sqlite3.Connection 风格的 .execute()/.executemany()。"""
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        cur = self._conn.cursor()
        cur.execute(translate_sql(sql), params)
        return _MySQLCursor(cur)

    def executemany(self, sql, seq_of_params):
        cur = self._conn.cursor()
        cur.executemany(translate_sql(sql), list(seq_of_params))
        return _MySQLCursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def _mysql_connect(database):
    import pymysql
    host, _, port = MYSQL_ADDRESS.partition(":")
    return pymysql.connect(
        host=host,
        port=int(port) if port else 3306,
        user=MYSQL_USERNAME,
        password=MYSQL_PASSWORD,
        database=database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


@contextmanager
def get_db():
    if use_mysql():
        raw = _mysql_connect(MYSQL_DATABASE)
        conn = _MySQLConn(raw)
        try:
            yield conn
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()
    else:
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


# --------------------------------------------------------------------------
# 建表
# --------------------------------------------------------------------------
_SQLITE_SCHEMA = [
    """
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
    """,
    """
    CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        openid TEXT NOT NULL REFERENCES users(openid),
        node_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'locked',
        completed_at TEXT,
        UNIQUE(openid, node_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        openid TEXT NOT NULL REFERENCES users(openid),
        mode TEXT NOT NULL DEFAULT 'chat',
        first_question TEXT NOT NULL DEFAULT '',
        messages_json TEXT NOT NULL DEFAULT '[]',
        message_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS prompts (
        key TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        text TEXT NOT NULL,
        options_json TEXT NOT NULL,
        answer TEXT NOT NULL,
        difficulty INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS lessons (
        node_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        phase TEXT NOT NULL DEFAULT '入门',
        sections_json TEXT NOT NULL DEFAULT '[]',
        generated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        display_name TEXT NOT NULL,
        model_name TEXT NOT NULL,
        api_key TEXT NOT NULL,
        base_url TEXT NOT NULL DEFAULT 'https://api.deepseek.com',
        is_active INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
]

# MySQL 版：TEXT 主键改 VARCHAR(带长度)，AUTOINCREMENT→AUTO_INCREMENT，保留字 key 加反引号；
# 长文本/JSON 列用 LONGTEXT（所有 INSERT 都显式提供其值，无需默认值）。
_MYSQL_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        openid VARCHAR(128) PRIMARY KEY,
        nickname VARCHAR(255) NOT NULL DEFAULT '学习者',
        avatar_url VARCHAR(512) NOT NULL DEFAULT '',
        level VARCHAR(32) NOT NULL DEFAULT 'beginner',
        points INT NOT NULL DEFAULT 0,
        streak_days INT NOT NULL DEFAULT 0,
        last_active_date VARCHAR(32),
        created_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS progress (
        id INT PRIMARY KEY AUTO_INCREMENT,
        openid VARCHAR(128) NOT NULL,
        node_id VARCHAR(128) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'locked',
        completed_at VARCHAR(64),
        UNIQUE KEY uniq_openid_node (openid, node_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id INT PRIMARY KEY AUTO_INCREMENT,
        openid VARCHAR(128) NOT NULL,
        mode VARCHAR(32) NOT NULL DEFAULT 'chat',
        first_question TEXT NOT NULL,
        messages_json LONGTEXT NOT NULL,
        message_count INT NOT NULL DEFAULT 0,
        created_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS prompts (
        `key` VARCHAR(128) PRIMARY KEY,
        content LONGTEXT NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS config (
        `key` VARCHAR(128) PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS questions (
        id INT PRIMARY KEY AUTO_INCREMENT,
        topic VARCHAR(64) NOT NULL,
        text TEXT NOT NULL,
        options_json LONGTEXT NOT NULL,
        answer VARCHAR(255) NOT NULL,
        difficulty INT NOT NULL DEFAULT 1,
        created_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS lessons (
        node_id VARCHAR(128) PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        phase VARCHAR(32) NOT NULL DEFAULT '入门',
        sections_json LONGTEXT NOT NULL,
        generated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS models (
        id INT PRIMARY KEY AUTO_INCREMENT,
        display_name VARCHAR(255) NOT NULL,
        model_name VARCHAR(255) NOT NULL,
        api_key VARCHAR(512) NOT NULL,
        base_url VARCHAR(512) NOT NULL DEFAULT 'https://api.deepseek.com',
        is_active INT NOT NULL DEFAULT 0,
        created_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def _ensure_mysql_database() -> None:
    """连接到 server（不指定库），确保目标库存在。"""
    raw = _mysql_connect(None)
    try:
        with raw.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        raw.commit()
    finally:
        raw.close()


def init_db() -> None:
    if use_mysql():
        _ensure_mysql_database()
        with get_db() as conn:
            for ddl in _MYSQL_SCHEMA:
                conn.execute(ddl)
            _seed(conn)
    else:
        with get_db() as conn:
            for ddl in _SQLITE_SCHEMA:
                conn.execute(ddl)
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


def _seed(conn) -> None:
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
