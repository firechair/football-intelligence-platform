"""
Cache Service con Redis per l'Operator
Ottimizza le risposte delle API riducendo query al database
"""

import redis
import json
import logging
from typing import Any, Optional
import os

logger = logging.getLogger(__name__)

class CacheService:
    """
    Servizio di caching con Redis
    Supporta fallback a in-memory cache se Redis non disponibile
    """
    
    def __init__(self):
        self.redis_client = None
        self.in_memory_cache = {}  # Fallback cache
        self.use_redis = False
        
        # Tenta connessione Redis
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connessione
                self.redis_client.ping()
                self.use_redis = True
                logger.info("✅ Redis cache initialized successfully")
            except Exception as e:
                logger.warning(f"⚠️ Redis connection failed, using in-memory cache: {str(e)}")
                self.use_redis = False
        else:
            logger.info("ℹ️ No REDIS_URL provided, using in-memory cache")
    
    def get(self, key: str) -> Optional[Any]:
        """Recupera valore dalla cache"""
        try:
            if self.use_redis and self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    logger.debug(f"🎯 Cache HIT (Redis): {key}")
                    return json.loads(value)
            else:
                # Fallback: in-memory cache
                if key in self.in_memory_cache:
                    logger.debug(f"🎯 Cache HIT (Memory): {key}")
                    return self.in_memory_cache[key]
            
            logger.debug(f"❌ Cache MISS: {key}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """Salva valore in cache con TTL (default 5 minuti)"""
        try:
            if self.use_redis and self.redis_client:
                self.redis_client.setex(
                    key,
                    ttl_seconds,
                    json.dumps(value, default=str)
                )
                logger.debug(f"💾 Cache SET (Redis): {key} (TTL: {ttl_seconds}s)")
            else:
                # Fallback: in-memory cache (senza TTL automatico)
                self.in_memory_cache[key] = value
                logger.debug(f"💾 Cache SET (Memory): {key}")
                
                # Pulizia automatica se troppi elementi
                if len(self.in_memory_cache) > 100:
                    # Rimuovi i primi 20 elementi (FIFO approssimativo)
                    for _ in range(20):
                        self.in_memory_cache.pop(next(iter(self.in_memory_cache)))
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {str(e)}")
            return False
    
    def delete(self, key: str):
        """Elimina valore dalla cache"""
        try:
            if self.use_redis and self.redis_client:
                self.redis_client.delete(key)
                logger.debug(f"🗑️ Cache DELETE (Redis): {key}")
            else:
                self.in_memory_cache.pop(key, None)
                logger.debug(f"🗑️ Cache DELETE (Memory): {key}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {str(e)}")
            return False
    
    def clear_pattern(self, pattern: str):
        """Elimina tutte le chiavi che matchano il pattern (solo Redis)"""
        try:
            if self.use_redis and self.redis_client:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                    logger.info(f"🗑️ Cache CLEAR pattern: {pattern} ({len(keys)} keys)")
                return True
            else:
                # In-memory: rimuovi tutte le chiavi che contengono il pattern
                keys_to_remove = [k for k in self.in_memory_cache.keys() if pattern.replace('*', '') in k]
                for key in keys_to_remove:
                    del self.in_memory_cache[key]
                logger.info(f"🗑️ Cache CLEAR pattern (Memory): {pattern} ({len(keys_to_remove)} keys)")
                return True
                
        except Exception as e:
            logger.error(f"Error clearing cache pattern {pattern}: {str(e)}")
            return False
    
    def get_stats(self):
        """Ottieni statistiche cache"""
        try:
            if self.use_redis and self.redis_client:
                info = self.redis_client.info('stats')
                return {
                    "type": "redis",
                    "connected": True,
                    "total_keys": self.redis_client.dbsize(),
                    "hits": info.get('keyspace_hits', 0),
                    "misses": info.get('keyspace_misses', 0)
                }
            else:
                return {
                    "type": "memory",
                    "connected": False,
                    "total_keys": len(self.in_memory_cache)
                }
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {"type": "unknown", "error": str(e)}


# Singleton instance
cache_service = CacheService()


# Helper functions per chiavi cache standardizzate
def get_fixtures_cache_key(date_str: str, league_id: Optional[int] = None) -> str:
    """Genera chiave cache per fixtures by date"""
    if league_id:
        return f"fixtures:date:{date_str}:league:{league_id}"
    return f"fixtures:date:{date_str}"


def get_fixtures_range_cache_key(start_date: str, end_date: str, league_id: Optional[int] = None) -> str:
    """Genera chiave cache per fixtures by range"""
    if league_id:
        return f"fixtures:range:{start_date}:{end_date}:league:{league_id}"
    return f"fixtures:range:{start_date}:{end_date}"


def get_live_fixtures_cache_key() -> str:
    """Genera chiave cache per live fixtures"""
    return "fixtures:live"
