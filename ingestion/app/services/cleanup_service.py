import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
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

    async def cleanup_old_predictions(self, db: Session, days_back: int = 14) -> Dict[str, Any]:
        """
        🚀 AGGRESSIVE CLEANUP: Sistema ottimizzato per ridurre spazio database
        Cancella predizioni più vecchie di 14 giorni (accuracy system usa solo ultimi 7 giorni)
        """
        try:
            # 🔍 FASE 1: VALUTAZIONE ACCURATEZZA (se disponibile)
            try:
                await self._complete_accuracy_evaluation_for_finished_matches(db)
                accuracy_evaluation_completed = True
            except Exception as e:
                logger.info(f"Accuracy evaluation not available or failed: {e}")
                accuracy_evaluation_completed = False

            # 🧹 FASE 2: PULISCE PREDIZIONI VECCHIE (dopo 14 giorni)
            aggressive_cleanup_stats = await self._aggressive_cleanup_old_data(db)

            # 🚀 FASE 3: PULISCE PREDIZIONI FUTURE LONTANE
            future_cleanup_stats = await self._cleanup_future_predictions(db)

            total_deleted = (
                aggressive_cleanup_stats['predictions_deleted'] +
                aggressive_cleanup_stats['accuracy_deleted'] +
                future_cleanup_stats['deleted']
            )

            cleanup_result = {
                "type": "aggressive_predictions_cleanup",
                "phases_completed": {
                    "accuracy_evaluation": accuracy_evaluation_completed,
                    "aggressive_cleanup": aggressive_cleanup_stats,
                    "future_cleanup": future_cleanup_stats
                },
                "total_predictions_deleted": total_deleted,
                "logic_explanation": {
                    "accuracy_system_needs": "Solo ultimi 7 giorni per valutazioni",
                    "cleanup_cutoff_days": 14,
                    "aggressive_approach": "Elimina dati non più necessari",
                    "space_optimization": "Riduce significativamente spazio database"
                }
            }

            if total_deleted > 0:
                logger.info(f"🧹 Aggressive predictions cleanup: {total_deleted} items removed")
            else:
                logger.info("🧹 Aggressive predictions cleanup: No old data to remove")

            return cleanup_result

        except Exception as e:
            db.rollback()
            logger.error(f"Aggressive predictions cleanup failed: {str(e)}")
            raise

    async def _complete_accuracy_evaluation_for_finished_matches(self, db: Session) -> Dict[str, Any]:
        """Completa la valutazione dell'accuratezza per tutte le partite finite che hanno predizioni"""
        try:
            from app.services.accuracy_evaluator import PredictionAccuracyEvaluator
            from app.models.accuracy_tracking import PredictionAccuracy
        except ImportError:
            logger.info("Accuracy evaluation not available, skipping")
            return {"evaluated": 0, "message": "Accuracy evaluation not available"}

        try:
            evaluator = PredictionAccuracyEvaluator(db)

            # Trova partite finite con predizioni non ancora valutate
            unvaluated_finished = db.query(MatchPredictions.fixture_id).filter(
                and_(
                    MatchPredictions.fixture_id.in_(
                        db.query(FixtureTrackingStatus.fixture_id).filter(
                            FixtureTrackingStatus.tracking_status == "completed"
                        )
                    ),
                    ~MatchPredictions.fixture_id.in_(
                        db.query(PredictionAccuracy.fixture_id)
                    )
                )
            ).distinct().all()

            unvaluated_fixture_ids = [row[0] for row in unvaluated_finished]

            if not unvaluated_fixture_ids:
                logger.info("✅ All finished matches with predictions are already evaluated")
                return {"evaluated": 0, "message": "All evaluations complete"}

            # Valuta l'accuratezza per queste partite
            logger.info(f"🔍 Evaluating accuracy for {len(unvaluated_fixture_ids)} finished matches")
            evaluated_count = 0

            for fixture_id in unvaluated_fixture_ids:
                try:
                    # Recupera dati necessari per valutazione
                    fixture_data = await self._get_fixture_data_for_accuracy_evaluation(db, fixture_id)
                    if fixture_data:
                        success = await evaluator._evaluate_single_prediction(fixture_data)
                        if success:
                            evaluated_count += 1
                except Exception as e:
                    logger.error(f"Failed to evaluate accuracy for fixture {fixture_id}: {str(e)}")
                    continue

            logger.info(f"✅ Completed accuracy evaluation for {evaluated_count} matches")
            return {"evaluated": evaluated_count, "total_found": len(unvaluated_fixture_ids)}

        except Exception as e:
            logger.warning(f"Accuracy evaluation failed, but cleanup will continue: {e}")
            return {"evaluated": 0, "message": f"Accuracy evaluation failed: {e}"}

    async def _get_fixture_data_for_accuracy_evaluation(self, db: Session, fixture_id: int) -> Optional[Dict[str, Any]]:
        """Recupera tutti i dati necessari per valutare l'accuratezza di una partita"""
        try:
            # Recupera dati partita finita
            finished_fixture = db.query(FinishedFixtures).filter(
                FinishedFixtures.fixture_id == fixture_id
            ).first()

            if not finished_fixture:
                logger.warning(f"No finished fixture data for {fixture_id}")
                return None

            # Recupera predizione
            prediction = db.query(MatchPredictions).filter(
                MatchPredictions.fixture_id == fixture_id
            ).first()

            if not prediction:
                logger.warning(f"No prediction data for {fixture_id}")
                return None

            return {
                'fixture_id': fixture_id,
                'fixture_date': finished_fixture.fixture_date,
                'actual_home_score': finished_fixture.home_score,
                'actual_away_score': finished_fixture.away_score,
                'actual_winner': finished_fixture.winner,
                'actual_total_goals': finished_fixture.total_goals,
                'home_team': finished_fixture.home_team,
                'away_team': finished_fixture.away_team,
                'predicted_winner_name': prediction.winner_team_name,
                'predicted_win_or_draw': prediction.win_or_draw,
                'predicted_under_over': prediction.under_over,
                'predicted_goals_home': prediction.goals_home,
                'predicted_goals_away': prediction.goals_away,
                'prediction_advice': prediction.advice,
                'prediction_collected_at': prediction.collected_at
            }

        except Exception as e:
            logger.error(f"Error getting fixture data for accuracy evaluation: {str(e)}")
            return None

    async def _cleanup_evaluated_predictions(self, db: Session) -> Dict[str, Any]:
        """Pulisce predizioni che sono state valutate e sono vecchie di almeno 7 giorni"""
        evaluation_cutoff = datetime.now() - timedelta(days=7)

        deleted = db.query(MatchPredictions).filter(
            and_(
                MatchPredictions.fixture_id.in_(
                    db.query(PredictionAccuracy.fixture_id).filter(
                        PredictionAccuracy.evaluated_at < evaluation_cutoff
                    )
                ),
                MatchPredictions.fixture_id.in_(
                    db.query(FixtureTrackingStatus.fixture_id).filter(
                        FixtureTrackingStatus.tracking_status == "completed"
                    )
                )
            )
        ).delete(synchronize_session=False)

        return {"deleted": deleted, "days_after_evaluation": 7}

    async def _cleanup_very_old_predictions(self, db: Session, days_back: int) -> Dict[str, Any]:
        """Pulisce predizioni molto vecchie (>90 giorni) come fallback di sicurezza"""
        very_old_cutoff = datetime.now() - timedelta(days=90)

        deleted = db.query(MatchPredictions).filter(
            MatchPredictions.collected_at < very_old_cutoff
        ).delete(synchronize_session=False)

        return {"deleted": deleted, "cutoff_days": 90}

    async def _aggressive_cleanup_old_data(self, db: Session) -> Dict[str, Any]:
        """🚀 AGGRESSIVE: Cancella predizioni e valutazioni più vecchie di 14 giorni"""
        cutoff_date = datetime.now() - timedelta(days=14)

        # Cancella predizioni vecchie
        predictions_deleted = db.query(MatchPredictions).filter(
            MatchPredictions.collected_at < cutoff_date
        ).delete(synchronize_session=False)

        # Cancella valutazioni accuratezza vecchie (associate alle predizioni)
        # Import inline to avoid circular imports
        accuracy_deleted = 0
        try:
            # Try to import the model
            from app.models.accuracy_tracking import PredictionAccuracy
            # Check if table exists before querying
            from sqlalchemy import text
            table_exists = db.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{PredictionAccuracy.__tablename__}'")).fetchone()
            if table_exists:
                accuracy_deleted = db.query(PredictionAccuracy).filter(
                    PredictionAccuracy.evaluated_at < cutoff_date
                ).delete(synchronize_session=False)
            else:
                logger.info(f"Table {PredictionAccuracy.__tablename__} does not exist, skipping accuracy cleanup")
        except (ImportError, AttributeError, Exception) as e:
            # If model not available or table doesn't exist, skip accuracy cleanup
            logger.info(f"PredictionAccuracy cleanup not available: {e}")
            accuracy_deleted = 0

        # Commit per liberare spazio
        db.commit()

        return {
            "predictions_deleted": predictions_deleted,
            "accuracy_deleted": accuracy_deleted,
            "cutoff_days": 14,
            "cutoff_date": cutoff_date.isoformat()
        }

    async def _cleanup_future_predictions(self, db: Session) -> Dict[str, Any]:
        """Pulisce predizioni per partite future molto lontane (>180 giorni)"""
        future_cutoff = datetime.now() + timedelta(days=180)

        deleted = db.query(MatchPredictions).filter(
            MatchPredictions.fixture_date > future_cutoff
        ).delete(synchronize_session=False)

        return {"deleted": deleted, "future_days": 180}

# Singleton instance
cleanup_service = MatchCleanupService()
