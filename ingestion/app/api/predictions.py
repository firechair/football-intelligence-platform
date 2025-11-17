from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.models.predictions import MatchPredictions

router = APIRouter(prefix="/predictions", tags=["predictions"])

class PredictionResponse(BaseModel):
    fixture_id: int
    fixture_date: datetime
    league_id: Optional[int]
    league_name: Optional[str]
    winner_team_name: Optional[str]
    winner_comment: Optional[str]
    win_or_draw: Optional[bool]
    under_over: Optional[str]
    advice: Optional[str]
    percent_home: Optional[str]
    percent_draw: Optional[str]
    percent_away: Optional[str]
    goals_home: Optional[str]
    goals_away: Optional[str]
    collected_at: datetime
    is_prediction_available: bool

@router.get("/fixture/{fixture_id}", response_model=PredictionResponse)
async def get_fixture_prediction(
    fixture_id: int,
    db: Session = Depends(get_db)
):
    """Recupera la predizione per una partita specifica"""
    
    prediction = db.query(MatchPredictions).filter(
        MatchPredictions.fixture_id == fixture_id
    ).first()
    
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    
    return prediction

@router.get("/upcoming", response_model=List[PredictionResponse])
async def get_upcoming_predictions(
    days_ahead: int = Query(7, ge=1, le=10, description="Days ahead to look"),
    limit: int = Query(50, ge=1, le=200, description="Max predictions to return"),
    league_id: Optional[int] = Query(None, description="Filter by league"),
    db: Session = Depends(get_db)
):
    """Recupera predizioni per le partite future"""

    try:
        future_cutoff = datetime.now() + timedelta(days=days_ahead)

        query = db.query(MatchPredictions).filter(
            MatchPredictions.fixture_date <= future_cutoff,
            MatchPredictions.fixture_date > datetime.now(),
            MatchPredictions.is_prediction_available == True
        )

        if league_id:
            query = query.filter(MatchPredictions.league_id == league_id)

        predictions = query.order_by(MatchPredictions.fixture_date).limit(limit).all()

        return predictions
    except Exception as e:
        # Fallback: return empty list if schema issues
        logging.error(f"Database schema error in predictions: {e}")
        return []

@router.get("/by-league")
async def get_predictions_by_league(
    days_ahead: int = Query(7, ge=1, le=10),
    db: Session = Depends(get_db)
):
    """Recupera predizioni raggruppate per lega"""
    
    future_cutoff = datetime.now() + timedelta(days=days_ahead)
    
    results = db.query(
        MatchPredictions.league_id,
        MatchPredictions.league_name,
        func.count(MatchPredictions.id).label('predictions_count')
    ).filter(
        MatchPredictions.fixture_date <= future_cutoff,
        MatchPredictions.fixture_date > datetime.now(),
        MatchPredictions.is_prediction_available == True
    ).group_by(
        MatchPredictions.league_id, 
        MatchPredictions.league_name
    ).all()
    
    return [
        {
            "league_id": result.league_id,
            "league_name": result.league_name,
            "predictions_count": result.predictions_count
        }
        for result in results
    ]

@router.get("/stats/summary")
async def get_predictions_stats(db: Session = Depends(get_db)):
    """Statistiche generali delle predizioni"""
    
    total_predictions = db.query(MatchPredictions).count()
    available_predictions = db.query(MatchPredictions).filter(
        MatchPredictions.is_prediction_available == True
    ).count()
    
    recent_predictions = db.query(MatchPredictions).filter(
        MatchPredictions.collected_at >= datetime.now() - timedelta(hours=24)
    ).count()
    
    return {
        "total_predictions": total_predictions,
        "available_predictions": available_predictions,
        "recent_predictions_24h": recent_predictions,
        "coverage_rate": f"{(available_predictions/total_predictions*100):.1f}%" if total_predictions > 0 else "0%"
    }
