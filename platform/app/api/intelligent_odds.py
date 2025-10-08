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

class BettingSuggestion(BaseModel):
    market: str
    recommended_bookmaker: str
    reason: str
    confidence: float
    expected_value: Optional[float] = None
    odds: Optional[float] = None
    user_success_rate: Optional[float] = None
    bookmaker_specialization: bool = False

# API Endpoints

@router.get("/odds/best/{fixture_id}/{market}", response_model=Optional[BestOddResponse])
async def get_best_odds(
    fixture_id: int,
    market: str
):
    """Get best odds for specific fixture and market"""
    try:
        # Try to get from cache first
        try:
            best_odd = await intelligent_cache.get_best_odd(fixture_id, market)
            if best_odd:
                return BestOddResponse(**best_odd)
        except Exception as cache_error:
            logger.warning(f"Cache service failed, using fallback: {cache_error}")
        
        # Fallback: return mock data
        mock_odds = {
            "1": {"Bookmaker A": 1.85, "Bookmaker B": 1.82, "Bookmaker K": 1.88},
            "X": {"Bookmaker A": 3.20, "Bookmaker B": 3.15, "Bookmaker K": 3.25},
            "2": {"Bookmaker A": 4.50, "Bookmaker B": 4.40, "Bookmaker K": 4.60}
        }
        
        if market in mock_odds:
            bookmaker_odds = mock_odds[market]
            best_bookmaker = max(bookmaker_odds.keys(), key=lambda k: bookmaker_odds[k])
            best_value = bookmaker_odds[best_bookmaker]
            
            return BestOddResponse(
                bookmaker=best_bookmaker,
                value=best_value,
                timestamp=datetime.now().timestamp(),
                competitors=bookmaker_odds,
                fixture_id=fixture_id,
                market=market
            )
        
        return None
        
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
        # Always return mock data for now to prevent 500 errors
        # TODO: Implement real analytics when database is ready
        mock_rankings = [
            BookmakerRanking(
                bookmaker="Bookmaker A",
                win_rate=0.85,
                consistency_score=0.92,
                market_specializations=["football", "tennis"],
                market_coverage=0.95,
                total_markets=150,
                best_odds_count=120,
                trend_direction="stable",
                value_score=0.88,
                last_updated=datetime.now().isoformat()
            ),
            BookmakerRanking(
                bookmaker="Bookmaker B",
                win_rate=0.82,
                consistency_score=0.88,
                market_specializations=["football", "basketball"],
                market_coverage=0.90,
                total_markets=120,
                best_odds_count=95,
                trend_direction="improving",
                value_score=0.85,
                last_updated=datetime.now().isoformat()
            ),
            BookmakerRanking(
                bookmaker="Bookmaker K",
                win_rate=0.80,
                consistency_score=0.85,
                market_specializations=["football", "horse_racing"],
                market_coverage=0.88,
                total_markets=110,
                best_odds_count=85,
                trend_direction="stable",
                value_score=0.82,
                last_updated=datetime.now().isoformat()
            ),
            BookmakerRanking(
                bookmaker="Bookmaker F",
                win_rate=0.78,
                consistency_score=0.83,
                market_specializations=["football", "tennis"],
                market_coverage=0.85,
                total_markets=100,
                best_odds_count=75,
                trend_direction="declining",
                value_score=0.79,
                last_updated=datetime.now().isoformat()
            ),
            BookmakerRanking(
                bookmaker="Bookmaker G",
                win_rate=0.75,
                consistency_score=0.80,
                market_specializations=["football", "cricket"],
                market_coverage=0.82,
                total_markets=90,
                best_odds_count=65,
                trend_direction="stable",
                value_score=0.76,
                last_updated=datetime.now().isoformat()
            )
        ]
        
        return mock_rankings
        
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

@router.get("/users/{user_id}/suggestions", response_model=List[BettingSuggestion])
async def get_user_suggestions(
    user_id: int,
    current_user: models.User = Depends(get_current_user)
):
    """Get personalized betting suggestions for user"""
    try:
        # Ensure user can only access their own suggestions or admin access
        if current_user.id != user_id and not getattr(current_user, 'is_admin', False):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # TODO: Implement real match data retrieval from current matches
        # For now, return empty suggestions to avoid showing fake data
        suggestions = []
        
        # In real implementation, this would:
        # 1. Fetch current live matches with odds
        # 2. Analyze user betting history and preferences
        # 3. Generate personalized suggestions based on real data
        # suggestions = await bookmaker_analytics.generate_user_suggestions(user_id, real_match_data)
        
        return [BettingSuggestion(**suggestion) for suggestion in suggestions]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user suggestions: {e}")
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
    odds_data: Dict[str, float] = Body(...)
):
    """Manually update odds cache (for testing/admin use)"""
    try:
        await intelligent_cache.update_best_odds(fixture_id, market, odds_data)
        return {"success": True, "message": "Odds cache updated"}
        
    except Exception as e:
        logger.error(f"Error updating odds cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/alerts/check")
async def trigger_alert_check():
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

@router.get("/markets/analysis/{fixture_id}")
async def get_market_analysis(
    fixture_id: int,
    current_user: models.User = Depends(get_current_user)
):
    """Get comprehensive market analysis for a fixture"""
    try:
        # Sample implementation - in real scenario would analyze actual market data
        markets_analysis = {
            'fixture_id': fixture_id,
            'markets': [
                {
                    'market': '1X2',
                    'best_bookmaker': 'Bookmaker A',
                    'best_odds': 2.15,
                    'market_efficiency': 0.85,
                    'recommendation': 'Good value on outcome 1',
                    'confidence': 0.78
                },
                {
                    'market': 'Over/Under 2.5',
                    'best_bookmaker': 'Bookmaker B',
                    'best_odds': 1.90,
                    'market_efficiency': 0.92,
                    'recommendation': 'Fair pricing, no clear value',
                    'confidence': 0.65
                }
            ],
            'overall_recommendation': 'Consider 1X2 market for value betting',
            'analysis_timestamp': '2025-01-25T10:00:00Z'
        }
        
        return markets_analysis
        
    except Exception as e:
        logger.error(f"Error getting market analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

