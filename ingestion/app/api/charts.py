from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.odds_tracking import ExtendedOddsHistory

router = APIRouter(prefix="/charts", tags=["charts"])

@router.get("/fixture/{fixture_id}/market/{market}/trend")
async def get_market_trend_chart_data(
    fixture_id: int,
    market: str,
    hours_back: int = Query(24, ge=1, le=168),  # Max 7 giorni
    resolution: str = Query("5min", description="5min, 15min, 1hour"),
    db: Session = Depends(get_db)
):
    """
    Restituisce dati formattati per grafici del frontend (Chart.js, D3.js, etc.)
    
    Format: {
        "labels": ["2024-01-01T10:00:00", "2024-01-01T10:05:00", ...],
        "datasets": [
            {
                "label": "Bookmaker A",
                "data": [2.10, 2.08, 2.12, ...],
                "borderColor": "#FF6384",
                "backgroundColor": "#FF6384"
            },
            ...
        ]
    }
    """
    
    cutoff_time = datetime.now() - timedelta(hours=hours_back)
    
    # Risoluzione temporale
    resolution_minutes = {
        "5min": 5,
        "15min": 15,
        "1hour": 60
    }.get(resolution, 5)
    
    odds_data = db.query(ExtendedOddsHistory).filter(
        ExtendedOddsHistory.fixture_id == fixture_id,
        ExtendedOddsHistory.market_name == market,
        ExtendedOddsHistory.collected_at >= cutoff_time
    ).order_by(ExtendedOddsHistory.collected_at).all()
    
    # Raggruppa per bookmaker e crea timeline
    bookmaker_data = {}
    timestamps = set()
    
    for odd in odds_data:
        # Arrotonda timestamp alla risoluzione
        rounded_time = odd.collected_at.replace(
            minute=(odd.collected_at.minute // resolution_minutes) * resolution_minutes,
            second=0,
            microsecond=0
        )
        
        timestamps.add(rounded_time)
        
        if odd.bookmaker_name not in bookmaker_data:
            bookmaker_data[odd.bookmaker_name] = {}
        
        # Prendi l'ultima quota per questo timestamp
        if rounded_time not in bookmaker_data[odd.bookmaker_name] or \
           odd.collected_at > bookmaker_data[odd.bookmaker_name][rounded_time]['collected_at']:
            bookmaker_data[odd.bookmaker_name][rounded_time] = {
                'value': float(odd.odd_value),
                'collected_at': odd.collected_at
            }
    
    # Ordina timestamps
    sorted_timestamps = sorted(timestamps)
    labels = [ts.isoformat() for ts in sorted_timestamps]
    
    # Colori predefiniti per bookmaker
    colors = [
        "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", 
        "#9966FF", "#FF9F40", "#FF6384", "#C9CBCF"
    ]
    
    datasets = []
    for i, (bookmaker, time_data) in enumerate(bookmaker_data.items()):
        data = []
        last_value = None
        
        for ts in sorted_timestamps:
            if ts in time_data:
                last_value = time_data[ts]['value']
                data.append(last_value)
            else:
                # Forward fill - mantieni l'ultimo valore
                data.append(last_value)
        
        datasets.append({
            "label": bookmaker,
            "data": data,
            "borderColor": colors[i % len(colors)],
            "backgroundColor": colors[i % len(colors)],
            "fill": False,
            "tension": 0.1
        })
    
    return {
        "labels": labels,
        "datasets": datasets,
        "metadata": {
            "fixture_id": fixture_id,
            "market": market,
            "resolution": resolution,
            "hours_back": hours_back,
            "total_points": len(labels)
        }
    }

@router.get("/fixture/{fixture_id}/comparison")
async def get_bookmaker_comparison_chart(
    fixture_id: int,
    markets: List[str] = Query(["1", "X", "2"]),
    db: Session = Depends(get_db)
):
    """
    Confronto attuale tra bookmaker per múltipli mercati
    
    Format: {
        "markets": ["1", "X", "2"],
        "bookmakers": ["Bookmaker A", "Bookmaker B", ...],
        "data": [
            [2.10, 3.20, 3.50],  // Bookmaker A odds for [1, X, 2]
            [2.08, 3.25, 3.45],  // Bookmaker B odds
            ...
        ]
    }
    """
    
    # Ottieni le quote più recenti
    latest_odds = db.query(ExtendedOddsHistory).filter(
        ExtendedOddsHistory.fixture_id == fixture_id,
        ExtendedOddsHistory.market_name.in_(markets)
    ).order_by(ExtendedOddsHistory.collected_at.desc()).all()
    
    # Raggruppa per bookmaker e mercato (prendi solo la più recente per ogni combinazione)
    bookmaker_market_odds = {}
    
    for odd in latest_odds:
        key = (odd.bookmaker_name, odd.market_name)
        if key not in bookmaker_market_odds:
            bookmaker_market_odds[key] = float(odd.odd_value)
    
    # Organizza i dati
    bookmakers = list(set(odd.bookmaker_name for odd in latest_odds))
    bookmakers.sort()
    
    data = []
    for bookmaker in bookmakers:
        bookmaker_odds = []
        for market in markets:
            odd_value = bookmaker_market_odds.get((bookmaker, market))
            bookmaker_odds.append(odd_value)
        data.append(bookmaker_odds)
    
    return {
        "markets": markets,
        "bookmakers": bookmakers,
        "data": data,
        "fixture_id": fixture_id
    }

