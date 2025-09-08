from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.database import get_db
from app.models.odds_tracking import ExtendedOddsHistory, FixtureTrackingStatus, BookmakerInfo

router = APIRouter(prefix="/odds", tags=["odds"])

class BestOddsResponse(BaseModel):
    fixture_id: int
    home_team: str
    away_team: str
    fixture_date: datetime
    league_name: str
    
    # Quote migliori per mercato
    market_odds: Dict[str, Dict[str, float]] = {}  # {"1": {"Bookmaker A": 2.10, "Bookmaker B": 2.05}, ...}
    
    # Info raccolta
    last_updated: datetime
    total_bookmakers: int

class MarketComparisonResponse(BaseModel):
    market: str
    best_odd: float
    best_bookmaker: str
    all_odds: Dict[str, float]  # bookmaker -> odd

class FixtureOddsResponse(BaseModel):
    fixture_id: int
    home_team: str
    away_team: str
    fixture_date: datetime
    league_name: str
    
    # Confronto per mercato
    market_comparisons: List[MarketComparisonResponse] = []
    
    # Info raccolta
    last_updated: datetime
    total_bookmakers: int

# 🆕 MERCATI SUPPORTATI COMPLETI
ALL_SUPPORTED_MARKETS = {
    # 1X2 Base
    "1": "Vittoria Casa",
    "X": "Pareggio", 
    "2": "Vittoria Ospite",
    
    # Double Chance
    "1X": "Casa o Pareggio",
    "12": "Casa o Ospite", 
    "X2": "Pareggio o Ospite",
    
    # Goal/NoGoal
    "Goal": "Entrambe le squadre segnano",
    "NoGoal": "Almeno una squadra non segna",
    
    # Over/Under
    "Over1.5": "Più di 1.5 goal",
    "Under1.5": "Meno di 1.5 goal",
    "Over2.5": "Più di 2.5 goal", 
    "Under2.5": "Meno di 2.5 goal",
    "Over3.5": "Più di 3.5 goal",
    "Under3.5": "Meno di 3.5 goal",
    
    # Combinati (se disponibili)
    "1+Over2.5": "Casa + Over 2.5",
    "2+Over2.5": "Ospite + Over 2.5", 
    "X+Under2.5": "Pareggio + Under 2.5",
    "1+Goal": "Casa + Goal",
    "2+Goal": "Ospite + Goal"
}

@router.get("/best/{fixture_id}", response_model=BestOddsResponse)
async def get_best_odds_for_fixture(
    fixture_id: int,
    markets: Optional[str] = Query(None, description="Comma-separated markets (1,X,2,Over2.5,etc.)"),
    db: Session = Depends(get_db)
):
    """🎯 Quote migliori per una partita specifica per tutti i mercati"""
    
    # Verifica che la partita esista
    fixture = db.query(FixtureTrackingStatus).filter(
        FixtureTrackingStatus.fixture_id == fixture_id
    ).first()
    
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")
    
    # Determina mercati da cercare
    if markets:
        requested_markets = [m.strip() for m in markets.split(",")]
        markets_to_search = [m for m in requested_markets if m in ALL_SUPPORTED_MARKETS]
    else:
        markets_to_search = list(ALL_SUPPORTED_MARKETS.keys())
    
    # Ottieni quote migliori per ogni mercato
    market_odds = {}
    for market in markets_to_search:
        odds_data = await _get_best_odds_for_market(fixture_id, market, db)
        if odds_data:
            market_odds[market] = odds_data
    
    # Ultimo aggiornamento
    last_updated = db.query(func.max(ExtendedOddsHistory.collected_at)).filter(
        ExtendedOddsHistory.fixture_id == fixture_id
    ).scalar() or datetime.now()
    
    # Numero bookmaker totali
    total_bookmakers = db.query(func.count(func.distinct(ExtendedOddsHistory.bookmaker_name))).filter(
        ExtendedOddsHistory.fixture_id == fixture_id
    ).scalar() or 0
    
    return BestOddsResponse(
        fixture_id=fixture.fixture_id,
        home_team=fixture.home_team,
        away_team=fixture.away_team,
        fixture_date=fixture.fixture_date,
        league_name=fixture.league_name,
        market_odds=market_odds,
        last_updated=last_updated,
        total_bookmakers=total_bookmakers
    )

@router.get("/comparison/{fixture_id}", response_model=FixtureOddsResponse)
async def get_odds_comparison_for_fixture(
    fixture_id: int,
    markets: Optional[str] = Query(None, description="Comma-separated markets"),
    db: Session = Depends(get_db)
):
    """🎯 Confronto quote per una partita (migliore per ogni mercato)"""
    
    # Verifica che la partita esista
    fixture = db.query(FixtureTrackingStatus).filter(
        FixtureTrackingStatus.fixture_id == fixture_id
    ).first()
    
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")
    
    # Determina mercati
    if markets:
        requested_markets = [m.strip() for m in markets.split(",")]
        markets_to_search = [m for m in requested_markets if m in ALL_SUPPORTED_MARKETS]
    else:
        markets_to_search = list(ALL_SUPPORTED_MARKETS.keys())
    
    # Confronto per ogni mercato
    market_comparisons = []
    for market in markets_to_search:
        comparison = await _get_market_comparison(fixture_id, market, db)
        if comparison:
            market_comparisons.append(comparison)
    
    # Info raccolta
    last_updated = db.query(func.max(ExtendedOddsHistory.collected_at)).filter(
        ExtendedOddsHistory.fixture_id == fixture_id
    ).scalar() or datetime.now()
    
    total_bookmakers = db.query(func.count(func.distinct(ExtendedOddsHistory.bookmaker_name))).filter(
        ExtendedOddsHistory.fixture_id == fixture_id
    ).scalar() or 0
    
    return FixtureOddsResponse(
        fixture_id=fixture.fixture_id,
        home_team=fixture.home_team,
        away_team=fixture.away_team,
        fixture_date=fixture.fixture_date,
        league_name=fixture.league_name,
        market_comparisons=market_comparisons,
        last_updated=last_updated,
        total_bookmakers=total_bookmakers
    )

