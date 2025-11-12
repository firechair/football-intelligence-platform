from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models import PredictionAccuracy, FinishedFixtures
from app.utils.football_api import football_api

router = APIRouter()

@router.get("/test")
async def test_accuracy_endpoint():
    """Endpoint di test per verificare che il modulo sia caricato"""
    return {"success": True, "message": "Accuracy module loaded successfully"}

@router.get("/results")
def get_accuracy_results(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Recupera i risultati di accuratezza delle predizioni - versione semplificata"""
    return {
        "success": True,
        "total": 0,
        "limit": limit,
        "offset": offset,
        "results": [],
        "note": "Dati non ancora disponibili - attendere raccolta"
    }

@router.get("/statistics/summary")
def get_accuracy_summary(
    days_back: int = Query(30, ge=1, le=365)
):
    """Recupera statistiche riassuntive di accuratezza - versione semplificata"""
    return {
        "success": True,
        "period_days": days_back,
        "total_predictions": 0,
        "average_scores": {
            "winner_accuracy": 0.0,
            "goals_accuracy": 0.0,
            "overall_accuracy": 0.0
        },
        "accuracy_counts": {
            "winner_correct": 0,
            "goals_correct": 0,
            "total_predictions": 0
        },
        "note": "Statistiche non ancora disponibili"
    }

@router.get("/finished-fixtures")
def get_finished_fixtures(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Recupera l'elenco delle partite finite - versione semplificata"""
    return {
        "success": True,
        "total": 0,
        "limit": limit,
        "offset": offset,
        "fixtures": [],
        "note": "Partite finite non ancora raccolte"
    }

@router.post("/collect")
def collect_finished_fixtures():
    """Raccoglie i risultati delle partite finite - versione minima"""
    return {
        "success": True,
        "message": "Collect endpoint working",
        "collected_count": 0
    }

@router.post("/evaluate")
def evaluate_predictions_accuracy():
    """Valuta l'accuratezza delle predizioni - versione minima"""
    return {
        "success": True,
        "message": "Evaluate endpoint working",
        "evaluated_count": 0
    }

@router.post("/collect-and-evaluate")
async def collect_and_evaluate_all(
    days_back: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """Raccoglie risultati partite finite e valuta accuratezza predizioni"""
    try:
        # 1. Raccogli partite finite dall'API
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        finished_fixtures = await football_api.get_finished_fixtures_by_date_range(
            start_date_str, end_date_str, status="FT"
        )

        collected_count = 0
        for fixture_data in finished_fixtures:
            try:
                fixture_id = fixture_data["fixture"]["id"]

                # Controlla se già esiste
                existing = db.query(FinishedFixtures).filter(
                    FinishedFixtures.fixture_id == fixture_id
                ).first()

                if not existing:
                    # Salva la partita finita
                    fixture = fixture_data["fixture"]
                    teams = fixture_data["teams"]
                    goals = fixture_data["goals"]
                    score = fixture_data["score"]

                    # Determina vincitore
                    winner = None
                    if goals["home"] > goals["away"]:
                        winner = "home"
                    elif goals["away"] > goals["home"]:
                        winner = "away"
                    else:
                        winner = "draw"

                    finished_fixture = FinishedFixtures(
                        fixture_id=fixture_id,
                        fixture_date=datetime.fromisoformat(fixture["date"].replace('Z', '+00:00')),
                        league_id=fixture_data["league"]["id"],
                        league_name=fixture_data["league"]["name"],
                        country_name=fixture_data["league"]["country"],
                        home_team=teams["home"]["name"],
                        away_team=teams["away"]["name"],
                        home_score=goals["home"],
                        away_score=goals["away"],
                        winner=winner,
                        halftime_home_score=score.get("halftime", {}).get("home"),
                        halftime_away_score=score.get("halftime", {}).get("away"),
                        total_goals=goals["home"] + goals["away"]
                    )

                    db.add(finished_fixture)
                    collected_count += 1

            except Exception as e:
                print(f"Error saving fixture {fixture_data.get('fixture', {}).get('id', 'unknown')}: {str(e)}")
                continue

        # Salva le partite finite
        db.commit()

        # 2. Ora valuta l'accuratezza per le partite finite che hanno predizioni
        evaluated_count = 0

        # Trova partite finite con predizioni non ancora valutate
        from app.models.predictions import MatchPredictions

        unvaluated_fixtures = db.query(MatchPredictions.fixture_id).filter(
            MatchPredictions.fixture_id.in_(
                db.query(FinishedFixtures.fixture_id)
            ),
            ~MatchPredictions.fixture_id.in_(
                db.query(PredictionAccuracy.fixture_id)
            )
        ).all()

        for (fixture_id,) in unvaluated_fixtures:
            try:
                # Recupera dati necessari
                finished_fixture = db.query(FinishedFixtures).filter(
                    FinishedFixtures.fixture_id == fixture_id
                ).first()

                prediction = db.query(MatchPredictions).filter(
                    MatchPredictions.fixture_id == fixture_id
                ).first()

                if finished_fixture and prediction:
                    # Calcola accuratezza semplice
                    winner_accuracy = False
                    goals_accuracy = False

                    # Controllo vincitore
                    if prediction.winner_team_name:
                        predicted_team = prediction.winner_team_name.lower()
                        if finished_fixture.winner == "home" and predicted_team in finished_fixture.home_team.lower():
                            winner_accuracy = True
                        elif finished_fixture.winner == "away" and predicted_team in finished_fixture.away_team.lower():
                            winner_accuracy = True
                        elif finished_fixture.winner == "draw" and ("draw" in predicted_team or prediction.win_or_draw):
                            winner_accuracy = True

                    # Controllo under/over
                    if prediction.under_over and finished_fixture.total_goals is not None:
                        if prediction.under_over.lower() == "under" and finished_fixture.total_goals < 2.5:
                            goals_accuracy = True
                        elif prediction.under_over.lower() == "over" and finished_fixture.total_goals > 2.5:
                            goals_accuracy = True

                    # Salva valutazione
                    accuracy_record = PredictionAccuracy(
                        fixture_id=fixture_id,
                        actual_home_score=finished_fixture.home_score,
                        actual_away_score=finished_fixture.away_score,
                        actual_winner=finished_fixture.winner,
                        actual_total_goals=finished_fixture.total_goals,
                        predicted_winner_name=prediction.winner_team_name,
                        predicted_win_or_draw=prediction.win_or_draw,
                        predicted_under_over=prediction.under_over,
                        predicted_goals_home=prediction.goals_home,
                        predicted_goals_away=prediction.goals_away,
                        prediction_advice=prediction.advice,
                        winner_accuracy=winner_accuracy,
                        goals_accuracy=goals_accuracy,
                        winner_score=100.0 if winner_accuracy else 0.0,
                        goals_score=100.0 if goals_accuracy else 0.0,
                        overall_score=(100.0 if winner_accuracy else 0.0 + 100.0 if goals_accuracy else 0.0) / 2,
                        fixture_date=finished_fixture.fixture_date,
                        league_id=finished_fixture.league_id,
                        league_name=finished_fixture.league_name,
                        home_team=finished_fixture.home_team,
                        away_team=finished_fixture.away_team,
                        prediction_collected_at=prediction.collected_at
                    )

                    db.add(accuracy_record)
                    evaluated_count += 1

            except Exception as e:
                print(f"Error evaluating fixture {fixture_id}: {str(e)}")
                continue

        db.commit()

        return {
            "success": True,
            "message": f"Collected {collected_count} fixtures and evaluated {evaluated_count} predictions",
            "result": {
                "fixtures_collected": collected_count,
                "predictions_evaluated": evaluated_count
            }
        }

    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": f"Failed to collect and evaluate: {str(e)}",
            "result": {"fixtures_collected": 0, "predictions_evaluated": 0}
        }
# Deploy test
# Emergency deploy fix
