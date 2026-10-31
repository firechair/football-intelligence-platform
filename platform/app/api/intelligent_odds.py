from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
from datetime import datetime

from app.db.session import get_db
from app.db import models
from app.services.auth import get_current_user
from app.services.intelligent_cache import intelligent_cache
from app.services.bookmaker_analytics import bookmaker_analytics
from app.services.alert_engine import alert_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["intelligent-odds"])

# Pydantic models for requests/responses
class BestOddResponse(BaseModel):
    bookmaker: str
    value: float
    timestamp: float
    competitors: Dict[str, float]
    fixture_id: int
    market: str

class BookmakerRanking(BaseModel):
    bookmaker: str
    win_rate: float
    consistency_score: float
    market_specializations: List[str]
    market_coverage: int
    total_markets: int
    best_odds_count: int
    trend_direction: str
    value_score: float
    last_updated: str

class UserPreferencesUpdate(BaseModel):
    preferred_sports: Optional[List[str]] = None
    preferred_markets: Optional[List[str]] = None
    preferred_bookmakers: Optional[List[str]] = None
    risk_tolerance: Optional[str] = None
    avg_stake: Optional[float] = None
    success_rate: Optional[float] = None

class AlertCreate(BaseModel):
    alert_type: str
    criteria: Dict[str, Any]

# API Endpoints

@router.get("/odds/best/{fixture_id}/{market}", response_model=Optional[BestOddResponse])
async def get_best_odds(
    fixture_id: int,
    market: str
):
    """Get best odds for specific fixture and market"""
    try:
        best_odd = await intelligent_cache.get_best_odd(fixture_id, market)
        return BestOddResponse(**best_odd) if best_odd else None

    except Exception as e:
        logger.error(f"Error getting best odds: {e}")
        # Return None instead of raising exception to prevent 500 errors
        return None

@router.get("/bookmakers/rankings", response_model=List[BookmakerRanking])
async def get_bookmaker_rankings(
    sport: str = Query("football", description="Sport to get rankings for"),
    period: str = Query("30d", description="Time period for rankings")
):
    """Get comprehensive bookmaker rankings"""
    try:
        rankings = await bookmaker_analytics.calculate_bookmaker_rankings(sport, period)
        return [BookmakerRanking(**ranking) for ranking in rankings]

    except Exception as e:
        logger.error(f"Error getting bookmaker rankings: {e}")
        # Return empty list instead of raising exception to prevent 500 errors
        return []

@router.get("/trends/{bookmaker}")
async def get_bookmaker_trends(
    bookmaker: str,
    period: str = Query("7d", description="Period for trend analysis")
):
    """Get trend analysis for specific bookmaker"""
    try:
        trends = await bookmaker_analytics.get_bookmaker_trends(bookmaker, period)
        return trends
        
    except Exception as e:
        logger.error(f"Error getting bookmaker trends: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/users/preferences")
async def update_user_preferences(
    preferences: UserPreferencesUpdate,
    current_user: models.User = Depends(get_current_user)
):
    """Update user betting preferences"""
    try:
        # Convert to dict, excluding None values
        prefs_dict = {k: v for k, v in preferences.dict().items() if v is not None}
        
        success = await bookmaker_analytics.update_user_preferences(
            current_user.id, 
            prefs_dict
        )
        
        if success:
            return {"success": True, "message": "Preferences updated successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to update preferences")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user preferences: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/alerts/create")
async def create_alert(
    alert: AlertCreate,
    current_user: models.User = Depends(get_current_user)
):
    """Create a new smart alert"""
    try:
        success = await alert_engine.create_alert(
            current_user.id,
            alert.alert_type,
            alert.criteria
        )
        
        if success:
            return {"success": True, "message": "Alert created successfully"}
        else:
            raise HTTPException(status_code=400, detail="Invalid alert criteria")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/alerts/my")
async def get_my_alerts(
    current_user: models.User = Depends(get_current_user)
):
    """Get user's alerts"""
    try:
        alerts = await alert_engine.get_user_alerts(current_user.id)
        return {"alerts": alerts}
        
    except Exception as e:
        logger.error(f"Error getting user alerts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/alerts/{alert_id}/toggle")
async def toggle_alert(
    alert_id: int,
    is_active: bool = Body(..., embed=True),
    current_user: models.User = Depends(get_current_user)
):
    """Toggle alert active status"""
    try:
        success = await alert_engine.toggle_alert(alert_id, current_user.id, is_active)
        
        if success:
            return {"success": True, "message": "Alert updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Alert not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling alert: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache performance statistics"""
    try:
        stats = await intelligent_cache.get_cache_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/cache/update-odds")
async def update_odds_cache(
    fixture_id: int = Body(...),
    market: str = Body(...),
    odds_data: Dict[str, float] = Body(...),
    current_user: models.User = Depends(get_current_user)
):
    """Manually update odds cache (for testing/admin use)"""
    try:
        await intelligent_cache.update_best_odds(fixture_id, market, odds_data)
        return {"success": True, "message": "Odds cache updated"}
        
    except Exception as e:
        logger.error(f"Error updating odds cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/alerts/check")
async def trigger_alert_check(current_user: models.User = Depends(get_current_user)):
    """Manually trigger alert checking (for testing/admin use)"""
    try:
        await alert_engine.check_all_alerts()
        return {"success": True, "message": "Alert check completed"}
        
    except Exception as e:
        logger.error(f"Error checking alerts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/analytics/summary")
async def get_analytics_summary(
    current_user: models.User = Depends(get_current_user)
):
    """Get analytics summary for user dashboard"""
    try:
        # Get user's betting preferences
        db = next(get_db())
        user_prefs = db.query(models.UserBettingPreferences).filter(
            models.UserBettingPreferences.user_id == current_user.id
        ).first()
        
        # Get top bookmakers
        top_bookmakers = await bookmaker_analytics.calculate_bookmaker_rankings("football", "7d")
        
        # Get cache stats
        cache_stats = await intelligent_cache.get_cache_stats()
        
        # Get user's active alerts count
        user_alerts = await alert_engine.get_user_alerts(current_user.id)
        active_alerts_count = len([a for a in user_alerts if a.get('is_active', False)])
        
        summary = {
            'user_preferences': {
                'sports': user_prefs.preferred_sports if user_prefs else ['football'],
                'markets': user_prefs.preferred_markets if user_prefs else ['1X2'],
                'bookmakers': user_prefs.preferred_bookmakers if user_prefs else [],
                'risk_tolerance': user_prefs.risk_tolerance if user_prefs else 'medium'
            },
            'top_bookmakers': top_bookmakers[:5],  # Top 5
            'cache_performance': cache_stats,
            'active_alerts': active_alerts_count,
            'system_status': 'operational'
        }
        
        db.close()
        return summary
        
    except Exception as e:
        logger.error(f"Error getting analytics summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
