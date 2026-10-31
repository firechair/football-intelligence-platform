import pytest

from app.main import app
from app.services.accuracy_evaluator import PredictionAccuracyEvaluator


def fixture_data(**overrides):
    data = {
        "actual_winner": "home",
        "actual_total_goals": 2,
        "predicted_winner_name": "Inter",
        "predicted_under_over": None,
        "predicted_win_or_draw": False,
        "predicted_goals_home": None,
        "predicted_goals_away": None,
        "home_team": "Inter",
        "away_team": "Milan",
    }
    return {**data, **overrides}


def accuracy(**overrides):
    return PredictionAccuracyEvaluator(db=None)._calculate_prediction_accuracy(fixture_data(**overrides))


@pytest.mark.parametrize(
    "under_over, total_goals, expected",
    [
        ("-3.5", 2, True),
        ("-3.5", 4, False),
        ("+2.5", 3, True),
        ("+2.5", 2, False),
        ("under", 2, True),
        ("over", 3, True),
        (None, 3, False),
    ],
)
def test_under_over_accepts_the_provider_format(under_over, total_goals, expected):
    result = accuracy(predicted_under_over=under_over, actual_total_goals=total_goals)
    assert result["goals_accuracy"] is expected


@pytest.mark.parametrize(
    "win_or_draw, actual_winner, expected",
    [
        (True, "home", True),  # predicted Inter (home), Inter won
        (True, "draw", True),
        (True, "away", False),  # predicted Inter (home), Inter lost
        (False, "home", True),  # no double chance: only the outright win counts
        (False, "draw", False),
    ],
)
def test_win_or_draw_follows_the_predicted_team(win_or_draw, actual_winner, expected):
    result = accuracy(predicted_win_or_draw=win_or_draw, actual_winner=actual_winner)
    assert result["win_draw_accuracy"] is expected


def test_collect_and_evaluate_runs_the_real_evaluator(client):
    response = client.post("/api/v1/accuracy/collect-and-evaluate")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True, body
    assert body["result"]["predictions_evaluated"] == 0


def test_stub_routes_that_always_reported_success_are_gone():
    paths = {route.path for route in app.routes}
    for stub in ("/api/v1/accuracy/test", "/api/v1/accuracy/collect", "/api/v1/accuracy/evaluate"):
        assert stub not in paths
