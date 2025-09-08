from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
from pydantic import BaseModel

from app.core.database import get_db
from app.models.odds_tracking import FixtureTrackingStatus, ExtendedOddsHistory, BookmakerInfo
from app.models.predictions import MatchPredictions

router = APIRouter(prefix="/fixtures", tags=["fixtures"])

class FixtureResponse(BaseModel):
    fixture_id: int
    home_team: str
    away_team: str
    home_team_logo: Optional[str] = None  # 🆕 Logo squadra casa
    away_team_logo: Optional[str] = None  # 🆕 Logo squadra ospite
    fixture_date: datetime
    league_id: Optional[int]
    league_name: str
    league_logo: Optional[str] = None     # 🆕 Logo lega
    
    # Quote migliori per tutti i mercati
    best_odds: Dict[str, Dict[str, float]] = {}  # {"1": {"Bookmaker A": 2.10, "Bookmaker B": 2.05}, ...}
    
    # Predizioni
    prediction: Optional[Dict[str, Any]] = None

class FixturesByDateResponse(BaseModel):
    date: str
    total_matches: int
    matches: List[FixtureResponse]

class FixturesByDateRangeResponse(BaseModel):
    start_date: str
    end_date: str
    total_matches: int
    daily_fixtures: List[FixturesByDateResponse]

# 🆕 MAPPATURA LOGHI SQUADRE (da espandere)
TEAM_LOGOS = {
    "Manchester United": "https://logos.football/teams/manchester-united.png",
    "Liverpool": "https://logos.football/teams/liverpool.png",
    "Arsenal": "https://logos.football/teams/arsenal.png",
    "Chelsea": "https://logos.football/teams/chelsea.png",
    "Manchester City": "https://logos.football/teams/manchester-city.png",
    "Tottenham": "https://logos.football/teams/tottenham.png",
    "Real Madrid": "https://logos.football/teams/real-madrid.png",
    "Barcelona": "https://logos.football/teams/barcelona.png",
    "Atletico Madrid": "https://logos.football/teams/atletico-madrid.png",
    "Bayern Munich": "https://logos.football/teams/bayern-munich.png",
    "Borussia Dortmund": "https://logos.football/teams/borussia-dortmund.png",
    "Juventus": "https://logos.football/teams/juventus.png",
    "AC Milan": "https://logos.football/teams/ac-milan.png",
    "Inter Milan": "https://logos.football/teams/inter-milan.png",
    "Napoli": "https://logos.football/teams/napoli.png",
    "PSG": "https://logos.football/teams/psg.png",
    "Marseille": "https://logos.football/teams/marseille.png",
    "Lyon": "https://logos.football/teams/lyon.png",
}

LEAGUE_LOGOS = {
    "Premier League": "https://logos.football/leagues/premier-league.png",
    "La Liga": "https://logos.football/leagues/la-liga.png",
    "Serie A": "https://logos.football/leagues/serie-a.png",
    "Bundesliga": "https://logos.football/leagues/bundesliga.png",
    "Ligue 1": "https://logos.football/leagues/ligue-1.png",
    "Champions League": "https://logos.football/leagues/champions-league.png",
    "Europa League": "https://logos.football/leagues/europa-league.png",
}

def get_team_logo_url(team_name: str) -> Optional[str]:
    """Genera URL proxy per logo squadra"""
    if not team_name:
        return None
    
    # Cerca logo diretto
    direct_url = TEAM_LOGOS.get(team_name)
    if direct_url:
        return f"/assets/logo?url={direct_url}"
    
    # Fallback generico
    fallback_url = f"https://logos.football/teams/{team_name.lower().replace(' ', '-')}.png"
    return f"/assets/logo?url={fallback_url}"

def get_league_logo_url(league_name: str) -> Optional[str]:
    """Genera URL proxy per logo lega"""
    if not league_name:
        return None
    
    # Cerca logo diretto
    direct_url = LEAGUE_LOGOS.get(league_name)
    if direct_url:
        return f"/assets/logo?url={direct_url}"
    
    # Fallback generico
    fallback_url = f"https://logos.football/leagues/{league_name.lower().replace(' ', '-')}.png"
    return f"/assets/logo?url={fallback_url}"

# 🆕 MERCATI SUPPORTATI
SUPPORTED_MARKETS = [
    # 1X2
    "1", "X", "2", "1X", "12", "X2",
    # Goal/NoGoal  
    "Goal", "NoGoal",
    # Over/Under
    "Over1.5", "Under1.5", "Over2.5", "Under2.5", "Over3.5", "Under3.5",
    # Combinati (se disponibili)
    "1+Over2.5", "2+Over2.5", "X+Under2.5", "1+Goal", "2+Goal"
]

@router.get("/today", response_model=FixturesByDateResponse)
async def get_today_fixtures(
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    db: Session = Depends(get_db)
):
    """🎯 Partite di oggi con quote migliori e loghi"""
    today = datetime.now().date()
    return await _get_fixtures_by_date(today, league_id, db)

@router.get("/tomorrow", response_model=FixturesByDateResponse)
async def get_tomorrow_fixtures(
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    db: Session = Depends(get_db)
):
    """🎯 Partite di domani con quote migliori e loghi"""
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    return await _get_fixtures_by_date(tomorrow, league_id, db)

@router.get("/date/{target_date}", response_model=FixturesByDateResponse)
async def get_fixtures_by_date(
    target_date: date,
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    db: Session = Depends(get_db)
):
    """🎯 Partite per una data specifica (YYYY-MM-DD)"""
    return await _get_fixtures_by_date(target_date, league_id, db)

