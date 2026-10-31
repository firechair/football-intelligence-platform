import asyncio

import pytest

from app.main import app
from app.services.football_api_mapper import FootballAPIMapper
from app.services.intelligent_cache import intelligent_cache

from .test_alerts import add_stats, services_use_test_db  # noqa: F401


def test_rankings_endpoint_reads_stats(client, db_session, services_use_test_db):  # noqa: F811
    assert client.get("/api/v2/bookmakers/rankings").json() == []
    add_stats(db_session)
    names = [row["bookmaker"] for row in client.get("/api/v2/bookmakers/rankings").json()]
    assert names == ["Bookmaker A", "Bookmaker B"]


def test_best_odd_without_data_returns_null(client):
    response = client.get("/api/v2/odds/best/1/1X2")
    assert response.status_code == 200
    assert response.json() is None


def test_best_odd_for_a_market_with_no_cache_is_not_invented(client):
    assert client.get("/api/v2/odds/best/1/1").json() is None


def test_write_endpoints_require_login(client):
    body = {"fixture_id": 1, "market": "1X2", "odds_data": {"Bookmaker A": 2.0}}
    assert client.post("/api/v2/cache/update-odds", json=body).status_code == 401
    assert client.post("/api/v2/alerts/check").status_code == 401


def test_routes_without_a_real_implementation_are_gone():
    paths = set(app.openapi()["paths"])
    assert "/api/v2/users/{user_id}/suggestions" not in paths
    assert "/api/v2/markets/analysis/{fixture_id}" not in paths


def test_mapper_maps_question_to_fixtures_call():
    calls = FootballAPIMapper().map_user_question("Quali partite ci sono oggi di Serie A?")
    assert calls
    assert any("fixtures" in call.endpoint for call in calls)


class SyncRedis:
    """Same interface as the synchronous redis client the cache uses."""

    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def setex(self, key, ttl, value):
        self.data[key] = value

    def keys(self, pattern):
        return list(self.data)

    def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)

    def info(self, section):
        return {"used_memory_human": "1K"} if section == "memory" else {"db0": {"keys": len(self.data)}}


@pytest.fixture
def fake_redis(monkeypatch):
    client = SyncRedis()
    monkeypatch.setattr(intelligent_cache, "redis", client)
    return client


async def test_best_odd_round_trip_through_the_cache(fake_redis, services_use_test_db):  # noqa: F811
    await intelligent_cache.update_best_odds(7, "1", {"Bookmaker A": 2.1, "Bookmaker B": 2.4})
    await asyncio.sleep(0)
    best = await intelligent_cache.get_best_odd(7, "1")
    assert best["bookmaker"] == "Bookmaker B"
    assert best["value"] == 2.4


async def test_cache_stats_with_redis_connected(fake_redis):
    stats = await intelligent_cache.get_cache_stats()
    assert stats["redis_connected"] is True


async def test_rankings_are_also_calculated_when_redis_is_connected(client, db_session, fake_redis, services_use_test_db):  # noqa: F811
    add_stats(db_session)
    names = [row["bookmaker"] for row in client.get("/api/v2/bookmakers/rankings").json()]
    assert names == ["Bookmaker A", "Bookmaker B"]
