# backend/services/prompts.py
from database import get_db, DEFAULT_CHAT_BASE, DEFAULT_CODE_SUFFIX, DEFAULT_ERROR_SUFFIX

LEVEL_DESC = {
    "beginner": "完全零基础，刚开始学 Python",
    "intermediate": "了解基本语法，正在学习函数、列表、字典等",
    "advanced": "掌握基础，正在学习面向对象、模块、数据处理等进阶内容",
}

NODE_DESC = {
    "beginner_syntax_1": "Python 变量与基础数据类型",
    "beginner_syntax_2": "条件判断与循环",
    "beginner_syntax_3": "函数定义与调用",
}


def _get_prompt(key: str, default: str) -> str:
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT content FROM prompts WHERE key = ?", (key,)
            ).fetchone()
            return row["content"] if row else default
    except Exception:
        return default


def build_chat_system_prompt(
    user_level: str,
    current_node: str,
    mode: str = "chat",
) -> str:
    level_text = LEVEL_DESC.get(user_level, "Python 学习者")
    node_text = NODE_DESC.get(current_node, current_node)
    base = _get_prompt("chat_base", DEFAULT_CHAT_BASE)
    prompt = base.format(level_text=level_text, node_text=node_text)
    if mode == "code":
        prompt += "\n" + _get_prompt("code_suffix", DEFAULT_CODE_SUFFIX)
    elif mode == "error":
        prompt += "\n" + _get_prompt("error_suffix", DEFAULT_ERROR_SUFFIX)
    return prompt
