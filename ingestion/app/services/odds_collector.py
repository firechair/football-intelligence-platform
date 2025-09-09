import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from app.utils.football_api import football_api
from app.models.odds_tracking import ExtendedOddsHistory, BookmakerInfo, FixtureTrackingStatus
import logging

logger = logging.getLogger(__name__)

class OddsCollector:
    def __init__(self):
        # Mappatura mercati API -> nostri codici
        self.market_mappings = {
            # 1X2 Base
            "match winner": {"type": "1x2", "subtype": None},
            "1x2": {"type": "1x2", "subtype": None},
            "full time result": {"type": "1x2", "subtype": None},
            
            # Double Chance
            "double chance": {"type": "double_chance", "subtype": None},
            
            # Over/Under
            "over/under 0.5": {"type": "over_under", "subtype": "0.5"},
            "over/under 1.5": {"type": "over_under", "subtype": "1.5"},
            "over/under 2.5": {"type": "over_under", "subtype": "2.5"},
            "over/under 3.5": {"type": "over_under", "subtype": "3.5"},
            "over/under 4.5": {"type": "over_under", "subtype": "4.5"},
            
            # Goal/NoGoal
            "both teams score": {"type": "both_teams_score", "subtype": None},
            "btts": {"type": "both_teams_score", "subtype": None},
            
            # Combinati (meno comuni nell'API base, potrebbero essere in mercati speciali)
            "1x2 & total goals": {"type": "combined", "subtype": "1x2_total"},
        }
        
        # Mappatura esiti
        self.outcome_mappings = {
            # 1X2
            "Home": "1", "Draw": "X", "Away": "2",
            "1": "1", "X": "X", "2": "2",
            
            # Double Chance
            "Home/Draw": "1X", "Draw/Home": "1X",
            "Home/Away": "12", "Away/Home": "12", 
            "Draw/Away": "X2", "Away/Draw": "X2",
            "1X": "1X", "12": "12", "X2": "X2",
            
            # Over/Under
            "Over": "Over", "Under": "Under",
            
            # Goal/NoGoal
            "Yes": "Goal", "No": "NoGoal",
            "Both Teams Score": "Goal",
            "Both Teams Not To Score": "NoGoal",
        }
    
    async def collect_odds_for_fixtures(self, fixture_ids: List[int], db: Session) -> Dict[str, Any]:
        """Raccoglie quote per una lista di partite in batch piccoli"""
        logger.info(f"Starting odds collection for {len(fixture_ids)} fixtures")
        
        # Processa in batch di 10 partite per volta per non bloccare il server
        batch_size = 10
        odds_map = {}
        
        for i in range(0, len(fixture_ids), batch_size):
            batch = fixture_ids[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(fixture_ids) + batch_size - 1)//batch_size}")
            
            batch_odds = await football_api.get_odds_for_multiple_fixtures(batch)
            odds_map.update(batch_odds)
            
            # Pausa tra batch per permettere al server di rispondere ad altre richieste
            await asyncio.sleep(5)
        
        collection_stats = {
            "fixtures_processed": 0,
            "quotes_collected": 0,
            "bookmakers_found": set(),
            "markets_found": set(),
            "errors": []
        }
        
        for fixture_id, odds_data in odds_map.items():
            if not odds_data:
                collection_stats["errors"].append(f"No odds data for fixture {fixture_id}")
                continue
            
            try:
                quotes_count = await self._process_fixture_odds(fixture_id, odds_data, db)
                collection_stats["quotes_collected"] += quotes_count
                collection_stats["fixtures_processed"] += 1
                
            except Exception as e:
                error_msg = f"Error processing fixture {fixture_id}: {str(e)}"
                collection_stats["errors"].append(error_msg)
                logger.error(error_msg)
        
        # Aggiorna stato tracking
        await self._update_fixtures_tracking_status(fixture_ids, collection_stats, db)
        
        logger.info(f"Collection completed: {collection_stats}")
        return collection_stats
    
    async def _process_fixture_odds(self, fixture_id: int, odds_data: Dict[str, Any], db: Session) -> int:
        """Processa le quote di una singola partita"""
        quotes_saved = 0
        
        # Ottieni info partita
        fixture_info = await self._get_fixture_info(fixture_id, db)
        if not fixture_info:
            return 0
        
        # Calcola minuti al calcio d'inizio
        minutes_to_kickoff = self._calculate_minutes_to_kickoff(fixture_info.fixture_date)
        
        # Processa bookmaker
        bookmakers = odds_data.get("bookmakers", [])
        
        for bookmaker in bookmakers:
            bookmaker_name = bookmaker.get("name", "Unknown")
            bookmaker_api_id = bookmaker.get("id", 0)
            
            # Assicurati che il bookmaker sia nel nostro DB
            await self._ensure_bookmaker_exists(bookmaker_api_id, bookmaker_name, db)
            
            # Processa mercati
            bets = bookmaker.get("bets", [])
            for bet in bets:
                market_name = bet.get("name", "").lower()
                
                if market_name not in self.market_mappings:
                    continue  # Salta mercati non supportati
                
                market_info = self.market_mappings[market_name]
                
                # Processa valori/quote
                values = bet.get("values", [])
                for value in values:
                    outcome_raw = value.get("value", "")
                    odd_value = value.get("odd")
                    
                    if not odd_value or float(odd_value) <= 1.0:
                        continue  # Salta quote invalide
                    
                    # Mappa outcome
                    outcome = self._map_outcome(outcome_raw, market_info["type"], market_info["subtype"])
                    if not outcome:
                        continue
                    
                    # Salva quota
                    await self._save_odds_record(
                        fixture_id=fixture_id,
                        market_name=outcome,
                        market_type=market_info["type"],
                        market_subtype=market_info["subtype"],
                        bookmaker_id=bookmaker_api_id,
                        bookmaker_name=bookmaker_name,
                        odd_value=Decimal(str(odd_value)),
                        fixture_date=fixture_info.fixture_date,
                        minutes_to_kickoff=minutes_to_kickoff,
                        db=db
                    )
                    
                    quotes_saved += 1
        
        return quotes_saved
    
    def _map_outcome(self, raw_outcome: str, market_type: str, market_subtype: Optional[str]) -> Optional[str]:
        """Mappa l'outcome raw al nostro formato standardizzato"""
        
        # Per over/under, combina con subtype
        if market_type == "over_under" and market_subtype:
            base_outcome = self.outcome_mappings.get(raw_outcome, raw_outcome)
            return f"{base_outcome}{market_subtype}"  # es: "Over2.5", "Under1.5"
        
        return self.outcome_mappings.get(raw_outcome, raw_outcome)
    
    async def _save_odds_record(self, **kwargs):
        """Salva un record delle quote nel database"""
        db = kwargs.pop('db')
        
        # Controlla se esiste già (evita duplicati)
        existing = db.query(ExtendedOddsHistory).filter(
            ExtendedOddsHistory.fixture_id == kwargs["fixture_id"],
            ExtendedOddsHistory.market_name == kwargs["market_name"],
            ExtendedOddsHistory.bookmaker_id == kwargs["bookmaker_id"],
            ExtendedOddsHistory.collected_at >= datetime.now() - timedelta(minutes=5)
        ).first()
        
        if existing:
            # Aggiorna se la quota è cambiata
            if existing.odd_value != kwargs["odd_value"]:
                existing.odd_value = kwargs["odd_value"]
                existing.collected_at = datetime.now()
        else:
            # Nuovo record
            odds_record = ExtendedOddsHistory(**kwargs)
            db.add(odds_record)
        
        db.commit()
    
    async def _get_fixture_info(self, fixture_id: int, db: Session) -> Optional[FixtureTrackingStatus]:
        """Ottieni info sulla partita"""
        return db.query(FixtureTrackingStatus).filter(
            FixtureTrackingStatus.fixture_id == fixture_id
        ).first()
    
    def _calculate_minutes_to_kickoff(self, fixture_date: datetime) -> int:
        """Calcola minuti rimanenti al calcio d'inizio"""
        now = datetime.now()
        if fixture_date.tzinfo is None:
            fixture_date = fixture_date.replace(tzinfo=datetime.now().astimezone().tzinfo)
        if now.tzinfo is None:
            now = now.replace(tzinfo=datetime.now().astimezone().tzinfo)
        
        delta = fixture_date - now
        return max(0, int(delta.total_seconds() / 60))
    
    async def _ensure_bookmaker_exists(self, api_id: int, name: str, db: Session):
        """Assicura che il bookmaker esista nel database"""
        existing = db.query(BookmakerInfo).filter(BookmakerInfo.api_id == api_id).first()
        
        if not existing:
            bookmaker = BookmakerInfo(
                api_id=api_id,
                name=name,
                display_name=name,
                is_active=True
            )
            db.add(bookmaker)
            db.commit()
    
    async def _update_fixtures_tracking_status(self, fixture_ids: List[int], stats: Dict[str, Any], db: Session):
        """Aggiorna lo stato di tracking delle partite"""
        for fixture_id in fixture_ids:
            fixture_status = db.query(FixtureTrackingStatus).filter(
                FixtureTrackingStatus.fixture_id == fixture_id
            ).first()
            
            if fixture_status:
                fixture_status.last_odds_collected_at = datetime.now()
                fixture_status.total_collections += 1
                if not fixture_status.first_odds_collected_at:
                    fixture_status.first_odds_collected_at = datetime.now()
                    fixture_status.tracking_status = "active"
                
        db.commit()

# Singleton instance
odds_collector = OddsCollector()

