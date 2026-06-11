# backend/tests/test_prompts.py
from services.prompts import build_chat_system_prompt

def test_prompt_contains_level():
    prompt = build_chat_system_prompt("beginner", "beginner_syntax_1")
    assert "零基础" in prompt
    assert "变量" in prompt

def test_prompt_contains_node():
    prompt = build_chat_system_prompt("intermediate", "beginner_syntax_2")
    assert "循环" in prompt
