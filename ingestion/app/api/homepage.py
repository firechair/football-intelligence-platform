from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime

from app.core.database import get_db
from app.models.predictions import MatchPredictions
from app.models.odds_tracking import ExtendedOddsHistory, FixtureTrackingStatus

router = APIRouter(prefix="/homepage", tags=["homepage"])




@router.get("/quick-stats")
async def get_quick_stats(db: Session = Depends(get_db)):
    """Stats velocissime per dashboard widgets"""
    now = datetime.now()
    
    # Query ottimizzata con una sola chiamata
    result = db.query(
        func.count(FixtureTrackingStatus.id).label('total_matches'),
        func.count(MatchPredictions.id).label('total_predictions'),
        func.max(ExtendedOddsHistory.collected_at).label('last_update')
    ).outerjoin(
        MatchPredictions, FixtureTrackingStatus.fixture_id == MatchPredictions.fixture_id
    ).outerjoin(
        ExtendedOddsHistory, FixtureTrackingStatus.fixture_id == ExtendedOddsHistory.fixture_id
    ).filter(
        FixtureTrackingStatus.fixture_date > now
    ).first()
    
    return {
        "total_matches": result.total_matches or 0,
        "total_predictions": result.total_predictions or 0,
        "last_update": result.last_update,
        "status": "active"
    }
