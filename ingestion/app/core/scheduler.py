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
        """🎯 PROCESSA QUOTE GIORNALIERE (dopo predizioni)"""
        logger.info("🎯 Processing DAILY odds for today's fixtures")
        
        db = next(get_db())
        try:
            # Raccogli quote SOLO per partite giornaliere che hanno predizioni
            fixture_ids = await fixtures_collector.get_daily_fixtures_for_tracking(db)
            
            if fixture_ids:
                limited_fixtures = fixture_ids[:100]  # Limita per performance
                stats = await odds_collector.collect_odds_for_fixtures(limited_fixtures, db)
                logger.info(f"🎯 Daily odds collected: {stats}")
            else:
                logger.info("🎯 No daily fixtures needing odds collection")
            
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
        """🎯 PROCESSA QUOTE FUTURE (limitato, non continuo)"""
        logger.info("🎯 Processing FUTURE odds (limited batch)")
        
        db = next(get_db())
        try:
            # Raccogli quote per future fixtures (max 50 alla volta)
            fixture_ids = await fixtures_collector.get_active_fixtures_for_tracking(db)
            if fixture_ids:
                limited_fixtures = fixture_ids[:50]  # Molto limitato per future
                stats = await odds_collector.collect_odds_for_fixtures(limited_fixtures, db)
                logger.info(f"🎯 Future odds collected: {stats}")
            
        finally:
            db.close()
    
    async def _process_daily_cleanup(self):
        """🧹 PROCESSA PULIZIA GIORNALIERA"""
        logger.info("🧹 Processing DAILY cleanup")
        
        db = next(get_db())
        try:
            await cleanup_service.perform_cleanup(db)
            logger.info("✅ Daily cleanup COMPLETED")
            
        finally:
            db.close()


# Singleton instance
scheduler = OddsTrackingScheduler()
