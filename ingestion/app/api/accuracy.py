from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models import PredictionAccuracy, FinishedFixtures

router = APIRouter()

@router.get("/test")
async def test_accuracy_endpoint():
    """Endpoint di test per verificare che il modulo sia caricato"""
    return {"success": True, "message": "Accuracy module loaded successfully"}

@router.get("/results")
def get_accuracy_results(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    league_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Recupera i risultati di accuratezza delle predizioni"""
    try:
        query = db.query(PredictionAccuracy)

        if league_id:
            query = query.filter(PredictionAccuracy.league_id == league_id)

        total = query.count()
        results = query.order_by(PredictionAccuracy.evaluated_at.desc())\
                      .offset(offset)\
                      .limit(limit)\
                      .all()

        return {
            "success": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": [
                {
                    "fixture_id": r.fixture_id,
                    "fixture_date": r.fixture_date.isoformat(),
                    "league_name": r.league_name,
                    "home_team": r.home_team,
                    "away_team": r.away_team,
                    "actual_score": f"{r.actual_home_score}-{r.actual_away_score}",
                    "actual_winner": r.actual_winner,
                    "predicted_winner": r.predicted_winner_name,
                    "winner_accuracy": r.winner_accuracy,
                    "goals_accuracy": r.goals_accuracy,
                    "winner_score": float(r.winner_score) if r.winner_score else None,
                    "goals_score": float(r.goals_score) if r.goals_score else None,
                    "overall_score": float(r.overall_score) if r.overall_score else None,
                    "evaluated_at": r.evaluated_at.isoformat()
                }
                for r in results
            ]
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to get accuracy results: {str(e)}"}

@router.get("/statistics/summary")
def get_accuracy_summary(
    days_back: int = Query(30, ge=1, le=365),
    league_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Recupera statistiche riassuntive di accuratezza"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days_back)

        query = db.query(PredictionAccuracy).filter(
            PredictionAccuracy.fixture_date >= cutoff_date
        )

        if league_id:
            query = query.filter(PredictionAccuracy.league_id == league_id)

        results = query.all()

        if not results:
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
                }
            }

        # Calcola statistiche
        winner_correct = sum(1 for r in results if r.winner_accuracy)
        goals_correct = sum(1 for r in results if r.goals_accuracy)

        winner_scores = [float(r.winner_score) for r in results if r.winner_score is not None]
        goals_scores = [float(r.goals_score) for r in results if r.goals_score is not None]
        overall_scores = [float(r.overall_score) for r in results if r.overall_score is not None]

        return {
            "success": True,
            "period_days": days_back,
            "total_predictions": len(results),
            "average_scores": {
                "winner_accuracy": sum(winner_scores) / len(winner_scores) if winner_scores else 0.0,
                "goals_accuracy": sum(goals_scores) / len(goals_scores) if goals_scores else 0.0,
                "overall_accuracy": sum(overall_scores) / len(overall_scores) if overall_scores else 0.0
            },
            "accuracy_counts": {
                "winner_correct": winner_correct,
                "goals_correct": goals_correct,
                "total_predictions": len(results)
            },
            "accuracy_percentages": {
                "winner_accuracy": (winner_correct / len(results)) * 100 if results else 0.0,
                "goals_accuracy": (goals_correct / len(results)) * 100 if results else 0.0
            }
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to get accuracy summary: {str(e)}"}

@router.get("/finished-fixtures")
def get_finished_fixtures(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Recupera l'elenco delle partite finite"""
    try:
        query = db.query(FinishedFixtures)
        total = query.count()

        results = query.order_by(FinishedFixtures.fixture_date.desc())\
                      .offset(offset)\
                      .limit(limit)\
                      .all()

        return {
            "success": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "fixtures": [
                {
                    "fixture_id": f.fixture_id,
                    "fixture_date": f.fixture_date.isoformat(),
                    "league_name": f.league_name,
                    "home_team": f.home_team,
                    "away_team": f.away_team,
                    "score": f"{f.home_score}-{f.away_score}",
                    "winner": f.winner,
                    "total_goals": f.total_goals,
                    "collected_at": f.collected_at.isoformat()
                }
                for f in results
            ]
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to get finished fixtures: {str(e)}"}

@router.post("/collect-results")
async def collect_finished_fixtures(
    days_back: int = Query(7, ge=1, le=30)
):
    """Raccoglie i risultati delle partite finite - versione semplificata"""
    try:
        # Per ora restituiamo un messaggio placeholder
        # TODO: Implementare la logica completa quando tutti gli import funzionano
        return {
            "success": True,
            "message": f"Would collect finished fixtures for {days_back} days back",
            "collected_count": 0,
            "note": "Endpoint disponibile, logica completa in sviluppo"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to collect results: {str(e)}")

@router.post("/evaluate-accuracy")
async def evaluate_predictions_accuracy(
    days_back: int = Query(7, ge=1, le=30)
):
    """Valuta l'accuratezza delle predizioni - versione semplificata"""
    try:
        # Per ora restituiamo un messaggio placeholder
        return {
            "success": True,
            "message": f"Would evaluate accuracy for {days_back} days back",
            "evaluated_count": 0,
            "note": "Endpoint disponibile, logica completa in sviluppo"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate accuracy: {str(e)}")

@router.post("/collect-and-evaluate")
async def collect_and_evaluate_all(
    days_back: int = Query(7, ge=1, le=30)
):
    """Raccoglie risultati e valuta accuratezza - versione semplificata"""
    try:
        # Per ora restituiamo un messaggio placeholder
        return {
            "success": True,
            "message": f"Would collect and evaluate for {days_back} days back",
            "result": {"fixtures_collected": 0, "predictions_evaluated": 0},
            "note": "Endpoint disponibile, logica completa in sviluppo"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to collect and evaluate: {str(e)}")
# Deploy test
# Emergency deploy fix
