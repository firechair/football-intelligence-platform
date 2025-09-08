from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.database import get_db
from app.models.odds_tracking import ExtendedOddsHistory, BookmakerInfo, FixtureTrackingStatus

router = APIRouter(prefix="/historical", tags=["historical"])

class OddsHistoryResponse(BaseModel):
    fixture_id: int
    market_name: str
    bookmaker_name: str
    odd_value: float
    collected_at: datetime
    minutes_to_kickoff: Optional[int]

class MarketTrendResponse(BaseModel):
    market_name: str
    bookmaker_name: str
    data_points: List[Dict[str, Any]]  # {timestamp, odd_value, minutes_to_kickoff}

class BookmakerComparisonResponse(BaseModel):
    market_name: str
    timestamp: datetime
    bookmaker_odds: Dict[str, float]  # bookmaker_name -> odd_value

@router.get("/odds/{fixture_id}", response_model=List[OddsHistoryResponse])
async def get_fixture_odds_history(
    fixture_id: int,
    market: Optional[str] = Query(None, description="Filter by market (1, X, 2, Over2.5, etc.)"),
    bookmaker: Optional[str] = Query(None, description="Filter by bookmaker name"),
    hours_back: int = Query(24, description="Hours of history to retrieve"),
    db: Session = Depends(get_db)
):
    """Recupera la cronologia delle quote per una partita specifica"""
    
    cutoff_time = datetime.now() - timedelta(hours=hours_back)
    
    query = db.query(ExtendedOddsHistory).filter(
        ExtendedOddsHistory.fixture_id == fixture_id,
        ExtendedOddsHistory.collected_at >= cutoff_time
    )
    
    if market:
        query = query.filter(ExtendedOddsHistory.market_name == market)
    
    if bookmaker:
        query = query.filter(ExtendedOddsHistory.bookmaker_name.ilike(f"%{bookmaker}%"))
    
    odds_history = query.order_by(desc(ExtendedOddsHistory.collected_at)).all()
    
    return [
        OddsHistoryResponse(
            fixture_id=odd.fixture_id,
            market_name=odd.market_name,
            bookmaker_name=odd.bookmaker_name,
            odd_value=float(odd.odd_value),
            collected_at=odd.collected_at,
            minutes_to_kickoff=odd.minutes_to_kickoff
        )
        for odd in odds_history
    ]

@router.get("/trends/{fixture_id}/{market}", response_model=List[MarketTrendResponse])
async def get_market_trends(
    fixture_id: int,
    market: str,
    hours_back: int = Query(24),
    db: Session = Depends(get_db)
):
    """Ottieni il trend delle quote per un mercato specifico, diviso per bookmaker"""
    
    cutoff_time = datetime.now() - timedelta(hours=hours_back)
    
    odds_data = db.query(ExtendedOddsHistory).filter(
        ExtendedOddsHistory.fixture_id == fixture_id,
        ExtendedOddsHistory.market_name == market,
        ExtendedOddsHistory.collected_at >= cutoff_time
    ).order_by(ExtendedOddsHistory.collected_at).all()
    
    # Raggruppa per bookmaker
    bookmaker_trends = {}
    
    for odd in odds_data:
        if odd.bookmaker_name not in bookmaker_trends:
            bookmaker_trends[odd.bookmaker_name] = []
        
        bookmaker_trends[odd.bookmaker_name].append({
            "timestamp": odd.collected_at.isoformat(),
            "odd_value": float(odd.odd_value),
            "minutes_to_kickoff": odd.minutes_to_kickoff
        })
    
    return [
        MarketTrendResponse(
            market_name=market,
            bookmaker_name=bookmaker,
            data_points=data_points
        )
        for bookmaker, data_points in bookmaker_trends.items()
    ]