@router.get("/latest", response_model=List[BestOddsResponse])
async def get_latest_odds(
    hours_back: int = Query(1, ge=1, le=24, description="Hours back to look"),
    limit: int = Query(50, ge=1, le=200, description="Max fixtures to return"),
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    db: Session = Depends(get_db)
):
    """🎯 Quote più recenti per partite attive"""
    
    cutoff_time = datetime.now() - timedelta(hours=hours_back)
    
    # Partite con quote recenti
    fixtures_with_recent_odds = db.query(FixtureTrackingStatus).join(
        ExtendedOddsHistory, FixtureTrackingStatus.fixture_id == ExtendedOddsHistory.fixture_id
    ).filter(
        and_(
            ExtendedOddsHistory.collected_at >= cutoff_time,
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"])
        )
    )
    
    if league_id:
        fixtures_with_recent_odds = fixtures_with_recent_odds.filter(
            FixtureTrackingStatus.league_id == league_id
        )
    
    fixtures = fixtures_with_recent_odds.distinct().order_by(
        desc(ExtendedOddsHistory.collected_at)
    ).limit(limit).all()
    
    result = []
    for fixture in fixtures:
        # Quote migliori per mercati principali
        main_markets = ["1", "X", "2", "Over2.5", "Under2.5", "Goal", "NoGoal"]
        market_odds = {}
        
        for market in main_markets:
            odds_data = await _get_best_odds_for_market(fixture.fixture_id, market, db)
            if odds_data:
                market_odds[market] = odds_data
        
        # Ultimo aggiornamento per questa partita
        last_updated = db.query(func.max(ExtendedOddsHistory.collected_at)).filter(
            ExtendedOddsHistory.fixture_id == fixture.fixture_id
        ).scalar() or datetime.now()
        
        # Bookmaker totali
        total_bookmakers = db.query(func.count(func.distinct(ExtendedOddsHistory.bookmaker_name))).filter(
            ExtendedOddsHistory.fixture_id == fixture.fixture_id
        ).scalar() or 0
        
        result.append(BestOddsResponse(
            fixture_id=fixture.fixture_id,
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            fixture_date=fixture.fixture_date,
            league_name=fixture.league_name,
            market_odds=market_odds,
            last_updated=last_updated,
            total_bookmakers=total_bookmakers
        ))
    
    return result

@router.get("/markets")
async def get_supported_markets():
    """🎯 Lista mercati supportati con descrizioni"""
    return {
        "markets": ALL_SUPPORTED_MARKETS,
        "total_count": len(ALL_SUPPORTED_MARKETS),
        "categories": {
            "1x2": ["1", "X", "2"],
            "double_chance": ["1X", "12", "X2"],
            "goal_nogoal": ["Goal", "NoGoal"],
            "over_under": ["Over1.5", "Under1.5", "Over2.5", "Under2.5", "Over3.5", "Under3.5"],
            "combined": ["1+Over2.5", "2+Over2.5", "X+Under2.5", "1+Goal", "2+Goal"]
        }
    }

async def _get_best_odds_for_market(fixture_id: int, market: str, db: Session) -> Dict[str, float]:
    """Helper per ottenere le migliori quote per un mercato"""
    
    # Quote più recenti per questo mercato (ultime 24h)
    latest_odds = db.query(ExtendedOddsHistory).filter(
        and_(
            ExtendedOddsHistory.fixture_id == fixture_id,
            ExtendedOddsHistory.market_name == market,
            ExtendedOddsHistory.collected_at >= datetime.now() - timedelta(hours=24)
        )
    ).order_by(desc(ExtendedOddsHistory.collected_at)).all()
    
    if not latest_odds:
        return {}
    
    # Raggruppa per bookmaker (ultima quota per bookmaker)
    bookmaker_odds = {}
    for odd in latest_odds:
        if odd.bookmaker_name not in bookmaker_odds:
            bookmaker_odds[odd.bookmaker_name] = float(odd.odd_value)
    
    return bookmaker_odds

async def _get_market_comparison(fixture_id: int, market: str, db: Session) -> Optional[MarketComparisonResponse]:
    """Helper per confronto mercato (migliore quota + tutte le quote)"""
    
    odds_data = await _get_best_odds_for_market(fixture_id, market, db)
    
    if not odds_data:
        return None
    
    # Trova la migliore quota
    best_bookmaker = max(odds_data.keys(), key=lambda k: odds_data[k])
    best_odd = odds_data[best_bookmaker]
    
    return MarketComparisonResponse(
        market=market,
        best_odd=best_odd,
        best_bookmaker=best_bookmaker,
        all_odds=odds_data
    )
