"""Answers /v1/chat/completions by keyword. It makes no decisions worth testing: it only drives the agent loop."""
from __future__ import annotations

import json
import os
from datetime import date
from typing import Literal

from fastapi import FastAPI, Request

from mock_football_api.data import CLUBS, generate_dataset

ALIASES = {"milan": "AC Milan", "roma": "AS Roma", "verona": "Hellas Verona"}


def _clubs_in(text: str) -> list[str]:
    lowered = text.lower()
    found = [(lowered.index(club.lower()), club) for club in CLUBS if club.lower() in lowered]
    found += [
        (lowered.index(alias), club)
        for alias, club in ALIASES.items()
        if alias in lowered and club.lower() not in lowered
    ]
    return [club for _, club in sorted(found)]


def _tool_call(question: str) -> tuple[str, dict]:
    lowered = question.lower()
    clubs = _clubs_in(question)
    match_id = None
    if len(clubs) >= 2:
        fixture = generate_dataset(42, date.today()).find_fixture(clubs[0], clubs[1])
        if fixture:
            match_id = str(fixture["fixture"]["id"])
    if match_id and any(word in lowered for word in ("odds", "quote")):
        return "get_match_odds", {"match_id": match_id}
    if match_id and any(word in lowered for word in ("predict", "pronostic")):
        return "get_predictions", {"match_id": match_id}
    if clubs and "stat" in lowered:
        return "get_team_stats", {"team_id": str(CLUBS.index(clubs[0]) + 1), "season": "2025"}
    return "search_matches", {"team_name": clubs[0]} if clubs else {}


def _completion(message: dict) -> dict:
    return {
        "id": "mock-completion",
        "object": "chat.completion",
        "model": "mock-llm",
        "choices": [{"index": 0, "message": {"role": "assistant", **message}, "finish_reason": "stop"}],
    }


def create_app(mode: Literal["normal", "loop"] | None = None) -> FastAPI:
    app = FastAPI(title="Mock LLM")
    chosen = mode or os.getenv("MOCK_LLM_MODE", "normal")
    app.state.requests = 0

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        app.state.requests += 1
        messages = (await request.json())["messages"]
        tool_results = [m for m in messages if m["role"] == "tool"]
        if tool_results and chosen != "loop":
            return _completion({"content": f"Mock LLM reply, based on the tool result: {tool_results[-1]['content'][:600]}"})
        question = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        name, arguments = _tool_call(question)
        call_id = f"call_{app.state.requests}"
        call = {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}
        return _completion({"content": None, "tool_calls": [call]})

    @app.get("/__requests")
    def requests_seen():
        return {"requests": app.state.requests}

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    return app
