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
            'brasiliana': 'Brazil', 'brasiliane': 'Brazil', 'brasiliani': 'Brazil', 'brasiliano': 'Brazil',
            # Portogallo
            'portugal': 'Portugal', 'portogallo': 'Portugal', 'portuguese': 'Portugal',
            'portoghese': 'Portugal', 'portoghesi': 'Portugal',
            # Olanda
            'netherlands': 'Netherlands', 'olanda': 'Netherlands', 'paesi bassi': 'Netherlands',
            'dutch': 'Netherlands', 'olandese': 'Netherlands', 'olandesi': 'Netherlands'
        }
        
        self.league_mappings = {
            # Italia
            'serie a': {'league': 135, 'country': 'Italy'},
            'serie b': {'league': 136, 'country': 'Italy'},
            'serie c': {'league': 137, 'country': 'Italy'},
            'coppa italia': {'league': 137, 'country': 'Italy'},  # Verificare ID corretto
            'champions league': {'league': 2, 'country': 'World'},
            'europa league': {'league': 3, 'country': 'World'},
            # Inghilterra  
            'premier league': {'league': 39, 'country': 'England'},
            'championship': {'league': 40, 'country': 'England'},
            # Spagna
            'la liga': {'league': 140, 'country': 'Spain'},
            'liga': {'league': 140, 'country': 'Spain'},
            'segunda division': {'league': 141, 'country': 'Spain'},
            # Francia
            'ligue 1': {'league': 61, 'country': 'France'},
            'ligue 2': {'league': 62, 'country': 'France'},
            # Germania
            'bundesliga': {'league': 78, 'country': 'Germany'},
            '2. bundesliga': {'league': 79, 'country': 'Germany'},
            '3. liga': {'league': 80, 'country': 'Germany'},
            'dfb-pokal': {'league': 81, 'country': 'Germany'},
            'dfb pokal': {'league': 81, 'country': 'Germany'},
            'coppa di germania': {'league': 81, 'country': 'Germany'},
            # Brasile
            'serie a brasileira': {'league': 71, 'country': 'Brazil'},
            'brasileirao': {'league': 71, 'country': 'Brazil'},
            'serie b brasileira': {'league': 72, 'country': 'Brazil'},
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
        
        # PRIORITÀ ALLE QUOTE - se contiene parole chiave di quote, usa quelle
        elif self._is_odds_query(question):
            calls = self._handle_odds(question)
            api_calls.extend(calls)
        
        # 1. TOP MATCH/PARTITE IMPORTANTI - priorità alta
        elif self._is_top_matches_query(question):
            calls = self._handle_top_matches(question)
            api_calls.extend(calls)
        
        # 2. PARTITE FUTURE/PROGRAMMATE
        elif self._is_upcoming_matches_query(question):
            calls = self._handle_upcoming_matches(question)
            api_calls.extend(calls)
        
        # 3. PARTITE LIVE
        elif self._is_live_matches_query(question):
            calls = self._handle_live_matches(question)
            api_calls.extend(calls)
        
        # 4. RISULTATI/PARTITE PASSATE
        elif self._is_past_matches_query(question):
            calls = self._handle_past_matches(question)
            api_calls.extend(calls)
        
        # 5. INFORMAZIONI DETTAGLIATE TRA DUE SQUADRE (priorità alta)
        elif self._is_team_comparison_query(question):
            calls = self._handle_team_comparison(question)
            api_calls.extend(calls)
        
        # 6. STATISTICHE SQUADRE
        elif self._is_team_stats_query(question):
            calls = self._handle_team_stats(question)
            api_calls.extend(calls)
        
        # 7. CLASSIFICHE
        elif self._is_standings_query(question):
            calls = self._handle_standings(question)
            api_calls.extend(calls)
        
        # 8. GIOCATORI/ROSA
        elif self._is_players_query(question):
            calls = self._handle_players(question)
            api_calls.extend(calls)
        
        # 9. INFORTUNI
        elif self._is_injuries_query(question):
            calls = self._handle_injuries(question)
            api_calls.extend(calls)
        
        # 10. TRASFERIMENTI
        elif self._is_transfers_query(question):
            calls = self._handle_transfers(question)
            api_calls.extend(calls)
            
        # 11. FALLBACK - prova a cercare squadre/campionati generici
        else:
            calls = self._handle_general_query(question)
            api_calls.extend(calls)
        
        # Ordina per priorità
        api_calls.sort(key=lambda x: x.priority)
        
        # Per team comparison, permetti più chiamate
        if self._is_team_comparison_query(question):
            return api_calls[:10]  # Limite più alto per confronti
        elif self._is_top_matches_query(question):
            return api_calls[:20]  # Limite più alto per top matches (include scheduled)
        else:
            return api_calls[:3]   # Limite normale per altre query
    
    def _is_upcoming_matches_query(self, question: str) -> bool:
        """Rileva domande sulle partite future"""
        keywords = [
            'prossim', 'futur', 'program', 'calendari', 'schedul',
            'when', 'quando', 'domani', 'oggi', 'questa settimana',
            'prossima settimana', 'weekend', 'fixtures', 'stasera',
            'questa sera', 'today', 'tomorrow', 'ci sono partite',
            'che partite ci sono', 'quali partite ci sono'
        ]
        return any(keyword in question for keyword in keywords)
    
    def _is_top_matches_query(self, question: str) -> bool:
        """Rileva domande sui top match/partite importanti"""
        keywords = [
            'top match', 'partite importanti', 'match importanti', 
            'important matches', 'partite della settimana', 'match della settimana',
            'partite principali', 'match principali', 'big match', 'big matches',
            'partite di rilievo', 'match di rilievo', 'partite significative',
            'match significativi', 'partite rilevanti', 'match rilevanti',
            'partite importanti oggi', 'match importanti oggi', 'important matches today',
            'partite importanti domani', 'match importanti domani', 'important matches tomorrow',
            'a momenti', 'tra poco', 'presto', 'imminenti', 'di oggi'
        ]
        return any(keyword in question.lower() for keyword in keywords)
    
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
            'pronostic', 'analisi', 'chi vince', 'vincerà',
            'prevedi', 'prevedere', 'predire', 'predici'
        ]
        return any(keyword in question.lower() for keyword in keywords)
    
    def _is_odds_query(self, question: str) -> bool:
        """Rileva domande sulle quote"""
        keywords = [
            'quote', 'odds', 'quota', 'quotazione', 'quotazioni',
            'bookmaker', 'scommess', 'bet', 'betting', 'puntata'
        ]
        return any(keyword in question.lower() for keyword in keywords)
    
    def _is_team_stats_query(self, question: str) -> bool:
        """Rileva domande sulle statistiche squadre"""
        keywords = [
            'statistic', 'performance', 'rendimento', 'forma',
            'vittorie', 'sconfitte', 'pareggi', 'goal', 'media',
            'informazioni statistiche', 'statistiche attuali', 'statistiche recenti',
            'statistiche aggiornate', 'info statistiche', 'dati statistici'
        ]
        return any(keyword in question.lower() for keyword in keywords)
    
    def _is_team_comparison_query(self, question: str) -> bool:
        """Rileva domande per informazioni dettagliate tra due squadre"""
        keywords = [
            'informazioni tra', 'info tra', 'dati tra', 'statistiche tra',
            'confronto tra', 'analisi tra', 'dettagli tra', 'che informazioni',
            'cosa sappiamo', 'forma delle squadre', 'infortuni', 'stato forma',
            'come stanno', 'situazione'
        ]
        # Controlla se ci sono due squadre menzionate
        has_vs = any(vs_word in question.lower() for vs_word in ['vs', 'contro', 'tra', ' e '])
        has_keywords = any(keyword in question.lower() for keyword in keywords)
        
        return has_keywords or (has_vs and any(info_word in question.lower() for info_word in ['informazioni', 'info', 'dati', 'statistiche', 'analisi']))
    
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
        # Prima prova con i mapping espliciti
        for key, value in self.country_codes.items():
            if key in question:
                return value
        
        # Se non trova mapping espliciti, prova a estrarre nomi di paesi comuni
        # usando pattern più generici
        import re
        
        # Pattern per paesi comuni non mappati
        country_patterns = {
            r'\bargentin[ai]\b': 'Argentina',
            r'\bchile\b': 'Chile', 
            r'\buruguay\b': 'Uruguay',
            r'\bcolomb[ia]\b': 'Colombia',
            r'\bper[uù]\b': 'Peru',
            r'\bmessico\b': 'Mexico',
            r'\bbelg[io]\b': 'Belgium',
            r'\bbelgio\b': 'Belgium',
            r'\bsvizzer[ai]\b': 'Switzerland',
            r'\baustr[ia]\b': 'Austria',
            r'\baustia\b': 'Austria',  # Gestisce errori di battitura comuni
            r'\bpoloni[ai]\b': 'Poland',
            r'\brepubblica ceca\b': 'Czech Republic',
            r'\bturchi[ai]\b': 'Turkey',
            r'\bgreci[ai]\b': 'Greece',
            r'\bsvezia\b': 'Sweden',
            r'\bnorvegia\b': 'Norway',
            r'\bdanimarca\b': 'Denmark'
        }
        
        question_lower = question.lower()
        for pattern, country in country_patterns.items():
            if re.search(pattern, question_lower):
                return country
                
        return None
    
    def _extract_league(self, question: str) -> Optional[Dict[str, Any]]:
        """Estrae il campionato dalla domanda"""
        for key, value in self.league_mappings.items():
            if key in question:
                return value
        return None
    
    def _extract_team_name(self, question: str) -> Optional[str]:
        """Estrae il nome della squadra dalla domanda con mappatura intelligente"""
        # Mappatura squadre con varianti e nomi completi
        team_mappings = {
            # Squadre italiane Serie A
            'milan': 'AC Milan',
            'ac milan': 'AC Milan',
            'inter': 'Inter Milan', 
            'inter milan': 'Inter Milan',
            'juventus': 'Juventus',
            'juve': 'Juventus',
            'napoli': 'Napoli',
            'roma': 'AS Roma',
            'as roma': 'AS Roma',
            'lazio': 'Lazio',
            'fiorentina': 'Fiorentina',
            'atalanta': 'Atalanta',
            'torino': 'Torino',
            'bologna': 'Bologna',
            'udinese': 'Udinese',
            'sassuolo': 'Sassuolo',
            'genoa': 'Genoa',
            'sampdoria': 'Sampdoria',
            'cagliari': 'Cagliari',
            'verona': 'Hellas Verona',
            'hellas verona': 'Hellas Verona',
            'empoli': 'Empoli',
            'lecce': 'Lecce',
            'monza': 'Monza',
            'salernitana': 'Salernitana',
            
            # Squadre internazionali famose
            'barcelona': 'Barcelona',
            'barca': 'Barcelona',
            'real madrid': 'Real Madrid',
            'madrid': 'Real Madrid',
            'atletico madrid': 'Atletico Madrid',
            'atletico': 'Atletico Madrid',
            'manchester united': 'Manchester United',
            'united': 'Manchester United',
            'manchester city': 'Manchester City',
            'city': 'Manchester City',
            'liverpool': 'Liverpool',
            'chelsea': 'Chelsea',
            'arsenal': 'Arsenal',
            'tottenham': 'Tottenham',
            'spurs': 'Tottenham',
            'bayern munich': 'Bayern Munich',
            'bayern': 'Bayern Munich',
            'borussia dortmund': 'Borussia Dortmund',
            'dortmund': 'Borussia Dortmund',
            'psg': 'Paris Saint Germain',
            'paris saint germain': 'Paris Saint Germain',
            'paris': 'Paris Saint Germain'
        }
        
        question_lower = question.lower()
        
        # Cerca la corrispondenza più lunga prima (per evitare che "real" matchi prima di "real madrid")
        sorted_teams = sorted(team_mappings.keys(), key=len, reverse=True)
        
        for team_key in sorted_teams:
            if team_key in question_lower:
                logger.info(f"[TEAM EXTRACTION] Found team '{team_key}' -> '{team_mappings[team_key]}'")
                return team_mappings[team_key]
        
        return None
    
    def _extract_two_teams(self, question: str) -> Optional[List[str]]:
        """Estrae due nomi di squadre da una domanda"""
        import re
        
        # Pattern per "tra X e Y", "X vs Y", "X contro Y", "come stanno X e Y"
        patterns = [
            r"(?:tra|between)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:e|and|vs|VS|Vs|contro)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)",
            r"([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:vs|VS|Vs|contro|\-|–)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)",
            r"(?:di|per|della partita)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:vs|VS|Vs|contro|\-|–)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)",
            r"(?:come\s+stanno|situazione)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:e|and)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)",
            r"(?:informazioni|info|dati)\s+(?:su|tra)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:e|and)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                team1 = match.group(1).strip()
                team2 = match.group(2).strip()
                
                # Pulisci i nomi delle squadre da parole comuni
                stop_words = ['il', 'la', 'del', 'della', 'di', 'da', 'con', 'per', 'su', 'in', 'a', 'the', 'of', 'and', 'or']
                
                def clean_team_name(name):
                    # Rimuovi informazioni sulla lega
                    name = re.sub(r'\s+(?:in|della|di)\s+(?:serie\s+a|champions\s+league|europa\s+league|coppa\s+italia).*$', '', name, flags=re.IGNORECASE)
                    
                    words = name.split()
                    cleaned_words = [word for word in words if word.lower() not in stop_words and len(word) > 1]
                    return ' '.join(cleaned_words) if cleaned_words else name
                
                team1_clean = clean_team_name(team1)
                team2_clean = clean_team_name(team2)
                
                if len(team1_clean) > 2 and len(team2_clean) > 2:
                    # Normalizza i nomi usando il mapping esistente
                    team1_normalized = self._normalize_team_name(team1_clean)
                    team2_normalized = self._normalize_team_name(team2_clean)
                    
                    logger.info(f"[TEAM EXTRACTION] Found teams: '{team1_clean}' -> '{team1_normalized}', '{team2_clean}' -> '{team2_normalized}'")
                    return [team1_normalized or team1_clean, team2_normalized or team2_clean]
        
        return None
    
    def _normalize_team_name(self, team_name: str) -> Optional[str]:
        """Normalizza il nome della squadra usando il mapping esistente"""
        team_mappings = {
            'juventus': 'Juventus',
            'juve': 'Juventus', 
            'inter': 'Inter',
            'internazionale': 'Inter',
            'milan': 'AC Milan',
            'ac milan': 'AC Milan',
            'roma': 'AS Roma',
            'as roma': 'AS Roma',
            'napoli': 'Napoli',
            'lazio': 'Lazio',
            'fiorentina': 'Fiorentina',
            'atalanta': 'Atalanta',
            'torino': 'Torino',
            'genoa': 'Genoa',
            'bologna': 'Bologna',
            'sassuolo': 'Sassuolo',
            'udinese': 'Udinese',
            'sampdoria': 'Sampdoria',
            'cagliari': 'Cagliari',
            'verona': 'Hellas Verona',
            'hellas verona': 'Hellas Verona',
            'spezia': 'Spezia',
            'salernitana': 'Salernitana',
            'empoli': 'Empoli',
            'venezia': 'Venezia',
            'real madrid': 'Real Madrid',
            'real': 'Real Madrid',
            'barcelona': 'Barcelona',
            'barca': 'Barcelona',
            'atletico madrid': 'Atletico Madrid',
            'atletico': 'Atletico Madrid',
            'sevilla': 'Sevilla',
            'valencia': 'Valencia',
            'villarreal': 'Villarreal',
            'real sociedad': 'Real Sociedad',
            'athletic bilbao': 'Athletic Bilbao',
            'manchester united': 'Manchester United',
            'united': 'Manchester United',
            'manchester city': 'Manchester City',
            'city': 'Manchester City',
            'liverpool': 'Liverpool',
            'chelsea': 'Chelsea',
            'arsenal': 'Arsenal',
            'tottenham': 'Tottenham',
            'spurs': 'Tottenham',
            'bayern munich': 'Bayern Munich',
            'bayern': 'Bayern Munich',
            'borussia dortmund': 'Borussia Dortmund',
            'dortmund': 'Borussia Dortmund',
            'psg': 'Paris Saint Germain',
            'paris saint germain': 'Paris Saint Germain',
            'paris': 'Paris Saint Germain',
            'marsiglia': 'Marseille',
            'marseille': 'Marseille',
            'olympique marseille': 'Marseille',
            'lyon': 'Lyon',
            'olympique lyon': 'Lyon',
            'monaco': 'Monaco',
            'as monaco': 'Monaco',
            'lille': 'Lille',
            'rennes': 'Rennes',
            'nice': 'Nice',
            'strasbourg': 'Strasbourg',
            'nizza': 'Nice',
            'nice': 'Nice'
        }
        
        team_lower = team_name.lower()
        return team_mappings.get(team_lower)
    
    def _get_date_range(self, question: str) -> Tuple[Optional[str], Optional[str]]:
        """Estrae il range di date dalla domanda"""
        now = datetime.now()
        
        # Riconoscimento di orari specifici (es. "sono le 18:15")
        time_pattern = r'(?:sono le|è|ore)\s*(\d{1,2})[:.](\d{2})'
        time_match = re.search(time_pattern, question, re.IGNORECASE)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            # Se l'orario è nel futuro di oggi, usa oggi, altrimenti domani
            current_time = now.time()
            specified_time = datetime.strptime(f"{hour}:{minute}", "%H:%M").time()
            
            if specified_time > current_time:
                # L'orario è ancora nel futuro di oggi
                date_str = now.strftime('%Y-%m-%d')
            else:
                # L'orario è già passato, considera domani
                tomorrow = now + timedelta(days=1)
                date_str = tomorrow.strftime('%Y-%m-%d')
            return date_str, date_str
        
        if 'oggi' in question:
            # Per "oggi", inizia dall'ora corrente fino alla fine della giornata
            date_str = now.strftime('%Y-%m-%d')
            return date_str, date_str
        elif 'domani' in question:
            tomorrow = now + timedelta(days=1)
            date_str = tomorrow.strftime('%Y-%m-%d')
            return date_str, date_str
        elif 'settimana' in question:
            end_week = now + timedelta(days=7)
            return now.strftime('%Y-%m-%d'), end_week.strftime('%Y-%m-%d')
        elif 'weekend' in question:
            # Prossimo weekend (sabato-domenica)
            days_ahead = 5 - now.weekday()  # Sabato
            if days_ahead <= 0:
                days_ahead += 7
            saturday = now + timedelta(days=days_ahead)
            sunday = saturday + timedelta(days=1)
            return saturday.strftime('%Y-%m-%d'), sunday.strftime('%Y-%m-%d')
        
        # Gestione dei mesi
        month_patterns = {
            'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
            'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8,
            'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
        }
        
        for month_name, month_num in month_patterns.items():
            if month_name in question.lower():
                # Determina l'anno - se il mese è passato quest'anno, usa l'anno prossimo
                current_year = now.year
                if month_num < now.month or (month_num == now.month and now.day > 15):
                    current_year += 1
                
                # Primo giorno del mese
                start_date = datetime(current_year, month_num, 1)
                
                # Ultimo giorno del mese
                if month_num == 12:
                    end_date = datetime(current_year + 1, 1, 1) - timedelta(days=1)
                else:
                    end_date = datetime(current_year, month_num + 1, 1) - timedelta(days=1)
                
                return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
        
        return None, None

    def _extract_number_of_matches(self, question: str) -> int:
        """Estrae il numero di partite richieste dalla domanda"""
        # Cerca pattern come "10 partite", "5 prossime", "tutte le 10", etc.
        patterns = [
            r'(\d+)\s+partite',
            r'(\d+)\s+prossime',
            r'tutte\s+le\s+(\d+)',
            r'primi\s+(\d+)',
            r'(\d+)\s+eventi'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, question.lower())
            if match:
                return int(match.group(1))
        
        # Default: se dice "prossime partite" senza numero, assume 10
        if any(word in question.lower() for word in ['prossime', 'future', 'next']):
            return 10
        
        return 5  # Default più conservativo

    def _handle_upcoming_matches(self, question: str) -> List[APICall]:
        """Gestisce domande sulle partite future"""
        calls = []
        
        country = self._extract_country(question)
        league = self._extract_league(question)
        team = self._extract_team_name(question)
        start_date, end_date = self._get_date_range(question)
        
        # Estrai numero di partite richieste (default 10 per "prossime partite")
        num_matches = self._extract_number_of_matches(question)
        
        # Definisci description_suffix basato sulla richiesta
        if any(word in question.lower() for word in ['oggi', 'today', 'stasera', 'questa sera', 'a momenti', 'tra poco', 'presto', 'imminenti', 'di oggi']):
            description_suffix = "di oggi"
        elif 'settimana' in question.lower() or 'week' in question.lower():
            description_suffix = "della settimana"
        else:
            description_suffix = "prossimi giorni"
        
        # Se non specifica date, usa un range più ampio per ottenere più partite
        if not start_date:
            today = datetime.now()
            start_date = today.strftime('%Y-%m-%d')
            
            # Se menziona "oggi" o "today", usa solo oggi
            if any(word in question.lower() for word in ['oggi', 'today', 'stasera', 'questa sera']):
                end_date = today.strftime('%Y-%m-%d')
            else:
                # Usa 30 giorni per avere abbastanza partite per la richiesta
                end_date = (today + timedelta(days=30)).strftime('%Y-%m-%d')
        
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
                "to": end_date,
                "status": "NS"  # Solo partite non iniziate
            }
            calls.append(APICall(
                endpoint="fixtures",
                params=params,
                description=f"Prossime {num_matches} partite di {team} dal {start_date} al {end_date}",
                priority=1
            ))
        elif league:
            # Cerca partite di un campionato specifico
            params = {
                "league": league['league'], 
                "season": self.current_season,
                "from": start_date,
                "to": end_date,
                "status": "NS"  # Solo partite non iniziate
            }
            calls.append(APICall(
                endpoint="fixtures",
                params=params,
                description=f"Prossime {num_matches} partite del campionato {league.get('name', 'Unknown')}",
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
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
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
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
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
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
                    },
                    description=f"Prossime partite Serie C",
                    priority=3
                ))
                # Serie D
                calls.append(APICall(
                    endpoint="fixtures", 
                    params={
                        "league": 138, # Serie D
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
                    },
                    description=f"Prossime partite Serie D",
                    priority=4
                ))
                # Coppa Italia
                calls.append(APICall(
                    endpoint="fixtures", 
                    params={
                        "league": 137, # Coppa Italia (stesso ID Serie C, verificare)
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
                    },
                    description=f"Prossime partite Coppa Italia",
                    priority=5
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
                # Championship
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 40, # Championship
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Prossime partite Championship",
                    priority=2
                ))
            elif country == "Germany":
                # Bundesliga
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 78, # Bundesliga
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
                    },
                    description=f"Prossime partite Bundesliga",
                    priority=1
                ))
                # 2. Bundesliga
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 79, # 2. Bundesliga
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
                    },
                    description=f"Prossime partite 2. Bundesliga",
                    priority=2
                ))
                # 3. Liga
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 80, # 3. Liga
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
                    },
                    description=f"Prossime partite 3. Liga",
                    priority=3
                ))
                # DFB-Pokal (Coppa di Germania)
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 81, # DFB-Pokal
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
                    },
                    description=f"Prossime partite DFB-Pokal",
                    priority=4
                ))
            elif country == "France":
                # Ligue 1
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 61, # Ligue 1
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
                    },
                    description=f"Prossime partite Ligue 1",
                    priority=1
                ))
                # Ligue 2
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 62, # Ligue 2
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
                    },
                    description=f"Prossime partite Ligue 2",
                    priority=2
                ))
            elif country == "Brazil":
                # Serie A Brasileira
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 71, # Serie A Brasileira
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
                    },
                    description=f"Prossime partite Serie A Brasileira",
                    priority=1
                ))
                # Serie B Brasileira
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 72, # Serie B Brasileira
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date,
                        "status": "NS-LIVE"  # Solo partite non iniziate o live
                    },
                    description=f"Prossime partite Serie B Brasileira",
                    priority=2
                ))
            else:
                # Fallback migliorato: prima prova a ottenere tutte le leghe del paese
                calls.append(APICall(
                    endpoint="leagues",
                    params={"country": country},
                    description=f"Recupera tutte le leghe di {country}",
                    priority=1
                ))
                # Poi cerca partite generiche per quella data
                params = {"date": start_date}
                calls.append(APICall(
                    endpoint="fixtures",
                    params=params,
                    description=f"Partite del {start_date} per filtrare per paese",
                    priority=2
                ))
        else:
            # Controlla se la richiesta menziona campionati europei o maggiori, o se è per "oggi"
            if any(word in question.lower() for word in ['europei', 'europe', 'maggiori', 'principali']) or description_suffix == "di oggi":
                # Top campionati europei (espanso)
                top_leagues = [
                    (135, "Serie A"),           # Italia
                    (39, "Premier League"),     # Inghilterra
                    (140, "La Liga"),           # Spagna
                    (78, "Bundesliga"),         # Germania
                    (61, "Ligue 1"),            # Francia
                    (88, "Eredivisie"),         # Olanda
                    (94, "Primeira Liga"),      # Portogallo
                    (203, "Super League"),      # Svizzera
                    (144, "Jupiler Pro League"), # Belgio
                    (169, "Championship"),      # Inghilterra (seconda divisione)
                    (40, "Champions League"),   # Champions League
                    (48, "Europa League"),      # Europa League
                    (529, "Conference League"), # Conference League
                    # Campionati aggiuntivi per garantire copertura
                    (169, "Liga MX"),           # Messico
                    (48, "Liga Profesional"),   # Argentina
                    (529, "Série A"),           # Brasile
                    (2, "Champions League"),    # Champions League (altra ID)
                    (3, "Europa League"),       # Europa League (altra ID)
                    (848, "Conference League"), # Conference League (altra ID)
                ]
                
                for league_id, league_name in top_leagues:
                    calls.append(APICall(
                        endpoint="fixtures",
                        params={
                            "league": league_id,
                            "season": self.current_season,
                            "from": start_date,
                            "to": end_date,
                            "status": "NS-LIVE"  # Partite non iniziate o live
                        },
                        description=f"Prossime partite {league_name}",
                        priority=1
                    ))
            else:
                # Fallback migliorato: partite dai campionati europei principali
                top_leagues = [
                    (135, "Serie A"),           # Italia
                    (39, "Premier League"),     # Inghilterra
                    (140, "La Liga"),           # Spagna
                    (78, "Bundesliga"),         # Germania
                    (61, "Ligue 1"),            # Francia
                    (88, "Eredivisie"),         # Olanda
                    (94, "Primeira Liga"),      # Portogallo
                    (203, "Super League"),      # Svizzera
                    (144, "Jupiler Pro League"), # Belgio
                    (169, "Championship"),      # Inghilterra (seconda divisione)
                    (40, "Champions League"),   # Champions League
                    (48, "Europa League"),      # Europa League
                    (529, "Conference League")  # Conference League
                ]
                
                for league_id, league_name in top_leagues:
                    calls.append(APICall(
                        endpoint="fixtures",
                        params={
                            "league": league_id,
                            "season": self.current_season,
                            "from": start_date,
                            "to": end_date,
                            "status": "NS-LIVE"  # Partite non iniziate e live
                        },
                        description=f"Prossime partite {league_name}",
                        priority=1
                    ))
        
        return calls
    
    def _handle_top_matches(self, question: str) -> List[APICall]:
        """Gestisce richieste di top match/partite importanti"""
        calls = []
        
        # Determina il range di date per la ricerca
        today = datetime.now()
        
        # Se menziona "oggi" o "today", usa solo oggi
        if any(word in question.lower() for word in ['oggi', 'today', 'stasera', 'questa sera', 'a momenti', 'tra poco', 'presto', 'imminenti', 'di oggi']):
            start_date = today.strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            description_suffix = "di oggi"
        # Se menziona "settimana", usa la settimana corrente
        elif 'settimana' in question.lower() or 'week' in question.lower():
            # Inizio settimana (lunedì)
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            start_date = start_of_week.strftime('%Y-%m-%d')
            end_date = end_of_week.strftime('%Y-%m-%d')
            description_suffix = "della settimana"
        else:
            # Default: prossimi 7 giorni
            start_date = today.strftime('%Y-%m-%d')
            end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
            description_suffix = "prossimi 7 giorni"
        
        # Top campionati europei per garantire partite importanti (espanso)
        top_leagues = [
            (135, "Serie A"),           # Italia
            (39, "Premier League"),     # Inghilterra
            (140, "La Liga"),           # Spagna
            (78, "Bundesliga"),         # Germania
            (61, "Ligue 1"),            # Francia
            (88, "Eredivisie"),         # Olanda
            (94, "Primeira Liga"),      # Portogallo
            (203, "Super League"),      # Svizzera
            (144, "Jupiler Pro League"), # Belgio
            (169, "Championship"),      # Inghilterra (seconda divisione)
            (40, "Champions League"),   # Champions League
            (48, "Europa League"),      # Europa League
            (529, "Conference League")  # Conference League
        ]
        
        # Aggiungi chiamate per i top campionati
        for league_id, league_name in top_leagues:
            calls.append(APICall(
                endpoint="fixtures",
                params={
                    "league": league_id,
                    "season": self.current_season,
                    "from": start_date,
                    "to": end_date,
                    "status": "NS-LIVE"  # Solo partite non iniziate o live
                },
                description=f"Top match {league_name} {description_suffix}",
                priority=1
            ))
        
        # Aggiungi chiamata generale per tutte le partite di oggi (fallback)
        if description_suffix == "di oggi":
            calls.append(APICall(
                endpoint="fixtures",
                params={
                    "from": start_date,
                    "to": end_date
                },
                description=f"Tutte le partite {description_suffix}",
                priority=2  # Priorità più bassa rispetto ai campionati principali
            ))
        
        # Aggiungi competizioni europee se disponibili
        european_competitions = [
            (2, "Champions League"),    # Champions League
            (3, "Europa League"),       # Europa League
            (848, "Conference League")  # Conference League
        ]
        
        for comp_id, comp_name in european_competitions:
            calls.append(APICall(
                endpoint="fixtures",
                params={
                    "league": comp_id,
                    "season": self.current_season,
                    "from": start_date,
                    "to": end_date,
                    "status": "NS-LIVE"
                },
                description=f"{comp_name} {description_suffix}",
            priority=1
        ))
        
        return calls
    
    def handle_generic_match_request(self, question: str, user_preferences: Dict[str, Any] = None) -> List[APICall]:
        """Gestisce richieste generiche di partite con supporto per preferenze utente"""
        calls = []
        
        # Se ci sono preferenze utente, usale
        if user_preferences:
            countries = user_preferences.get('countries', [])
            leagues = user_preferences.get('leagues', [])
            time_filter = user_preferences.get('time_filter', 'normal')
            
            today = datetime.now()
            
            # Gestione filtro temporale
            if time_filter == 'imminent':
                # Per richieste "tra poco", cerca solo nelle prossime 6 ore
                start_date = today.strftime('%Y-%m-%d')
                end_date = (today + timedelta(hours=6)).strftime('%Y-%m-%d')
                status_filter = "NS"  # Solo partite non iniziate
            else:
                # Filtro normale: prossimi 7 giorni
                start_date = today.strftime('%Y-%m-%d')
                end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
                status_filter = "NS-LIVE"  # Partite non iniziate e live
            
            # Gestisci preferenze per campionati specifici
            if leagues:
                for league_name in leagues:
                    league_info = self._extract_league(league_name)
                    if league_info:
                        calls.append(APICall(
                            endpoint="fixtures",
                            params={
                                "league": league_info['league'],
                                "season": self.current_season,
                                "from": start_date,
                                "to": end_date,
                                "status": status_filter
                            },
                            description=f"Partite {league_name} {'imminenti' if time_filter == 'imminent' else 'prossimi 7 giorni'}",
                            priority=1
                        ))
            
            # Gestisci preferenze per paesi
            elif countries:
                for country in countries:
                    country_normalized = self.country_codes.get(country.lower(), country)
                    
                    if country_normalized == "Italy":
                        # Serie A priorità alta
                        calls.append(APICall(
                            endpoint="fixtures",
                            params={
                                "league": 135,  # Serie A
                                "season": self.current_season,
                                "from": start_date,
                                "to": end_date,
                                "status": status_filter
                            },
                            description=f"Partite Serie A {'imminenti' if time_filter == 'imminent' else 'prossimi 7 giorni'}",
                            priority=1
                        ))
                    elif country_normalized == "Spain":
                        calls.append(APICall(
                            endpoint="fixtures",
                            params={
                                "league": 140,  # La Liga
                                "season": self.current_season,
                                "from": start_date,
                                "to": end_date,
                                "status": "NS-LIVE"
                            },
                            description="Partite La Liga prossimi 7 giorni",
                            priority=1
                        ))
                    elif country_normalized == "England":
                        calls.append(APICall(
                            endpoint="fixtures",
                            params={
                                "league": 39,  # Premier League
                                "season": self.current_season,
                                "from": start_date,
                                "to": end_date,
                                "status": "NS-LIVE"
                            },
                            description="Partite Premier League prossimi 7 giorni",
                            priority=1
                        ))
                    elif country_normalized == "Germany":
                        calls.append(APICall(
                            endpoint="fixtures",
                            params={
                                "league": 78,  # Bundesliga
                                "season": self.current_season,
                                "from": start_date,
                                "to": end_date,
                                "status": "NS-LIVE"
                            },
                            description="Partite Bundesliga prossimi 7 giorni",
                            priority=1
                        ))
                    elif country_normalized == "France":
                        calls.append(APICall(
                            endpoint="fixtures",
                            params={
                                "league": 61,  # Ligue 1
                                "season": self.current_season,
                                "from": start_date,
                                "to": end_date,
                                "status": "NS-LIVE"
                            },
                            description="Partite Ligue 1 prossimi 7 giorni",
                            priority=1
                        ))
        
        # Se non ci sono preferenze o chiamate, usa il metodo generale esistente
        if not calls:
            calls = self._handle_general_query(question)
        
        return calls
    
    def _handle_live_matches(self, question: str) -> List[APICall]:
        """Gestisce domande sulle partite live"""
        calls = []
        
        country = self._extract_country(question)
        league = self._extract_league(question)
        team = self._extract_team_name(question)
        
        if team:
            # Prima aggiungi una chiamata per ottenere l'ID della squadra
            calls.append(APICall(
                endpoint="teams",
                params={"search": team},
                description=f"Ricerca ID per {team}",
                priority=1
            ))
            
            # Poi aggiungi la chiamata per i fixtures live della squadra
            calls.append(APICall(
                endpoint="fixtures",
                params={
                    "team": team,
                    "live": "all"
                },
                description=f"Partite live di {team}",
                priority=1
            ))
        elif league:
            # Partite live di un campionato specifico
            calls.append(APICall(
                endpoint="fixtures",
                params={
                    "league": league['league'],
                    "live": "all"
                },
                description=f"Partite live del campionato",
                priority=1
            ))
        elif country:
            # Prima recupera tutte le leghe del paese
            calls.append(APICall(
                endpoint="leagues",
                params={"country": country},
                description=f"Recupera tutte le leghe di {country}",
                priority=1
            ))
            # Poi cerca partite live generiche
            calls.append(APICall(
                endpoint="fixtures",
                params={"live": "all"},
                description="Partite live per filtrare per paese",
                priority=2
            ))
        else:
            # Fallback: tutte le partite live
            calls.append(APICall(
                endpoint="fixtures",
                params={"live": "all"},
                description="Partite attualmente in corso",
                priority=1
            ))
        
        return calls
    
    def _handle_past_matches(self, question: str) -> List[APICall]:
        """Gestisce domande sui risultati passati"""
        calls = []
        
        team = self._extract_team_name(question)
        league = self._extract_league(question)
        country = self._extract_country(question)
        
        # Date passate - estendi il range per assicurarsi di trovare partite terminate
        today = datetime.now()
        last_month = today - timedelta(days=30)  # Esteso a 30 giorni per trovare più partite
        start_date = last_month.strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
        
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
                "from": start_date,
                "to": end_date,
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
                "to": end_date,
                "status": "FT"  # Solo partite finite
            }
            calls.append(APICall(
                endpoint="fixtures",
                params=params,
                description="Risultati recenti del campionato (partite terminate)",
                priority=1
            ))
        elif country:
            # Fallback migliorato: prima prova a ottenere tutte le leghe del paese
            calls.append(APICall(
                endpoint="leagues",
                params={"country": country},
                description=f"Recupera tutte le leghe di {country}",
                priority=1
            ))
            # Poi cerca partite generiche per quella data
            params = {
                "date": start_date,
                "status": "FT"  # Solo partite finite
            }
            calls.append(APICall(
                endpoint="fixtures",
                params=params,
                description=f"Partite terminate del {start_date} per filtrare per paese",
                priority=2
            ))
        else:
            # Fallback: partite terminate di ieri
            yesterday = (today - timedelta(days=1)).strftime('%Y-%m-%d')
            params = {
                "date": yesterday,
                "status": "FT"  # Solo partite finite
            }
            calls.append(APICall(
                endpoint="fixtures",
                params=params,
                description=f"Partite terminate del {yesterday}",
                priority=2
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
            # CICLO 5 FIX: Predizioni per una squadra specifica - AGGIUNTE CHIAMATE PREDICTIONS
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
            
            # FIX CRITICO: NON fare chiamata predictions qui con team (non funziona)
            # Le predictions verranno fatte successivamente con fixture=ID una volta ottenuti i fixtures
            # calls.append(APICall(...predictions con team...)) ← RIMOSSO perché non funziona
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
                # Serie A
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
            elif country == "England":
                # Premier League
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 39,  # Premier League
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Prossime partite Premier League per predizioni dal {start_date} al {end_date}",
                    priority=1
                ))
            elif country == "Spain":
                # La Liga
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 140,  # La Liga
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Prossime partite La Liga per predizioni dal {start_date} al {end_date}",
                    priority=1
                ))
            elif country == "Germany":
                # Bundesliga
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 78,  # Bundesliga
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Prossime partite Bundesliga per predizioni dal {start_date} al {end_date}",
                    priority=1
                ))
            elif country == "France":
                # Ligue 1
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 61,  # Ligue 1
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Prossime partite Ligue 1 per predizioni dal {start_date} al {end_date}",
                    priority=1
                ))
        
        # FIX CRITICO: Le predictions richiedono sempre un fixture ID specifico
        # Non possiamo fare chiamate predictions senza fixture
        # Le predictions verranno fatte dopo aver ottenuto i fixtures nel _execute_football_api_calls
        
        return calls
    
    def _handle_odds(self, question: str) -> List[APICall]:
        """Gestisce domande sulle quote"""
        calls = []
        
        country = self._extract_country(question)
        league = self._extract_league(question)
        team = self._extract_team_name(question)
        start_date, end_date = self._get_date_range(question)
        
        # Se non specifica date, usa i prossimi 7 giorni per le quote
        if not start_date:
            today = datetime.now()
            start_date = today.strftime('%Y-%m-%d')
            end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
        
        if team:
            # Quote per una squadra specifica
            calls.append(APICall(
                endpoint="fixtures",
                params={
                    "team": team,
                    "season": self.current_season,
                    "from": start_date,
                    "to": end_date
                },
                description=f"Prossime partite di {team} per quote dal {start_date} al {end_date}",
                priority=1
            ))
        elif league:
            # Quote per un campionato specifico
            calls.append(APICall(
                endpoint="fixtures",
                params={
                    "league": league["id"],
                    "season": self.current_season,
                    "from": start_date,
                    "to": end_date
                },
                description=f"Partite {league['name']} per quote dal {start_date} al {end_date}",
                priority=1
            ))
        elif country:
            # Gestione speciale per l'Italia (Serie A)
            if country.lower() == "italy":
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 135,  # Serie A
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Partite Serie A per quote dal {start_date} al {end_date}",
                    priority=1
                ))
            else:
                # Fallback per altri paesi
                calls.append(APICall(
                    endpoint="fixtures",
                    params={"date": start_date},
                    description="Quote per partite di oggi",
                    priority=2
                ))
        else:
            # Controlla se menziona campionati specifici anche senza riconoscimento automatico
            if 'serie a' in question.lower():
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 135,  # Serie A
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Partite Serie A per quote dal {start_date} al {end_date}",
                    priority=1
                ))
            elif 'premier league' in question.lower():
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 39,  # Premier League
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Partite Premier League per quote dal {start_date} al {end_date}",
                    priority=1
                ))
            elif 'la liga' in question.lower():
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 140,  # La Liga
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Partite La Liga per quote dal {start_date} al {end_date}",
                    priority=1
                ))
            elif 'bundesliga' in question.lower():
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 78,  # Bundesliga
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Partite Bundesliga per quote dal {start_date} al {end_date}",
                    priority=1
                ))
            elif 'ligue 1' in question.lower():
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": 61,  # Ligue 1
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date
                    },
                    description=f"Partite Ligue 1 per quote dal {start_date} al {end_date}",
                    priority=1
                ))
            else:
                # Fallback: partite di oggi per quote
                calls.append(APICall(
                    endpoint="fixtures",
                    params={"date": start_date},
                    description="Quote per partite di oggi",
                    priority=2
                ))
        
        return calls
    
    def _handle_team_stats(self, question: str) -> List[APICall]:
        """Gestisce domande sulle statistiche squadre"""
        calls = []
        
        team = self._extract_team_name(question)
        league = self._extract_league(question)
        
        if team:
            # Cerca prima l'ID della squadra
            calls.append(APICall(
                endpoint="teams",
                params={"search": team},
                description=f"Ricerca squadra {team}",
                priority=1
            ))
            
            # Aggiungi chiamate per statistiche dettagliate
            if league:
                calls.append(APICall(
                    endpoint="teams/statistics",
                    params={
                        "team": team,
                        "league": league['league'],
                        "season": self.current_season
                    },
                    description=f"Statistiche {team} in {league.get('name', 'campionato')}",
                    priority=1
                ))
            
            # Infortuni della squadra
            calls.append(APICall(
                endpoint="injuries",
                params={"team": team},
                description=f"Infortuni {team}",
                priority=2
            ))
        
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
    
    def _handle_team_comparison(self, question: str) -> List[APICall]:
        """Gestisce richieste di informazioni dettagliate tra due squadre"""
        calls = []
        
        # Estrai entrambe le squadre dalla domanda
        teams = self._extract_two_teams(question)
        league = self._extract_league(question)
        
        if teams and len(teams) == 2:
            team1, team2 = teams
            
            # Per ogni squadra, recupera informazioni complete
            for team in [team1, team2]:
                # 1. Cerca l'ID della squadra
                calls.append(APICall(
                    endpoint="teams",
                    params={"search": team},
                    description=f"Ricerca squadra {team}",
                    priority=1
                ))
                
                # 2. Statistiche della squadra
                if league:
                    calls.append(APICall(
                        endpoint="teams/statistics",
                        params={
                            "team": team,
                            "league": league['league'],
                            "season": self.current_season
                        },
                        description=f"Statistiche {team}",
                        priority=1
                    ))
                
                # 3. Ultime partite per valutare la forma
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "team": team,
                        "last": 5,
                        "season": self.current_season
                    },
                    description=f"Ultime 5 partite {team}",
                    priority=1
                ))
                
                # 4. Infortuni
                calls.append(APICall(
                    endpoint="injuries",
                    params={"team": team},
                    description=f"Infortuni {team}",
                    priority=2
                ))
            
            # 5. Head-to-head tra le due squadre
            calls.append(APICall(
                endpoint="fixtures/headtohead",
                params={
                    "h2h": f"{team1}-{team2}",
                    "last": 10
                },
                description=f"Precedenti {team1} vs {team2}",
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
        """Gestisce domande generiche come fallback con filtri intelligenti"""
        calls = []
        
        # 🔍 PRIORITÀ: Se viene menzionata una squadra specifica, cerca le sue partite
        team_name = self._extract_team_name(question)
        if team_name:
            logger.info(f"[GENERAL QUERY] Detected team: {team_name}")
            
            # 1. Cerca prima l'ID della squadra
            calls.append(APICall(
                endpoint="teams",
                params={"search": team_name},
                description=f"Ricerca squadra {team_name}",
                priority=1
            ))
            
            # 2. Cerca le prossime partite della squadra (usando il nome, poi l'ID verrà risolto)
            today = datetime.now()
            end_date = (today + timedelta(days=30)).strftime('%Y-%m-%d')  # Prossimi 30 giorni
            
            calls.append(APICall(
                endpoint="fixtures",
                params={
                    "team": team_name,  # Questo verrà convertito in ID dalla logica di esecuzione
                    "season": self.current_season,
                    "from": today.strftime('%Y-%m-%d'),
                    "to": end_date,
                    "status": "NS"  # Solo partite non iniziate
                },
                description=f"Prossime partite di {team_name}",
                priority=1
            ))
            
            # 3. Cerca anche le ultime partite giocate
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')  # Ultimi 30 giorni
            
            calls.append(APICall(
                endpoint="fixtures",
                params={
                    "team": team_name,
                    "season": self.current_season,
                    "from": start_date,
                    "to": today.strftime('%Y-%m-%d'),
                    "status": "FT"  # Solo partite finite
                },
                description=f"Ultime partite di {team_name}",
                priority=2
            ))
            
            return calls
        
        # Analizza se la richiesta menziona campionati europei o maggiori
        elif any(word in question for word in ['europei', 'europe', 'maggiori', 'principali']):
            # Invece di recuperare tutte le partite, recupera solo dai top campionati
            today = datetime.now()
            
            # Se menziona "oggi" o "today", usa solo oggi
            if any(word in question.lower() for word in ['oggi', 'today', 'stasera', 'questa sera']):
                start_date = today.strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
            else:
                start_date = today.strftime('%Y-%m-%d')
                end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
            
            # Top campionati europei (espanso)
            top_leagues = [
                (135, "Serie A"),           # Italia
                (39, "Premier League"),     # Inghilterra
                (140, "La Liga"),           # Spagna
                (78, "Bundesliga"),         # Germania
                (61, "Ligue 1"),            # Francia
                (88, "Eredivisie"),         # Olanda
                (94, "Primeira Liga"),      # Portogallo
                (203, "Super League"),      # Svizzera
                (144, "Jupiler Pro League"), # Belgio
                (169, "Championship"),      # Inghilterra (seconda divisione)
                (40, "Champions League"),   # Champions League
                (48, "Europa League"),      # Europa League
                (529, "Conference League")  # Conference League
            ]
            
            for league_id, league_name in top_leagues:
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": league_id,
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date,
                        "status": "NS"  # Solo partite non iniziate
                    },
                    description=f"Prossime partite {league_name}",
                    priority=1
                ))
        else:
            # Fallback migliorato: partite dei prossimi 7 giorni dai campionati principali
            today = datetime.now()
            
            # Se menziona "oggi" o "today", usa solo oggi
            if any(word in question.lower() for word in ['oggi', 'today', 'stasera', 'questa sera']):
                start_date = today.strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
            else:
                start_date = today.strftime('%Y-%m-%d')
                end_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
            
            # Top campionati europei per il fallback (espanso)
            top_leagues = [
                (135, "Serie A"),           # Italia
                (39, "Premier League"),     # Inghilterra
                (140, "La Liga"),           # Spagna
                (78, "Bundesliga"),         # Germania
                (61, "Ligue 1"),            # Francia
                (88, "Eredivisie"),         # Olanda
                (94, "Primeira Liga"),      # Portogallo
                (203, "Super League"),      # Svizzera
                (144, "Jupiler Pro League"), # Belgio
                (169, "Championship"),      # Inghilterra (seconda divisione)
                (40, "Champions League"),   # Champions League
                (48, "Europa League"),      # Europa League
                (529, "Conference League")  # Conference League
            ]
            
            for league_id, league_name in top_leagues:
                calls.append(APICall(
                    endpoint="fixtures",
                    params={
                        "league": league_id,
                        "season": self.current_season,
                        "from": start_date,
                        "to": end_date,
                        "status": "NS-LIVE"  # Partite non iniziate e live
                    },
                    description=f"Prossime partite {league_name}",
                    priority=1
                ))
        
        return calls

