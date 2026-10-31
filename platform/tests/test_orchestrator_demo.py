"""Runs the real orchestrator against the mock LLM and the mock football API, over real HTTP."""
import json
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "demo"))

from mock_football_api.app import create_app as create_football_api  # noqa: E402
from mock_llm.app import create_app as create_llm  # noqa: E402

from app.services import function_calling_orchestrator as orchestrator_module  # noqa: E402

QUESTION = "What are the odds for Inter vs Milan?"


def serve(app) -> tuple[str, uvicorn.Server]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            httpx.get(f"{url}/health", timeout=0.2)
            return url, server
        except httpx.TransportError:
            time.sleep(0.05)
    raise RuntimeError("mock did not start")


@pytest.fixture
def live_mocks(monkeypatch):
    servers = []

    def start(llm_mode: str = "normal") -> str:
        football_url, football = serve(create_football_api(rate_limit_per_second=1000))
        llm_url, llm = serve(create_llm(mode=llm_mode))
        servers.extend([football, llm])
        monkeypatch.setenv("FOOTBALL_TOOLS_API_BASE_URL", f"{football_url}/v3")
        monkeypatch.setattr(orchestrator_module, "OPENROUTER_API_URL", f"{llm_url}/v1/chat/completions")
        monkeypatch.setattr(orchestrator_module, "OPENROUTER_API_KEY", "demo")
        return llm_url

    yield start
    for server in servers:
        server.should_exit = True


async def test_agent_uses_odds_tool_and_replies(live_mocks):
    live_mocks()
    result = await orchestrator_module.FunctionCallingOrchestrator().process_message(QUESTION, user_id="demo")
    assert result["tool_calls_made"][0]["tool"] == "get_match_odds"
    assert "error" not in result["metadata"]
    assert "Bookmaker A" in result["reply"]
    arguments = json.loads(result["tool_calls_made"][0]["arguments"])
    assert arguments["match_id"]


async def test_agent_stops_after_max_iterations(live_mocks):
    llm_url = live_mocks(llm_mode="loop")
    result = await orchestrator_module.FunctionCallingOrchestrator().process_message(QUESTION, user_id="demo")
    assert result["metadata"]["error"] == "max_iterations_reached"
    assert httpx.get(f"{llm_url}/__requests").json()["requests"] == 5


async def test_agent_reports_llm_failure(live_mocks, monkeypatch):
    live_mocks()
    monkeypatch.setattr(orchestrator_module, "OPENROUTER_API_URL", "http://127.0.0.1:9/v1/chat/completions")
    result = await orchestrator_module.FunctionCallingOrchestrator().process_message(QUESTION, user_id="demo")
    assert "error" in result["metadata"]
    assert result["tool_calls_made"] == []
