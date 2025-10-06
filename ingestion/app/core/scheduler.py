import asyncio
import logging
from datetime import datetime, timedelta

from app.services.fixtures_collector import fixtures_collector
from app.services.odds_collector import odds_collector
from app.services.cleanup_service import cleanup_service
from app.services.predictions_collector import predictions_collector
from app.core.database import get_db, SessionLocal
from app.core.config import settings

logger = logging.getLogger(__name__)

class OddsTrackingScheduler:
    def __init__(self):
        self.running = False
        self.tasks = []
        self.daily_fixtures_completed = False
        self.daily_predictions_completed = False
        self.last_fixtures_date = None
        self.last_predictions_date = None
    
    async def start(self):
        """Avvia il flusso SEQUENZIALE ottimizzato: Fixtures → Predictions → Odds → Future"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        logger.info("🚀 Starting FIP Scheduler with SEQUENTIAL LOGIC")
        logger.info("📅 Fixtures → 🔮 Predictions → 🎯 Odds → 🔄 Future → Repeat")
        
        try:
            # 🔥 EMERGENCY FIX: Prima esecuzione immediata per popolare database vuoto
            logger.info("🔥 EMERGENCY: Collecting fixtures immediately on startup...")
            await self._process_daily_fixtures()
            logger.info("🔥 EMERGENCY: Fixtures collected, continuing normal flow...")

            while self.running:
                # 1. FIXTURES GIORNALIERE (1x/giorno)
                await self._process_daily_fixtures()
                
                # 2. PREDIZIONI per fixtures giornaliere (1x/giorno)
                await self._process_daily_predictions()
                
                # 3. QUOTE per fixtures giornaliere (dopo predizioni)
                await self._process_daily_odds()
                
                # 4. FIXTURES FUTURE (settimanale)
                await self._process_future_fixtures()
                
                # 5. PREDIZIONI FUTURE (settimanale)
                await self._process_future_predictions()
                
                # 6. QUOTE FUTURE (limitato, non continuo)
                await self._process_future_odds()

                # 7. PULIZIA (1x/giorno)
                await self._process_daily_cleanup()
                
                # Attendi fino al prossimo giorno
                logger.info("✅ Daily cycle completed. Waiting until tomorrow...")
                await asyncio.sleep(24 * 60 * 60)  # 24 ore
                
        except Exception as e:
            logger.error(f"Scheduler error: {str(e)}")
        finally:
            self.running = False
    
    async def stop(self):
        """Ferma il scheduler"""
        logger.info("Stopping odds tracking scheduler")
        self.running = False
        
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        await asyncio.gather(*self.tasks, return_exceptions=True)
    
    async def _collect_daily_fixtures(self):
        """Helper: Raccogli fixtures giornaliere"""
        from datetime import date
        today = date.today()
        
        db = next(get_db())
        try:
            # Raccolta fixtures giornaliere (oggi + domani)
            daily_fixtures = await fixtures_collector.collect_upcoming_fixtures(days_ahead=1)
            await fixtures_collector.update_tracking_status(daily_fixtures, db)
            logger.info(f"📅 Daily fixtures collected: {len(daily_fixtures)}")
            return len(daily_fixtures)
        finally:
            db.close()
    
    async def _count_future_fixtures(self, db) -> int:
        """Conta fixtures future nel database per controllo intelligente"""
        from app.models.odds_tracking import FixtureTrackingStatus
        
        future_cutoff = datetime.now() + timedelta(days=2)
        count = db.query(FixtureTrackingStatus).filter(
            FixtureTrackingStatus.fixture_date > future_cutoff
        ).count()
        return count
    
    # ==========================================
    # NUOVI METODI SEQUENZIALI
    # ==========================================
    
    async def _process_daily_fixtures(self):
        """📅 PROCESSA FIXTURES GIORNALIERE (1x/giorno)"""
        from datetime import date
        today = date.today()
        
        # Controlla se già processate oggi
        if self.last_fixtures_date == today:
            logger.info(f"📅 Daily fixtures already processed today ({today})")
            return
        
        logger.info(f"📅 Processing DAILY fixtures for {today}")
        
        db = next(get_db())
        try:
            # Raccolta fixtures giornaliere (oggi + domani)
            daily_fixtures = await fixtures_collector.collect_upcoming_fixtures(days_ahead=1)
            await fixtures_collector.update_tracking_status(daily_fixtures, db)
            logger.info(f"📅 Daily fixtures: {len(daily_fixtures)}")
            
            self.last_fixtures_date = today
            logger.info(f"✅ Daily fixtures COMPLETED for {today}")
            
        finally:
            db.close()
    
    async def _process_daily_predictions(self):
        """🔮 PROCESSA PREDIZIONI GIORNALIERE (dopo fixtures)"""
        from datetime import date
        today = date.today()
        
        if self.last_predictions_date == today:
            logger.info(f"🔮 Daily predictions already processed today ({today})")
            return
        
        logger.info(f"🔮 Processing DAILY predictions for {today}")
        
        db = next(get_db())
        try:
            # Usa il nuovo metodo ottimizzato (oggi + domani)
            stats = await predictions_collector.collect_daily_predictions_only(db)
            logger.info(f"🔮 Daily predictions: {stats}")
            self.last_predictions_date = today
            logger.info(f"✅ Daily predictions COMPLETED for {today}")
            
        finally:
            db.close()
    
    async def _process_daily_odds(self):
        """🎯 PROCESSA QUOTE GIORNALIERE (tracking continuo per andamento nel tempo)"""
        logger.info("🎯 Processing DAILY odds for continuous tracking")

        db = next(get_db())
        try:
            # Raccogli quote per TUTTE le partite giornaliere per tracking CONTINUO
            fixture_ids = await fixtures_collector.get_daily_fixtures_for_tracking(db)

            if fixture_ids:
                # Non limitiamo più - vogliamo tracking completo per vedere andamento
                stats = await odds_collector.collect_odds_for_fixtures(fixture_ids, db)
                logger.info(f"🎯 Daily odds collected (continuous tracking): {stats}")
            else:
                logger.info("🎯 No daily fixtures for odds tracking")

        finally:
            db.close()
    
    async def _process_future_fixtures(self):
        """🔄 PROCESSA FIXTURES FUTURE (settimanale)"""
        from datetime import date
        today = date.today()
        
        # Solo una volta a settimana (lunedi) o se necessario
        if today.weekday() != 0:  # Non lunedi
            logger.info("🔄 Future fixtures: skipping (not Monday)")
            return
        
        logger.info("🔄 Processing FUTURE fixtures (weekly)")
        
        db = next(get_db())
        try:
            # Controlla se necessario
            future_count = await self._count_future_fixtures(db)
            if future_count >= 5000:  # Soglia sufficiente
                logger.info(f"🔄 Future fixtures: {future_count} already sufficient")
                return
            
            # Raccogli fixtures future
            future_fixtures = await fixtures_collector.collect_upcoming_fixtures(days_ahead=14)
            await fixtures_collector.update_tracking_status(future_fixtures, db)
            logger.info(f"🔄 Future fixtures added: {len(future_fixtures)}")
            
        finally:
            db.close()
    
    async def _process_future_predictions(self):
        """🔮 PROCESSA PREDIZIONI FUTURE (settimanale)"""
        from datetime import date
        today = date.today()
        
        if today.weekday() != 0:  # Solo lunedi
            logger.info("🔮 Future predictions: skipping (not Monday)")
            return
        
        logger.info("🔮 Processing FUTURE predictions (weekly)")
        
        db = next(get_db())
        try:
            future_stats = await predictions_collector.collect_predictions_for_all_fixtures(db)
            logger.info(f"🔮 Future predictions: {future_stats}")
            
        finally:
            db.close()
    
    async def _process_future_odds(self):
        """🎯 PROCESSA QUOTE FUTURE (tracking continuo per andamento nel tempo)"""
        logger.info("🎯 Processing FUTURE odds (continuous tracking)")

        db = next(get_db())
        try:
            # Raccogli quote per TUTTE le future fixtures (non limitato, per storico completo)
            fixture_ids = await fixtures_collector.get_active_fixtures_for_tracking(db)
            if fixture_ids:
                # Non limitiamo più - vogliamo tracking completo per vedere andamento
                stats = await odds_collector.collect_odds_for_fixtures(fixture_ids, db)
                logger.info(f"🎯 Future odds collected (continuous tracking): {stats}")

        finally:
            db.close()

    async def _process_daily_cleanup(self):
        """🧹 PROCESSA PULIZIA GIORNALIERA"""
        logger.info("🧹 Processing DAILY cleanup")
        
        db = next(get_db())
        try:
            cleanup_result = await cleanup_service.cleanup_finished_matches(db)
            logger.info(f"✅ Daily cleanup COMPLETED: {cleanup_result}")
        finally:
            db.close()


class LiveOddsMonitor:
    """🔴 MONITORAGGIO CONTINUO QUOTE LIVE - Processo separato e indipendente"""

    def __init__(self):
        self.running = False
        self.check_interval = 30  # Controlla ogni 30 secondi
        self.max_live_fixtures_per_cycle = 10  # Max 10 partite live per ciclo
        self.rate_limit_semaphore = asyncio.Semaphore(2)  # Max 2 chiamate API simultanee

    async def start(self):
        """🚀 Avvia monitoraggio continuo delle quote live"""
        if self.running:
            logger.warning("🔴 LiveOddsMonitor already running")
            return

        self.running = True
        logger.info("🔴 🚀 Starting LIVE ODDS MONITOR (continuous, separate process)")
        logger.info(f"🔴 ⏰ Check interval: {self.check_interval}s | Max fixtures per cycle: {self.max_live_fixtures_per_cycle} | Rate limit: 2 concurrent API calls")

        try:
            while self.running:
                try:
                    await self._check_and_collect_live_odds()
                except Exception as e:
                    logger.error(f"🔴 ❌ Error in live odds cycle: {str(e)}")

                # Attendi fino al prossimo controllo
                await asyncio.sleep(self.check_interval)

        except Exception as e:
            logger.error(f"🔴 ❌ LiveOddsMonitor fatal error: {str(e)}")
        finally:
            self.running = False

    async def stop(self):
        """🛑 Ferma monitoraggio live"""
        logger.info("🔴 🛑 Stopping LIVE ODDS MONITOR")
        self.running = False

    async def _check_and_collect_live_odds(self):
        """🔍 Controlla partite live e raccogli quote"""
        logger.debug("🔴 🔍 Checking for live fixtures...")

        db = next(get_db())
        try:
            # 1. Ottieni partite attualmente live dal provider
            live_fixture_ids = await self._get_current_live_fixtures()
            logger.debug(f"🔴 📡 Found {len(live_fixture_ids)} live fixtures from API")

            if not live_fixture_ids:
                logger.debug("🔴 💤 No live fixtures found - sleeping...")
                return

            # 2. Limita numero partite per ciclo (protezione sovraccarico)
            limited_ids = live_fixture_ids[:self.max_live_fixtures_per_cycle]
            if len(live_fixture_ids) > self.max_live_fixtures_per_cycle:
                logger.info(f"🔴 ⚠️ Limited to {self.max_live_fixtures_per_cycle} fixtures (found {len(live_fixture_ids)})")

            # 3. Raccolta quote live con rate limiting controllato dal monitor
            logger.info(f"🔴 🎯 Collecting LIVE odds for {len(limited_ids)} fixtures")
            stats = await odds_collector.collect_live_odds_for_fixtures(limited_ids, db, self.rate_limit_semaphore)

            if stats['quotes_collected'] > 0:
                logger.info(f"🔴 ✅ Live odds collected: {stats}")
            else:
                logger.debug(f"🔴 ⚠️ No new live odds collected: {stats}")

        except Exception as e:
            logger.error(f"🔴 ❌ Error checking live fixtures: {str(e)}")
        finally:
            db.close()

    async def _get_current_live_fixtures(self) -> List[int]:
        """📡 Ottieni ID partite attualmente live dal provider"""
        try:
            import httpx
            api_key = "REDACTED"
            url = "https://v3.football.api-sports.io/fixtures?live=all"

            async with httpx.AsyncClient(timeout=10.0) as client:  # Timeout ridotto per velocità
                response = await client.get(url, headers={"x-apisports-key": api_key})

                if response.status_code != 200:
                    logger.warning(f"🔴 ⚠️ API returned status {response.status_code}")
                    return []

                data = response.json()
                live_fixtures = data.get('response', [])

                # Filtra solo partite davvero live
                truly_live_ids = []
                for fixture in live_fixtures:
                    status = fixture.get('fixture', {}).get('status', {})
                    live_statuses = ['1H', 'HT', '2H', 'ET', 'BT', 'P', 'LIVE', 'IN_PLAY', 'PLAYING']

                    if status.get('short') in live_statuses:
                        fixture_id = fixture.get('fixture', {}).get('id')
                        if fixture_id:
                            truly_live_ids.append(fixture_id)

                return truly_live_ids

        except Exception as e:
            logger.error(f"🔴 ❌ Error getting live fixtures from API: {str(e)}")
            return []


# Singleton instances
scheduler = OddsTrackingScheduler()
live_odds_monitor = LiveOddsMonitor()
