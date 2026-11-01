from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db

router = APIRouter()

@router.get("/results")
def get_accuracy_results(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Recupera i risultati di accuratezza delle predizioni - versione con dati reali"""
    try:
        from app.models.accuracy_tracking import PredictionAccuracy, FinishedFixtures
        from sqlalchemy import desc

        # Query per ottenere risultati con join a finished fixtures
        results = db.query(
            PredictionAccuracy,
            FinishedFixtures.home_score,
            FinishedFixtures.away_score,
            FinishedFixtures.winner
        ).join(
            FinishedFixtures,
            PredictionAccuracy.fixture_id == FinishedFixtures.fixture_id
        ).order_by(
            desc(PredictionAccuracy.evaluated_at)
        ).limit(limit).offset(offset).all()

        # Formatta i risultati
        formatted_results = []
        for pred, home_score, away_score, actual_winner in results:
            actual_score = f"{home_score}-{away_score}" if home_score is not None and away_score is not None else "N/A"

            formatted_results.append({
                "fixture_id": pred.fixture_id,
                "fixture_date": pred.fixture_date.isoformat() if pred.fixture_date else None,
                "league_name": pred.league_name or "N/A",
                "home_team": pred.home_team or "N/A",
                "away_team": pred.away_team or "N/A",
                "actual_score": actual_score,
                "actual_winner": actual_winner or "N/A",
                "predicted_winner": pred.predicted_winner_name or "N/A",
                "predicted_win_or_draw": pred.predicted_win_or_draw,
                "winner_accuracy": pred.winner_accuracy,
                "goals_accuracy": pred.goals_accuracy,
                "winner_score": float(pred.winner_score) if pred.winner_score else 0.0,
                "goals_score": float(pred.goals_score) if pred.goals_score else 0.0,
                "overall_score": float(pred.overall_score) if pred.overall_score else 0.0,
                "evaluated_at": pred.evaluated_at.isoformat() if pred.evaluated_at else None
            })

        # Conta totale risultati
        total_count = db.query(PredictionAccuracy).count()

        return {
            "success": True,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "results": formatted_results
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "total": 0,
            "limit": limit,
            "offset": offset,
            "results": []
        }

@router.get("/statistics/summary")
def get_accuracy_summary(
    days_back: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Recupera statistiche riassuntive di accuratezza - versione con dati reali"""
    try:
        from app.models.accuracy_tracking import PredictionAccuracy
        from datetime import datetime, timedelta

        # Calcola la data di inizio
        start_date = datetime.now() - timedelta(days=days_back)

        # Query per ottenere statistiche reali
        predictions = db.query(PredictionAccuracy).filter(
            PredictionAccuracy.evaluated_at >= start_date
        ).all()

        if not predictions:
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
                "note": "Nessuna valutazione disponibile nel periodo richiesto"
            }

        # Calcola statistiche
        total_predictions = len(predictions)
        winner_correct = sum(1 for p in predictions if p.winner_accuracy)
        goals_correct = sum(1 for p in predictions if p.goals_accuracy)

        winner_accuracy = (winner_correct / total_predictions * 100) if total_predictions > 0 else 0.0
        goals_accuracy = (goals_correct / total_predictions * 100) if total_predictions > 0 else 0.0
        overall_accuracy = ((winner_correct + goals_correct) / (total_predictions * 2) * 100) if total_predictions > 0 else 0.0

        return {
            "success": True,
            "period_days": days_back,
            "total_predictions": total_predictions,
            "average_scores": {
                "winner_accuracy": round(winner_accuracy, 2),
                "goals_accuracy": round(goals_accuracy, 2),
                "overall_accuracy": round(overall_accuracy, 2)
            },
            "accuracy_counts": {
                "winner_correct": winner_correct,
                "goals_correct": goals_correct,
                "total_predictions": total_predictions
            },
            "accuracy_percentages": {
                "winner_accuracy": round(winner_accuracy, 2),
                "goals_accuracy": round(goals_accuracy, 2)
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
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
            }
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

@router.post("/collect-and-evaluate")
async def collect_and_evaluate_all(db: Session = Depends(get_db)):
    """Valuta l'accuratezza delle predizioni - versione con logica reale"""
    try:
        from app.services.accuracy_evaluator import PredictionAccuracyEvaluator

        evaluator = PredictionAccuracyEvaluator(db)
        result = await evaluator.collect_and_evaluate_all()

        return {
            "success": True,
            "message": f"Collected {result.get('fixtures_collected', 0)} fixtures and evaluated {result.get('predictions_evaluated', 0)} predictions",
            "result": result
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Evaluation failed: {str(e)}",
            "result": {
                "fixtures_collected": 0,
                "predictions_evaluated": 0,
                "error": str(e)
            }
        }
