import redis
import json
import time
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
import logging

from app.core.config import REDIS_URL
from app.db.session import get_db
from app.db import models

logger = logging.getLogger(__name__)

class IntelligentOddsCache:
    def __init__(self):
        """Initialize intelligent caching system with Redis"""
        try:
            self.redis = redis.from_url(REDIS_URL, decode_responses=True)
            # Test connection
            self.redis.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None
        
        self.cache_keys = {
            'best_odds': 'best_odds:{fixture_id}:{market}',
            'bookmaker_rank': 'bm_rank:{sport}:{market}:{timeframe}',
            'trend_data': 'trends:{bookmaker}:{period}',
            'user_suggestions': 'suggestions:{user_id}:{sport}',
            'market_cache': 'market_cache:{fixture_id}',
            'top_bookmakers': 'top_bm:{sport}:{period}'
        }
    
    async def update_best_odds(self, fixture_id: int, market: str, odds_data: dict):
        """Update best odds with automatic invalidation and analytics tracking"""
        if not self.redis:
            return
            
        try:
            current_best = await self.get_best_odd(fixture_id, market)
            
            # Find actual best from new data
            if not odds_data:
                return
                
            best_bookmaker, best_value = max(odds_data.items(), key=lambda x: float(x[1]))
            
            # Only update if this is actually better
            should_update = (
                not current_best or 
                float(best_value) > float(current_best.get('value', 0))
            )
            
            if should_update:
                cache_key = self.cache_keys['best_odds'].format(
                    fixture_id=fixture_id, market=market
                )
                
                ttl = self._calculate_dynamic_ttl(fixture_id, market)
                
                cache_data = {
                    'bookmaker': best_bookmaker,
                    'value': float(best_value),
                    'timestamp': time.time(),
                    'competitors': {k: float(v) for k, v in odds_data.items()},
                    'fixture_id': fixture_id,
                    'market': market
                }
                
                self.redis.setex(
                    cache_key, 
                    ttl,
                    json.dumps(cache_data)
                )
                
                # Update bookmaker stats async (don't await to avoid blocking)
                asyncio.create_task(
                    self._update_bookmaker_stats(best_bookmaker, market, fixture_id, best_value)
                )
                
                # Store in odds history for trend analysis
                asyncio.create_task(
                    self._store_odds_history(fixture_id, market, odds_data, best_bookmaker)
                )
                
                logger.debug(f"Updated best odds cache: {fixture_id}/{market} = {best_bookmaker}@{best_value}")
                
        except Exception as e:
            logger.error(f"Error updating best odds cache: {e}")
    
    async def get_best_odd(self, fixture_id: int, market: str) -> Optional[Dict[str, Any]]:
        """Get best odd from cache"""
        if not self.redis:
            return None
            
        try:
            cache_key = self.cache_keys['best_odds'].format(
                fixture_id=fixture_id, market=market
            )
            
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
                
        except Exception as e:
            logger.error(f"Error getting best odds from cache: {e}")
            
        return None
    
    async def get_bookmaker_rankings(self, sport: str, timeframe: str = '30d') -> List[Dict[str, Any]]:
        """Get cached bookmaker rankings"""
        if not self.redis:
            return []
            
        try:
            cache_key = self.cache_keys['bookmaker_rank'].format(
                sport=sport, market='all', timeframe=timeframe
            )
            
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
                
            # If not cached, calculate and cache
            rankings = await self._calculate_bookmaker_rankings(sport, timeframe)
            
            # Cache for 1 hour
            self.redis.setex(cache_key, 3600, json.dumps(rankings))
            
            return rankings
            
        except Exception as e:
            logger.error(f"Error getting bookmaker rankings: {e}")
            return []
    
    async def get_user_suggestions(self, user_id: int, sport: str) -> List[Dict[str, Any]]:
        """Get personalized user suggestions from cache"""
        if not self.redis:
            return []
            
        try:
            cache_key = self.cache_keys['user_suggestions'].format(
                user_id=user_id, sport=sport
            )
            
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
                
        except Exception as e:
            logger.error(f"Error getting user suggestions: {e}")
            
        return []
    
    def _calculate_dynamic_ttl(self, fixture_id: int, market: str) -> int:
        """Calculate dynamic TTL based on match proximity and market type"""
        # Default TTLs based on market type and match status
        base_ttl = {
            'live': 30,          # Live matches: 30 seconds
            'pre_match_soon': 120,  # Pre-match <2 hours: 2 minutes
            'pre_match': 600,    # Pre-match >2 hours: 10 minutes
            'outrights': 3600,   # Outrights: 1 hour
        }
        
        # Simple logic - can be enhanced with actual match time data
        if 'winner' in market.lower() or 'outright' in market.lower():
            return base_ttl['outrights']
        
        # Default to pre-match
        return base_ttl['pre_match']
    
    async def _update_bookmaker_stats(self, bookmaker: str, market: str, fixture_id: int, odd_value: float):
        """Update bookmaker statistics asynchronously"""
        try:
            db = next(get_db())
            
            # Find or create bookmaker stats record
            stats = db.query(models.BookmakerStats).filter(
                and_(
                    models.BookmakerStats.bookmaker == bookmaker,
                    models.BookmakerStats.market_type == market,
                    models.BookmakerStats.sport == 'football'  # Default to football
                )
            ).first()
            
            if not stats:
                stats = models.BookmakerStats(
                    bookmaker=bookmaker,
                    sport='football',
                    market_type=market,
                    best_odds_count=1,
                    total_markets=1
                )
                db.add(stats)
            else:
                stats.best_odds_count += 1
                stats.total_markets += 1
            
            # Update win percentage
            if stats.total_markets > 0:
                stats.win_percentage = (stats.best_odds_count / stats.total_markets) * 100
            
            # Simple consistency score (can be enhanced)
            stats.consistency_score = min(stats.win_percentage / 100, 1.0) if stats.win_percentage else 0
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating bookmaker stats: {e}")
        finally:
            db.close()
    
    async def _store_odds_history(self, fixture_id: int, market: str, odds_data: dict, best_bookmaker: str):
        """Store odds history for trend analysis"""
        try:
            db = next(get_db())
            
            for bookmaker, odd_value in odds_data.items():
                history_record = models.OddsHistory(
                    fixture_id=fixture_id,
                    market_name=market,
                    bookmaker=bookmaker,
                    odd_value=float(odd_value),
                    is_best_odd=(bookmaker == best_bookmaker)
                )
                db.add(history_record)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error storing odds history: {e}")
        finally:
            db.close()
    
    async def _calculate_bookmaker_rankings(self, sport: str, timeframe: str) -> List[Dict[str, Any]]:
        """Calculate comprehensive bookmaker rankings"""
        try:
            db = next(get_db())
            
            # Parse timeframe
            days = self._parse_timeframe(timeframe)
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get bookmaker statistics
            stats_query = db.query(models.BookmakerStats).filter(
                and_(
                    models.BookmakerStats.sport == sport,
                    models.BookmakerStats.last_updated >= cutoff_date
                )
            ).all()
            
            rankings = []
            for stat in stats_query:
                value_score = (
                    (stat.win_percentage or 0) * 0.4 +
                    (stat.consistency_score or 0) * 100 * 0.3 +
                    min((stat.total_markets or 0) / 1000 * 100, 100) * 0.3
                )
                
                rankings.append({
                    'bookmaker': stat.bookmaker,
                    'win_rate': float(stat.win_percentage or 0),
                    'consistency_score': float(stat.consistency_score or 0),
                    'total_markets': stat.total_markets or 0,
                    'best_odds_count': stat.best_odds_count or 0,
                    'value_score': round(value_score, 2),
                    'trend_direction': 'stable'  # TODO: Calculate from historical data
                })
            
            # Sort by value score
            rankings.sort(key=lambda x: x['value_score'], reverse=True)
            
            return rankings[:20]  # Top 20
            
        except Exception as e:
            logger.error(f"Error calculating bookmaker rankings: {e}")
            return []
        finally:
            db.close()
    
    def _parse_timeframe(self, timeframe: str) -> int:
        """Parse timeframe string to days"""
        timeframe_map = {
            '1d': 1, '7d': 7, '30d': 30, '90d': 90
        }
        return timeframe_map.get(timeframe, 30)
    
    async def invalidate_cache(self, pattern: str):
        """Invalidate cache entries matching pattern"""
        if not self.redis:
            return
            
        try:
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries matching {pattern}")
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        if not self.redis:
            return {}
            
        try:
            info = self.redis.info('memory')
            keyspace_info = self.redis.info('keyspace')
            
            stats = {
                'redis_memory_usage': info.get('used_memory_human', '0B'),
                'total_keys': sum([db_info.get('keys', 0) for db_info in keyspace_info.values() if isinstance(db_info, dict)]),
                'redis_connected': True
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'redis_connected': False}

# Global cache instance
intelligent_cache = IntelligentOddsCache()

