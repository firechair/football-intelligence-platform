import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

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
        """Avvia tutti i task schedulati con la NUOVA LOGICA CORRETTA"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        logger.info("🚀 Starting FIP Scheduler with OPTIMIZED LOGIC")
        logger.info("📅 Fixtures: 1x/day with anti-duplicates")
        logger.info("🔮 Predictions: 1x/day (can update)")
        logger.info("🎯 Odds: Continuous for historical timestamps")
        
        # Task principali con NUOVA LOGICA OTTIMIZZATA
        self.tasks = [
            asyncio.create_task(self._daily_fixtures_loop()),      # 1x/giorno
            asyncio.create_task(self._daily_predictions_loop()),   # 1x/giorno
            asyncio.create_task(self._continuous_odds_loop()),     # Continuo
            asyncio.create_task(self._daily_cleanup_loop()),       # 1x/giorno
        ]
        
        # Attendere tutti i task
        try:
            await asyncio.gather(*self.tasks)
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
    
    async def _daily_fixtures_loop(self):
        """📅 FIXTURES: 1x/giorno con controllo anti-duplicati"""
        while self.running:
            try:
                from datetime import date
                today = date.today()
                
                # Controlla se fixtures già processate oggi
                if self.last_fixtures_date != today:
                    logger.info(f"📅 Starting DAILY fixtures collection for {today}")
                    
                    db = next(get_db())
                    try:
                        # 1. Fixtures giornaliere (oggi + domani) 
                        daily_fixtures = await fixtures_collector.collect_upcoming_fixtures(days_ahead=1)
                        await fixtures_collector.update_tracking_status(daily_fixtures, db)
                        logger.info(f"📅 Daily fixtures: {len(daily_fixtures)}")
                        
                        # 2. Fixtures future (fino a 10 giorni) - SOLO se necessario
                        future_count = await self._count_future_fixtures(db)
                        if future_count < 5000:  # Soglia intelligente
                            future_fixtures = await fixtures_collector.collect_upcoming_fixtures(days_ahead=10)
                            await fixtures_collector.update_tracking_status(future_fixtures, db)
                            logger.info(f"📅 Future fixtures: {len(future_fixtures)}")
                        else:
                            logger.info(f"📅 Future fixtures: {future_count} already sufficient")
                        
                        self.last_fixtures_date = today
                        logger.info(f"✅ FIXTURES completed for {today} - next run tomorrow")
                        
                    finally:
                        db.close()
                else:
                    logger.info(f"📅 Fixtures already processed today ({today}) - waiting until tomorrow")
                
            except Exception as e:
                logger.error(f"Error in daily fixtures: {str(e)}")
            
            # Attendi 2 ore prima di ricontrollare (per gestire restart)
            await asyncio.sleep(7200)
    
    async def _daily_predictions_loop(self):
        """🔮 PREDICTIONS: 1x/giorno (può aggiornare quelle esistenti)"""
        while self.running:
            try:
                from datetime import date
                today = date.today()
                
                # Controlla se predictions già processate oggi
                if self.last_predictions_date != today:
                    logger.info(f"🔮 Starting DAILY predictions update for {today}")
                    
                    db = next(get_db())
                    try:
                        # Usa il nuovo metodo ottimizzato (oggi + domani)
                        stats = await predictions_collector.collect_daily_predictions_only(db)
                        logger.info(f"🔮 Daily predictions: {stats}")
                        
                        # Future predictions (aggiornamento settimanale)
                        if today.weekday() == 0:  # Lunedì
                            logger.info("🔮 Weekly future predictions update")
                            future_stats = await predictions_collector.collect_predictions_for_all_fixtures(db)
                            logger.info(f"🔮 Future predictions: {future_stats}")
                        
                        self.last_predictions_date = today
                        logger.info(f"✅ PREDICTIONS completed for {today} - next run tomorrow")
                        
                    finally:
                        db.close()
                else:
                    logger.info(f"🔮 Predictions already processed today ({today}) - waiting until tomorrow")
                    
            except Exception as e:
                logger.error(f"Error in daily predictions: {str(e)}")
            
            # Attendi 2 ore prima di ricontrollare
            await asyncio.sleep(7200)
    
    async def _continuous_odds_loop(self):
        """🎯 ODDS: Processo continuo per storico con timestamp"""
        while self.running:
            try:
                logger.info("🎯 Starting continuous ODDS collection")
                
                db = next(get_db())
                try:
                    # Recupera fixtures che necessitano odds (oggi + prossimi giorni)
                    fixture_ids = await fixtures_collector.get_active_fixtures_for_tracking(db)
                    
                    if fixture_ids:
                        # Limita a 200 fixtures per ciclo per evitare timeout
                        limited_fixtures = fixture_ids[:200] if len(fixture_ids) > 200 else fixture_ids
                        
                        stats = await odds_collector.collect_odds_for_fixtures(limited_fixtures, db)
                        logger.info(f"🎯 Odds collected: {stats} (processed {len(limited_fixtures)}/{len(fixture_ids)})")
                    else:
                        logger.info("🎯 No fixtures needing odds collection")
                        
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"Error in continuous odds: {str(e)}")
            
            # Attendi 30 minuti per il prossimo ciclo odds (CONTINUO per storico)
            await asyncio.sleep(1800)
    
    async def _count_future_fixtures(self, db) -> int:
        """Conta fixtures future nel database per controllo intelligente"""
        from datetime import datetime, timedelta
        from app.models.odds_tracking import FixtureTrackingStatus
        
        future_cutoff = datetime.now() + timedelta(days=2)
        count = db.query(FixtureTrackingStatus).filter(
            FixtureTrackingStatus.fixture_date > future_cutoff
        ).count()
        return count
        
    # ==========================================
    # METODI VECCHI RIMOSSI - SOSTITUITI DA LOGICA OTTIMIZZATA
    # ==========================================
    
    async def _execute_daily_macro_process_OLD_DEPRECATED(self):
        """Esegue il macro processo per le partite giornaliere"""
        logger.info("📊 Starting DAILY macro process")
        
        # 1. Recupero fixtures giornaliere (avvio immediato)
        logger.info("🔄 Collecting daily fixtures")
        await self._collect_daily_fixtures()
        
        # 2. Recupero quote giornaliere (dopo 3 minuti)
        logger.info("⏰ Waiting 3 minutes before daily odds collection")
        await asyncio.sleep(180)  # 3 minuti
        
        logger.info("🎯 Collecting daily odds")
        await self._collect_daily_odds()
        
        # 3. Recupero predizioni giornaliere (dopo 15 minuti dall'inizio)
        logger.info("⏰ Waiting 12 minutes before daily predictions")
        await asyncio.sleep(720)  # 12 minuti (totale 15 dall'inizio)
        
        logger.info("🔮 Collecting daily predictions")
        await self._collect_daily_predictions()
        
        logger.info("✅ DAILY macro process completed")
    
    async def _execute_future_macro_process(self):
        """Esegue il macro processo per le partite future (solo dopo completamento giornaliero)"""
        # Attendi che il processo giornaliero sia completato
        await self.daily_process_completed.wait()
        
        logger.info("🔮 Starting FUTURE macro process")
        
        # 1. Recupero fixtures future
        logger.info("🔄 Collecting future fixtures")
        await self._collect_future_fixtures()
        
        # 2. Recupero quote future
        logger.info("🎯 Collecting future odds")
        await self._collect_future_odds()
        
        # 3. Recupero predizioni future
        logger.info("🔮 Collecting future predictions")
        await self._collect_future_predictions()
        
        logger.info("✅ FUTURE macro process completed")
        
        # Resetta gli eventi per il prossimo ciclo
        self.daily_process_completed.clear()
        self.future_process_completed.clear()
    
    async def _collect_daily_fixtures(self):
        """Raccolta fixtures giornaliere"""
        try:
            db = next(get_db())
            try:
                fixtures = await fixtures_collector.collect_upcoming_fixtures(days_ahead=1)  # Solo 1 giorno
                await fixtures_collector.update_tracking_status(fixtures, db)
                logger.info(f"📅 Daily fixtures collected: {len(fixtures)} fixtures")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error collecting daily fixtures: {str(e)}")
    
    async def _collect_daily_odds(self):
        """Raccolta quote giornaliere"""
        try:
            db = next(get_db())
            try:
                fixture_ids = await fixtures_collector.get_daily_fixtures_for_tracking(db)
                if fixture_ids:
                    stats = await odds_collector.collect_odds_for_fixtures(fixture_ids, db)
                    logger.info(f"🎯 Daily odds collected: {stats}")
                else:
                    logger.info("No daily fixtures for odds collection")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error collecting daily odds: {str(e)}")
    
    async def _collect_daily_predictions(self):
        """Raccolta predizioni giornaliere - NUOVO METODO INDIPENDENTE DALLE ODDS"""
        try:
            db = next(get_db())
            try:
                # USA IL NUOVO METODO: indipendente dalle odds, solo fixtures giornaliere
                stats = await predictions_collector.collect_daily_predictions_only(db)
                logger.info(f"🔮 Daily predictions collected (INDEPENDENT from odds): {stats}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error collecting daily predictions: {str(e)}")
    
    async def _collect_future_fixtures(self):
        """Raccolta fixtures future"""
        try:
            db = next(get_db())
            try:
                fixtures = await fixtures_collector.collect_upcoming_fixtures(days_ahead=settings.FIXTURE_LOOKAHEAD_DAYS)
                await fixtures_collector.update_tracking_status(fixtures, db)
                logger.info(f"📅 Future fixtures collected: {len(fixtures)} fixtures")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error collecting future fixtures: {str(e)}")
    
    async def _collect_future_odds(self):
        """Raccolta quote future"""
        try:
            db = next(get_db())
            try:
                fixture_ids = await fixtures_collector.get_active_fixtures_for_tracking(db)
                if fixture_ids:
                    stats = await odds_collector.collect_odds_for_fixtures(fixture_ids, db)
                    logger.info(f"🎯 Future odds collected: {stats}")
                else:
                    logger.info("No future fixtures for odds collection")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error collecting future odds: {str(e)}")
    
    async def _collect_future_predictions(self):
        """Raccolta predizioni future"""
        try:
            db = next(get_db())
            try:
                stats = await predictions_collector.collect_predictions_for_all_fixtures(db)
                logger.info(f"🔮 Future predictions collected: {stats}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error collecting future predictions: {str(e)}")
    
    async def _daily_cleanup_loop(self):
        """Loop di pulizia frequente (ogni ora per match finiti, daily per dati vecchi)"""
        last_daily_cleanup = None
        
        while self.running:
            try:
                logger.info("🧹 Starting cleanup cycle (hourly)")
                
                db = next(get_db())
                try:
                    # Pulizia match finiti (OGNI ORA)
                    match_stats = await cleanup_service.cleanup_finished_matches(db)
                    logger.info(f"🧹 Hourly cleanup completed: {match_stats}")
                    
                    # Pulizia dati vecchi (SOLO 1 VOLTA AL GIORNO)
                    now = datetime.now()
                    if last_daily_cleanup is None or (now - last_daily_cleanup).total_seconds() >= 86400:
                        await self._cleanup_old_data(db)
                        last_daily_cleanup = now
                        logger.info(f"🧹 Daily cleanup (old data) completed")
                        
                finally:
                    db.close()
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {str(e)}")
            
            # ✅ Attendi 1 ora prima del prossimo cleanup (invece di 24 ore!)
            await asyncio.sleep(3600)  # 1 ora
    
    async def _cleanup_old_data(self, db):
        """Pulisce i dati più vecchi del periodo di retention"""
        from app.models.odds_tracking import ExtendedOddsHistory
        from app.models.predictions import MatchPredictions
        
        cutoff_date = datetime.now() - timedelta(days=settings.ODDS_RETENTION_DAYS)
        
        # Elimina quote vecchie
        deleted_odds = db.query(ExtendedOddsHistory).filter(
            ExtendedOddsHistory.collected_at < cutoff_date
        ).delete(synchronize_session=False)
        
        # Elimina predizioni vecchie
        deleted_predictions = db.query(MatchPredictions).filter(
            MatchPredictions.collected_at < cutoff_date
        ).delete(synchronize_session=False)
        
        db.commit()
        logger.info(f"🧹 Cleanup: deleted {deleted_odds} old odds and {deleted_predictions} old predictions")

# Singleton instance
scheduler = OddsTrackingScheduler()

