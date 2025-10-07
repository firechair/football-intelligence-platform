import asyncio
import logging
from datetime import datetime, timedelta
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
        self.last_macro_process_date = None
        self.continuous_odds_running = False
    
    async def start(self):
        """Avvia il flusso SEQUENZIALE ESATTO richiesto: MACRO → FUTURE → SEQUENZA GIORNO PER GIORNO"""
        if self.running:
            logger.warning("Scheduler already running")
            return

        self.running = True
        logger.info("🚀 Starting FIP Scheduler with EXACT SEQUENTIAL LOGIC (NO LIMITS)")
        logger.info("📅 MACRO: Fixtures Giornaliere → Predizioni Giornaliere → Quote Giornaliere")
        logger.info("🔄 POI: Fixtures Future → Sequenza Predizioni+Quote giorno per giorno")
        logger.info("🎯 POI: Processo Quote Continuo per storico")

        try:
            # 🔥 STARTUP: Prima esecuzione immediata per popolare database
            logger.info("🔥 STARTUP: Running initial macro process...")
            await self._run_macro_process()
            logger.info("🔥 STARTUP: Initial macro completed, starting continuous quote monitoring...")

            # 🚀 AVVIA MONITORAGGIO QUOTE CONTINUO (processo separato)
            if not self.continuous_odds_running:
                asyncio.create_task(self._run_continuous_odds_monitoring())
                self.continuous_odds_running = True

            while self.running:
                # ⏰ MACRO PROCESSO GIORNALIERO (ogni 24 ore alla mezzanotte)
                current_date = datetime.now().date()
                if self.last_macro_process_date != current_date:
                    logger.info(f"🕛 Starting MACRO PROCESS for {current_date}")

                    # FERMA monitoraggio quote continuo durante macro processo
                    self.continuous_odds_running = False
                    await asyncio.sleep(2)  # Dà tempo al processo continuo di fermarsi

                    await self._run_macro_process()

                    # SUBITO DOPO: SEQUENZA FUTURE (fixtures future + predizioni+quote giorno per giorno)
                    logger.info("🔄 Starting FUTURE SEQUENCE after macro process")
                    await self._run_future_sequence()

                    self.last_macro_process_date = current_date

                    # RIAVVIA monitoraggio quote continuo
                    if not self.continuous_odds_running:
                        asyncio.create_task(self._run_continuous_odds_monitoring())
                        self.continuous_odds_running = True

                # Attendi controllo ogni ora
                await asyncio.sleep(60 * 60)  # 1 ora

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
    
    async def _count_future_fixtures(self, db) -> int:
        """Conta fixtures future nel database per controllo intelligente"""
        from app.models.odds_tracking import FixtureTrackingStatus

        future_cutoff = datetime.now() + timedelta(days=2)
        count = db.query(FixtureTrackingStatus).filter(
            FixtureTrackingStatus.fixture_date > future_cutoff
        ).count()
        return count
    
    # ==========================================
    # NUOVI METODI SEQUENZIALI ESATTI
    # ==========================================

    async def _run_macro_process(self):
        """📅 MACRO PROCESSO GIORNALIERO: Fixtures → Predizioni → Quote (sequenziale, no limiti)"""
        logger.info("🚀 STARTING MACRO PROCESS: Fixtures Giornaliere → Predizioni → Quote")

        db = next(get_db())
        try:
            # 1. FIXTURES GIORNALIERE (oggi + domani)
            logger.info("📅 Step 1: Collecting DAILY fixtures (today + tomorrow)")
            daily_fixtures = await fixtures_collector.collect_upcoming_fixtures(days_ahead=1)
            await fixtures_collector.update_tracking_status(daily_fixtures, db)
            logger.info(f"📅 Daily fixtures collected: {len(daily_fixtures)} matches")

            # SUBITO DOPO: 2. PREDIZIONI per fixtures giornaliere
            logger.info("🔮 Step 2: Collecting PREDICTIONS for daily fixtures")
            daily_predictions_stats = await predictions_collector.collect_daily_predictions_only(db)
            logger.info(f"🔮 Daily predictions completed: {daily_predictions_stats}")

            # SUBITO DOPO: 3. QUOTE per fixtures giornaliere
            logger.info("🎯 Step 3: Collecting ODDS for daily fixtures")
            daily_fixture_ids = await fixtures_collector.get_daily_fixtures_for_tracking(db)
            if daily_fixture_ids:
                daily_odds_stats = await odds_collector.collect_odds_for_fixtures(daily_fixture_ids, db)
                logger.info(f"🎯 Daily odds completed: {daily_odds_stats}")
            else:
                logger.info("🎯 No daily fixtures for odds collection")

            logger.info("✅ MACRO PROCESS COMPLETED: Daily fixtures → predictions → odds")

        finally:
            db.close()

    async def _run_future_sequence(self):
        """🔄 SEQUENZA FUTURE: Fixtures Future → Predizioni+Quote giorno per giorno"""
        logger.info("🔄 STARTING FUTURE SEQUENCE: Future Fixtures → Day-by-Day Predictions+Odds")

        db = next(get_db())
        try:
            # 1. FIXTURES FUTURE (9-10 giorni)
            logger.info("🏟️ Step 1: Collecting FUTURE fixtures (9-10 days ahead)")
            future_fixtures = await fixtures_collector.collect_upcoming_fixtures(days_ahead=10)
            await fixtures_collector.update_tracking_status(future_fixtures, db)
            logger.info(f"🏟️ Future fixtures collected: {len(future_fixtures)} matches")

            # SUBITO DOPO: 2. SEQUENZA PREDIZIONI + QUOTE GIORNO PER GIORNO
            logger.info("🔄 Step 2: Starting DAY-BY-DAY sequence for predictions and odds")

            # Da domani fino a 9-10 giorni dopo
            from datetime import date, timedelta
            today = date.today()

            for day_offset in range(1, 11):  # Giorno 1 a giorno 10
                target_date = today + timedelta(days=day_offset)

                logger.info(f"📆 Processing day {day_offset}/10: {target_date}")

                # PREDIZIONI per questo giorno
                logger.info(f"🔮 Collecting PREDICTIONS for {target_date}")
                day_predictions_stats = await predictions_collector.collect_future_predictions_by_day(db, days_ahead=10)
                logger.info(f"🔮 Day {day_offset} predictions: {day_predictions_stats}")

                # SUBITO DOPO: QUOTE per questo giorno
                logger.info(f"🎯 Collecting ODDS for {target_date}")
                day_odds_stats = await odds_collector.collect_future_odds_by_day(db, days_ahead=10)
                logger.info(f"🎯 Day {day_offset} odds: {day_odds_stats}")

            logger.info("✅ FUTURE SEQUENCE COMPLETED: All days processed")

        finally:
            db.close()

    async def _run_continuous_odds_monitoring(self):
        """🎯 MONITORAGGIO QUOTE CONTINUO per storico (separato, con timestamp)"""
        logger.info("🎯 STARTING CONTINUOUS ODDS MONITORING (historical tracking)")

        while self.continuous_odds_running and self.running:
            try:
                # FERMATI durante il macro processo giornaliero
                current_date = datetime.now().date()
                if self.last_macro_process_date == current_date:
                    logger.info("🎯 Continuous odds: Pausing during macro process...")
                    await asyncio.sleep(60)  # Aspetta 1 minuto e ricontrolla
                    continue

                logger.info("🎯 Continuous odds: Processing historical odds tracking")

                db = next(get_db())
                try:
                    # Raccolta quote continue per storico (da oggi in poi, giorno per giorno)
                    continuous_stats = await odds_collector.collect_future_odds_by_day(db, days_ahead=10)
                    logger.info(f"🎯 Continuous odds completed: {continuous_stats}")

                finally:
                    db.close()

                # Aspetta prima del prossimo ciclo (non sovrapporsi con macro)
                # Rate limiting: aspettiamo 3 ore come raccomandato dalla documentazione API per odds
                await asyncio.sleep(3 * 60 * 60)  # 3 ore = 10800 secondi

            except Exception as e:
                logger.error(f"🎯 Continuous odds error: {str(e)}")
                await asyncio.sleep(5 * 60)  # Aspetta 5 minuti in caso di errore

        logger.info("🎯 CONTINUOUS ODDS MONITORING STOPPED")


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
