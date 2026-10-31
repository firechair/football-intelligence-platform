import json
from datetime import date

from fastapi.testclient import TestClient

from mock_football_api.data import generate_dataset
from mock_llm.app import create_app

QUESTION = "What are the odds for Inter vs Milan?"


def ask(client, messages):
    response = client.post("/v1/chat/completions", json={"model": "mock", "messages": messages, "tools": []})
    assert response.status_code == 200
    return response.json()["choices"][0]["message"]


def test_first_turn_returns_tool_call():
    client = TestClient(create_app())
    message = ask(client, [{"role": "user", "content": QUESTION}])
    call = message["tool_calls"][0]
    assert call["function"]["name"] == "get_match_odds"
    arguments = json.loads(call["function"]["arguments"])
    expected = generate_dataset(42, date.today()).find_fixture("Inter", "AC Milan")
    assert arguments["match_id"] == str(expected["fixture"]["id"])


def test_keywords_choose_the_tool():
    client = TestClient(create_app())
    for question, tool in (
        ("Quote per Inter vs Milan", "get_match_odds"),
        ("Who is predicted to win Inter vs Milan?", "get_predictions"),
        ("Show me the stats of Juventus", "get_team_stats"),
        ("When does Napoli play?", "search_matches"),
    ):
        message = ask(client, [{"role": "user", "content": question}])
        assert message["tool_calls"][0]["function"]["name"] == tool


def test_after_tool_result_returns_text():
    client = TestClient(create_app())
    messages = [
        {"role": "user", "content": QUESTION},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1"}]},
        {"role": "tool", "tool_call_id": "call_1", "content": '{"success": true, "best": 2.1}'},
    ]
    message = ask(client, messages)
    assert "tool_calls" not in message
    assert "2.1" in message["content"]


def test_loop_mode_always_calls_tools():
    client = TestClient(create_app(mode="loop"))
    messages = [
        {"role": "user", "content": QUESTION},
        {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
    ]
    assert ask(client, messages)["tool_calls"]