@router.get("/range", response_model=FixturesByDateRangeResponse)
async def get_fixtures_by_date_range(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    db: Session = Depends(get_db)
):
    """🎯 Partite in un range di date (fino a 10 giorni)"""
    
    if (end_date - start_date).days > 10:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 10 days")
    
    daily_fixtures = []
    current_date = start_date
    
    while current_date <= end_date:
        day_fixtures = await _get_fixtures_by_date(current_date, league_id, db)
        daily_fixtures.append(day_fixtures)
        current_date += timedelta(days=1)
    
    total_matches = sum(day.total_matches for day in daily_fixtures)
    
    return FixturesByDateRangeResponse(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        total_matches=total_matches,
        daily_fixtures=daily_fixtures
    )

@router.get("/upcoming", response_model=List[FixtureResponse])
async def get_upcoming_fixtures(
    days_ahead: int = Query(10, ge=1, le=10, description="Days ahead to look"),
    limit: int = Query(100, ge=1, le=500, description="Max fixtures to return"),
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    db: Session = Depends(get_db)
):
    """🎯 Partite prossime (fino a 10 giorni) con quote migliori"""
    
    end_date = datetime.now().date() + timedelta(days=days_ahead)
    
    query = db.query(FixtureTrackingStatus).filter(
        and_(
            FixtureTrackingStatus.fixture_date >= datetime.now(),
            FixtureTrackingStatus.fixture_date <= datetime.combine(end_date, datetime.min.time()),
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"])
        )
    )
    
    if league_id:
        query = query.filter(FixtureTrackingStatus.league_id == league_id)
    
    fixtures = query.order_by(FixtureTrackingStatus.fixture_date).limit(limit).all()
    
    result = []
    for fixture in fixtures:
        fixture_data = await _build_fixture_response(fixture, db)
        result.append(fixture_data)
    
    return result

async def _get_fixtures_by_date(target_date: date, league_id: Optional[int], db: Session) -> FixturesByDateResponse:
    """Helper per ottenere partite per una data specifica"""
    
    start_datetime = datetime.combine(target_date, datetime.min.time())
    end_datetime = datetime.combine(target_date, datetime.max.time())
    
    query = db.query(FixtureTrackingStatus).filter(
        and_(
            FixtureTrackingStatus.fixture_date >= start_datetime,
            FixtureTrackingStatus.fixture_date <= end_datetime,
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"])
        )
    )
    
    if league_id:
        query = query.filter(FixtureTrackingStatus.league_id == league_id)
    
    fixtures = query.order_by(FixtureTrackingStatus.fixture_date).all()
    
    matches = []
    for fixture in fixtures:
        fixture_data = await _build_fixture_response(fixture, db)
        matches.append(fixture_data)
    
    return FixturesByDateResponse(
        date=target_date.isoformat(),
        total_matches=len(matches),
        matches=matches
    )

async def _build_fixture_response(fixture: FixtureTrackingStatus, db: Session) -> FixtureResponse:
    """Helper per costruire risposta fixture completa con quote migliori"""
    
    # 🆕 Loghi squadre tramite proxy
    home_logo = get_team_logo_url(fixture.home_team)
    away_logo = get_team_logo_url(fixture.away_team)
    league_logo = get_league_logo_url(fixture.league_name)
    
    # 🆕 Quote migliori per TUTTI i mercati supportati
    best_odds = {}
    for market in SUPPORTED_MARKETS:
        market_odds = await _get_best_odds_for_market(fixture.fixture_id, market, db)
        if market_odds:
            best_odds[market] = market_odds
    
    # 🆕 Predizioni
    prediction = db.query(MatchPredictions).filter(
        MatchPredictions.fixture_id == fixture.fixture_id
    ).first()
    
    prediction_data = None
    if prediction:
        prediction_data = {
            "winner_team": prediction.winner_team_name,
            "advice": prediction.advice,
            "percent_home": prediction.percent_home,
            "percent_draw": prediction.percent_draw,
            "percent_away": prediction.percent_away,
            "goals_home": prediction.goals_home,
            "goals_away": prediction.goals_away
        }
    
    return FixtureResponse(
        fixture_id=fixture.fixture_id,
        home_team=fixture.home_team,
        away_team=fixture.away_team,
        home_team_logo=home_logo,
        away_team_logo=away_logo,
        fixture_date=fixture.fixture_date,
        league_id=fixture.league_id,
        league_name=fixture.league_name,
        league_logo=league_logo,
        best_odds=best_odds,
        prediction=prediction_data
    )

async def _get_best_odds_for_market(fixture_id: int, market: str, db: Session) -> Dict[str, float]:
    """Helper per ottenere le migliori quote per un mercato specifico"""
    
    # Ottieni le quote più recenti per questo mercato
    latest_odds = db.query(ExtendedOddsHistory).filter(
        and_(
            ExtendedOddsHistory.fixture_id == fixture_id,
            ExtendedOddsHistory.market_name == market,
            ExtendedOddsHistory.collected_at >= datetime.now() - timedelta(hours=24)
        )
    ).order_by(desc(ExtendedOddsHistory.collected_at)).all()
    
    if not latest_odds:
        return {}
    
    # Raggruppa per bookmaker e prendi la quota più recente per ogni bookmaker
    bookmaker_odds = {}
    for odd in latest_odds:
        if odd.bookmaker_name not in bookmaker_odds:
            bookmaker_odds[odd.bookmaker_name] = float(odd.odd_value)
    
    return bookmaker_odds
