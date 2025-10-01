import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.core.database import get_db
from app.models.odds_tracking import ExtendedOddsHistory, FixtureTrackingStatus
from app.models.predictions import MatchPredictions  # 🆕 NUOVO
from app.utils.football_api import football_api
import logging

logger = logging.getLogger(__name__)

class MatchCleanupService:
    def __init__(self):
        self.cleanup_batch_size = 50  # Processa max 50 match alla volta
        self.check_interval_minutes = 15  # Controlla ogni 15 minuti
    
    async def cleanup_finished_matches(self, db: Session) -> Dict[str, Any]:
        """
        ⚡ OTTIMIZZATO: Marca partite finite senza chiamate API + Invalida cache
        Partite iniziate > 2 ore fa vengono marcate come 'completed'
        """
        cleanup_stats = {
            "matches_checked": 0,
            "matches_finished": 0,
            "tracking_records_updated": 0,
            "cache_cleared": False,
            "errors": []
        }
        
        try:
            # ✅ SEMPLICE: Marca come 'completed' tutte le partite iniziate > 2 ore fa
            cutoff_time = datetime.now() - timedelta(hours=2)
            
            finished_fixtures = db.query(FixtureTrackingStatus).filter(
                and_(
                    FixtureTrackingStatus.tracking_status.in_(["active", "pending", "live"]),
                    FixtureTrackingStatus.fixture_date < cutoff_time
                )
            ).all()
            
            cleanup_stats["matches_checked"] = len(finished_fixtures)
            
            if not finished_fixtures:
                logger.info("No finished fixtures to cleanup")
                return cleanup_stats
            
            # Marca tutte come 'completed' in una singola transaction
            updated_count = 0
            for fixture in finished_fixtures:
                fixture.tracking_status = "completed"
                updated_count += 1
            
            db.commit()
            
            cleanup_stats["matches_finished"] = updated_count
            cleanup_stats["tracking_records_updated"] = updated_count
            
            # ✅ INVALIDA LA CACHE dopo aver aggiornato gli stati
            try:
                from app.services.cache_service import cache_service
                cache_service.clear_pattern("fixtures:*")
                cleanup_stats["cache_cleared"] = True
                logger.info("✅ Cache invalidated after cleanup")
            except Exception as cache_error:
                logger.warning(f"⚠️ Failed to clear cache: {cache_error}")
            
            logger.info(f"✅ Cleanup completed: {updated_count} matches marked as completed")
        
        except Exception as e:
            error_msg = f"Error in cleanup process: {str(e)}"
            cleanup_stats["errors"].append(error_msg)
            logger.error(error_msg)
            db.rollback()
        
        return cleanup_stats
    
    def _get_active_fixtures_to_check(self, db: Session) -> List[FixtureTrackingStatus]:
        """Ottieni fixture attive che potrebbero essere finite"""
        # Controlla fixture che dovrebbero essere iniziate da almeno 2 ore
        cutoff_time = datetime.now() - timedelta(hours=2)
        
        return db.query(FixtureTrackingStatus).filter(
            and_(
                FixtureTrackingStatus.tracking_status.in_(["active", "pending"]),
                FixtureTrackingStatus.fixture_date < cutoff_time
            )
        ).order_by(FixtureTrackingStatus.fixture_date).limit(self.cleanup_batch_size).all()
    
    async def _check_fixtures_status_batch(self, fixtures: List[FixtureTrackingStatus]) -> List[int]:
        """Controlla lo stato di più fixture in batch rispettando rate limits"""
        finished_fixture_ids = []
        
        # Dividi in batch di 10 per le chiamate API
        batch_size = 10
        for i in range(0, len(fixtures), batch_size):
            batch = fixtures[i:i + batch_size]
            fixture_ids = [f.fixture_id for f in batch]
            
            try:
                # Chiamata batch per controllare stato
                batch_results = await self._check_multiple_fixtures_status(fixture_ids)
                finished_fixture_ids.extend(batch_results)
                
                # Pausa tra batch per rispettare rate limits
                if i + batch_size < len(fixtures):
                    await asyncio.sleep(2)  # 2 secondi tra batch
                    
            except Exception as e:
                logger.error(f"Error checking batch {i}-{i+batch_size}: {str(e)}")
                continue
        
        return finished_fixture_ids
    
    async def _check_multiple_fixtures_status(self, fixture_ids: List[int]) -> List[int]:
        """Controlla lo stato di multiple fixture usando l'API"""
        finished_fixtures = []
        
        for fixture_id in fixture_ids:
            try:
                # Usa l'endpoint /fixtures?id={fixture_id} per controllare stato
                data = await football_api._make_request("fixtures", {"id": fixture_id})
                fixtures_data = data.get("response", [])
                
                if fixtures_data:
                    fixture = fixtures_data[0]
                    status = fixture.get("fixture", {}).get("status", {}).get("short", "")
                    
                    # Stati che indicano match finito
                    finished_statuses = ["FT", "AET", "PEN", "CANC", "SUSP", "ABD", "AWD", "WO"]
                    if status in finished_statuses:
                        finished_fixtures.append(fixture_id)
                        logger.info(f"Fixture {fixture_id} finished with status: {status}")
                
                # Piccola pausa tra richieste individuali
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error checking fixture {fixture_id}: {str(e)}")
                continue
        
        return finished_fixtures
    
    async def _cleanup_fixtures_batch(self, finished_fixture_ids: List[int], db: Session) -> tuple[int, int, int]:
        """Pulisce i dati di fixture finite in batch per evitare lock"""
        total_odds_deleted = 0
        total_predictions_deleted = 0  # 🆕 NUOVO
        total_tracking_updated = 0
        
        # Processa in batch di 10 per evitare lock del database
        batch_size = 10
        for i in range(0, len(finished_fixture_ids), batch_size):
            batch = finished_fixture_ids[i:i + batch_size]
            
            try:
                # Cancella le quote per questo batch
                odds_deleted = db.query(ExtendedOddsHistory).filter(
                    ExtendedOddsHistory.fixture_id.in_(batch)
                ).delete(synchronize_session=False)
                
                # 🆕 Cancella le predizioni per questo batch
                predictions_deleted = db.query(MatchPredictions).filter(
                    MatchPredictions.fixture_id.in_(batch)
                ).delete(synchronize_session=False)
                
                # Aggiorna lo stato di tracking
                tracking_updated = db.query(FixtureTrackingStatus).filter(
                    FixtureTrackingStatus.fixture_id.in_(batch)
                ).update({
                    "tracking_status": "completed",
                    "updated_at": datetime.now()
                }, synchronize_session=False)
                
                # Commit batch
                db.commit()
                
                total_odds_deleted += odds_deleted
                total_predictions_deleted += predictions_deleted  # 🆕 NUOVO
                total_tracking_updated += tracking_updated
                
                logger.info(f"Cleaned batch {i+1}-{min(i+batch_size, len(finished_fixture_ids))}: "
                          f"{odds_deleted} odds deleted, {predictions_deleted} predictions deleted, "
                          f"{tracking_updated} tracking updated")
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error cleaning batch {i}-{i+batch_size}: {str(e)}")
                continue
        
        return total_odds_deleted, total_predictions_deleted, total_tracking_updated  # 🆕 NUOVO
    
    async def emergency_cleanup(self, db: Session, days_back: int = 7) -> Dict[str, Any]:
        """
        Cleanup di emergenza per liberare spazio nel database
        Rimuove tutti i dati più vecchi di N giorni
        """
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        try:
            # Cancella quote vecchie
            odds_deleted = db.query(ExtendedOddsHistory).filter(
                ExtendedOddsHistory.collected_at < cutoff_date
            ).delete(synchronize_session=False)
            
            # Aggiorna tracking status per fixture vecchie
            tracking_updated = db.query(FixtureTrackingStatus).filter(
                and_(
                    FixtureTrackingStatus.fixture_date < cutoff_date,
                    FixtureTrackingStatus.tracking_status != "completed"
                )
            ).update({
                "tracking_status": "completed",
                "updated_at": datetime.now()
            }, synchronize_session=False)
            
            db.commit()
            
            logger.warning(f"Emergency cleanup executed: {odds_deleted} odds deleted, "
                         f"{tracking_updated} tracking updated for data older than {days_back} days")
            
            return {
                "type": "emergency",
                "days_back": days_back,
                "odds_deleted": odds_deleted,
                "tracking_updated": tracking_updated,
                "cutoff_date": cutoff_date.isoformat()
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Emergency cleanup failed: {str(e)}")
            raise

# Singleton instance
cleanup_service = MatchCleanupService()
