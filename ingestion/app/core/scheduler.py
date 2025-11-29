import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import List

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
        """🚀 PRODUCTION SCHEDULER: Continuous execution with proper timing intervals"""
        if self.running:
            logger.warning("Scheduler already running")
            return

        self.running = True
        logger.info("🚀 Starting FIP Production Scheduler")
        logger.info("📋 Schedule: Job A (fixtures) every 6h, Job B (predictions) every 6h, Job C (odds) every 3h, Job D (results) every 30min")

        try:
            # Initialize tracking variables
            self.last_fixtures_daily = None
            self.last_fixtures_future = None
            self.last_predictions = None
            self.last_odds = None
            self.last_results_check = None

            # Start continuous scheduling loop
            await self._run_scheduling_loop()

        except Exception as e:
            logger.error(f"Scheduler error: {str(e)}")
        finally:
            self.running = False

    async def _run_scheduling_loop(self):
        """Main scheduling loop with proper timing"""
        logger.info("🔄 Starting continuous scheduling loop...")

        while self.running:
            try:
                current_time = datetime.now()

                # Job A - Fetch Fixtures (daily fixtures every 6 hours, future fixtures daily)
                await self._check_and_run_job_a(current_time)

                # Job B - Fetch Predictions (every 6 hours)
                await self._check_and_run_job_b(current_time)

                # Job C - Fetch Odds (every 3 hours)
                await self._check_and_run_job_c(current_time)

                # Job D - Match Result Checker (every 30 minutes)
                await self._check_and_run_job_d(current_time)

                # Wait 5 minutes before next check (fine-grained control)
                await asyncio.sleep(300)  # 5 minutes

            except Exception as e:
                logger.error(f"Error in scheduling loop: {str(e)}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    async def _check_and_run_job_a(self, current_time):
        """Job A - Fetch Fixtures: Daily fixtures every 6h, future fixtures daily"""
        # Daily fixtures - every 6 hours
        if (self.last_fixtures_daily is None or
            (current_time - self.last_fixtures_daily) >= timedelta(hours=6)):
            logger.info("📅 Job A: Running daily fixtures collection")
            await self._process_daily_fixtures()
            self.last_fixtures_daily = current_time

        # Future fixtures - once daily
        if (self.last_fixtures_future is None or
            current_time.date() != self.last_fixtures_future.date()):
            logger.info("🔄 Job A: Running future fixtures collection")
            await self._process_future_fixtures()
            self.last_fixtures_future = current_time

    async def _check_and_run_job_b(self, current_time):
        """Job B - Fetch Predictions: Every 6 hours"""
        if (self.last_predictions is None or
            (current_time - self.last_predictions) >= timedelta(hours=6)):
            logger.info("🔮 Job B: Running predictions collection")
            await self._process_daily_predictions()
            await self._process_future_predictions()
            self.last_predictions = current_time

    async def _check_and_run_job_c(self, current_time):
        """Job C - Fetch Odds: Every 3 hours"""
        if (self.last_odds is None or
            (current_time - self.last_odds) >= timedelta(hours=3)):
            logger.info("🎯 Job C: Running odds collection")
            await self._process_daily_odds()
            await self._process_future_odds()
            self.last_odds = current_time

    async def _check_and_run_job_d(self, current_time):
        """Job D - Match Result Checker: Every 30 minutes"""
        if (self.last_results_check is None or
            (current_time - self.last_results_check) >= timedelta(minutes=30)):
            logger.info("✅ Job D: Running result checker")
            await self._process_results_check()
            self.last_results_check = current_time

    async def run_daily_collection(self):
        """🎯 MANUAL DAILY COLLECTION - Can be called by cron jobs"""
        logger.info("📅 Running manual daily collection cycle...")

        try:
            # Core daily tasks
            await self._process_daily_fixtures()
            await self._process_daily_predictions()
            await self._process_daily_odds()
            await self._process_daily_cleanup()

            logger.info("✅ Daily collection completed!")

        except Exception as e:
            logger.error(f"Daily collection error: {str(e)}")
            raise

    async def run_weekly_collection(self):
        """📆 MANUAL WEEKLY COLLECTION - Can be called by cron jobs"""
        logger.info("📆 Running manual weekly collection cycle...")

        try:
            # Weekly tasks
            await self._process_future_fixtures()
            await self._process_future_predictions()
            await self._process_future_odds()

            logger.info("✅ Weekly collection completed!")

        except Exception as e:
            logger.error(f"Weekly collection error: {str(e)}")
            raise
    
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
        """📅 Job A - PROCESSA FIXTURES GIORNALIERE (ogni 6 ore)"""
        logger.info("📅 Job A: Processing daily fixtures (today + tomorrow)")

        db = next(get_db())
        try:
            # Raccolta fixtures giornaliere (oggi + domani) - ogni 6 ore
            daily_fixtures = await fixtures_collector.collect_upcoming_fixtures(days_ahead=1)
            await fixtures_collector.update_tracking_status(daily_fixtures, db)
            logger.info(f"📅 Daily fixtures collected: {len(daily_fixtures)} fixtures")

        finally:
            db.close()
    
    async def _process_daily_predictions(self):
        """🔮 Job B - PROCESSA PREDIZIONI GIORNALIERE (ogni 6 ore)"""
        logger.info("🔮 Job B: Processing daily predictions (every 6 hours)")

        db = next(get_db())
        try:
            # Collect predictions for daily fixtures (today + tomorrow)
            stats = await predictions_collector.collect_daily_predictions_only(db)
            logger.info(f"🔮 Daily predictions collected: {stats}")

        finally:
            db.close()
    
    async def _process_daily_odds(self):
        """🎯 Job C - PROCESSA QUOTE GIORNALIERE (ogni 3 ore)"""
        logger.info("🎯 Job C: Processing daily odds (every 3 hours)")

        db = next(get_db())
        try:
            # Collect odds for daily fixtures
            fixture_ids = await fixtures_collector.get_daily_fixtures_for_tracking(db)

            if fixture_ids:
                stats = await odds_collector.collect_odds_for_fixtures(fixture_ids, db)
                logger.info(f"🎯 Daily odds collected: {stats}")
            else:
                logger.info("🎯 No daily fixtures for odds collection")

        finally:
            db.close()
    
    async def _process_future_fixtures(self):
        """🔄 Job A - PROCESSA FIXTURES FUTURE (una volta al giorno)"""
        logger.info("🔄 Job A: Processing future fixtures (7-14 days, daily)")

        db = next(get_db())
        try:
            # Collect future fixtures (7-14 days ahead)
            future_fixtures = await fixtures_collector.collect_upcoming_fixtures(days_ahead=14)
            await fixtures_collector.update_tracking_status(future_fixtures, db)
            logger.info(f"🔄 Future fixtures collected: {len(future_fixtures)} fixtures")

        finally:
            db.close()
    
    async def _process_future_predictions(self):
        """🔮 Job B - PROCESSA PREDIZIONI FUTURE (settimanale - lunedì)"""
        from datetime import date
        today = date.today()

        if today.weekday() != 0:  # Solo lunedì
            logger.info("🔮 Future predictions: skipping (not Monday)")
            return

        logger.info("🔮 Job B: Processing future predictions (weekly)")

        db = next(get_db())
        try:
            future_stats = await predictions_collector.collect_predictions_for_all_fixtures(db)
            logger.info(f"🔮 Future predictions collected: {future_stats}")

        finally:
            db.close()
    
    async def _process_future_odds(self):
        """🎯 Job C - PROCESSA QUOTE FUTURE (ogni 3 ore)"""
        logger.info("🎯 Job C: Processing future odds (every 3 hours)")

        db = next(get_db())
        try:
            # Collect odds for future fixtures
            fixture_ids = await fixtures_collector.get_active_fixtures_for_tracking(db)
            if fixture_ids:
                stats = await odds_collector.collect_odds_for_fixtures(fixture_ids, db)
                logger.info(f"🎯 Future odds collected: {stats}")

        finally:
            db.close()

    async def _process_results_check(self):
        """✅ Job D - Match Result Checker (ogni 30 minuti)"""
        logger.info("✅ Processing match result checker")

        db = next(get_db())
        try:
            # Check for finished matches and update results
            # This would integrate with a results checking service
            # For now, use the existing cleanup service which handles finished matches
            result_check = await cleanup_service.cleanup_finished_matches(db)
            logger.info(f"✅ Result checker processed: {result_check} matches")

        finally:
            db.close()

    async def _process_daily_cleanup(self):
        """🧹 PROCESSA PULIZIA GIORNALIERA"""
        logger.info("🧹 Processing DAILY cleanup")

        db = next(get_db())
        try:
            # 1. Cleanup partite finite
            cleanup_result = await cleanup_service.cleanup_finished_matches(db)
            logger.info(f"✅ Fixtures cleanup COMPLETED: {cleanup_result}")

            # 2. 🆕 Cleanup predizioni vecchie
            predictions_cleanup_result = await cleanup_service.cleanup_old_predictions(db)
            logger.info(f"✅ Predictions cleanup COMPLETED: {predictions_cleanup_result}")

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
            from app.core.config import settings
            
            # Use secure API key from settings
            api_key = settings.FOOTBALL_API_KEY
            url = f"{settings.FOOTBALL_API_BASE_URL}/fixtures?live=all"

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
