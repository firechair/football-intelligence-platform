import asyncio
import httpx
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Rate limiter globale per tutte le chiamate API
_global_rate_limiter = asyncio.Semaphore(2)  # Massimo 2 chiamate simultanee
_last_request_time = 0
_request_spacing = 1.0  # 1 secondo tra richieste (1 req/sec)

# 📊 API Statistics Tracker
class APIStats:
    """Global statistics tracker for football API calls"""
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_response_time = 0.0
        self.last_request_time = None
        self.endpoint_counts = {}  # endpoint -> count
        self.error_counts = {}  # status_code -> count
        self.hourly_requests = []  # list of (timestamp, endpoint)
        self.daily_requests = []  # list of (timestamp, endpoint)
    
    def record_request(self, endpoint: str, success: bool, response_time: float, error_code: int = None):
        """Record an API request"""
        self.total_requests += 1
        self.last_request_time = datetime.now()
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            if error_code:
                self.error_counts[error_code] = self.error_counts.get(error_code, 0) + 1
        
        self.total_response_time += response_time
        self.endpoint_counts[endpoint] = self.endpoint_counts.get(endpoint, 0) + 1
        
        # Track for hourly/daily stats (keep last 24 hours)
        now = datetime.now()
        self.hourly_requests.append((now, endpoint))
        self.daily_requests.append((now, endpoint))
        
        # Cleanup old entries
        cutoff_hour = now - timedelta(hours=1)
        cutoff_day = now - timedelta(days=1)
        self.hourly_requests = [(t, e) for t, e in self.hourly_requests if t > cutoff_hour]
        self.daily_requests = [(t, e) for t, e in self.daily_requests if t > cutoff_day]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        avg_response_time = (self.total_response_time / self.total_requests) if self.total_requests > 0 else 0
        success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate_percent": round(success_rate, 2),
            "average_response_time_ms": round(avg_response_time * 1000, 2),
            "last_request_time": self.last_request_time.isoformat() if self.last_request_time else None,
            "requests_last_hour": len(self.hourly_requests),
            "requests_last_day": len(self.daily_requests),
            "endpoint_breakdown": self.endpoint_counts,
            "error_breakdown": self.error_counts,
            "rate_limit_config": {
                "max_concurrent": 2,
                "request_spacing_seconds": _request_spacing
            }
        }

# Global stats instance
_api_stats = APIStats()

