"""
Football API Mapper - Maps user questions to appropriate Football API endpoints
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class APICall:
    """Rappresenta una chiamata API con endpoint e parametri"""
    endpoint: str
    params: Dict[str, Any]
    description: str
    priority: int = 1  # 1 = alta priorità, 2 = media, 3 = bassa

class FootballAPIMapper:
    """Mappa le domande utente agli endpoint Football API appropriati"""
    
    def __init__(self):
        self.country_codes = {
            # Italia - tutte le varianti
            'italia': 'Italy', 'italy': 'Italy', 'italian': 'Italy', 
            'italiana': 'Italy', 'italiane': 'Italy', 'italiani': 'Italy', 'italiano': 'Italy',
            # Spagna
            'spain': 'Spain', 'spagna': 'Spain', 'spanish': 'Spain',
            'spagnola': 'Spain', 'spagnole': 'Spain', 'spagnoli': 'Spain', 'spagnolo': 'Spain',
            # Inghilterra  
            'england': 'England', 'inghilterra': 'England', 'english': 'England',
            'inglese': 'England', 'inglesi': 'England',
            # Francia
            'france': 'France', 'francia': 'France', 'french': 'France',  
            'francese': 'France', 'francesi': 'France',
            # Germania
            'germany': 'Germany', 'germania': 'Germany', 'german': 'Germany',
            'tedesca': 'Germany', 'tedesche': 'Germany', 'tedeschi': 'Germany', 'tedesco': 'Germany',
            # Brasile
            'brasil': 'Brazil', 'brasile': 'Brazil', 'brazil': 'Brazil',
            'brasiliana': 'Brazil', 'brasiliane': 'Brazil', 'brasiliani': 'Brazil', 'brasiliano': 'Brazil'
        }
        
        self.league_mappings = {
            # Italia
            'serie a': {'league': 135, 'country': 'Italy'},
            'serie b': {'league': 136, 'country': 'Italy'},
            'serie c': {'league': 137, 'country': 'Italy'},
            'champions league': {'league': 2, 'country': 'World'},
            'europa league': {'league': 3, 'country': 'World'},
            # Inghilterra  
            'premier league': {'league': 39, 'country': 'England'},
            'championship': {'league': 40, 'country': 'England'},
            # Spagna
            'la liga': {'league': 140, 'country': 'Spain'},
            'liga': {'league': 140, 'country': 'Spain'},
            # Francia
            'ligue 1': {'league': 61, 'country': 'France'},
            # Germania
            'bundesliga': {'league': 78, 'country': 'Germany'},
        }
        
        # Usa l'anno corrente per supportare richieste future
        self.current_season = datetime.now().year

    def map_user_question(self, question: str) -> List[APICall]:
        """Mappa una domanda utente a una lista di chiamate API prioritizzate"""
        question = question.lower().strip()
        api_calls = []
        
        logger.info(f"[API MAPPER] Analyzing question: {question}")
        
        # PRIORITÀ ALLE PREDIZIONI - se contiene parole chiave di predizioni, usa quelle
        # anche se contiene altre parole chiave come "prossime"
        if self._is_predictions_query(question):
            calls = self._handle_predictions(question)
            api_calls.extend(calls)
        
        # 1. PARTITE FUTURE/PROGRAMMATE
        elif self._is_upcoming_matches_query(question):
            calls = self._handle_upcoming_matches(question)
            api_calls.extend(calls)
        
        # 2. PARTITE LIVE
        elif self._is_live_matches_query(question):
            calls = self._handle_live_matches(question)
            api_calls.extend(calls)
        
        # 3. RISULTATI/PARTITE PASSATE
        elif self._is_past_matches_query(question):
            calls = self._handle_past_matches(question)
            api_calls.extend(calls)
        
        # 4. STATISTICHE SQUADRE
        elif self._is_team_stats_query(question):
            calls = self._handle_team_stats(question)
            api_calls.extend(calls)
        
        # 5. CLASSIFICHE
        elif self._is_standings_query(question):
            calls = self._handle_standings(question)
            api_calls.extend(calls)
        
        # 6. GIOCATORI/ROSA
        elif self._is_players_query(question):
            calls = self._handle_players(question)
            api_calls.extend(calls)
        
        # 7. INFORTUNI
        elif self._is_injuries_query(question):
            calls = self._handle_injuries(question)
            api_calls.extend(calls)
        
        # 8. TRASFERIMENTI
        elif self._is_transfers_query(question):
            calls = self._handle_transfers(question)
            api_calls.extend(calls)
            
        # 9. FALLBACK - prova a cercare squadre/campionati generici
        else:
            calls = self._handle_general_query(question)
            api_calls.extend(calls)
        
        # Ordina per priorità e limita a max 3 chiamate
        api_calls.sort(key=lambda x: x.priority)
        return api_calls[:3]
    
    def _is_upcoming_matches_query(self, question: str) -> bool:
        """Rileva domande sulle partite future"""
        keywords = [
            'prossim', 'futur', 'program', 'calendari', 'schedul',
            'when', 'quando', 'domani', 'oggi', 'questa settimana',
            'prossima settimana', 'weekend', 'fixtures'
        ]
        return any(keyword in question for keyword in keywords)
    
    def _is_live_matches_query(self, question: str) -> bool:
        """Rileva domande sulle partite live"""
        keywords = [
            'live', 'in corso', 'adesso', 'ora', 'current', 'playing',
            'tempo reale', 'diretta'
        ]
        return any(keyword in question for keyword in keywords)
    
    def _is_past_matches_query(self, question: str) -> bool:
        """Rileva domande sui risultati passati"""
        keywords = [
            'risultat', 'result', 'passate', 'scorso', 'ultima',
            'precedent', 'storico', 'history', 'finished'
        ]
        return any(keyword in question for keyword in keywords)
    
    def _is_predictions_query(self, question: str) -> bool:
        """Rileva domande sulle predizioni"""
        keywords = [
            'predizion', 'prediction', 'previsioni', 'forecast',
            'pronostic', 'analisi', 'chi vince', 'vincerà'
        ]
        return any(keyword in question for keyword in keywords)
    
    def _is_team_stats_query(self, question: str) -> bool:
        """Rileva domande sulle statistiche squadre"""
        keywords = [
            'statistic', 'performance', 'rendimento', 'forma',
            'vittorie', 'sconfitte', 'pareggi', 'goal', 'media'
        ]
        return any(keyword in question for keyword in keywords)
    
    def _is_standings_query(self, question: str) -> bool:
        """Rileva domande sulle classifiche"""
        keywords = [
            'classifica', 'standing', 'posizione', 'punti',
            'tabella', 'ranking', 'leaderboard'
        ]
        return any(keyword in question for keyword in keywords)
    
    def _is_players_query(self, question: str) -> bool:
        """Rileva domande sui giocatori"""
        keywords = [
            'giocator', 'player', 'rosa', 'squad', 'team',
            'attaccant', 'difensor', 'portier', 'centrocampist'
        ]
        return any(keyword in question for keyword in keywords)
    
    def _is_injuries_query(self, question: str) -> bool:
        """Rileva domande sugli infortuni"""
        keywords = [
            'infortun', 'injury', 'indisponibil', 'injured',
            'squalific', 'suspended'
        ]
        return any(keyword in question for keyword in keywords)
    
    def _is_transfers_query(self, question: str) -> bool:
        """Rileva domande sui trasferimenti"""
        keywords = [
            'trasferiment', 'transfer', 'mercato', 'acquist',
            'vendite', 'comprato', 'venduto'
        ]
        return any(keyword in question for keyword in keywords)

    def _extract_country(self, question: str) -> Optional[str]:
        """Estrae il paese dalla domanda"""
        for key, value in self.country_codes.items():
            if key in question:
                return value
        return None
    
    def _extract_league(self, question: str) -> Optional[Dict[str, Any]]:
        """Estrae il campionato dalla domanda"""
        for key, value in self.league_mappings.items():
            if key in question:
                return value
        return None
    
    def _extract_team_name(self, question: str) -> Optional[str]:
        """Estrae il nome della squadra dalla domanda (semplificato)"""
        # Lista squadre famose italiane
        italian_teams = [
            'milan', 'inter', 'juventus', 'juve', 'napoli', 'roma', 'lazio',
            'fiorentina', 'atalanta', 'torino', 'bologna', 'udinese', 'sassuolo'
        ]
        
        for team in italian_teams:
            if team in question:
                return team.title()
        return None
    
    def _get_date_range(self, question: str) -> Tuple[Optional[str], Optional[str]]:
        """Estrae il range di date dalla domanda"""
        today = datetime.now()
        
        if 'oggi' in question:
            date_str = today.strftime('%Y-%m-%d')
            return date_str, date_str
        elif 'domani' in question:
            tomorrow = today + timedelta(days=1)
            date_str = tomorrow.strftime('%Y-%m-%d')
            return date_str, date_str
        elif 'settimana' in question:
            end_week = today + timedelta(days=7)
            return today.strftime('%Y-%m-%d'), end_week.strftime('%Y-%m-%d')
        elif 'weekend' in question:
            # Prossimo weekend (sabato-domenica)
            days_ahead = 5 - today.weekday()  # Sabato
            if days_ahead <= 0:
                days_ahead += 7
            saturday = today + timedelta(days=days_ahead)
            sunday = saturday + timedelta(days=1)
            return saturday.strftime('%Y-%m-%d'), sunday.strftime('%Y-%m-%d')
        
        return None, None

    def _handle_upcoming_matches(self, question: str) -> List[APICall]:
        """Gestisce domande sulle partite future"""
        calls = []
        
        country = self._extract_country(question)
        league = self._extract_league(question)
        team = self._extract_team_name(question)
        start_date, end_date = self._get_date_range(question)
        
        # Se non specifica date, usa i prossimi 7 giorni
        if not start_date:
            today = datetime.now()
            start_date = today.strftime('%Y-%m-%d')
            end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Parametri base
        params = {}
        
        if team:
            # Prima cerca l'ID della squadra
            calls.append(APICall(
                endpoint="teams",
                params={"search": team},
                description=f"Ricerca ID per {team}",
                priority=1
            ))
            
            # Poi cerca partite di una squadra specifica
            params = {
                "team": team, 
                "season": self.current_season,
                "from": start_date,
                "to": end_date
            }
            calls.append(APICall(
                endpoint="fixtures",
                params=params,
                description=f"Prossime partite di {team} dal {start_date} al {end_date}",
                priority=1
            ))
        elif league:
            # Cerca partite di un campionato specifico
            params = {
                "league": league['league'], 
                "season": self.current_season,
                "from": start_date,
                "to": end_date
            }
            calls.append(APICall(
                endpoint="fixtures",
                params=params,
                description=f"Prossime partite del campionato",
                priority=1
            ))
        elif country:
            # Cerca per paese - usa i campionati principali del paese
            if country == "Italy":
                # Serie A
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 135, # Serie A
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Prossime partite Serie A",
                    priority=1
                ))
                # Serie B
                calls.append(APICall(
                    endpoint="fixtures", 
                    params={
                        "league": 136, # Serie B
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Prossime partite Serie B",
                    priority=2
                ))
                # Serie C
                calls.append(APICall(
                    endpoint="fixtures", 
                    params={
                        "league": 137, # Serie C
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Prossime partite Serie C",
                    priority=3
                ))
            elif country == "Spain":
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 140, # La Liga
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Prossime partite La Liga",
                    priority=1
                ))
            elif country == "England":
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 39, # Premier League
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Prossime partite Premier League",
                    priority=1
                ))
            else:
                # Fallback generico per altri paesi
                params = {"date": start_date}
                calls.append(APICall(
                    endpoint="fixtures",
                    params=params,
                    description=f"Partite del {start_date} per filtrare per paese",
                    priority=2
                ))
        else:
            # Fallback: partite di oggi/domani
            params = {"date": start_date}
            calls.append(APICall(
                endpoint="fixtures",
                params=params,
                description=f"Partite del {start_date}",
                priority=2
            ))
        
        return calls
    
    def _handle_live_matches(self, question: str) -> List[APICall]:
        """Gestisce domande sulle partite live"""
        calls = [
            APICall(
                endpoint="fixtures",
                params={"live": "all"},
                description="Partite attualmente in corso",
                priority=1
            )
        ]
        return calls
    
    def _handle_past_matches(self, question: str) -> List[APICall]:
        """Gestisce domande sui risultati passati"""
        calls = []
        
        team = self._extract_team_name(question)
        league = self._extract_league(question)
        
        # Date passate - estendi il range per assicurarsi di trovare partite terminate
        today = datetime.now()
        last_month = today - timedelta(days=30)  # Esteso a 30 giorni per trovare più partite
        
        if team:
            # Prima aggiungi una chiamata per ottenere l'ID della squadra
            calls.append(APICall(
                endpoint="teams",
                params={"search": team},
                description=f"Ricerca ID per {team}",
                priority=1
            ))
            
            # Poi aggiungi la chiamata per i fixtures usando il nome (sarà convertito in ID dal backend)
            # Usa un range di date invece di "last" per avere più controllo sui filtri
            params = {
                "team": team,
                "season": self.current_season,
                "from": last_month.strftime('%Y-%m-%d'),
                "to": today.strftime('%Y-%m-%d'),
                "status": "FT"  # Solo partite finite
            }
            calls.append(APICall(
                endpoint="fixtures",
                params=params,
                description=f"Ultimi risultati di {team} (partite terminate)",
                priority=1
            ))
        elif league:
            # Per i campionati, usa un range più breve (ultima settimana)
            last_week = today - timedelta(days=7)
            params = {
                "league": league['league'],
                "season": self.current_season,
                "from": last_week.strftime('%Y-%m-%d'),
                "to": today.strftime('%Y-%m-%d'),
                "status": "FT"  # Solo partite finite
            }
            calls.append(APICall(
                endpoint="fixtures",
                params=params,
                description="Risultati recenti del campionato (partite terminate)",
                priority=1
            ))
        
        return calls
    
    def _handle_predictions(self, question: str) -> List[APICall]:
        """Gestisce domande sulle predizioni"""
        calls = []
        
        country = self._extract_country(question)
        league = self._extract_league(question)
        team = self._extract_team_name(question)
        start_date, end_date = self._get_date_range(question)
        
        # Se non specifica date, usa i prossimi 7 giorni per le predizioni
        if not start_date:
            today = datetime.now()
            start_date = today.strftime('%Y-%m-%d')
            end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
        
        if team:
            # Predizioni per una squadra specifica
            calls.append(APICall(
                endpoint="teams",
                params={"search": team},
                description=f"Ricerca ID per {team}",
                priority=1
            ))
            
            calls.append(APICall(
                endpoint="fixtures",
                params={
                    "team": team,
                    "season": self.current_season,
                    "from": start_date,
                    "to": end_date
                },
                description=f"Prossime partite di {team} per predizioni dal {start_date} al {end_date}",
                priority=1
            ))
        elif league:
            # Predizioni per un campionato specifico (es. Serie A)
            calls.append(APICall(
                endpoint="fixtures",
                params={
                    "league": league['league'],
                    "season": self.current_season,
                    "from": start_date,
                    "to": end_date
                },
                description=f"Prossime partite del campionato per predizioni dal {start_date} al {end_date}",
                priority=1
            ))
        elif country:
            # Predizioni per paese - usa i campionati principali del paese
            if country == "Italy":
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 135,  # Serie A
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Prossime partite Serie A per predizioni dal {start_date} al {end_date}",
                    priority=1
                ))
            else:
                # Fallback per altri paesi
                calls.append(APICall(
                    endpoint="predictions",
                    params={"days": 3},
                    description="Predizioni generali per le prossime partite",
                    priority=2
                ))
        else:
            # Fallback: predizioni generali
            calls.append(APICall(
                endpoint="predictions",
                params={"days": 3},
                description="Predizioni generali per le prossime partite",
                priority=2
            ))
        
        return calls
    
    def _handle_team_stats(self, question: str) -> List[APICall]:
        """Gestisce domande sulle statistiche squadre"""
        calls = []
        
        team = self._extract_team_name(question)
        league = self._extract_league(question)
        
        if team and league:
            # Cerca prima l'ID della squadra, poi le statistiche
            calls.append(APICall(
                endpoint="teams",
                params={"search": team},
                description=f"Ricerca squadra {team}",
                priority=1
            ))
            # Nota: dovremmo fare una seconda chiamata con l'ID trovato
        
        return calls
    
    def _handle_standings(self, question: str) -> List[APICall]:
        """Gestisce domande sulle classifiche"""
        calls = []
        
        league = self._extract_league(question)
        
        if league:
            calls.append(APICall(
                endpoint="standings",
                params={
                    "league": league['league'],
                    "season": self.current_season
                },
                description="Classifica del campionato",
                priority=1
            ))
        else:
            # Default: Serie A
            calls.append(APICall(
                endpoint="standings", 
                params={"league": 135, "season": self.current_season},
                description="Classifica Serie A",
                priority=2
            ))
        
        return calls
    
    def _handle_players(self, question: str) -> List[APICall]:
        """Gestisce domande sui giocatori"""
        calls = []
        
        team = self._extract_team_name(question)
        
        if team:
            calls.append(APICall(
                endpoint="teams",
                params={"search": team},
                description=f"Ricerca squadra {team} per ottenere rosa",
                priority=1
            ))
        
        return calls
    
    def _handle_injuries(self, question: str) -> List[APICall]:
        """Gestisce domande sugli infortuni"""
        calls = []
        
        team = self._extract_team_name(question)
        
        if team:
            calls.append(APICall(
                endpoint="teams",
                params={"search": team},
                description=f"Ricerca squadra {team} per infortuni",
                priority=1
            ))
        
        return calls
    
    def _handle_transfers(self, question: str) -> List[APICall]:
        """Gestisce domande sui trasferimenti"""
        calls = []
        
        team = self._extract_team_name(question)
        
        if team:
            calls.append(APICall(
                endpoint="teams",
                params={"search": team},
                description=f"Ricerca squadra {team} per trasferimenti",
                priority=1
            ))
        
        return calls
    
    def _handle_general_query(self, question: str) -> List[APICall]:
        """Gestisce domande generiche come fallback"""
        calls = []
        
        # Fallback: partite di oggi
        today = datetime.now().strftime('%Y-%m-%d')
        calls.append(APICall(
            endpoint="fixtures",
            params={"date": today},
            description="Partite di oggi come fallback",
            priority=3
        ))
        
        return calls

