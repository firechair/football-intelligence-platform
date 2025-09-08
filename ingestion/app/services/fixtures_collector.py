import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.utils.football_api import football_api
from app.models.odds_tracking import FixtureTrackingStatus
from app.core.database import get_db
import logging

logger = logging.getLogger(__name__)

class FixturesCollector:
    def __init__(self):
        self.collected_fixtures = []
    
    async def collect_upcoming_fixtures(self, days_ahead: int = 10) -> List[Dict[str, Any]]:
        """Raccoglie tutte le partite dei prossimi N giorni"""
        from_date = datetime.now().date().isoformat()
        to_date = (datetime.now().date() + timedelta(days=days_ahead)).isoformat()
        
        logger.info(f"Collecting fixtures from {from_date} to {to_date}")
        
        fixtures = await football_api.get_fixtures_by_date_range(from_date, to_date)
        
        # Filtra solo partite non iniziate
        upcoming_fixtures = []
        for fixture in fixtures:
            status = fixture.get("fixture", {}).get("status", {}).get("short", "")
            if status in ["NS", "TBD"]:  # Not Started, To Be Defined
                upcoming_fixtures.append(fixture)
        
        logger.info(f"Found {len(upcoming_fixtures)} upcoming fixtures")
        self.collected_fixtures = upcoming_fixtures
        
        return upcoming_fixtures
    
    async def update_tracking_status(self, fixtures: List[Dict[str, Any]], db: Session):
        """Aggiorna lo stato di tracking per le partite"""
        for fixture in fixtures:
            fixture_data = fixture.get("fixture", {})
            league_data = fixture.get("league", {})
            teams_data = fixture.get("teams", {})
            
            fixture_id = fixture_data.get("id")
            if not fixture_id:
                continue
            
            # Cerca se esiste già
            existing = db.query(FixtureTrackingStatus).filter(
                FixtureTrackingStatus.fixture_id == fixture_id
            ).first()
            
            if existing:
                # Aggiorna dati esistenti
                existing.fixture_date = datetime.fromisoformat(
                    fixture_data.get("date", "").replace("Z", "+00:00")
                )
                existing.updated_at = datetime.now()
            else:
                # Crea nuovo record
                new_tracking = FixtureTrackingStatus(
                    fixture_id=fixture_id,
                    league_id=league_data.get("id"),
                    league_name=league_data.get("name"),
                    home_team=teams_data.get("home", {}).get("name", "Unknown"),
                    away_team=teams_data.get("away", {}).get("name", "Unknown"),
                    fixture_date=datetime.fromisoformat(
                        fixture_data.get("date", "").replace("Z", "+00:00")
                    ),
                    tracking_status="pending"
                )
                db.add(new_tracking)
        
        db.commit()
        logger.info(f"Updated tracking status for {len(fixtures)} fixtures")
    
    async def get_active_fixtures_for_tracking(self, db: Session) -> List[int]:
        """Restituisce fixture ID che devono essere trackati"""
        cutoff_date = datetime.now() - timedelta(hours=2)  # Non tracciare partite iniziate da più di 2 ore
        future_date = datetime.now() + timedelta(days=10)
        
        active_fixtures = db.query(FixtureTrackingStatus).filter(
            FixtureTrackingStatus.fixture_date > cutoff_date,
            FixtureTrackingStatus.fixture_date < future_date,
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"])
        ).all()
        
        return [f.fixture_id for f in active_fixtures]

# Singleton instance
fixtures_collector = FixturesCollector()