class FootballAPIClient:
    def __init__(self):
        self.base_url = settings.FOOTBALL_API_BASE_URL
        # FIXED: Use correct API-Football headers format
        self.headers = {
            "x-apisports-key": settings.FOOTBALL_API_KEY
        }
        # Rate limiter: utilizza configurazione da settings
        self.rate_limiter = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)
        self.request_spacing = settings.REQUEST_SPACING
        self.last_request_time = 0
        
        # Rate limiter separato per predizioni
        self.predictions_rate_limiter = asyncio.Semaphore(settings.PREDICTIONS_MAX_CONCURRENT)
        self.predictions_request_spacing = settings.PREDICTIONS_REQUEST_SPACING
        self.last_predictions_request = 0
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Effettua richiesta API con rate limiting globale"""
        global _global_rate_limiter, _last_request_time, _request_spacing, _api_stats
        
        request_start_time = time.time()
        
        async with _global_rate_limiter:
            # Rate limiting globale: utilizza spacing globale
            current_time = time.time()
            time_since_last = current_time - _last_request_time
            if time_since_last < _request_spacing:
                await asyncio.sleep(_request_spacing - time_since_last)
            
            _last_request_time = time.time()
            
            url = f"{self.base_url}/{endpoint}"
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, headers=self.headers, params=params or {})
                    response.raise_for_status()
                    
                    data = response.json()
                    response_time = time.time() - request_start_time
                    
                    # Record successful request
                    _api_stats.record_request(endpoint, success=True, response_time=response_time)
                    
                    logger.info(f"API Request: {endpoint} - Status: {response.status_code} - Time: {response_time:.2f}s")
                    
                    return data
                    
            except httpx.HTTPStatusError as e:
                response_time = time.time() - request_start_time
                _api_stats.record_request(endpoint, success=False, response_time=response_time, error_code=e.response.status_code)
                logger.error(f"HTTP error for {endpoint}: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                response_time = time.time() - request_start_time
                _api_stats.record_request(endpoint, success=False, response_time=response_time)
                logger.error(f"Request error for {endpoint}: {str(e)}")
                raise
    
    async def get_fixtures_by_date_range(self, from_date: str, to_date: str) -> List[Dict[str, Any]]:
        """Recupera tutte le partite in un range di date"""
        fixtures = []

        # L'API ha limite su quante partite restituisce per chiamata
        # Dividiamo per giorni per essere sicuri di prenderle tutte
        current_date = datetime.fromisoformat(from_date).date()
        end_date = datetime.fromisoformat(to_date).date()

        while current_date <= end_date:
            date_str = current_date.isoformat()

            try:
                data = await self._make_request("fixtures", {"date": date_str})
                daily_fixtures = data.get("response", [])
                fixtures.extend(daily_fixtures)
                logger.info(f"Retrieved {len(daily_fixtures)} fixtures for {date_str}")

            except Exception as e:
                logger.error(f"Failed to get fixtures for {date_str}: {str(e)}")
                continue

            current_date += timedelta(days=1)
            await asyncio.sleep(1)  # Pausa tra le richieste

        return fixtures

    async def get_live_fixtures(self) -> List[Dict[str, Any]]:
        """Recupera tutte le partite attualmente live (in corso)"""
        try:
            logger.info("Fetching live fixtures from API-Football")
            data = await self._make_request("fixtures", {"live": "all"})
            live_fixtures = data.get("response", [])

            logger.info(f"Retrieved {len(live_fixtures)} live fixtures from API")
            return live_fixtures

        except Exception as e:
            logger.error(f"Failed to get live fixtures: {str(e)}")
            return []
    
    async def get_odds_for_fixture(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """Recupera le quote per una specifica partita"""
        try:
            data = await self._make_request("odds", {"fixture": fixture_id})
            odds_data = data.get("response", [])
            if not odds_data:
                logger.warning(f"No odds available from API for fixture {fixture_id}")
                return None
            return odds_data[0]
        except Exception as e:
            logger.error(f"Failed to get odds for fixture {fixture_id}: {str(e)}")
            return None
    
    async def get_odds_for_multiple_fixtures(self, fixture_ids: List[int]) -> Dict[int, Optional[Dict[str, Any]]]:
        """Recupera quote per multiple partite sequenzialmente per evitare sovraccarico"""
        logger.info(f"Processing {len(fixture_ids)} fixtures for odds collection")
        
        # Processa sequenzialmente per evitare sovraccarico API
        odds_map = {}
        for i, fixture_id in enumerate(fixture_ids):
            try:
                logger.info(f"Processing fixture {fixture_id} ({i+1}/{len(fixture_ids)})")
                odds_data = await self.get_odds_for_fixture(fixture_id)
                odds_map[fixture_id] = odds_data
            except Exception as e:
                logger.error(f"Exception fetching odds for fixture {fixture_id}: {str(e)}")
                odds_map[fixture_id] = None
        
        return odds_map
    
    # 🆕 NUOVO METODO
    async def _make_predictions_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Effettua richiesta API per predizioni con rate limiting globale"""
        global _global_rate_limiter, _last_request_time, _request_spacing, _api_stats
        
        request_start_time = time.time()
        
        async with _global_rate_limiter:
            # Rate limiting globale: utilizza spacing globale
            current_time = time.time()
            time_since_last = current_time - _last_request_time
            if time_since_last < _request_spacing:
                await asyncio.sleep(_request_spacing - time_since_last)
            
            _last_request_time = time.time()
            
            url = f"{self.base_url}/{endpoint}"
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, headers=self.headers, params=params or {})
                    response.raise_for_status()
                    
                    data = response.json()
                    response_time = time.time() - request_start_time
                    
                    # Record successful request
                    _api_stats.record_request(endpoint, success=True, response_time=response_time)
                    
                    logger.info(f"API Request: {endpoint} - Status: {response.status_code} - Time: {response_time:.2f}s")
                    
                    return data
                    
            except httpx.HTTPStatusError as e:
                response_time = time.time() - request_start_time
                _api_stats.record_request(endpoint, success=False, response_time=response_time, error_code=e.response.status_code)
                logger.error(f"HTTP error for {endpoint}: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                response_time = time.time() - request_start_time
                _api_stats.record_request(endpoint, success=False, response_time=response_time)
                logger.error(f"Request error for {endpoint}: {str(e)}")
                raise

    async def get_predictions_for_fixture(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """Recupera predizioni per una specifica partita con rate limiting conservativo"""
        try:
            data = await self._make_predictions_request("predictions", {"fixture": fixture_id})
            predictions_data = data.get("response", [])
            return predictions_data[0] if predictions_data else None
        except Exception as e:
            logger.error(f"Failed to get predictions for fixture {fixture_id}: {str(e)}")
            return None
    
    # 🆕 NUOVO METODO
    async def get_predictions_for_multiple_fixtures(self, fixture_ids: List[int]) -> Dict[int, Optional[Dict[str, Any]]]:
        """Recupera predizioni per multiple partite (2 req/sec) con timeout"""
        results = {}
        
        for fixture_id in fixture_ids:
            try:
                logger.info(f"Getting predictions for fixture {fixture_id}...")
                # Timeout di 30 secondi per ogni richiesta
                prediction_data = await asyncio.wait_for(
                    self.get_predictions_for_fixture(fixture_id), 
                    timeout=30.0
                )
                results[fixture_id] = prediction_data
                
                # Progress logging every 10 requests
                if len(results) % 10 == 0:
                    logger.info(f"Processed {len(results)}/{len(fixture_ids)} predictions")
                    
            except asyncio.TimeoutError:
                logger.error(f"Timeout getting predictions for fixture {fixture_id}")
                results[fixture_id] = None
            except Exception as e:
                logger.error(f"Error getting predictions for fixture {fixture_id}: {str(e)}")
                results[fixture_id] = None
        
        return results

    async def get_finished_fixtures_by_date_range(self, from_date: str, to_date: str, status: str = "FT") -> List[Dict[str, Any]]:
        """Recupera le partite finite (FT = Full Time) in un range di date"""
        fixtures = []

        # L'API ha limite su quante partite restituisce per chiamata
        # Dividiamo per giorni per essere sicuri di prenderle tutte
        current_date = datetime.fromisoformat(from_date).date()
        end_date = datetime.fromisoformat(to_date).date()

        while current_date <= end_date:
            date_str = current_date.isoformat()

            try:
                data = await self._make_request("fixtures", {"date": date_str, "status": status})
                daily_fixtures = data.get("response", [])
                fixtures.extend(daily_fixtures)
                logger.info(f"Retrieved {len(daily_fixtures)} finished fixtures for {date_str}")

            except Exception as e:
                logger.error(f"Failed to get finished fixtures for {date_str}: {str(e)}")
                continue

            current_date += timedelta(days=1)
            await asyncio.sleep(1)  # Pausa tra le richieste

        return fixtures

    async def get_fixture_results(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """Recupera il risultato di una specifica partita finita"""
        try:
            data = await self._make_request("fixtures", {"id": fixture_id})
            fixtures = data.get("response", [])
            if fixtures:
                fixture = fixtures[0]
                # Verifica che la partita sia finita
                if fixture.get("fixture", {}).get("status", {}).get("short") == "FT":
                    return fixture
            return None
        except Exception as e:
            logger.error(f"Failed to get results for fixture {fixture_id}: {str(e)}")
            return None

# Singleton instance
football_api = FootballAPIClient()