@router.get("/comparison/{fixture_id}", response_model=List[BookmakerComparisonResponse])
async def get_bookmaker_comparison(
    fixture_id: int,
    markets: List[str] = Query(["1", "X", "2"], description="Markets to compare"),
    latest_only: bool = Query(True, description="Get only the latest odds"),
    db: Session = Depends(get_db)
):
    """Confronta le quote di diversi bookmaker per gli stessi mercati"""
    
    base_query = db.query(ExtendedOddsHistory).filter(
        ExtendedOddsHistory.fixture_id == fixture_id,
        ExtendedOddsHistory.market_name.in_(markets)
    )
    
    if latest_only:
        # Ottieni solo le quote più recenti per ogni combinazione market/bookmaker
        subquery = db.query(
            ExtendedOddsHistory.market_name,
            ExtendedOddsHistory.bookmaker_name,
            func.max(ExtendedOddsHistory.collected_at).label('latest_time')
        ).filter(
            ExtendedOddsHistory.fixture_id == fixture_id,
            ExtendedOddsHistory.market_name.in_(markets)
        ).group_by(
            ExtendedOddsHistory.market_name,
            ExtendedOddsHistory.bookmaker_name
        ).subquery()
        
        odds_data = db.query(ExtendedOddsHistory).join(
            subquery,
            (ExtendedOddsHistory.market_name == subquery.c.market_name) &
            (ExtendedOddsHistory.bookmaker_name == subquery.c.bookmaker_name) &
            (ExtendedOddsHistory.collected_at == subquery.c.latest_time)
        ).all()
    else:
        odds_data = base_query.order_by(desc(ExtendedOddsHistory.collected_at)).all()
    
    # Raggruppa per market e timestamp
    comparison_data = {}
    
    for odd in odds_data:
        key = f"{odd.market_name}_{odd.collected_at.isoformat()}"
        
        if key not in comparison_data:
            comparison_data[key] = {
                "market_name": odd.market_name,
                "timestamp": odd.collected_at,
                "bookmaker_odds": {}
            }
        
        comparison_data[key]["bookmaker_odds"][odd.bookmaker_name] = float(odd.odd_value)
    
    return [
        BookmakerComparisonResponse(**data)
        for data in comparison_data.values()
    ]

@router.get("/stats/fixture/{fixture_id}")
async def get_fixture_stats(fixture_id: int, db: Session = Depends(get_db)):
    """Ottieni statistiche di raccolta per una partita"""
    
    stats = db.query(
        func.count(ExtendedOddsHistory.id).label('total_odds'),
        func.count(func.distinct(ExtendedOddsHistory.bookmaker_name)).label('unique_bookmakers'),
        func.count(func.distinct(ExtendedOddsHistory.market_name)).label('unique_markets'),
        func.min(ExtendedOddsHistory.collected_at).label('first_collection'),
        func.max(ExtendedOddsHistory.collected_at).label('last_collection')
    ).filter(ExtendedOddsHistory.fixture_id == fixture_id).first()
    
    return {
        "fixture_id": fixture_id,
        "total_odds_collected": stats.total_odds,
        "unique_bookmakers": stats.unique_bookmakers,
        "unique_markets": stats.unique_markets,
        "first_collection": stats.first_collection,
        "last_collection": stats.last_collection
    }

@router.get("/markets")
async def get_available_markets(db: Session = Depends(get_db)):
    """Ottieni lista di tutti i mercati disponibili"""
    
    markets = db.query(
        ExtendedOddsHistory.market_name,
        ExtendedOddsHistory.market_type,
        func.count(ExtendedOddsHistory.id).label('odds_count')
    ).group_by(
        ExtendedOddsHistory.market_name,
        ExtendedOddsHistory.market_type
    ).all()
    
    return [
        {
            "market_name": market.market_name,
            "market_type": market.market_type,
            "odds_count": market.odds_count
        }
        for market in markets
    ]

@router.get("/bookmakers")
async def get_active_bookmakers(db: Session = Depends(get_db)):
    """Ottieni lista di bookmaker attivi con statistiche"""
    
    bookmaker_stats = db.query(
        BookmakerInfo.name,
        BookmakerInfo.display_name,
        func.count(ExtendedOddsHistory.id).label('total_odds'),
        func.max(ExtendedOddsHistory.collected_at).label('last_update')
    ).join(
        ExtendedOddsHistory, BookmakerInfo.api_id == ExtendedOddsHistory.bookmaker_id
    ).group_by(
        BookmakerInfo.name,
        BookmakerInfo.display_name
    ).all()
    
    return [
        {
            "name": stat.name,
            "display_name": stat.display_name,
            "total_odds": stat.total_odds,
            "last_update": stat.last_update
        }
        for stat in bookmaker_stats
    ]

