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


async def _evaluated_fixture(db_session):
    from datetime import datetime

    from app.models import FinishedFixtures, MatchPredictions

    db_session.add(
        FinishedFixtures(
            fixture_id=1,
            fixture_date=datetime.now(),
            league_id=135,
            league_name="Serie A",
            country_name="Italy",
            home_team="Inter",
            away_team="AC Milan",
            home_score=2,
            away_score=0,
            winner="home",
            total_goals=2,
        )
    )
    db_session.add(
        MatchPredictions(
            fixture_id=1,
            fixture_date=datetime.now(),
            winner_team_name="Inter",
            under_over="-3.5",
            win_or_draw=True,
            collected_at=datetime.now(),
        )
    )
    db_session.commit()
    result = await PredictionAccuracyEvaluator(db_session).evaluate_predictions_accuracy(days_back=7)
    assert result["evaluated_count"] == 1


async def test_results_endpoint_lists_evaluated_matches(client, db_session):
    await _evaluated_fixture(db_session)
    body = client.get("/api/v1/accuracy/results").json()
    assert body["success"] is True, body
    row = body["results"][0]
    assert (row["home_team"], row["away_team"], row["league_name"]) == ("Inter", "AC Milan", "Serie A")
    assert row["actual_score"] == "2-0"
    assert row["predicted_winner"] == "Inter"
    assert row["winner_accuracy"] is True


async def test_evaluation_sets_its_own_timestamp(db_session):
    # The migrated table has no server default, unlike the model: without this the summary stays at zero.
    from app.models import PredictionAccuracy

    await _evaluated_fixture(db_session)
    row = db_session.query(PredictionAccuracy).one()
    assert row.evaluated_at is not None


async def test_summary_counts_evaluated_matches(client, db_session):
    await _evaluated_fixture(db_session)
    body = client.get("/api/v1/accuracy/statistics/summary").json()
    assert body["total_predictions"] == 1
    assert body["accuracy_percentages"]["winner_accuracy"] == 100.0


async def test_cleanup_of_evaluated_predictions_runs(db_session):
    from app.services.cleanup_service import cleanup_service

    assert (await cleanup_service._cleanup_evaluated_predictions(db_session))["deleted"] == 0


async def test_fixture_data_for_evaluation_is_read_back(db_session):
    from app.services.cleanup_service import cleanup_service

    await _evaluated_fixture(db_session)
    data = await cleanup_service._get_fixture_data_for_accuracy_evaluation(db_session, 1)
    assert data["home_team"] == "Inter"
