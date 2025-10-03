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
                # Aggiorna loghi se disponibili
                existing.home_team_logo = teams_data.get("home", {}).get("logo")
                existing.away_team_logo = teams_data.get("away", {}).get("logo")
                existing.league_logo = league_data.get("logo")
                # Aggiorna country_name se disponibile e colonna esiste
                if league_data.get("country"):
                    try:
                        # Prova ad aggiornare country_name solo se la colonna esiste
                        if not getattr(existing, 'country_name', None):
                            setattr(existing, 'country_name', league_data.get("country"))
                    except AttributeError:
                        # La colonna non esiste, ignora
                        pass
                existing.updated_at = datetime.now()
            else:
                # Crea nuovo record - gestione sicura di country_name
                fixture_date = datetime.fromisoformat(
                    fixture_data.get("date", "").replace("Z", "+00:00")
                )

                tracking_data = {
                    'fixture_id': fixture_id,
                    'league_id': league_data.get("id"),
                    'league_name': league_data.get("name"),
                    'home_team': teams_data.get("home", {}).get("name", "Unknown"),
                    'away_team': teams_data.get("away", {}).get("name", "Unknown"),
                    'fixture_date': fixture_date,
                    'home_team_logo': teams_data.get("home", {}).get("logo"),
                    'away_team_logo': teams_data.get("away", {}).get("logo"),
                    'league_logo': league_data.get("logo"),
                    'tracking_status': "pending",
                }

                # Aggiungi country_name solo se la colonna esiste nel database
                try:
                    # Prova a creare un record di test per vedere se la colonna esiste
                    test_record = FixtureTrackingStatus(
                        fixture_id=999999999,  # ID fittizio per test
                        league_id=1,
                        league_name="Test",
                        country_name="Test",  # Prova ad impostare country_name
                        home_team="Test",
                        away_team="Test",
                        fixture_date=datetime.now()
                    )
                    # Se arriva qui senza errori, la colonna esiste
                    tracking_data['country_name'] = league_data.get("country")
                    logger.debug(f"✅ Column country_name exists in database")
                except Exception as e:
                    # La colonna non esiste, non impostarla
                    logger.warning(f"⚠️ Column country_name does not exist in database: {str(e)}")
                    # Non aggiungere country_name ai dati

                new_tracking = FixtureTrackingStatus(**tracking_data)
                db.add(new_tracking)
        
        db.commit()
        logger.info(f"Updated tracking status for {len(fixtures)} fixtures")
    
    async def get_active_fixtures_for_tracking(self, db: Session) -> List[int]:
        """Restituisce fixture ID che devono essere trackati CONTINUAMENTE per storico quote nel tempo"""
        cutoff_date = datetime.now() - timedelta(hours=2)  # Non tracciare partite iniziate da più di 2 ore
        future_date = datetime.now() + timedelta(days=10)

        # Priorità 1: TUTTE le partite di oggi e domani (prossime 24 ore) per tracking CONTINUO
        # Vogliamo raccogliere quote per tutte le partite giornaliere per vedere andamento nel tempo
        tomorrow_end = datetime.now() + timedelta(hours=24)
        daily_fixtures = db.query(FixtureTrackingStatus).filter(
            FixtureTrackingStatus.fixture_date > cutoff_date,
            FixtureTrackingStatus.fixture_date <= tomorrow_end,
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"])
        ).order_by(FixtureTrackingStatus.fixture_date).all()

        # Priorità 2: Altre partite future (dopo 24 ore) - limitato per non sprecare troppo
        other_fixtures = db.query(FixtureTrackingStatus).filter(
            FixtureTrackingStatus.fixture_date > tomorrow_end,
            FixtureTrackingStatus.fixture_date < future_date,
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"])
        ).order_by(FixtureTrackingStatus.fixture_date).all()

        # Combina con priorità
        prioritized_fixtures = daily_fixtures + other_fixtures

        logger.info(f"Found {len(prioritized_fixtures)} fixtures for continuous odds tracking: {len(daily_fixtures)} daily + {len(other_fixtures)} future")
        return [f.fixture_id for f in prioritized_fixtures]
    
    async def get_daily_fixtures_for_tracking(self, db: Session) -> List[int]:
        """Restituisce solo le fixture ID delle partite giornaliere (prossime 24 ore)"""
        cutoff_date = datetime.now() - timedelta(hours=2)  # Non tracciare partite iniziate da più di 2 ore
        tomorrow_end = datetime.now() + timedelta(hours=24)
        
        daily_fixtures = db.query(FixtureTrackingStatus).filter(
            FixtureTrackingStatus.fixture_date > cutoff_date,
            FixtureTrackingStatus.fixture_date <= tomorrow_end,
            FixtureTrackingStatus.tracking_status.in_(["pending", "active"])
        ).order_by(FixtureTrackingStatus.fixture_date).all()
        
        logger.info(f"Found {len(daily_fixtures)} daily fixtures for immediate processing")
        return [f.fixture_id for f in daily_fixtures]

# Singleton instance
fixtures_collector = FixturesCollector()

