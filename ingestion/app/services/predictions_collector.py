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
    
    async def collect_predictions_for_all_fixtures(self, db: Session) -> Dict[str, Any]:
        """Raccoglie predizioni per tutte le partite attive"""
        logger.info("Starting predictions collection for all active fixtures")
        
        # Get active fixtures
        fixture_ids = await self._get_active_fixtures_for_predictions(db)
        
        if not fixture_ids:
            logger.info("No active fixtures found for predictions")
            return {"fixtures_processed": 0, "predictions_collected": 0, "errors": []}
        
        logger.info(f"Found {len(fixture_ids)} fixtures for predictions collection")
        
        # Collect predictions (1 req/sec)
        predictions_map = await football_api.get_predictions_for_multiple_fixtures(fixture_ids)
        
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
                    result = await self._process_fixture_prediction(fixture_id, prediction_data, db)
                    
                    if result["success"]:
                        if result["is_update"]:
                            collection_stats["predictions_updated"] += 1
                        else:
                            collection_stats["predictions_collected"] += 1
                    else:
                        collection_stats["no_predictions"] += 1
                else:
                    collection_stats["no_predictions"] += 1
                    logger.warning(f"No prediction data for fixture {fixture_id}")
                
                collection_stats["fixtures_processed"] += 1
                
            except Exception as e:
                error_msg = f"Error processing prediction for fixture {fixture_id}: {str(e)}"
                collection_stats["errors"].append(error_msg)
                logger.error(error_msg)
        
        logger.info(f"Predictions collection completed: {collection_stats}")
        return collection_stats
    
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
