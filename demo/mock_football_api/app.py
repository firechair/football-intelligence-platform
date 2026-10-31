"""Serves the synthetic dataset on the API-Football routes, including its 429 rate limit."""
from __future__ import annotations

import time
from collections import deque
from datetime import date

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from .data import CLUBS, LEAGUE, SEASON, generate_dataset
from .data import team as make_team

CONTROL_PREFIX = "/__"


def _envelope(path: str, params: dict, response) -> dict:
    results = len(response) if isinstance(response, list) else 1
    return {
        "get": path.strip("/").removeprefix("v3/"),
        "parameters": params,
        "errors": [],
        "results": results,
        "paging": {"current": 1, "total": 1},
        "response": response,
    }


def create_app(seed: int = 42, today: date | None = None, rate_limit_per_second: int = 5) -> FastAPI:
    """today=None follows the clock, so the demo works on any day and survives midnight."""
    app = FastAPI(title="Mock football API")
    stats = {"requests": 0, "rejected_429": 0}
    recent: deque[float] = deque()
    current = {"dataset": None}

    def dataset():
        wanted = today or date.today()
        if current["dataset"] is None or current["dataset"].today != wanted:
            current["dataset"] = generate_dataset(seed, wanted)
        return current["dataset"]

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if request.url.path.startswith(CONTROL_PREFIX) or request.url.path == "/health":
            return await call_next(request)
        stats["requests"] += 1
        now = time.monotonic()
        while recent and now - recent[0] >= 1.0:
            recent.popleft()
        if len(recent) >= rate_limit_per_second:
            stats["rejected_429"] += 1
            return JSONResponse(status_code=429, content={"message": "Too many requests"})
        recent.append(now)
        return await call_next(request)

    router = APIRouter()

    @router.get("/status")
    def status(request: Request):
        return _envelope(request.url.path, {}, {"account": {"plan": "demo"}, "requests": dict(stats)})

    @router.get("/fixtures")
    def fixtures(request: Request):
        params = dict(request.query_params)
        rows = dataset().fixtures
        if "id" in params:
            rows = [f for f in rows if f["fixture"]["id"] == int(params["id"])]
        if "date" in params:
            rows = [f for f in rows if f["fixture"]["date"].startswith(params["date"])]
        if "from" in params:
            rows = [f for f in rows if f["fixture"]["date"][:10] >= params["from"]]
        if "to" in params:
            rows = [f for f in rows if f["fixture"]["date"][:10] <= params["to"]]
        if "team" in params:
            team_id = int(params["team"])
            rows = [f for f in rows if team_id in (f["teams"]["home"]["id"], f["teams"]["away"]["id"])]
        if "league" in params:
            rows = [f for f in rows if f["league"]["id"] == int(params["league"])]
        if "status" in params:
            rows = [f for f in rows if f["fixture"]["status"]["short"] == params["status"]]
        if "live" in params:
            rows = []
        return _envelope(request.url.path, params, rows)

    @router.get("/odds")
    def odds(request: Request, fixture: int):
        entry = dataset().odds.get(fixture)
        return _envelope(request.url.path, dict(request.query_params), [entry] if entry else [])

    @router.get("/predictions")
    def predictions(request: Request, fixture: int):
        entry = dataset().predictions.get(fixture)
        return _envelope(request.url.path, dict(request.query_params), [entry] if entry else [])

    @router.get("/teams/statistics")
    def team_statistics(request: Request, team: int):
        return _envelope(request.url.path, dict(request.query_params), dataset().team_stats.get(team, []))

    @router.get("/teams")
    def teams(request: Request, search: str = ""):
        rows = [{"team": make_team(name)} for name in CLUBS if search.lower() in name.lower()]
        return _envelope(request.url.path, dict(request.query_params), rows)

    @router.get("/leagues")
    def leagues(request: Request, search: str = ""):
        rows = [{"league": LEAGUE, "seasons": [{"year": SEASON}]}] if search.lower() in LEAGUE["name"].lower() else []
        return _envelope(request.url.path, dict(request.query_params), rows)

    @app.post("/__finish-today")
    def finish_today():
        """Simulated clock: today's matches get their results, so predictions can be evaluated."""
        current_dataset = dataset()
        todays = [f for f in current_dataset.fixtures if f["fixture"]["date"].startswith(current_dataset.today.isoformat())]
        for fixture in todays:
            current_dataset.finish(fixture)
        return {"finished": len(todays)}

    @app.get("/__stats")
    def get_stats():
        return dict(stats)

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    app.include_router(router)
    app.include_router(router, prefix="/v3")
    return app
