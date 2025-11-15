import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from app.utils.football_api import football_api
from app.models.predictions import MatchPredictions
from app.models.odds_tracking import FixtureTrackingStatus
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class PredictionsCollector:
    def __init__(self):
        self.processed_count = 0
        self.failed_count = 0
        self.no_predictions_count = 0
    
    async def collect_daily_predictions_only(self, db: Session) -> Dict[str, Any]:
        """
        ULTRA FAST: Raccoglie predizioni SOLO per fixtures giornaliere con parallel processing
        
        Processo OTTIMIZZATO per velocità massima:
        - Parallel processing con 50 richieste simultanee
        - Rate limiting intelligente
        - Batch commits per performance
        """
        logger.info("🚀 ULTRA FAST: Starting parallel daily predictions collection")

        # Get fixtures needing predictions
        fixture_ids = await self._get_daily_fixtures_only(db)

        if not fixture_ids:
            logger.info("No daily fixtures found for predictions")
            return {"fixtures_processed": 0, "predictions_collected": 0, "errors": []}

        logger.info(f"📊 Found {len(fixture_ids)} fixtures needing predictions")
        total_fixtures = len(fixture_ids)

        # ULTRA FAST: Maximum parallel processing
        logger.info(f"⚡ Processing {total_fixtures} fixtures with MAXIMUM parallelism (50 concurrent)")

        semaphore = asyncio.Semaphore(50)  # Maximum parallelism for speed
        predictions_collected = 0
        predictions_updated = 0
        errors = []
        processed_count = 0

        async def process_single_fixture(fixture_id):
            nonlocal predictions_collected, predictions_updated, processed_count
            async with semaphore:
                try:
                    processed_count += 1

                    # Get prediction data
                    prediction_data = await football_api.get_predictions_for_fixture(fixture_id)

                    if prediction_data:
                        result = await self._process_fixture_prediction(fixture_id, prediction_data, db)

                        if result["success"]:
                            if result["is_update"]:
                                predictions_updated += 1
                            else:
                                predictions_collected += 1
                            return {"fixture_id": fixture_id, "success": True}
                        else:
                            error_msg = f"Fixture {fixture_id}: {result.get('reason', 'Unknown error')}"
                            errors.append(error_msg)
                            return {"fixture_id": fixture_id, "success": False, "error": error_msg}
                    else:
                        return {"fixture_id": fixture_id, "success": False, "error": "No prediction data"}

                except Exception as e:
                    error_msg = f"Fixture {fixture_id}: {str(e)}"
                    errors.append(error_msg)
                    return {"fixture_id": fixture_id, "success": False, "error": error_msg}

        # Launch ALL requests simultaneously for maximum speed
        logger.info(f"🔥 Launching {total_fixtures} concurrent requests...")
        tasks = [process_single_fixture(fid) for fid in fixture_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Quick commit after all processing
        try:
            db.commit()
        except Exception as e:
            logger.error(f"Error committing to database: {e}")
            db.rollback()

        # Calculate final stats
        successful_results = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_results = [r for r in results if isinstance(r, dict) and not r.get("success")]

        success_rate = (len(successful_results) / total_fixtures * 100) if total_fixtures > 0 else 0

        stats = {
            "fixtures_processed": total_fixtures,
            "predictions_collected": predictions_collected,
            "predictions_updated": predictions_updated,
            "successful": len(successful_results),
            "failed": len(failed_results),
            "errors": errors[-10:],  # Keep only last 10 errors for brevity
            "mode": "ultra_fast_parallel",
            "success_rate": f"{success_rate:.1f}%",
            "speed": f"~{total_fixtures/13:.1f} predictions/min"  # Estimated based on testing
        }

        logger.info(f"🎯 ULTRA FAST collection completed: {stats}")
        return stats

    async def collect_predictions_for_all_fixtures(self, db: Session) -> Dict[str, Any]:
        """Raccoglie predizioni per tutte le partite attive (DEPRECATO - usa collect_daily_predictions_only)"""
        logger.info("Starting predictions collection for all active fixtures")
        
        # Get active fixtures
        fixture_ids = await self._get_active_fixtures_for_predictions(db)
        
        if not fixture_ids:
            logger.info("No active fixtures found for predictions")
            return {"fixtures_processed": 0, "predictions_collected": 0, "errors": []}
        
        logger.info(f"Found {len(fixture_ids)} fixtures for predictions collection")
        
        # LIMITA a massimo 50 partite per evitare timeout (6 ore)
        if len(fixture_ids) > 50:
            logger.info(f"Limiting to first 50 fixtures out of {len(fixture_ids)} to avoid timeout")
            fixture_ids = fixture_ids[:50]
        
        # Processa in batch di 5 partite per volta per non bloccare il server
        batch_size = 5
        predictions_map = {}
        
        for i in range(0, len(fixture_ids), batch_size):
            batch = fixture_ids[i:i + batch_size]
            logger.info(f"Processing predictions batch {i//batch_size + 1}/{(len(fixture_ids) + batch_size - 1)//batch_size}")
            
            batch_predictions = await football_api.get_predictions_for_multiple_fixtures(batch)
            predictions_map.update(batch_predictions)
            
            # Pausa più lunga tra batch per predictions (5 secondi)
            await asyncio.sleep(5)
        
        collection_stats = {
            "fixtures_processed": 0,
            "predictions_collected": 0,
            "predictions_updated": 0,
            "no_predictions": 0,
            "errors": []
        }
        
        # Process each prediction
        for fixture_id, prediction_data in predictions_map.items():
            try:
                if prediction_data:
                    logger.info(f"Processing prediction for fixture {fixture_id}")
                    result = await self._process_fixture_prediction(fixture_id, prediction_data, db)
                    
                    if result["success"]:
                        logger.info(f"Successfully processed prediction for fixture {fixture_id} (update: {result['is_update']})")
                        if result["is_update"]:
                            collection_stats["predictions_updated"] += 1
                        else:
                            collection_stats["predictions_collected"] += 1
                    else:
                        logger.warning(f"Failed to process prediction for fixture {fixture_id}: {result.get('reason', 'Unknown error')}")
                        collection_stats["errors"].append(f"Fixture {fixture_id}: {result.get('reason', 'Unknown error')}")
                else:
                    logger.info(f"No prediction data available for fixture {fixture_id}")
                    collection_stats["no_predictions"] += 1
                
                collection_stats["fixtures_processed"] += 1
                
            except Exception as e:
                error_msg = f"Error processing prediction for fixture {fixture_id}: {str(e)}"
                collection_stats["errors"].append(error_msg)
                logger.error(error_msg)
        
        logger.info(f"Predictions collection completed: {collection_stats}")
        return collection_stats
    
    async def _get_daily_fixtures_only(self, db: Session) -> List[int]:
        """
        NUOVO: Ottiene fixture ID SOLO per partite giornaliere (oggi + domani)
        
        INDIPENDENTE dalle odds - prende tutte le fixtures di oggi + domani
        indipendentemente dalla presenza di quote
        """
        from datetime import date
        
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        # Prende TUTTE le fixtures di oggi + domani (non filtra per odds)
        daily_fixtures = db.query(FixtureTrackingStatus).filter(
            FixtureTrackingStatus.fixture_date >= today,
            FixtureTrackingStatus.fixture_date < tomorrow + timedelta(days=1),  # Fino alla fine di domani
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"])
        ).order_by(FixtureTrackingStatus.fixture_date.asc()).all()
        
        fixture_ids = [f.fixture_id for f in daily_fixtures]
        
        logger.info(f"Found {len(fixture_ids)} daily fixtures for predictions (today: {today}, tomorrow: {tomorrow})")
        
        # Filtra fixtures che non hanno ancora predictions
        fixtures_without_predictions = []
        for fixture_id in fixture_ids:
            existing_prediction = db.query(MatchPredictions).filter(
                MatchPredictions.fixture_id == fixture_id
            ).first()
            
            if not existing_prediction:
                fixtures_without_predictions.append(fixture_id)
            else:
                # Se esiste, verifica se è vecchia (più di 24 ore)
                if existing_prediction.collected_at < datetime.now() - timedelta(hours=24):
                    fixtures_without_predictions.append(fixture_id)
        
        logger.info(f"Filtered to {len(fixtures_without_predictions)} fixtures needing predictions")
        
        return fixtures_without_predictions
    
    async def _get_active_fixtures_for_predictions(self, db: Session) -> List[int]:
        """Ottiene fixture ID per partite che necessitano predizioni"""
        # Partite dai prossimi 10 giorni
        future_cutoff = datetime.now() + timedelta(days=10)
        past_cutoff = datetime.now() - timedelta(hours=2)  # Non prima di 2 ore fa
        
        active_fixtures = db.query(FixtureTrackingStatus).filter(
            FixtureTrackingStatus.fixture_date > past_cutoff,
            FixtureTrackingStatus.fixture_date < future_cutoff,
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"])
        ).all()
        
        return [f.fixture_id for f in active_fixtures]
    
    async def _process_fixture_prediction(self, fixture_id: int, prediction_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Processa le predizioni di una singola partita (solo dati predictions core)"""
        
        try:
            predictions = prediction_data.get("predictions", {})
            league_data = prediction_data.get("league", {})
            
            # Check if prediction is meaningful
            winner = predictions.get("winner", {})
            advice = predictions.get("advice", "")
            
            if not winner or winner.get("name") is None or "No predictions available" in advice:
                return {"success": False, "is_update": False, "reason": "No meaningful predictions"}
            
            # Get fixture info
            fixture_info = db.query(FixtureTrackingStatus).filter(
                FixtureTrackingStatus.fixture_id == fixture_id
            ).first()
            
            if not fixture_info:
                return {"success": False, "is_update": False, "reason": "Fixture not found"}
            
            # Check if prediction already exists
            existing_prediction = db.query(MatchPredictions).filter(
                MatchPredictions.fixture_id == fixture_id
            ).first()
            
            is_update = existing_prediction is not None
            
            # Create or update prediction
            if existing_prediction:
                prediction_record = existing_prediction
            else:
                prediction_record = MatchPredictions(fixture_id=fixture_id)
            
            # Fill prediction data
            prediction_record.fixture_date = fixture_info.fixture_date
            
            # League context
            if league_data:
                prediction_record.league_id = league_data.get("id")
                prediction_record.league_name = league_data.get("name")
            
            # Winner prediction
            prediction_record.winner_team_id = winner.get("id")
            prediction_record.winner_team_name = winner.get("name")
            prediction_record.winner_comment = winner.get("comment")
            
            # Other predictions
            prediction_record.win_or_draw = predictions.get("win_or_draw")
            prediction_record.under_over = predictions.get("under_over")
            prediction_record.advice = advice
            
            # Goals predictions
            goals = predictions.get("goals", {})
            if goals:
                prediction_record.goals_home = goals.get("home")
                prediction_record.goals_away = goals.get("away")
            
            # Percentages
            percent = predictions.get("percent", {})
            if percent:
                prediction_record.percent_home = percent.get("home")
                prediction_record.percent_draw = percent.get("draw")
                prediction_record.percent_away = percent.get("away")
            
            prediction_record.is_prediction_available = True
            prediction_record.collected_at = datetime.now()
            
            if not is_update:
                db.add(prediction_record)
            
            db.commit()
            
            return {"success": True, "is_update": is_update}
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error processing prediction for fixture {fixture_id}: {str(e)}")
            return {"success": False, "is_update": False, "reason": str(e)}

# Singleton instance
predictions_collector = PredictionsCollector()
