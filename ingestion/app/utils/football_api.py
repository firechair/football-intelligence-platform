import asyncio
import httpx
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class FootballAPIClient:
    def __init__(self):
        self.base_url = settings.FOOTBALL_API_BASE_URL
        self.headers = {
            "X-Rapidapi-Key": settings.FOOTBALL_API_KEY,
            "X-Rapidapi-Host": settings.FOOTBALL_API_HOST,
            "Host": settings.FOOTBALL_API_HOST
        }
        # Rate limiter più conservativo per evitare sovraccarico
        self.rate_limiter = asyncio.Semaphore(1)  # Solo 1 richiesta alla volta
        self.last_request_time = 0
        
        # Rate limiter separato per predizioni
        self.predictions_rate_limiter = asyncio.Semaphore(1)
        self.last_predictions_request = 0
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Effettua richiesta API con rate limiting conservativo (1 req/2 secondi)"""
        async with self.rate_limiter:
            # Rate limiting conservativo: 2 secondi tra richieste
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < 2.0:
                await asyncio.sleep(2.0 - time_since_last)
            
            self.last_request_time = time.time()
            
            url = f"{self.base_url}/{endpoint}"
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, headers=self.headers, params=params or {})
                    response.raise_for_status()
                    
                    data = response.json()
                    logger.info(f"API Request: {endpoint} - Status: {response.status_code}")
                    
                    return data
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error for {endpoint}: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
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
    
    async def get_odds_for_fixture(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """Recupera le quote per una specifica partita"""
        try:
            data = await self._make_request("odds", {"fixture": fixture_id})
            odds_data = data.get("response", [])
            return odds_data[0] if odds_data else None
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
    async def get_predictions_for_fixture(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        """Recupera predizioni per una specifica partita con rate limiting conservativo (3 sec)"""
        async with self.predictions_rate_limiter:
            # Assicura 3 secondi tra richieste predizioni
            current_time = time.time()
            time_since_last = current_time - self.last_predictions_request
            if time_since_last < 3.0:
                await asyncio.sleep(3.0 - time_since_last)
            
            self.last_predictions_request = time.time()
            
            try:
                data = await self._make_request("predictions", {"fixture": fixture_id})
                predictions_data = data.get("response", [])
                return predictions_data[0] if predictions_data else None
            except Exception as e:
                logger.error(f"Failed to get predictions for fixture {fixture_id}: {str(e)}")
                return None
    
    # 🆕 NUOVO METODO
    async def get_predictions_for_multiple_fixtures(self, fixture_ids: List[int]) -> Dict[int, Optional[Dict[str, Any]]]:
        """Recupera predizioni per multiple partite (1 req/sec)"""
        results = {}
        
        for fixture_id in fixture_ids:
            logger.info(f"Getting predictions for fixture {fixture_id}...")
            prediction_data = await self.get_predictions_for_fixture(fixture_id)
            results[fixture_id] = prediction_data
            
            # Progress logging every 50 requests
            if len(results) % 50 == 0:
                logger.info(f"Processed {len(results)}/{len(fixture_ids)} predictions")
        
        return results

# Singleton instance
football_api = FootballAPIClient()

