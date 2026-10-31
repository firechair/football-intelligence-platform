import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from mock_football_api.app import create_app
from mock_football_api.data import generate_dataset

TODAY = date(2027, 3, 1)


@pytest.fixture
def client():
    return TestClient(create_app(today=TODAY, rate_limit_per_second=10_000))


def fixtures_for(client, **params):
    return client.get("/fixtures", params=params).json()["response"]


def test_envelope_shape(client):
    body = client.get("/fixtures", params={"date": TODAY.isoformat()}).json()
    assert set(body) == {"get", "parameters", "errors", "results", "paging", "response"}
    assert body["results"] == len(body["response"]) > 0
    assert body["paging"] == {"current": 1, "total": 1}


def test_fixtures_follow_today():
    dataset = generate_dataset(seed=42, today=TODAY)
    dates = {date.fromisoformat(f["fixture"]["date"][:10]) for f in dataset.fixtures}
    assert min(dates) >= date(2027, 2, 22)
    assert max(dates) <= date(2027, 3, 11)


def test_past_matches_are_finished_and_future_ones_are_not_started(client):
    yesterday_and_before = fixtures_for(client, **{"from": "2027-02-22", "to": "2027-02-28"})
    assert yesterday_and_before
    assert all(f["fixture"]["status"]["short"] == "FT" for f in yesterday_and_before)
    assert all(isinstance(f["goals"]["home"], int) for f in yesterday_and_before)
    upcoming = fixtures_for(client, **{"from": "2027-03-01", "to": "2027-03-11"})
    assert all(f["fixture"]["status"]["short"] == "NS" for f in upcoming)
    assert all(f["goals"]["home"] is None for f in upcoming)


def test_only_placeholder_bookmakers(client):
    fixture_id = fixtures_for(client, date=TODAY.isoformat())[0]["fixture"]["id"]
    response = client.get("/odds", params={"fixture": fixture_id}).json()["response"]
    names = {b["name"] for entry in response for b in entry["bookmakers"]}
    assert names == {"Bookmaker A", "Bookmaker B", "Bookmaker C"}
    assert all(re.fullmatch(r"Bookmaker [A-C]", name) for name in names)


def test_sixth_request_in_one_second_is_429():
    client = TestClient(create_app(today=TODAY, rate_limit_per_second=5))
    codes = [client.get("/status").status_code for _ in range(6)]
    assert codes == [200, 200, 200, 200, 200, 429]
    assert client.get("/__stats").json()["rejected_429"] == 1


def test_same_seed_same_data():
    assert generate_dataset(seed=42, today=TODAY) == generate_dataset(seed=42, today=TODAY)
    assert generate_dataset(seed=1, today=TODAY) != generate_dataset(seed=42, today=TODAY)


def test_finish_today_turns_todays_matches_into_results(client):
    todays = fixtures_for(client, date=TODAY.isoformat())
    assert client.post("/__finish-today").json()["finished"] == len(todays)
    fixture_id = todays[0]["fixture"]["id"]
    finished = fixtures_for(client, id=fixture_id)[0]
    assert finished["fixture"]["status"]["short"] == "FT"
    assert isinstance(finished["goals"]["home"], int)
    assert finished["score"]["halftime"]["home"] <= finished["goals"]["home"]


def test_prediction_has_the_fields_the_collectors_read(client):
    fixture_id = fixtures_for(client, date=TODAY.isoformat())[0]["fixture"]["id"]
    entry = client.get("/predictions", params={"fixture": fixture_id}).json()["response"][0]
    prediction = entry["predictions"]
    assert prediction["winner"]["name"]
    assert re.fullmatch(r"[+-]\d\.5", prediction["under_over"])
    assert set(prediction["percent"]) == {"home", "draw", "away"}
    assert set(entry["league"]) >= {"id", "name", "country"}
    assert "last_5" in entry["teams"]["home"]


def test_team_search_and_statistics(client):
    team = client.get("/teams", params={"search": "Inter"}).json()["response"][0]["team"]
    assert team["name"] == "Inter"
    stats = client.get("/teams/statistics", params={"team": team["id"], "season": 2025}).json()["response"]
    assert stats["team"]["id"] == team["id"]
    assert stats["goals"]["for"]["total"]["total"] >= 0


def test_also_served_under_v3(client):
    assert client.get("/v3/status").status_code == 200
    assert client.get("/v3/fixtures", params={"date": TODAY.isoformat()}).json()["results"] > 0


def test_inter_milan_is_always_on_today():
    dataset = generate_dataset(seed=42, today=TODAY + timedelta(days=50))
    assert dataset.find_fixture("Inter", "AC Milan") is not None
