import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
import logging

from app.db.session import get_db
from app.db import models
from app.services.intelligent_cache import intelligent_cache
from app.services.bookmaker_analytics import bookmaker_analytics

logger = logging.getLogger(__name__)

class SmartAlertEngine:
    """Engine for detecting and triggering smart betting alerts"""
    
    def __init__(self):
        self.cache = intelligent_cache
        self.analytics = bookmaker_analytics
        
    async def check_all_alerts(self):
        """Check all types of alerts"""
        try:
            await asyncio.gather(
                self.check_value_bet_alerts(),
                self.check_odds_movement_alerts(),
                self.check_bookmaker_special_alerts(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Error in alert checking: {e}")
    
    async def check_value_bet_alerts(self):
        """Detect and trigger value betting opportunities"""
        try:
            db = next(get_db())
            
            # Get all active value bet alerts
            active_alerts = db.query(models.SmartAlerts).filter(
                and_(
                    models.SmartAlerts.alert_type == 'value_bet',
                    models.SmartAlerts.is_active == True
                )
            ).all()
            
            for alert in active_alerts:
                try:
                    # Check if alert was triggered recently (avoid spam)
                    if alert.last_triggered:
                        time_diff = datetime.utcnow() - alert.last_triggered
                        if time_diff < timedelta(hours=1):  # Minimum 1 hour between alerts
                            continue
                    
                    criteria = alert.criteria
                    user = db.query(models.User).filter(models.User.id == alert.user_id).first()
                    
                    if not user:
                        continue
                    
                    # Detect value opportunities
                    value_bets = await self._detect_value_opportunities(
                        sports=criteria.get('sports', ['football']),
                        min_value_threshold=criteria.get('min_ev', 5.0),
                        max_odds=criteria.get('max_odds', 10.0),
                        user_id=alert.user_id
                    )
                    
                    if value_bets:
                        await self._send_alert(alert.user_id, 'value_bet', {
                            'alert_id': alert.id,
                            'opportunities': value_bets,
                            'message': f"Found {len(value_bets)} value betting opportunities!",
                            'priority': 'high' if len(value_bets) > 3 else 'medium'
                        })
                        
                        # Update last triggered
                        alert.last_triggered = datetime.utcnow()
                        
                except Exception as e:
                    logger.error(f"Error processing value bet alert {alert.id}: {e}")
            
            db.commit()
            db.close()
            
        except Exception as e:
            logger.error(f"Error checking value bet alerts: {e}")
    
    async def check_odds_movement_alerts(self):
        """Monitor significant odds movements"""
        try:
            db = next(get_db())
            
            # Get recent odds movements (last 1 hour)
            recent_movements = await self._detect_odds_movements(
                min_change_threshold=0.10,  # 10% change
                time_window='1h'
            )
            
            if not recent_movements:
                db.close()
                return
            
            # Get users interested in odds movement alerts
            movement_alerts = db.query(models.SmartAlerts).filter(
                and_(
                    models.SmartAlerts.alert_type == 'odds_movement',
                    models.SmartAlerts.is_active == True
                )
            ).all()
            
            for alert in movement_alerts:
                try:
                    criteria = alert.criteria
                    relevant_movements = []
                    
                    for movement in recent_movements:
                        # Check if movement matches user criteria
                        if self._movement_matches_criteria(movement, criteria):
                            relevant_movements.append(movement)
                    
                    if relevant_movements:
                        await self._send_alert(alert.user_id, 'odds_movement', {
                            'alert_id': alert.id,
                            'movements': relevant_movements,
                            'message': f"Detected {len(relevant_movements)} significant odds movements",
                            'priority': 'high' if any(abs(m['change_pct']) > 20 for m in relevant_movements) else 'medium'
                        })
                        
                        alert.last_triggered = datetime.utcnow()
                
                except Exception as e:
                    logger.error(f"Error processing odds movement alert {alert.id}: {e}")
            
            db.commit()
            db.close()
            
        except Exception as e:
            logger.error(f"Error checking odds movement alerts: {e}")
    
    async def check_bookmaker_special_alerts(self):
        """Check for special bookmaker opportunities (trends, new best odds, etc.)"""
        try:
            db = next(get_db())
            
            # Get bookmaker special alerts
            special_alerts = db.query(models.SmartAlerts).filter(
                and_(
                    models.SmartAlerts.alert_type == 'bookmaker_special',
                    models.SmartAlerts.is_active == True
                )
            ).all()
            
            for alert in special_alerts:
                try:
                    criteria = alert.criteria
                    
                    # Check if alert was triggered recently
                    if alert.last_triggered:
                        time_diff = datetime.utcnow() - alert.last_triggered
                        if time_diff < timedelta(hours=6):  # Minimum 6 hours between special alerts
                            continue
                    
                    special_opportunities = await self._detect_bookmaker_specials(
                        preferred_bookmakers=criteria.get('bookmakers', []),
                        sports=criteria.get('sports', ['football']),
                        user_id=alert.user_id
                    )
                    
                    if special_opportunities:
                        await self._send_alert(alert.user_id, 'bookmaker_special', {
                            'alert_id': alert.id,
                            'opportunities': special_opportunities,
                            'message': f"Special opportunities from your preferred bookmakers",
                            'priority': 'medium'
                        })
                        
                        alert.last_triggered = datetime.utcnow()
                
                except Exception as e:
                    logger.error(f"Error processing bookmaker special alert {alert.id}: {e}")
            
            db.commit()
            db.close()
            
        except Exception as e:
            logger.error(f"Error checking bookmaker special alerts: {e}")
    
    async def create_alert(self, user_id: int, alert_type: str, criteria: Dict[str, Any]) -> bool:
        """Create a new smart alert for user"""
        try:
            db = next(get_db())
            
            # Validate alert type and criteria
            if not self._validate_alert_criteria(alert_type, criteria):
                return False
            
            # Check if user already has similar alert
            existing = db.query(models.SmartAlerts).filter(
                and_(
                    models.SmartAlerts.user_id == user_id,
                    models.SmartAlerts.alert_type == alert_type,
                    models.SmartAlerts.is_active == True
                )
            ).first()
            
            if existing:
                # Update existing alert
                existing.criteria = criteria
                existing.created_at = datetime.utcnow()
            else:
                # Create new alert
                alert = models.SmartAlerts(
                    user_id=user_id,
                    alert_type=alert_type,
                    criteria=criteria,
                    is_active=True
                )
                db.add(alert)
            
            db.commit()
            db.close()
            return True
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return False
    
    async def get_user_alerts(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all alerts for a user"""
        try:
            db = next(get_db())
            
            alerts = db.query(models.SmartAlerts).filter(
                models.SmartAlerts.user_id == user_id
            ).all()
            
            result = []
            for alert in alerts:
                result.append({
                    'id': alert.id,
                    'alert_type': alert.alert_type,
                    'criteria': alert.criteria,
                    'is_active': alert.is_active,
                    'last_triggered': alert.last_triggered.isoformat() if alert.last_triggered else None,
                    'created_at': alert.created_at.isoformat()
                })
            
            db.close()
            return result
            
        except Exception as e:
            logger.error(f"Error getting user alerts: {e}")
            return []
    
    async def toggle_alert(self, alert_id: int, user_id: int, is_active: bool) -> bool:
        """Toggle alert active status"""
        try:
            db = next(get_db())
            
            alert = db.query(models.SmartAlerts).filter(
                and_(
                    models.SmartAlerts.id == alert_id,
                    models.SmartAlerts.user_id == user_id
                )
            ).first()
            
            if alert:
                alert.is_active = is_active
                db.commit()
                db.close()
                return True
            
            db.close()
            return False
            
        except Exception as e:
            logger.error(f"Error toggling alert: {e}")
            return False
    
    async def _detect_value_opportunities(self, sports: List[str], min_value_threshold: float, max_odds: float, user_id: int) -> List[Dict[str, Any]]:
        """Detect value betting opportunities"""
        try:
            opportunities = []
            
            # Get user preferences for better targeting
            user_prefs = await self._get_user_preferences(user_id)
            preferred_markets = user_prefs.get('preferred_markets', ['1X2', 'Over/Under'])
            
            # This is a simplified implementation - in real scenario, you'd:
            # 1. Compare current odds with historical averages
            # 2. Use mathematical models to calculate expected value
            # 3. Consider bookmaker margins and market efficiency
            
            # TODO: Implement real value betting opportunity detection
            # For now, return empty opportunities to avoid showing fake data
            # In real implementation, this would:
            # 1. Compare current odds with historical averages
            # 2. Use mathematical models to calculate expected value
            # 3. Consider bookmaker margins and market efficiency
            # 4. Filter based on user criteria and preferences
            
            # Return empty list until real implementation is ready
            opportunities = []
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Error detecting value opportunities: {e}")
            return []
    
    async def _detect_odds_movements(self, min_change_threshold: float, time_window: str) -> List[Dict[str, Any]]:
        """Detect significant odds movements"""
        try:
            db = next(get_db())
            
            # Parse time window
            if time_window == '1h':
                cutoff_time = datetime.utcnow() - timedelta(hours=1)
            elif time_window == '30m':
                cutoff_time = datetime.utcnow() - timedelta(minutes=30)
            else:
                cutoff_time = datetime.utcnow() - timedelta(hours=1)
            
            # Get recent odds history
            recent_odds = db.query(models.OddsHistory).filter(
                models.OddsHistory.timestamp >= cutoff_time
            ).order_by(models.OddsHistory.timestamp.desc()).all()
            
            movements = []
            
            # Group by fixture_id, market, bookmaker and detect movements
            odds_groups = {}
            for odd in recent_odds:
                key = f"{odd.fixture_id}_{odd.market_name}_{odd.bookmaker}"
                if key not in odds_groups:
                    odds_groups[key] = []
                odds_groups[key].append(odd)
            
            for key, odds_list in odds_groups.items():
                if len(odds_list) < 2:
                    continue
                
                # Sort by timestamp
                odds_list.sort(key=lambda x: x.timestamp)
                first_odd = odds_list[0]
                last_odd = odds_list[-1]
                
                # Calculate change percentage
                change_pct = ((float(last_odd.odd_value) - float(first_odd.odd_value)) / float(first_odd.odd_value)) * 100
                
                if abs(change_pct) >= min_change_threshold * 100:
                    movements.append({
                        'fixture_id': last_odd.fixture_id,
                        'market': last_odd.market_name,
                        'bookmaker': last_odd.bookmaker,
                        'old_odds': float(first_odd.odd_value),
                        'new_odds': float(last_odd.odd_value),
                        'change_pct': round(change_pct, 2),
                        'direction': 'up' if change_pct > 0 else 'down',
                        'timestamp': last_odd.timestamp.isoformat()
                    })
            
            db.close()
            return movements
            
        except Exception as e:
            logger.error(f"Error detecting odds movements: {e}")
            return []
    
    async def _detect_bookmaker_specials(self, preferred_bookmakers: List[str], sports: List[str], user_id: int) -> List[Dict[str, Any]]:
        """Detect special opportunities from preferred bookmakers"""
        try:
            opportunities = []
            
            for bookmaker in preferred_bookmakers:
                # Get recent trend for this bookmaker
                trend_data = await self.analytics.get_bookmaker_trends(bookmaker, '7d')
                
                if trend_data.get('trend_direction') == 'improving':
                    opportunities.append({
                        'type': 'trend_improvement',
                        'bookmaker': bookmaker,
                        'message': f"{bookmaker} odds have improved significantly this week",
                        'details': trend_data.get('insights', []),
                        'recommendation': 'Consider checking their current offers'
                    })
                
                # Check if bookmaker has new best odds
                # This would require real-time odds comparison
                # For now, add sample data
                if bookmaker in ['Bookmaker A', 'Bookmaker B']:
                    opportunities.append({
                        'type': 'new_best_odds',
                        'bookmaker': bookmaker,
                        'message': f"{bookmaker} now offers the best odds on popular markets",
                        'markets_count': 5,
                        'recommendation': 'Check their latest offerings'
                    })
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Error detecting bookmaker specials: {e}")
            return []
    
    async def _send_alert(self, user_id: int, alert_type: str, data: Dict[str, Any]):
        """Send alert to user (this would integrate with notification system)"""
        try:
            # In a real implementation, this would:
            # 1. Send push notifications
            # 2. Send emails
            # 3. Store in user's alert history
            # 4. Trigger WebSocket notifications
            
            logger.info(f"Alert sent to user {user_id}: {alert_type} - {data.get('message')}")
            
            # Store alert in cache for real-time delivery
            alert_key = f"user_alerts:{user_id}"
            alert_data = {
                'type': alert_type,
                'timestamp': datetime.utcnow().isoformat(),
                'data': data
            }
            
            if self.cache.redis:
                # Store alert for 24 hours
                self.cache.redis.lpush(alert_key, json.dumps(alert_data))
                self.cache.redis.expire(alert_key, 86400)  # 24 hours
                
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
    
    def _movement_matches_criteria(self, movement: Dict[str, Any], criteria: Dict[str, Any]) -> bool:
        """Check if odds movement matches user criteria"""
        try:
            # Check minimum change threshold
            min_change = criteria.get('min_change_pct', 10)
            if abs(movement['change_pct']) < min_change:
                return False
            
            # Check markets
            interested_markets = criteria.get('markets', [])
            if interested_markets and movement['market'] not in interested_markets:
                return False
            
            # Check bookmakers
            interested_bookmakers = criteria.get('bookmakers', [])
            if interested_bookmakers and movement['bookmaker'] not in interested_bookmakers:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error matching movement criteria: {e}")
            return False
    
    def _validate_alert_criteria(self, alert_type: str, criteria: Dict[str, Any]) -> bool:
        """Validate alert criteria"""
        valid_types = ['value_bet', 'odds_movement', 'bookmaker_special']
        
        if alert_type not in valid_types:
            return False
        
        # Basic validation - can be extended
        if alert_type == 'value_bet':
            return 'min_ev' in criteria
        elif alert_type == 'odds_movement':
            return 'min_change_pct' in criteria
        elif alert_type == 'bookmaker_special':
            return 'bookmakers' in criteria or 'sports' in criteria
        
        return True
    
    async def _get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """Get user preferences"""
        try:
            db = next(get_db())
            
            prefs = db.query(models.UserBettingPreferences).filter(
                models.UserBettingPreferences.user_id == user_id
            ).first()
            
            if prefs:
                result = {
                    'preferred_sports': prefs.preferred_sports or ['football'],
                    'preferred_markets': prefs.preferred_markets or ['1X2'],
                    'preferred_bookmakers': prefs.preferred_bookmakers or [],
                    'risk_tolerance': prefs.risk_tolerance or 'medium'
                }
            else:
                result = {
                    'preferred_sports': ['football'],
                    'preferred_markets': ['1X2', 'Over/Under'],
                    'preferred_bookmakers': [],
                    'risk_tolerance': 'medium'
                }
            
            db.close()
            return result
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {}

# Global alert engine instance
alert_engine = SmartAlertEngine()

