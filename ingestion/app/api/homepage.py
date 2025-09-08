from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from typing import List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.database import get_db
from app.models.predictions import MatchPredictions
from app.models.odds_tracking import ExtendedOddsHistory, FixtureTrackingStatus, BookmakerInfo

router = APIRouter(prefix="/homepage", tags=["homepage"])

class HomepageMatch(BaseModel):
    fixture_id: int
    home_team: str
    away_team: str
    fixture_date: datetime
    league_name: str
    
    # Quote principali (1X2)
    best_odds: Dict[str, float] = {}  # {"1": 2.10, "X": 3.20, "2": 3.50}
    
    # Predizioni
    predicted_winner: str = None
    win_probability: str = None

class HomepageStats(BaseModel):
    total_active_matches: int
    total_bookmakers: int
    latest_update: datetime
    predictions_available: int

class HomepageData(BaseModel):
    stats: HomepageStats
    featured_matches: List[HomepageMatch]
    upcoming_matches: List[HomepageMatch]

@router.get("/data", response_model=HomepageData)
async def get_homepage_data(
    featured_limit: int = Query(6, description="Number of featured matches"),
    upcoming_limit: int = Query(20, description="Number of upcoming matches"),
    db: Session = Depends(get_db)
):
    """
    🚀 ENDPOINT OTTIMIZZATO PER HOMEPAGE
    Ritorna tutti i dati necessari in una chiamata
    """
    
    # === STATS GENERALI ===
    now = datetime.now()
    today_plus_7 = now + timedelta(days=7)
    
    # Query ottimizzate
    total_active = db.query(FixtureTrackingStatus).filter(
        and_(
            FixtureTrackingStatus.fixture_date > now,
            FixtureTrackingStatus.fixture_date <= today_plus_7,
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"])
        )
    ).count()
    
    total_bookmakers = db.query(BookmakerInfo).filter(
        BookmakerInfo.is_active == True
    ).count()
    
    latest_odds_update = db.query(func.max(ExtendedOddsHistory.collected_at)).scalar()
    
    predictions_count = db.query(MatchPredictions).filter(
        and_(
            MatchPredictions.fixture_date > now,
            MatchPredictions.is_prediction_available == True
        )
    ).count()
    
    stats = HomepageStats(
        total_active_matches=total_active,
        total_bookmakers=total_bookmakers,
        latest_update=latest_odds_update or now,
        predictions_available=predictions_count
    )
    
    # === FEATURED MATCHES (big leagues, today-tomorrow) ===
    tomorrow = now + timedelta(days=2)
    
    featured_fixtures = db.query(FixtureTrackingStatus).filter(
        and_(
            FixtureTrackingStatus.fixture_date > now,
            FixtureTrackingStatus.fixture_date <= tomorrow,
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"]),
            # Big leagues filter
            FixtureTrackingStatus.league_name.in_([
                "Premier League", "La Liga", "Serie A", "Bundesliga", 
                "Ligue 1", "Champions League", "Europa League"
            ])
        )
    ).order_by(FixtureTrackingStatus.fixture_date).limit(featured_limit).all()
    
    featured_matches = []
    for fixture in featured_fixtures:
        match_data = await _build_match_data(fixture, db)
        featured_matches.append(match_data)
    
    # === UPCOMING MATCHES (next 7 days) ===
    upcoming_fixtures = db.query(FixtureTrackingStatus).filter(
        and_(
            FixtureTrackingStatus.fixture_date > now,
            FixtureTrackingStatus.fixture_date <= today_plus_7,
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"])
        )
    ).order_by(FixtureTrackingStatus.fixture_date).limit(upcoming_limit).all()
    
    upcoming_matches = []
    for fixture in upcoming_fixtures:
        match_data = await _build_match_data(fixture, db)
        upcoming_matches.append(match_data)
    
    return HomepageData(
        stats=stats,
        featured_matches=featured_matches,
        upcoming_matches=upcoming_matches
    )

async def _build_match_data(fixture: FixtureTrackingStatus, db: Session) -> HomepageMatch:
    """Helper per costruire dati match completi"""
    
    # Migliori quote 1X2 (una query per tutte)
    best_odds = {}
    for market in ["1", "X", "2"]:
        best_odd = db.query(func.max(ExtendedOddsHistory.odd_value)).filter(
            and_(
                ExtendedOddsHistory.fixture_id == fixture.fixture_id,
                ExtendedOddsHistory.market_name == market
            )
        ).scalar()
        
        if best_odd:
            best_odds[market] = float(best_odd)
    
    # Predizione (se disponibile)
    prediction = db.query(MatchPredictions).filter(
        MatchPredictions.fixture_id == fixture.fixture_id
    ).first()
    
    predicted_winner = None
    win_probability = None
    if prediction:
        predicted_winner = prediction.winner_team_name
        if prediction.percent_home:
            win_probability = prediction.percent_home
    
    return HomepageMatch(
        fixture_id=fixture.fixture_id,
        home_team=fixture.home_team,
        away_team=fixture.away_team,
        fixture_date=fixture.fixture_date,
        league_name=fixture.league_name,
        best_odds=best_odds,
        predicted_winner=predicted_winner,
        win_probability=win_probability
    )

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
