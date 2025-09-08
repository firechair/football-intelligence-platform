import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from app.services.fixtures_collector import fixtures_collector
from app.services.odds_collector import odds_collector
from app.services.cleanup_service import cleanup_service
from app.services.predictions_collector import predictions_collector  # 🆕 NUOVO
from app.core.database import get_db
from app.core.config import settings

logger = logging.getLogger(__name__)

class OddsTrackingScheduler:
    def __init__(self):
        self.running = False
        self.tasks = []
    
    async def start(self):
        """Avvia tutti i task schedulati"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        logger.info("Starting odds tracking scheduler")
        
        # Task principali
        self.tasks = [
            asyncio.create_task(self._fixtures_collection_loop()),
            asyncio.create_task(self._odds_collection_loop()),
            asyncio.create_task(self._predictions_collection_loop()),  # 🆕 NUOVO
            asyncio.create_task(self._cleanup_loop()),
            asyncio.create_task(self._match_cleanup_loop()),
            asyncio.create_task(self._health_check_loop()),
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
    
    async def _fixtures_collection_loop(self):
        """Loop di raccolta partite (ogni 30 minuti)"""
        while self.running:
            try:
                logger.info("Starting fixtures collection cycle")
                
                # Raccogli partite
                fixtures = await fixtures_collector.collect_upcoming_fixtures(
                    days_ahead=settings.FIXTURE_LOOKAHEAD_DAYS
                )
                
                # Aggiorna database
                db = next(get_db())
                try:
                    await fixtures_collector.update_tracking_status(fixtures, db)
                    logger.info(f"Fixtures collection completed: {len(fixtures)} fixtures")
                finally:
                    db.close()
                
            except Exception as e:
                logger.error(f"Error in fixtures collection: {str(e)}")
            
            # Attendi prossimo ciclo
            await asyncio.sleep(settings.FIXTURES_SYNC_INTERVAL)
    
    async def _odds_collection_loop(self):
        """Loop di raccolta quote (ogni ora)"""
        while self.running:
            try:
                logger.info("Starting odds collection cycle")
                
                db = next(get_db())
                try:
                    # Ottieni partite da tracciare
                    fixture_ids = await fixtures_collector.get_active_fixtures_for_tracking(db)
                    
                    if fixture_ids:
                        # Raccogli quote
                        stats = await odds_collector.collect_odds_for_fixtures(fixture_ids, db)
                        logger.info(f"Odds collection completed: {stats}")
                    else:
                        logger.info("No fixtures to track")
                
                finally:
                    db.close()
                
            except Exception as e:
                logger.error(f"Error in odds collection: {str(e)}")
            
            # Attendi prossimo ciclo
            await asyncio.sleep(settings.ODDS_COLLECTION_INTERVAL)
    
    async def _cleanup_loop(self):
        """Loop di pulizia dati vecchi (ogni giorno)"""
        while self.running:
            try:
                logger.info("Starting cleanup cycle")
                
                db = next(get_db())
                try:
                    await self._cleanup_old_data(db)
                    logger.info("Cleanup completed")
                finally:
                    db.close()
                
            except Exception as e:
                logger.error(f"Error in cleanup: {str(e)}")
            
            # Attendi prossimo ciclo
            await asyncio.sleep(settings.CLEANUP_INTERVAL)
    
    async def _match_cleanup_loop(self):
        """Loop di cleanup match finiti (ogni 15 minuti)"""
        while self.running:
            try:
                logger.info("Starting match cleanup cycle")
                
                db = next(get_db())
                try:
                    # Esegui cleanup dei match finiti
                    stats = await cleanup_service.cleanup_finished_matches(db)
                    logger.info(f"Match cleanup completed: {stats}")
                finally:
                    db.close()
                
            except Exception as e:
                logger.error(f"Error in match cleanup: {str(e)}")
            
            # Attendi prossimo ciclo (15 minuti)
            await asyncio.sleep(900)  # 15 minuti
    
    async def _health_check_loop(self):
        """Loop di monitoraggio salute (ogni 10 minuti)"""
        while self.running:
            try:
                await self._perform_health_checks()
            except Exception as e:
                logger.error(f"Health check error: {str(e)}")
            
            await asyncio.sleep(600)  # 10 minuti
    
    async def _cleanup_old_data(self, db):
        """Pulisce i dati più vecchi del periodo di retention"""
        from app.models.odds_tracking import ExtendedOddsHistory
        
        cutoff_date = datetime.now() - timedelta(days=settings.ODDS_RETENTION_DAYS)
        
        # Elimina quote vecchie
        deleted_odds = db.query(ExtendedOddsHistory).filter(
            ExtendedOddsHistory.collected_at < cutoff_date
        ).delete(synchronize_session=False)
        
        db.commit()
        logger.info(f"Cleanup: deleted {deleted_odds} old odds records")
    
    async def _perform_health_checks(self):
        """Esegue controlli di salute del sistema"""
        checks = {
            "api_connectivity": await self._check_api_connectivity(),
            "database_connectivity": await self._check_database_connectivity(),
            "recent_data_collection": await self._check_recent_data_collection(),
        }
        
        all_healthy = all(checks.values())
        
        if all_healthy:
            logger.info("Health check: All systems healthy")
        else:
            failed_checks = [check for check, status in checks.items() if not status]
            logger.warning(f"Health check: Failed checks: {failed_checks}")
    
    async def _check_api_connectivity(self) -> bool:
        """Controlla connettività API"""
        try:
            from app.utils.football_api import football_api
            data = await football_api._make_request("fixtures", {"date": "2024-01-01"})
            return data is not None
        except Exception:
            return False
    
    async def _check_database_connectivity(self) -> bool:
        """Controlla connettività database"""
        try:
            db = next(get_db())
            try:
                from app.models.odds_tracking import ExtendedOddsHistory
                db.query(ExtendedOddsHistory).first()
                return True
            finally:
                db.close()
        except Exception:
            return False
    
    async def _check_recent_data_collection(self) -> bool:
        """Controlla se ci sono state raccolte di dati recenti"""
        try:
            db = next(get_db())
            try:
                from app.models.odds_tracking import ExtendedOddsHistory
                recent_cutoff = datetime.now() - timedelta(hours=2)
                recent_data = db.query(ExtendedOddsHistory).filter(
                    ExtendedOddsHistory.collected_at > recent_cutoff
                ).first()
                return recent_data is not None
            finally:
                db.close()
        except Exception:
            return False
    
    # 🆕 NUOVO METODO
    async def _predictions_collection_loop(self):
        """Loop di raccolta predizioni (ogni 6 ore)"""
        while self.running:
            try:
                logger.info("Starting predictions collection cycle")
                
                db = next(get_db())
                try:
                    stats = await predictions_collector.collect_predictions_for_all_fixtures(db)
                    logger.info(f"Predictions collection completed: {stats}")
                finally:
                    db.close()
                
            except Exception as e:
                logger.error(f"Error in predictions collection: {str(e)}")
            
            # Attendi prossimo ciclo (6 ore)
            await asyncio.sleep(settings.PREDICTIONS_COLLECTION_INTERVAL)

# Singleton instance
scheduler = OddsTrackingScheduler()

