"""AI / Text-to-SQL tests — 对应第一版.md Section 18 V1.1"""
from unittest.mock import MagicMock, patch

import pytest
from engine.ai import search_demo_sql, generate_sql, DEMO_TRANSLATIONS
from engine.errors import AIServiceError


# ============================================================
# search_demo_sql — 离线模式（无 API key）
# ============================================================

def test_offline_exact_match() -> None:
    result = search_demo_sql("所有用户")
    assert "SELECT" in result
    assert "users" in result.lower()


def test_offline_fuzzy_match() -> None:
    result = search_demo_sql("统计用户数")
    assert "COUNT" in result.upper()
    assert "users" in result.lower()


def test_offline_unknown_question() -> None:
    result = search_demo_sql("火星上有什么东西")
    assert "SELECT" in result
    assert "LIMIT 10" in result.upper()


def test_offline_all_questions_return_sql() -> None:
    for question, expected_sql in DEMO_TRANSLATIONS.items():
        result = search_demo_sql(question)
        assert "SELECT" in result, f"Key '{question}' did not produce SELECT"


# ============================================================
# generate_sql — 离线模式
# ============================================================

def test_generate_sql_offline_mode(db_session, demo_datasource) -> None:
    result = generate_sql(db_session, demo_datasource.id, "所有用户")
    assert "sql" in result
    assert "guardrail" in result
    assert result["mode"] == "offline"


def test_generate_sql_guardrail_applied(db_session, demo_datasource) -> None:
    result = generate_sql(db_session, demo_datasource.id, "所有用户")
    guard = result["guardrail"]
    assert guard["result"] in ("pass", "warn", "reject")
    assert "safeSql" in guard
    assert "checks" in guard


# ============================================================
# generate_sql — 在线模式（mock httpx）
# ============================================================

def test_generate_sql_online_success(db_session, demo_datasource) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "```sql\nSELECT * FROM users LIMIT 10\n```"}}]
    }

    with patch("engine.ai.httpx.post", return_value=mock_resp):
        result = generate_sql(db_session, demo_datasource.id, "list all users",
                              llm_config={"api_key": "sk-test", "api_base": "https://test/v1",
                                          "model": "gpt-test"})
    assert result["sql"] == "SELECT * FROM users LIMIT 10"
    assert result["mode"] == "online"
    assert result["guardrail"]["result"] in ("pass", "warn", "reject")


def test_generate_sql_online_no_code_fence(db_session, demo_datasource) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "SELECT id, name FROM products LIMIT 20"}}]
    }

    with patch("engine.ai.httpx.post", return_value=mock_resp):
        result = generate_sql(db_session, demo_datasource.id, "list products",
                              llm_config={"api_key": "sk-test"})
    assert "SELECT" in result["sql"]
    assert "products" in result["sql"]
    assert result["mode"] == "online"


def test_generate_sql_online_http_error(db_session, demo_datasource) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("engine.ai.httpx.post", return_value=mock_resp):
        with pytest.raises(AIServiceError, match="LLM API returned an error"):
            generate_sql(db_session, demo_datasource.id, "test question",
                         llm_config={"api_key": "sk-test"})


def test_generate_sql_online_guardrail_reject(db_session, demo_datasource) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "```sql\nDROP TABLE users;\n```"}}]
    }

    with patch("engine.ai.httpx.post", return_value=mock_resp):
        result = generate_sql(db_session, demo_datasource.id, "delete all users",
                              llm_config={"api_key": "sk-test"})
    assert result["guardrail"]["result"] == "reject"
