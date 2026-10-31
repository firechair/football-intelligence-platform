import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, text
import logging
import statistics

from app.db.session import get_db
from app.db import models
from app.services.intelligent_cache import intelligent_cache

logger = logging.getLogger(__name__)

class BookmakerAnalyticsService:
    """Service for comprehensive bookmaker analytics and performance tracking"""
    
    def __init__(self):
        self.cache = intelligent_cache
    
    async def calculate_bookmaker_rankings(self, sport: str = 'football', timeframe: str = '30d') -> List[Dict[str, Any]]:
        """Calculate comprehensive bookmaker rankings"""
        try:
            # Try cache first
            cached_rankings = await self.cache.get_bookmaker_rankings(sport, timeframe)
            if cached_rankings:
                return cached_rankings
            
            db = next(get_db())
            days = self._parse_timeframe(timeframe)
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get all bookmaker statistics for the timeframe
            bookmaker_stats = db.query(models.BookmakerStats).filter(
                and_(
                    models.BookmakerStats.sport == sport,
                    models.BookmakerStats.last_updated >= cutoff_date
                )
            ).all()
            
            # Group by bookmaker and calculate aggregated metrics
            bookmaker_data = {}
            for stat in bookmaker_stats:
                if stat.bookmaker not in bookmaker_data:
                    bookmaker_data[stat.bookmaker] = {
                        'markets': [],
                        'total_best_odds': 0,
                        'total_markets': 0,
                        'specializations': []
                    }
                
                data = bookmaker_data[stat.bookmaker]
                data['markets'].append(stat)
                data['total_best_odds'] += stat.best_odds_count or 0
                data['total_markets'] += stat.total_markets or 0
                
                # Track market specializations (where win rate > 70%)
                if stat.win_percentage and stat.win_percentage > 70:
                    data['specializations'].append(stat.market_type)
            
            rankings = []
            for bookmaker, data in bookmaker_data.items():
                if data['total_markets'] == 0:
                    continue
                    
                # Calculate comprehensive metrics
                win_rate = (data['total_best_odds'] / data['total_markets']) * 100 if data['total_markets'] > 0 else 0
                consistency_scores = [m.consistency_score for m in data['markets'] if m.consistency_score]
                avg_consistency = statistics.mean(consistency_scores) if consistency_scores else 0
                
                # Market coverage score (how many different markets they cover well)
                market_coverage = len(set(m.market_type for m in data['markets']))
                
                # Calculate trend direction
                trend_direction = await self._calculate_trend_direction(bookmaker, sport, days)
                
                # Overall value score (weighted combination)
                value_score = (
                    win_rate * 0.40 +                    # 40% - How often they have best odds
                    (avg_consistency * 100) * 0.25 +     # 25% - Consistency score
                    min(market_coverage * 10, 100) * 0.20 +  # 20% - Market coverage
                    min(data['total_markets'] / 100, 10) * 10 * 0.15  # 15% - Volume/experience
                )
                
                rankings.append({
                    'bookmaker': bookmaker,
                    'win_rate': round(win_rate, 2),
                    'consistency_score': round(avg_consistency, 3),
                    'market_specializations': list(set(data['specializations'])),
                    'market_coverage': market_coverage,
                    'total_markets': data['total_markets'],
                    'best_odds_count': data['total_best_odds'],
                    'trend_direction': trend_direction,
                    'value_score': round(value_score, 2),
                    'last_updated': datetime.utcnow().isoformat()
                })
            
            # Sort by value score
            rankings.sort(key=lambda x: x['value_score'], reverse=True)
            
            db.close()
            return rankings[:20]  # Return top 20
            
        except Exception as e:
            logger.error(f"Error calculating bookmaker rankings: {e}")
            return []
    
    async def generate_user_suggestions(self, user_id: int, match_data: dict) -> List[Dict[str, Any]]:
        """Generate personalized betting suggestions based on user history and preferences"""
        try:
            db = next(get_db())
            
            # Get user preferences
            user_prefs = db.query(models.UserBettingPreferences).filter(
                models.UserBettingPreferences.user_id == user_id
            ).first()
            
            if not user_prefs:
                # Create default preferences for new users
                user_prefs = models.UserBettingPreferences(
                    user_id=user_id,
                    preferred_sports=['football'],
                    preferred_markets=['1X2', 'Over/Under'],
                    preferred_bookmakers=[],
                    risk_tolerance='medium'
                )
                db.add(user_prefs)
                db.commit()
            
            suggestions = []
            markets = match_data.get('markets', ['1X2', 'Over/Under', 'Both Teams to Score'])
            
            for market in markets:
                # Find optimal bookmaker for this market based on user profile
                best_bm = await self._find_optimal_bookmaker(
                    market=market,
                    user_preferences=user_prefs,
                    current_odds=match_data.get('odds', {}),
                    sport='football'
                )
                
                if best_bm and best_bm.get('confidence', 0) > 0.6:  # Only suggest if confident
                    suggestions.append({
                        'market': market,
                        'recommended_bookmaker': best_bm['bookmaker'],
                        'reason': best_bm['reason'],
                        'confidence': best_bm['confidence'],
                        'expected_value': best_bm.get('ev', 0),
                        'odds': best_bm.get('odds'),
                        'user_success_rate': best_bm.get('user_success_rate'),
                        'bookmaker_specialization': best_bm.get('specialization', False)
                    })
            
            db.close()
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating user suggestions: {e}")
            return []
    
    async def get_bookmaker_trends(self, bookmaker: str, period: str = '7d') -> Dict[str, Any]:
        """Get trend analysis for specific bookmaker"""
        try:
            db = next(get_db())
            days = self._parse_timeframe(period)
            
            # Get historical performance data
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get odds history for trend calculation
            odds_history = db.query(models.OddsHistory).filter(
                and_(
                    models.OddsHistory.bookmaker == bookmaker,
                    models.OddsHistory.timestamp >= cutoff_date,
                    models.OddsHistory.is_best_odd == True
                )
            ).order_by(models.OddsHistory.timestamp).all()
            
            if not odds_history:
                return {
                    'bookmaker': bookmaker,
                    'period': period,
                    'trend_direction': 'insufficient_data',
                    'insights': ['Not enough data available for trend analysis'],
                    'recommendation': 'neutral'
                }
            
            # Calculate trend metrics
            daily_performance = self._calculate_daily_performance(odds_history)
            trend_direction = self._analyze_trend(daily_performance)
            
            # Generate insights
            insights = self._generate_trend_insights(daily_performance, bookmaker)
            
            # Generate recommendation
            recommendation = self._get_trend_recommendation(trend_direction, daily_performance)
            
            db.close()
            
            return {
                'bookmaker': bookmaker,
                'period': period,
                'trend_direction': trend_direction,
                'daily_performance': daily_performance[-7:],  # Last 7 days
                'insights': insights,
                'recommendation': recommendation,
                'total_best_odds': len(odds_history),
                'average_daily_performance': statistics.mean(daily_performance) if daily_performance else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting bookmaker trends: {e}")
            return {}
    
    async def update_user_preferences(self, user_id: int, preferences: Dict[str, Any]) -> bool:
        """Update user betting preferences"""
        try:
            db = next(get_db())
            
            user_prefs = db.query(models.UserBettingPreferences).filter(
                models.UserBettingPreferences.user_id == user_id
            ).first()
            
            if not user_prefs:
                user_prefs = models.UserBettingPreferences(user_id=user_id)
                db.add(user_prefs)
            
            # Update preferences
            for key, value in preferences.items():
                if hasattr(user_prefs, key):
                    setattr(user_prefs, key, value)
            
            user_prefs.updated_at = datetime.utcnow()
            db.commit()
            
            # Invalidate user suggestions cache
            await self.cache.invalidate_cache(f"suggestions:{user_id}:*")
            
            db.close()
            return True
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            return False
    
    async def _find_optimal_bookmaker(self, market: str, user_preferences, current_odds: dict, sport: str) -> Optional[Dict[str, Any]]:
        """Find optimal bookmaker based on user preferences and historical data"""
        try:
            db = next(get_db())
            
            # Get bookmaker stats for this market
            market_stats = db.query(models.BookmakerStats).filter(
                and_(
                    models.BookmakerStats.sport == sport,
                    models.BookmakerStats.market_type == market
                )
            ).all()
            
            if not market_stats:
                return None
            
            best_recommendation = None
            best_score = 0
            
            for stat in market_stats:
                if stat.bookmaker not in current_odds:
                    continue
                
                # Calculate recommendation score
                score = 0
                reasons = []
                
                # Performance score (40% weight)
                if stat.win_percentage:
                    score += (stat.win_percentage / 100) * 0.4
                    if stat.win_percentage > 70:
                        reasons.append(f"Excellent track record ({stat.win_percentage:.1f}% best odds)")
                
                # Consistency score (30% weight)
                if stat.consistency_score:
                    score += stat.consistency_score * 0.3
                
                # User preference bonus (20% weight)
                preferred_bookmakers = user_preferences.preferred_bookmakers or []
                if stat.bookmaker in preferred_bookmakers:
                    score += 0.2
                    reasons.append("Matches your preferences")
                
                # Market specialization bonus (10% weight)
                if stat.win_percentage and stat.win_percentage > 75:
                    score += 0.1
                    reasons.append(f"Specializes in {market} markets")
                
                if score > best_score:
                    best_score = score
                    best_recommendation = {
                        'bookmaker': stat.bookmaker,
                        'confidence': min(score, 1.0),
                        'reason': ' • '.join(reasons) if reasons else f"Good performance in {market} markets",
                        'odds': current_odds.get(stat.bookmaker),
                        'specialization': stat.win_percentage > 75 if stat.win_percentage else False,
                        'user_success_rate': getattr(user_preferences, 'success_rate', None)
                    }
            
            db.close()
            return best_recommendation
            
        except Exception as e:
            logger.error(f"Error finding optimal bookmaker: {e}")
            return None
    
    async def _calculate_trend_direction(self, bookmaker: str, sport: str, days: int) -> str:
        """Calculate trend direction for bookmaker"""
        try:
            db = next(get_db())
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get daily best odds count for trend analysis
            daily_counts = db.execute(
                text("""
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM odds_history 
                WHERE bookmaker = :bookmaker 
                    AND is_best_odd = true 
                    AND timestamp >= :cutoff_date
                GROUP BY DATE(timestamp)
                ORDER BY date
                """),
                {"bookmaker": bookmaker, "cutoff_date": cutoff_date}
            ).fetchall()
            
            if len(daily_counts) < 3:
                return 'insufficient_data'
            
            counts = [row.count for row in daily_counts]
            
            # Simple trend analysis
            first_half = counts[:len(counts)//2]
            second_half = counts[len(counts)//2:]
            
            first_avg = statistics.mean(first_half)
            second_avg = statistics.mean(second_half)
            
            if second_avg > first_avg * 1.1:
                return 'improving'
            elif second_avg < first_avg * 0.9:
                return 'declining'
            else:
                return 'stable'
                
        except Exception as e:
            logger.error(f"Error calculating trend direction: {e}")
            return 'unknown'
    
    def _calculate_daily_performance(self, odds_history: List) -> List[float]:
        """Calculate daily performance metrics from odds history"""
        daily_data = {}
        
        for record in odds_history:
            date_key = record.timestamp.date()
            if date_key not in daily_data:
                daily_data[date_key] = 0
            daily_data[date_key] += 1
        
        # Convert to sorted list of daily counts
        return [daily_data[date] for date in sorted(daily_data.keys())]
    
    def _analyze_trend(self, daily_performance: List[float]) -> str:
        """Analyze trend from daily performance data"""
        if len(daily_performance) < 3:
            return 'insufficient_data'
        
        # Calculate trend using linear regression slope
        n = len(daily_performance)
        x = list(range(n))
        
        # Simple trend calculation
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(daily_performance)
        
        numerator = sum((x[i] - x_mean) * (daily_performance[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 'stable'
        
        slope = numerator / denominator
        
        if slope > 0.1:
            return 'improving'
        elif slope < -0.1:
            return 'declining'
        else:
            return 'stable'
    
    def _generate_trend_insights(self, daily_performance: List[float], bookmaker: str) -> List[str]:
        """Generate human-readable insights from trend data"""
        insights = []
        
        if not daily_performance:
            return ["No performance data available"]
        
        avg_performance = statistics.mean(daily_performance)
        recent_performance = statistics.mean(daily_performance[-3:]) if len(daily_performance) >= 3 else avg_performance
        
        if recent_performance > avg_performance * 1.2:
            insights.append(f"{bookmaker} has shown strong recent performance")
        elif recent_performance < avg_performance * 0.8:
            insights.append(f"{bookmaker} performance has declined recently")
        
        if len(daily_performance) >= 7:
            week_trend = daily_performance[-7:]
            if max(week_trend) - min(week_trend) < avg_performance * 0.1:
                insights.append(f"{bookmaker} shows consistent daily performance")
        
        return insights if insights else [f"{bookmaker} maintains stable performance"]
    
    def _get_trend_recommendation(self, trend_direction: str, daily_performance: List[float]) -> str:
        """Generate recommendation based on trend analysis"""
        if trend_direction == 'improving':
            return 'recommended'
        elif trend_direction == 'declining':
            return 'caution'
        elif trend_direction == 'stable':
            return 'neutral'
        else:
            return 'insufficient_data'
    
    def _parse_timeframe(self, timeframe: str) -> int:
        """Parse timeframe string to days"""
        timeframe_map = {
            '1d': 1, '3d': 3, '7d': 7, '14d': 14, '30d': 30, '90d': 90
        }
        return timeframe_map.get(timeframe, 30)

# Global analytics service instance
bookmaker_analytics = BookmakerAnalyticsService()

