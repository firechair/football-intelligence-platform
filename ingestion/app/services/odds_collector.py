import asyncio
import json
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
    
    def extract_best_1x2_odds_from_any_structure(self, odds_container):
        """
        Extract best odds for 1, X, 2, 1X, X2, 12, O2.5, U2.5 from either the new FootballAPI structure (odds at root) or the old (bookmakers array).
        Returns (best_odds, all_odds) as before.
        Enhanced with robust JSON validation and error handling.
        """
        # Initialize default structures
        best_odds = {k: None for k in ["1", "X", "2", "1X", "X2", "12", "O2.5", "U2.5"]}
        all_odds = {k: {} for k in ["1", "X", "2", "1X", "X2", "12", "O2.5", "U2.5"]}
        
        # Validate input data
        if not odds_container:
            logger.warning("[ODDS] Empty or None odds container provided")
            return best_odds, all_odds
        
        if not isinstance(odds_container, (list, dict)):
            logger.error(f"[ODDS] Invalid odds container type: {type(odds_container)}. Expected list or dict.")
            return best_odds, all_odds
        
        market_names_1x2 = ["match winner", "1x2", "full time result", "fulltime result", "risultato finale", "esito finale", "result"]
        market_names_dc = ["double chance"]
        market_names_ou = ["over/under", "over/under 2.5", "total goals"]
        
        # New format: odds is a list of markets at the root
        if isinstance(odds_container, list):
            # For new format, we need to extract bookmaker names from the market structure
            # This format doesn't have explicit bookmaker names, so we'll use a generic approach
            for market in odds_container:
                if not isinstance(market, dict):
                    continue
                
                market_name = market.get("name", "").lower()
                
                # 1X2 markets
                if any(m in market_name for m in market_names_1x2):
                    for value in market.get("values", []):
                        raw_label = value.get("value", "")
                        odd = value.get("odd")
                        label_map_1x2 = {"Home": "1", "Draw": "X", "Away": "2"}
                        label = label_map_1x2.get(raw_label, raw_label)
                        if label in ["1", "X", "2"] and odd:
                            try:
                                odd_float = float(odd)
                                if best_odds[label] is None or odd_float > best_odds[label]:
                                    best_odds[label] = odd_float
                                all_odds[label]["Generic"] = odd_float
                            except (ValueError, TypeError):
                                pass
                
                # Double chance markets
                elif any(m in market_name for m in market_names_dc):
                    for value in market.get("values", []):
                        raw_label = value.get("value", "")
                        odd = value.get("odd")
                        label_map = {"Home/Draw": "1X", "Draw/Home": "1X", "Home/Away": "12", "Away/Home": "12", "Draw/Away": "X2", "Away/Draw": "X2"}
                        label = label_map.get(raw_label, raw_label.replace(" ", "").replace("-", "").replace("or", "").upper())
                        if label in ["1X", "X2", "12"] and odd:
                            try:
                                odd_float = float(odd)
                                if best_odds[label] is None or odd_float > best_odds[label]:
                                    best_odds[label] = odd_float
                                all_odds[label]["Generic"] = odd_float
                            except (ValueError, TypeError):
                                pass
                
                # Over/Under markets
                elif any(m in market_name for m in market_names_ou):
                    for value in market.get("values", []):
                        raw_label = value.get("value", "")
                        odd = value.get("odd")
                        if "Over 2.5" in raw_label and odd:
                            try:
                                odd_float = float(odd)
                                if best_odds["O2.5"] is None or odd_float > best_odds["O2.5"]:
                                    best_odds["O2.5"] = odd_float
                                all_odds["O2.5"]["Generic"] = odd_float
                            except (ValueError, TypeError):
                                pass
                        elif "Under 2.5" in raw_label and odd:
                            try:
                                odd_float = float(odd)
                                if best_odds["U2.5"] is None or odd_float > best_odds["U2.5"]:
                                    best_odds["U2.5"] = odd_float
                                all_odds["U2.5"]["Generic"] = odd_float
                            except (ValueError, TypeError):
                                pass
        
        # Old format: bookmakers is a list of bookmakers, each with bets
        elif isinstance(odds_container, dict) and "bookmakers" in odds_container:
            for bookmaker in odds_container.get("bookmakers", []):
                bookmaker_name = bookmaker.get("name", "Unknown")
                for bet in bookmaker.get("bets", []):
                    bet_name = bet.get("name", "").lower()
                    
                    # 1X2 markets
                    if any(m in bet_name for m in market_names_1x2):
                        for value in bet.get("values", []):
                            raw_label = value.get("value", "")
                            odd = value.get("odd")
                            label_map_1x2 = {"Home": "1", "Draw": "X", "Away": "2"}
                            label = label_map_1x2.get(raw_label, raw_label)
                            if label in ["1", "X", "2"] and odd:
                                try:
                                    odd_float = float(odd)
                                    if best_odds[label] is None or odd_float > best_odds[label]:
                                        best_odds[label] = odd_float
                                    all_odds[label][bookmaker_name] = odd_float
                                except (ValueError, TypeError):
                                    pass
                    
                    # Double chance markets
                    elif any(m in bet_name for m in market_names_dc):
                        for value in bet.get("values", []):
                            raw_label = value.get("value", "")
                            odd = value.get("odd")
                            label_map = {"Home/Draw": "1X", "Draw/Home": "1X", "Home/Away": "12", "Away/Home": "12", "Draw/Away": "X2", "Away/Draw": "X2"}
                            label = label_map.get(raw_label, raw_label.replace(" ", "").replace("-", "").replace("or", "").upper())
                            if label in ["1X", "X2", "12"] and odd:
                                try:
                                    odd_float = float(odd)
                                    if best_odds[label] is None or odd_float > best_odds[label]:
                                        best_odds[label] = odd_float
                                    all_odds[label][bookmaker_name] = odd_float
                                except (ValueError, TypeError):
                                    pass
                    
                    # Over/Under markets
                    elif any(m in bet_name for m in market_names_ou):
                        for value in bet.get("values", []):
                            raw_label = value.get("value", "")
                            odd = value.get("odd")
                            if "Over 2.5" in raw_label and odd:
                                try:
                                    odd_float = float(odd)
                                    if best_odds["O2.5"] is None or odd_float > best_odds["O2.5"]:
                                        best_odds["O2.5"] = odd_float
                                    all_odds["O2.5"][bookmaker_name] = odd_float
                                except (ValueError, TypeError):
                                    pass
                            elif "Under 2.5" in raw_label and odd:
                                try:
                                    odd_float = float(odd)
                                    if best_odds["U2.5"] is None or odd_float > best_odds["U2.5"]:
                                        best_odds["U2.5"] = odd_float
                                    all_odds["U2.5"][bookmaker_name] = odd_float
                                except (ValueError, TypeError):
                                    pass
        else:
            logger.warning(f"[ODDS] Unknown odds structure: {type(odds_container)}. Data: {str(odds_container)[:300]}")
            return best_odds, all_odds
        
        # Validate and correct best_odds to ensure they match the highest values in all_odds
        for outcome in ["1", "X", "2", "1X", "X2", "12", "O2.5", "U2.5"]:
            if outcome in all_odds and all_odds[outcome]:
                try:
                    max_odd = max(all_odds[outcome].values())
                    if best_odds[outcome] is None or abs(float(best_odds[outcome]) - max_odd) > 0.001:
                        best_odds[outcome] = max_odd
                        logger.debug(f"[ODDS] Corrected {outcome}: {best_odds[outcome]} (was inconsistent)")
                except (ValueError, TypeError):
                    pass
        
        logger.debug(f"[ODDS] Final best_odds: {best_odds}, all_odds: {all_odds}")
        return best_odds, all_odds
    
    async def collect_odds_for_fixtures(self, fixture_ids: List[int], db: Session) -> Dict[str, Any]:
        """Raccoglie quote per una lista di partite in modo CONTINUO con limite 2 chiamate/secondo"""
        logger.info(f"Starting CONTINUOUS odds collection for {len(fixture_ids)} fixtures")
        
        # Processa in modo CONTINUO con limite 2 chiamate/secondo
        odds_map = {}
        
        collection_stats = {
            "fixtures_processed": 0,
            "quotes_collected": 0,
            "bookmakers_found": set(),
            "markets_found": set(),
            "errors": []
        }
        
        # Processa ogni partita individualmente per controllo preciso del rate limit
        for i, fixture_id in enumerate(fixture_ids):
            try:
                logger.info(f"Processing fixture {i+1}/{len(fixture_ids)}: {fixture_id}")
                
                # Chiamata API singola per questa partita
                fixture_odds = await football_api.get_odds_for_fixture(fixture_id)
                
                if fixture_odds:
                    odds_map[fixture_id] = fixture_odds
                    collection_stats["fixtures_processed"] += 1
                    
                    # Processa e salva le quote nel database usando il metodo avanzato
                    try:
                        quotes_saved = await self._process_fixture_odds(fixture_id, fixture_odds, db)
                        collection_stats["quotes_collected"] += quotes_saved
                        collection_stats["bookmakers_found"].add("API-Football")  # Placeholder
                        collection_stats["markets_found"].add("1X2")  # Placeholder
                    except Exception as e:
                        logger.error(f"Error processing odds for fixture {fixture_id}: {str(e)}")
                        collection_stats["errors"].append(f"Error processing fixture {fixture_id}: {str(e)}")
                else:
                    collection_stats["errors"].append(f"No odds data for fixture {fixture_id}")
                
                # Rate limiting: massimo 2 chiamate/secondo
                # Attendi 0.5 secondi tra ogni chiamata per rispettare il limite
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing fixture {fixture_id}: {str(e)}")
                collection_stats["errors"].append(f"Error processing fixture {fixture_id}: {str(e)}")
                continue
        
        # Converti set in list per JSON serialization
        collection_stats["bookmakers_found"] = list(collection_stats["bookmakers_found"])
        collection_stats["markets_found"] = list(collection_stats["markets_found"])
        
        logger.info(f"Continuous odds collection completed: {collection_stats}")
        return collection_stats
    
    async def _process_and_save_odds(self, fixture_id: int, odds_data: Dict, db: Session, stats: Dict):
        """Helper per processare e salvare le quote nel database"""
        try:
            # Estrai le migliori quote 1X2
            best_odds, all_odds = self.extract_best_1x2_odds_from_any_structure(odds_data)
            
            if not best_odds or not any(best_odds.values()):
                logger.warning(f"No valid 1X2 odds found for fixture {fixture_id}")
                return
            
            # Salva nel database
            for outcome in ["1", "X", "2"]:
                if best_odds.get(outcome):
                    # Trova il bookmaker con la quota migliore
                    best_bookmaker = None
                    best_value = 0
                    
                    if outcome in all_odds:
                        for bookmaker, value in all_odds[outcome].items():
                            if value > best_value:
                                best_value = value
                                best_bookmaker = bookmaker
                    
                    if best_bookmaker and best_value > 0:
                        # Salva nel database
                        odds_record = ExtendedOddsHistory(
                            fixture_id=fixture_id,
                            market_name=outcome,
                            market_type="1x2",
                            market_subtype=None,
                            bookmaker_id=1,  # Placeholder
                            bookmaker_name=best_bookmaker,
                            odd_value=best_value,
                            fixture_date=datetime.now(),  # Placeholder
                            is_pre_match=True,
                            is_best_odd=True
                        )
                        
                        db.add(odds_record)
                        stats["quotes_collected"] += 1
                        stats["bookmakers_found"].add(best_bookmaker)
                        stats["markets_found"].add(outcome)
            
            db.commit()
            logger.debug(f"Saved odds for fixture {fixture_id}")
            
        except Exception as e:
            logger.error(f"Error processing odds for fixture {fixture_id}: {str(e)}")
            db.rollback()
            raise
    
    async def _process_fixture_odds(self, fixture_id: int, odds_data: Dict[str, Any], db: Session) -> int:
        """Processa le quote di una singola partita usando l'estrazione avanzata dal backend"""
        quotes_saved = 0
        
        # Ottieni info partita
        fixture_info = await self._get_fixture_info(fixture_id, db)
        if not fixture_info:
            logger.warning(f"No fixture info found for fixture {fixture_id}")
            return 0
        
        # Log dei dati ricevuti
        bookmakers_count = len(odds_data.get("bookmakers", []))
        logger.info(f"Processing fixture {fixture_id}: {bookmakers_count} bookmakers found")
        
        # Calcola minuti al calcio d'inizio
        minutes_to_kickoff = self._calculate_minutes_to_kickoff(fixture_info.fixture_date)
        
        # Usa la funzione avanzata di estrazione delle quote dal backend
        best_odds, all_odds = self.extract_best_1x2_odds_from_any_structure(odds_data)
        
        # Processa tutte le quote estratte
        for outcome_type, bookmaker_odds in all_odds.items():
            if not bookmaker_odds:
                continue
                
            for bookmaker_name, odd_value in bookmaker_odds.items():
                if not odd_value or float(odd_value) <= 1.0:
                    continue  # Salta quote invalide
                
                # Trova l'ID del bookmaker nel database
                bookmaker_info = db.query(BookmakerInfo).filter(
                    BookmakerInfo.name == bookmaker_name
                ).first()
                
                if not bookmaker_info:
                    # Crea nuovo bookmaker se non esiste
                    bookmaker_info = BookmakerInfo(
                        api_id=0,  # Usa 0 per bookmaker generici
                        name=bookmaker_name,
                        display_name=bookmaker_name,
                        is_active=True
                    )
                    db.add(bookmaker_info)
                    db.commit()
                    db.refresh(bookmaker_info)
                
                # Determina il tipo di mercato in base all'outcome
                market_type, market_subtype = self._determine_market_type(outcome_type)
                
                # Salva quota direttamente nel database
                odds_record = ExtendedOddsHistory(
                    fixture_id=fixture_id,
                    market_name=outcome_type,
                    market_type=market_type,
                    market_subtype=market_subtype,
                    bookmaker_id=bookmaker_info.id,
                    bookmaker_name=bookmaker_name,
                    odd_value=Decimal(str(odd_value)),
                    fixture_date=datetime.now(),  # Usa data corrente per ora
                    is_pre_match=True,
                    is_best_odd=False  # Sarà calcolato dopo
                )
                db.add(odds_record)
                
                quotes_saved += 1
        
        # Commit delle quote salvate
        db.commit()
        logger.info(f"Fixture {fixture_id}: salvate {quotes_saved} quote usando estrazione avanzata")
        return quotes_saved
    
    def _determine_market_type(self, outcome_type: str) -> tuple:
        """Determina il tipo di mercato basato sull'outcome"""
        if outcome_type in ["1", "X", "2"]:
            return "1x2", None
        elif outcome_type in ["1X", "X2", "12"]:
            return "double_chance", None
        elif outcome_type in ["O2.5", "U2.5"]:
            return "over_under", "2.5"
        elif outcome_type in ["Goal", "NoGoal"]:
            return "both_teams_score", None
        else:
            return "other", None
    
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
                logger.info(f"Updated odds for fixture {kwargs['fixture_id']}, market {kwargs['market_name']}, bookmaker {kwargs['bookmaker_name']}")
        else:
            # Nuovo record
            kwargs['collected_at'] = datetime.now()
            odds_record = ExtendedOddsHistory(**kwargs)
            db.add(odds_record)
            logger.info(f"Saved new odds for fixture {kwargs['fixture_id']}, market {kwargs['market_name']}, bookmaker {kwargs['bookmaker_name']}, value {kwargs['odd_value']}")
        
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

