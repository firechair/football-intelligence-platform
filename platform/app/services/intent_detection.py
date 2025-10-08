import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class IntentType(Enum):
    """Tipi di intent supportati dal chatbot"""
    NAVIGATION = "navigation"
    BET_ANALYSIS = "bet_analysis"
    ODDS_QUERY = "odds_query"
    CHART_REQUEST = "chart_request"
    STATISTICS = "statistics"
    OPEN_EVENT = "open_event"
    OPEN_EVENT_SECTION = "open_event_section"  # Nuovo intent per aprire sezioni specifiche
    TEAM_COMPARISON = "team_comparison"  # Nuovo intent per informazioni dettagliate tra squadre
    TEAM_INFO = "team_info"  # Nuovo intent per informazioni su singola squadra
    GENERIC_MATCH_REQUEST = "generic_match_request"  # Nuovo intent per richieste generiche sui match
    PREDICTIONS = "predictions"  # Nuovo intent per predizioni sportive
    LEAGUE_STANDINGS = "league_standings"  # Nuovo intent per classifiche di campionati
    VAGUE_REQUEST = "vague_request"  # Nuovo intent per richieste troppo vaghe che richiedono specificità
    HELP = "help"
    GREETING = "greeting"
    UNKNOWN = "unknown"
    AMBIGUOUS = "ambiguous"
    ERROR = "error"

class ConfidenceLevel(Enum):
    """Livelli di confidenza per il riconoscimento degli intent"""
    HIGH = 0.9
    MEDIUM = 0.7
    LOW = 0.5
    VERY_LOW = 0.3

@dataclass
class IntentMatch:
    """Risultato del riconoscimento di un intent"""
    intent_type: IntentType
    confidence: float
    entities: Dict[str, Any]
    original_text: str
    normalized_text: str
    patterns_matched: List[str]
    suggestions: List[str] = None
    error_type: Optional[str] = None

class IntentDetector:
    """Sistema avanzato di rilevamento intent per chatbot in italiano"""
    
    def __init__(self):
        self.intent_patterns = self._initialize_patterns()
        self.error_patterns = self._initialize_error_patterns()
        self.ambiguity_resolvers = self._initialize_ambiguity_resolvers()
        
    def _initialize_patterns(self) -> Dict[IntentType, List[Dict]]:
        """Inizializza i pattern per il riconoscimento degli intent"""
        return {
            IntentType.NAVIGATION: [
                {
                    "patterns": [
                        r"vai\s+(?:a|alla|al|in)\s+(homepage|simulator|matches|news|features|funzionalita)",
                        r"apri\s+(?:pagina|la\s+pagina)\s+(homepage|simulator|matches|news|features|funzionalita)",
                        r"naviga\s+(?:a|in)\s+(homepage|simulator|matches|news|features|funzionalita)",
                        r"spostami\s+(?:a|in)\s+(homepage|simulator|matches|news|features|funzionalita)",
                        r"portami\s+(?:a|in)\s+(homepage|simulator|matches|news|features|funzionalita)",
                        # Pattern più specifico per evitare conflitti con OPEN_EVENT
                        r"mostrami\s+(?:la\s+)?(?:pagina\s+)?(homepage|simulator|matches|news|features|funzionalita)",
                        # Pattern per "le partite", "il simulatore", etc.
                        r"mostrami\s+(?:le\s+)?(partite|matches)",
                        r"apri\s+(?:il\s+)?(simulatore|simulator)",
                        r"naviga\s+(?:alle\s+)?(news|notizie)",
                        # Pattern generici per navigazione
                        r"vai\s+(?:a|alla|al|in)\s+(\w+)",
                        r"apri\s+(?:pagina|la\s+pagina)\s+(\w+)",
                        r"naviga\s+(?:a|in)\s+(\w+)",
                        r"spostami\s+(?:a|in)\s+(\w+)",
                        r"portami\s+(?:a|in)\s+(\w+)",
                        # Nuovi pattern per domande frequenti
                        r"partite\s+di\s+oggi",
                        r"partite\s+di\s+domani",
                        r"prossima\s+partita\s+di\s+([\w\s]+)",
                        r"prossima\s+partita\s+del\s+([\w\s]+)",
                        r"campionati\s+di\s+domani",
                        r"campionati\s+di\s+oggi"
                    ],
                    "entities": ["destination"],
                    "confidence": ConfidenceLevel.HIGH
                }
            ],
            
            # CICLO 5 FIX CRITICO: Aggiungo pattern mancanti per PREDICTIONS
            IntentType.PREDICTIONS: [
                {
                    "patterns": [
                        # Pattern base per predizioni
                        r"(?:predizione|predizioni|pronostico|pronosici|previsione|previsioni)\s+",
                        r"(?:chi\s+vince|chi\s+vincerà|vincitore)\s+",
                        r"(?:risultato|esito)\s+(?:previsto|probabile)\s+",
                        # Pattern squadra vs squadra
                        r"predizione\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:vs|contro|[-])\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)",
                        r"pronostico\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:vs|contro|[-])\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)",
                        r"(?:chi\s+vince)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:vs|contro|[-])\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)",
                        # Pattern con squadre specifiche
                        r"predizione\s+(?:juventus|inter|milan|napoli|roma|lazio|atalanta|barcelona|real\s+madrid|manchester|chelsea|arsenal|liverpool|bayern|psg)",
                        r"pronostico\s+(?:juventus|inter|milan|napoli|roma|lazio|atalanta|barcelona|real\s+madrid|manchester|chelsea|arsenal|liverpool|bayern|psg)",
                        # Pattern temporali
                        r"(?:predizioni|pronosici|previsioni)\s+(?:di\s+)?(?:oggi|domani|questa\s+settimana|settimana|weekend)(?!.*partite)",
                        r"(?:predizioni|pronosici|previsioni)\s+(?:serie\s+a|premier|liga|bundesliga|champions)",
                        # Pattern generici per predizioni multiple
                        r"(?:migliori|best)\s+(?:predizioni|pronosici|previsioni)",
                        r"(?:predizioni|pronosici|previsioni)\s+(?:più\s+)?(?:sicure|profittabili|affidabili)",
                        r"(?:tutte\s+le\s+)?(?:predizioni|pronosici|previsioni)\s+(?:di\s+oggi|di\s+domani)",
                        # Pattern più specifici per tipster
                        r"(?:consigli|suggerimenti)\s+(?:per\s+)?(?:scommesse|betting|bet)",
                        r"(?:partite\s+)?(?:più\s+)?(?:sicure|profittabili)\s+(?:di\s+oggi|di\s+domani|oggi|domani)",
                        r"(?:quale|quali)\s+(?:partita|partite)\s+(?:scommettere|giocare|puntare)",
                        # Pattern value betting
                        r"(?:underdog|sorprese|value)\s+(?:di\s+oggi|di\s+domani|oggi|domani)",
                        r"(?:migliori\s+)?(?:value\s+bet|value\s+betting)",
                        r"(?:sorprese|upset)\s+(?:possibili|probabili)"
                    ],
                    "entities": ["team1", "team2", "date", "league", "prediction_type"],
                    "confidence": ConfidenceLevel.HIGH
                }
            ],
            
            IntentType.BET_ANALYSIS: [
                {
                    "patterns": [
                        r"(?:miglior|best)\s+(?:scommessa|bet)?\s*(?:multipla|multiple|multipla\s+del\s+giorno)",
                        r"(?:scommessa|bet)?\s*(?:multipla|multiple|multipla\s+del\s+giorno)\s*(?:miglior|best)",
                        r"analizza\s+(?:la\s+)?(?:miglior\s+)?(?:scommessa\s+)?(?:multipla|multiple)",
                        r"trova\s+(?:la\s+)?(?:miglior\s+)?(?:scommessa\s+)?(?:multipla|multiple)",
                        r"consiglia\s+(?:una\s+)?(?:scommessa\s+)?(?:multipla|multiple)"
                    ],
                    "entities": ["bet_type"],
                    "confidence": ConfidenceLevel.HIGH
                },
                {
                    "patterns": [
                        r"(?:miglior|best)\s+(?:scommessa|bet)?\s*(?:singola|single|singola\s+del\s+giorno)",
                        r"(?:scommessa|bet)?\s*(?:singola|single|singola\s+del\s+giorno)\s*(?:miglior|best)",
                        r"analizza\s+(?:la\s+)?(?:miglior\s+)?(?:scommessa\s+)?(?:singola|single)",
                        r"trova\s+(?:la\s+)?(?:miglior\s+)?(?:scommessa\s+)?(?:singola|single)",
                        r"consiglia\s+(?:una\s+)?(?:scommessa\s+)?(?:singola|single)"
                    ],
                    "entities": ["bet_type"],
                    "confidence": ConfidenceLevel.HIGH
                },
                {
                    "patterns": [
                        r"(?:miglior|best)\s+(?:sistema|system|sistema\s+del\s+giorno)",
                        r"analizza\s+(?:il\s+)?(?:miglior\s+)?(?:sistema|system)",
                        r"trova\s+(?:il\s+)?(?:miglior\s+)?(?:sistema|system)",
                        r"consiglia\s+(?:un\s+)?(?:sistema|system)"
                    ],
                    "entities": ["bet_type"],
                    "confidence": ConfidenceLevel.HIGH
                }
            ],
            
            IntentType.ODDS_QUERY: [
                {
                    "patterns": [
                        r"quota\s+(?:per|di|del)\s+([\w\s]+)",
                        r"odds\s+(?:per|di|del)\s+([\w\s]+)",
                        r"quanto\s+(?:paga|rende)\s+([\w\s]+)",
                        r"che\s+quota\s+(?:ha|ha\s+)?([\w\s]+)",
                        r"quota\s+([\w\s]+)"
                    ],
                    "entities": ["team_or_match"],
                    "confidence": ConfidenceLevel.MEDIUM
                }
            ],
            
            IntentType.CHART_REQUEST: [
                {
                    "patterns": [
                        r"(?:mostra|visualizza|vedi|apri|aprimi|aprirmi)\s+(?:il\s+)?(?:grafico\s+)?(?:della\s+)?(?:quota|odds)\s+(?:per|di|del)\s+([\w\s]+)",
                        r"(?:puoi\s+)?apr(?:ire|irmi)\s+(?:il\s+)?(?:grafico\s+)?(?:della\s+)?(?:quota|odds)\s+(?:per|di|del)\s+([\w\s]+)",
                        r".*grafico.*quot[ae].*(?:per|di|del)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)"
                    ],
                    "entities": ["team_or_match"],
                    "confidence": ConfidenceLevel.MEDIUM
                }
            ],
            
            IntentType.STATISTICS: [
                {
                    "patterns": [
                        r"(?:statistiche|stats)\s+(?:per|di|del)\s+([\w\s]+)",
                        r"(?:mostra|visualizza)\s+(?:le\s+)?(?:statistiche|stats)\s+(?:per|di|del)\s+([\w\s]+)",
                        r"(?:analisi|analizza)\s+(?:statistiche|stats)\s+(?:per|di|del)\s+([\w\s]+)"
                    ],
                    "entities": ["team_or_match"],
                    "confidence": ConfidenceLevel.MEDIUM
                }
            ],
            
            IntentType.OPEN_EVENT: [
                {
                    "patterns": [
                        # Pattern per "mostrami evento X" e "parlami di evento X"
                        r"(?:mostrami|mostra|parlami|parla)\s+(?:di\s+)?(?:evento|partita|match)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        r"(?:mostrami|mostra|parlami|parla)\s+(?:dell['\s]+|del\s+)?(?:evento|partita|match)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        r"(?:mostrami|mostra|parlami|parla)\s+(?:dell['\s]+|del\s+)?(?:evento|partita|match)\s+(?:di|per|tra)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        r"(?:mostrami|mostra|parlami|parla)\s+(?:dell['\s]+|del\s+)?(?:evento|partita|match)\s+(?:relativo\s+a|di|per)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        # Pattern per "mostrami la partita del Napoli vs Pisa"
                        r"(?:mostrami|mostra|parlami|parla)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:del|della|di)\s+([A-Z][\w\s]+)\s+(?:vs|contro)\s+([A-Z][\w\s]+)",
                        r"(?:mostrami|mostra|parlami|parla)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:del|della|di)\s+([A-Z][\w\s]+)\s+(?:vs|contro)\s+([A-Z][\w\s]+)",
                        r"(?:mostrami|mostra|parlami|parla)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:tra|fra)\s+([A-Z][\w\s]+)\s+(?:e|ed)\s+([A-Z][\w\s]+)",
                        r"(?:mostrami|mostra|parlami|parla)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:tra|fra)\s+([A-Z][\w\s]+)\s+(?:e|ed)\s+([A-Z][\w\s]+)",
                        # Pattern specifici con nome evento (devono essere prima di quelli generici)
                        r"(?:vai|va)\s+(?:a|all['\s]+|alla\s+)?(?:evento|partita|match)\s+(?:del|della|di)\s+([\w\s]+)",
                        r"(?:portami|spostami|naviga)\s+(?:a|all['\s]+|alla\s+)?(?:evento|partita|match)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        r"(?:portami|spostami|naviga)\s+(?:a|all['\s]+|alla\s+)?(?:evento|partita|match)\s+(?:di|per|tra)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        # Pattern per "apri la partita X vs Y"
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:la\s+)?(?:partita|evento|match)\s+([\w\s]+)\s+(?:vs|contro)\s+([\w\s]+)",
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:del|della|di)\s+([\w\s]+)\s+(?:vs|contro)\s+([\w\s]+)",
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:tra|fra)\s+([\w\s]+)\s+(?:e|ed)\s+([\w\s]+)",
                        # Pattern generici senza nome evento specifico
                        r"(?:portami|spostami|naviga)\s+(?:a|all['\s]+|alla\s+)?(?:evento|partita|match)(?:\s+corrente|\s+attuale)?",
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)(?:\s+corrente|\s+attuale)?",
                        r"(?:vai|va)\s+(?:a|all['\s]+|alla\s+)?(?:evento|partita|match)",
                        r"ti\s+apro\s*$",
                        # Pattern semplici e flessibili con nome evento
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)\s+(?:di|per)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)\s+(?:relativa\s+a|di|per)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        # Pattern per "apri la partita dell' Itapirense" con apostrofo
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:la\s+)?(?:evento|partita|match)\s+dell['\s]+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        # Pattern più semplice per catturare "dell Itapirense"
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:la\s+)?(?:evento|partita|match)\s+dell\s+([A-Za-z0-9\s]+)",
                        # Pattern per "portami all'evento" con nome
                        r"(?:portami|spostami|naviga)\s+(?:a|all['\s]+|alla\s+)?(?:evento|partita|match)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        r"(?:portami|spostami|naviga)\s+(?:a|all['\s]+|alla\s+)?(?:evento|partita|match)\s+(?:di|per|tra)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        # Pattern specifici per catturare "U contro Manchester United U21"
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)\s+(?:dell['\s]+evento\s+)?([A-Za-z0-9]+)\s+(?:contro|vs)\s+([\w\s]+)",
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)\s+(?:dell['\s]+evento\s+)?([\w\s]+)\s+(?:contro|vs)\s+([A-Za-z0-9\s]+)",
                        # Pattern per "Apri l'evento Team1 vs Team2"
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)\s+([\w\s]+)\s+vs\s+([\w\s]+)",
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)\s+(?:tra|contro)\s+([\w\s]+)\s+e\s+([\w\s]+)",
                        # Pattern specifici per "Mostrami la partita tra Napoli vs Pisa"
                        r"(?:mostrami|mostra|parlami|parla)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:tra|fra)\s+([A-Z][\w\s]+)\s+(?:vs|contro)\s+([A-Z][\w\s]+)",
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:tra|fra)\s+([A-Z][\w\s]+)\s+(?:vs|contro)\s+([A-Z][\w\s]+)",
                        # Pattern originali più specifici
                        r"(?:apri|mostra|aprimi)\s+(?:la\s+)?(?:pagina\s+)?(?:evento|partita|match)\s+(?:relativa\s+a|di|per)\s+([\w\s]+)",
                        r"(?:apri|mostra|aprimi)\s+(?:la\s+)?(?:pagina\s+)?(?:evento|partita|match)\s+([\w\s]+)",
                        r"(?:apri|mostra|aprimi)\s+(?:pagina\s+)?(?:evento|partita|match)\s+(?:tra|vs|contro)\s+([\w\s]+)",
                        r"(?:apri|mostra|aprimi)\s+(?:la\s+)?(?:pagina\s+)?(?:evento|partita|match)\s+(?:relativa\s+a|di|per)\s+(?:il\s+)?(?:match|partita)\s+(?:tra|vs|contro)\s+([\w\s]+)",
                        r"(?:apri|mostra|aprimi)\s+(?:la\s+)?(?:pagina\s+)?(?:evento|partita|match)\s+(?:relativa\s+a|di|per)\s+(?:il\s+)?(?:match|partita)\s+(?:tra|vs|contro)\s+([\w\s]+)\s+e\s+([\w\s]+)",
                        r"(?:apri|mostra|aprimi)\s+(?:la\s+)?(?:pagina\s+)?(?:evento|partita|match)\s+(?:relativa\s+a|di|per)\s+([\w\s]+)\s+(?:vs|VS|Vs)\s+([\w\s]+)"
                    ],
                    "entities": ["team_or_match"],
                    "confidence": ConfidenceLevel.HIGH
                }
            ],
            
            IntentType.OPEN_EVENT_SECTION: [
                {
                    "patterns": [
                        r"apri\s+(?:la\s+)?(?:sezione\s+)?(?:classifica|standings)\s+(?:di\s+)?([\w\s]+)",
                        r"mostrami\s+(?:la\s+)?(?:sezione\s+)?(?:classifica|standings)\s+(?:di\s+)?([\w\s]+)",
                        r"vai\s+(?:alla\s+)?(?:sezione\s+)?(?:classifica|standings)\s+(?:di\s+)?([\w\s]+)",
                        r"apri\s+(?:la\s+)?(?:sezione\s+)?(?:quote|odds)\s+(?:di\s+)?([\w\s]+)",
                        r"mostrami\s+(?:la\s+)?(?:sezione\s+)?(?:quote|odds)\s+(?:di\s+)?([\w\s]+)",
                        r"vai\s+(?:alla\s+)?(?:sezione\s+)?(?:quote|odds)\s+(?:di\s+)?([\w\s]+)",
                        r"apri\s+(?:la\s+)?(?:sezione\s+)?(?:formazioni|lineups)\s+(?:di\s+)?([\w\s]+)",
                        r"mostrami\s+(?:la\s+)?(?:sezione\s+)?(?:formazioni|lineups)\s+(?:di\s+)?([\w\s]+)",
                        r"vai\s+(?:alla\s+)?(?:sezione\s+)?(?:formazioni|lineups)\s+(?:di\s+)?([\w\s]+)",
                        r"apri\s+(?:la\s+)?(?:sezione\s+)?(?:statistiche|stats)\s+(?:di\s+)?([\w\s]+)",
                        r"mostrami\s+(?:la\s+)?(?:sezione\s+)?(?:statistiche|stats)\s+(?:di\s+)?([\w\s]+)",
                        r"vai\s+(?:alla\s+)?(?:sezione\s+)?(?:statistiche|stats)\s+(?:di\s+)?([\w\s]+)",
                        r"apri\s+(?:la\s+)?(?:sezione\s+)?(?:scontri\s+diretti|h2h)\s+(?:di\s+)?([\w\s]+)",
                        r"mostrami\s+(?:la\s+)?(?:sezione\s+)?(?:scontri\s+diretti|h2h)\s+(?:di\s+)?([\w\s]+)",
                        r"vai\s+(?:alla\s+)?(?:sezione\s+)?(?:scontri\s+diretti|h2h)\s+(?:di\s+)?([\w\s]+)",
                        r"apri\s+(?:la\s+)?(?:sezione\s+)?(?:overview|panoramica)\s+(?:di\s+)?([\w\s]+)",
                        r"mostrami\s+(?:la\s+)?(?:sezione\s+)?(?:overview|panoramica)\s+(?:di\s+)?([\w\s]+)",
                        r"vai\s+(?:alla\s+)?(?:sezione\s+)?(?:overview|panoramica)\s+(?:di\s+)?([\w\s]+)",
                        # Pattern per sezioni senza specificare l'evento (usa il contesto)
                        r"apri\s+(?:la\s+)?(?:sezione\s+)?(?:classifica|standings)",
                        r"mostrami\s+(?:la\s+)?(?:sezione\s+)?(?:classifica|standings)",
                        r"vai\s+(?:alla\s+)?(?:sezione\s+)?(?:classifica|standings)",
                        r"apri\s+(?:la\s+)?(?:sezione\s+)?(?:quote|odds)",
                        r"mostrami\s+(?:la\s+)?(?:sezione\s+)?(?:quote|odds)",
                        r"vai\s+(?:alla\s+)?(?:sezione\s+)?(?:quote|odds)",
                        r"apri\s+(?:la\s+)?(?:sezione\s+)?(?:formazioni|lineups)",
                        r"mostrami\s+(?:la\s+)?(?:sezione\s+)?(?:formazioni|lineups)",
                        r"vai\s+(?:alla\s+)?(?:sezione\s+)?(?:formazioni|lineups)",
                        r"apri\s+(?:la\s+)?(?:sezione\s+)?(?:statistiche|stats)",
                        r"mostrami\s+(?:la\s+)?(?:sezione\s+)?(?:statistiche|stats)",
                        r"vai\s+(?:alla\s+)?(?:sezione\s+)?(?:statistiche|stats)",
                        r"apri\s+(?:la\s+)?(?:sezione\s+)?(?:scontri\s+diretti|h2h)",
                        r"mostrami\s+(?:la\s+)?(?:sezione\s+)?(?:scontri\s+diretti|h2h)",
                        r"vai\s+(?:alla\s+)?(?:sezione\s+)?(?:scontri\s+diretti|h2h)",
                        r"apri\s+(?:la\s+)?(?:sezione\s+)?(?:overview|panoramica)",
                        r"mostrami\s+(?:la\s+)?(?:sezione\s+)?(?:overview|panoramica)",
                        r"vai\s+(?:alla\s+)?(?:sezione\s+)?(?:overview|panoramica)"
                    ],
                    "entities": ["team_or_match", "section"],
                    "confidence": ConfidenceLevel.HIGH
                }
            ],
            
            IntentType.TEAM_COMPARISON: [
                {
                    "patterns": [
                        r"informazioni\s+(?:tra|su)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                        r"(?:analisi|confronto|statistiche)\s+(?:tra|di)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                        r"(?:forma|stato)\s+(?:di|delle)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                        r"(?:infortuni|giocatori)\s+(?:di|delle)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                        r"(?:come\s+stanno|situazione)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                        r"(.+?)\s+(?:vs|contro)\s+(.+?)\s+(?:informazioni|statistiche|analisi)",
                        r"che\s+(?:informazioni|dati)\s+(?:abbiamo|hai)\s+(?:su|tra)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                        # Pattern più specifici per evitare conflitti con league_standings
                        r"(?:confronta|confronto)\s+(?:le\s+)?(?:prestazioni|performance)\s+(?:di|delle)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                        r"(?:prestazioni|performance)\s+(?:di|delle)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                        r"(?:ultime\s+partite)\s+(?:di|delle)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                        # Pattern più specifici per squadre reali
                        r"(?:confronta|confronto)\s+(?:le\s+)?(?:prestazioni|performance)\s+(?:di|delle)\s+(?:squadre\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:e|vs|contro)\s+(?:squadre\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                        r"(?:informazioni|analisi|statistiche)\s+(?:tra|su)\s+(?:le\s+)?(?:squadre\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:e|vs|contro)\s+(?:le\s+)?(?:squadre\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
                    ],
                    "entities": ["team1", "team2", "league"],
                    "confidence": ConfidenceLevel.HIGH
                }
            ],
            
            IntentType.TEAM_INFO: [
                {
                    "patterns": [
                        # Pattern per "parlami di squadra X" e "mostrami squadra X"
                        r"(?:parlami|parla)\s+(?:di\s+)?(?:squadra|team)\s+([\w\s]+)",
                        r"(?:mostrami|mostra)\s+(?:la\s+)?(?:squadra|team)\s+([\w\s]+)",
                        r"(?:mostrami|mostra)\s+(?:le\s+)?(?:statistiche|stats)\s+(?:della\s+)?(?:squadra|team)\s+([\w\s]+)",
                        r"(?:dammi|dai)\s+(?:le\s+)?(?:statistiche|stats)\s+(?:della\s+)?(?:squadra|team)\s+([\w\s]+)",
                        r"(?:mostrami|mostra)\s+(?:le\s+)?(?:ultime\s+)?(?:statistiche|stats)\s+(?:della\s+)?(?:squadra|team)\s+([\w\s]+)",
                        r"(?:informazioni|info)\s+(?:sulla\s+)?(?:squadra|team)\s+([\w\s]+)",
                        r"(?:analisi|analizza)\s+(?:la\s+)?(?:squadra|team)\s+([\w\s]+)",
                        r"(?:come\s+sta|situazione)\s+(?:la\s+)?(?:squadra|team)\s+([\w\s]+)",
                        r"(?:forma|stato)\s+(?:della\s+)?(?:squadra|team)\s+([\w\s]+)",
                        r"(?:infortuni|giocatori)\s+(?:della\s+)?(?:squadra|team)\s+([\w\s]+)",
                        # Pattern per squadre specifiche (escludi pattern con vs/contro)
                        r"(?:parlami|parla)\s+(?:di\s+)?([A-Z][\w\s]+)(?:\s+(?:squadra|team))?(?!\s+(?:vs|contro))",
                        r"(?:mostrami|mostra)\s+(?:la\s+)?([A-Z][\w\s]+)(?:\s+(?:squadra|team))?(?!\s+(?:vs|contro))",
                        r"(?:statistiche|stats)\s+(?:di|della)\s+([A-Z][\w\s]+)",
                        r"(?:analisi|analizza)\s+([A-Z][\w\s]+)",
                        # Pattern per "squadra X" senza verbo specifico
                        r"(?:squadra|team)\s+([A-Z][\w\s]+)",
                        r"([A-Z][\w\s]+)\s+(?:squadra|team)",
                        # Pattern per "informazioni statistiche attuali"
                        r"(?:informazioni|info)\s+(?:statistiche|stats)\s+(?:attuali|recenti|aggiornate)\s+(?:sul|sulla|del|della)\s+([A-Z][\w\s]+)",
                        r"(?:statistiche|stats)\s+(?:attuali|recenti|aggiornate)\s+(?:sul|sulla|del|della)\s+([A-Z][\w\s]+)",
                        r"(?:dammi|forniscimi)\s+(?:le\s+)?(?:informazioni|info)\s+(?:statistiche|stats)\s+(?:attuali|recenti|aggiornate)\s+(?:sul|sulla|del|della)\s+([A-Z][\w\s]+)",
                        r"(?:mostrami|mostra)\s+(?:le\s+)?(?:informazioni|info)\s+(?:statistiche|stats)\s+(?:attuali|recenti|aggiornate)\s+(?:sul|sulla|del|della)\s+([A-Z][\w\s]+)",
                        r"(?:analisi|analizza)\s+(?:le\s+)?(?:informazioni|info)\s+(?:statistiche|stats)\s+(?:attuali|recenti|aggiornate)\s+(?:sul|sulla|del|della)\s+([A-Z][\w\s]+)"
                    ],
                    "entities": ["team_name"],
                    "confidence": ConfidenceLevel.HIGH
                }
            ],
            
            IntentType.LEAGUE_STANDINGS: [
                {
                    "patterns": [
                        r"(?:mostrami|mostra)\s+(?:la\s+)?(?:classifica|standings)\s+(?:di\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)",
                        r"(?:classifica|standings)\s+(?:di\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)",
                        r"(?:situazione|posizione)\s+(?:della\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)",
                        r"(?:analisi|analizza)\s+(?:la\s+)?(?:situazione|classifica)\s+(?:della\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)",
                        r"(?:forniscimi|dammi)\s+(?:un\s+)?(?:analisi|quadro)\s+(?:dettagliato|completo)\s+(?:della\s+)?(?:situazione|classifica)\s+(?:attuale\s+)?(?:della\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)",
                        r"(?:classifica|standings)\s+(?:attuale\s+)?(?:della\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)",
                        r"(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)\s+(?:classifica|standings)",
                        r"(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)\s+(?:situazione|posizione)",
                        r"(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)\s+(?:analisi|quadro)",
                        r"(?:squadre|team)\s+(?:più\s+)?(?:performanti|in\s+forma)\s+(?:della\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)",
                        r"(?:prestazioni|performance)\s+(?:delle\s+)?(?:squadre|team)\s+(?:principali\s+)?(?:della\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)",
                        # Pattern più specifici per evitare conflitti con team_comparison - ALTA PRIORITÀ
                        r"(?:situazione\s+attuale\s+della\s+)(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)",
                        r"(?:analisi\s+dettagliata\s+della\s+situazione\s+attuale\s+della\s+)(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)",
                        r"(?:forniscimi\s+un\s+analisi\s+dettagliata\s+della\s+situazione\s+attuale\s+della\s+)(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)"
                    ],
                    "entities": ["league_name"],
                    "confidence": ConfidenceLevel.HIGH
                }
            ],
            
            IntentType.HELP: [
                {
                    "patterns": [
                        r"aiuto|help|soccorso",
                        r"come\s+(?:funziona|si\s+usa)",
                        r"cosa\s+(?:puoi|sai)\s+(?:fare|dire)",
                        r"istruzioni|guida",
                        r"manuale|tutorial"
                    ],
                    "entities": [],
                    "confidence": ConfidenceLevel.HIGH
                }
            ],
            
            IntentType.GENERIC_MATCH_REQUEST: [
                {
                    "patterns": [
                        r"(?:partite|match|incontri)\s+(?:di\s+)?(domani|oggi|stasera)",
                        r"(?:che\s+)?(?:partite|match|incontri)\s+(?:ci\s+sono\s+)?(?:domani|oggi|stasera)",
                        r"(?:informazioni|info)\s+(?:su|sulle)\s+(?:partite|match|incontri)\s+(?:di\s+)?(domani|oggi|stasera)",
                        r"(?:partite|match|incontri)\s+(?:in\s+programma|previste?)\s+(?:per\s+)?(domani|oggi|stasera)",
                        r"(?:quali|che)\s+(?:partite|match|incontri)\s+(?:ci\s+sono\s+)?(?:domani|oggi|stasera)",
                        r"(?:partite|match|incontri)\s+(?:del|di)\s+(weekend|fine\s+settimana)",
                        r"(?:partite|match|incontri)\s+(?:della\s+)?settimana",
                        r"(?:partite|match|incontri)\s+(?:di\s+)?(?:questa\s+)?settimana",
                        r"(?:partite|match|incontri)\s+(?:nel\s+)?weekend",
                        r"(?:partite|match|incontri)\s+(?:del\s+)?fine\s+settimana",
                        r"(?:quali|che)\s+(?:partite|match|incontri)\s+(?:ci\s+sono\s+)?(?:di\s+)?(?:questa\s+)?settimana",
                        r"(?:quali|che)\s+(?:partite|match|incontri)\s+(?:ci\s+sono\s+)?(?:nel\s+)?weekend",
                        r"(?:partite|match|incontri)\s+(?:più\s+)?importanti\s+(?:di\s+)?(?:questa\s+)?settimana",
                        # Pattern specifico per "partite importanti" con tempo - PRIORITÀ ALTA
                        r"(?:che\s+)?(?:partite|match|incontri)\s+(?:più\s+|più\s+)?importanti\s+(?:ci\s+sono\s+)?(?:domani|oggi|stasera)",
                        r"(?:partite|match|incontri)\s+(?:più\s+|più\s+)?importanti\s+(?:di\s+)?(?:domani|oggi|stasera)",
                        r"(?:partite|match|incontri)\s+(?:di\s+)?(?:serie\s+a|premier\s+league|champions\s+league|europa\s+league)",
                        r"(?:partite|match|incontri)\s+(?:del|di)\s+(\w+)\s*(?:campionato|league)?",
                        r"(?:campionati|tornei)\s+(?:di\s+)?(domani|oggi|stasera)",
                        r"(?:che\s+)?(?:campionati|tornei)\s+(?:ci\s+sono\s+)?(?:domani|oggi|stasera)",
                        # Pattern per "tra poco", "imminenti", "prossime"
                        r"(?:che\s+)?(?:partite|match|incontri)\s+(?:ci\s+stanno\s+)?(?:tra\s+poco|imminenti|prossime)",
                        r"(?:partite|match|incontri)\s+(?:tra\s+poco|imminenti|prossime)",
                        r"(?:quali|che)\s+(?:partite|match|incontri)\s+(?:ci\s+stanno\s+)?(?:tra\s+poco|imminenti|prossime)",
                        r"(?:partite|match|incontri)\s+(?:che\s+iniziano\s+)?(?:tra\s+poco|presto|a\s+breve)",
                        r"(?:prossime|imminenti)\s+(?:partite|match|incontri)",
                        r"(?:partite|match|incontri)\s+(?:in\s+programma|previste?)\s+(?:tra\s+poco|presto|a\s+breve)",
                        r"(?:che\s+partite|quali\s+partite)\s+(?:ci\s+stanno|ci\s+sono)\s+(?:tra\s+poco|imminenti|prossime)",
                        r"(?:partite|match|incontri)\s+(?:del\s+giorno|di\s+oggi)\s+(?:che\s+iniziano\s+)?(?:tra\s+poco|presto)",
                        r"(?:partite|match|incontri)\s+(?:che\s+iniziano\s+)?(?:tra\s+poco|presto|a\s+breve|imminenti)"
                    ],
                    "entities": ["time_reference", "competition", "date"],
                    "confidence": ConfidenceLevel.HIGH
                }
            ],
            
            IntentType.GREETING: [
                {
                    "patterns": [
                        r"ciao|salve|buongiorno|buonasera|buonanotte",
                        r"hey|hi|hello",
                        r"come\s+stai|come\s+va(?!\s+(?:la\s+)?(?:juventus|inter|milan|napoli|roma|lazio|atalanta|barcelona|barcellona|real madrid|manchester|chelsea|arsenal|liverpool|tottenham|bayern|psg|dortmund))",
                        r"piacere\s+(?:di\s+)?conoscerti"
                    ],
                    "entities": [],
                    "confidence": ConfidenceLevel.HIGH
                }
            ]
        }
    
    def _initialize_error_patterns(self) -> List[Dict]:
        """Inizializza i pattern per il rilevamento di errori"""
        return [
            {
                "pattern": r"^\s*$",
                "error_type": "empty_input",
                "message": "Il messaggio è vuoto. Puoi ripetere la tua richiesta?"
            },
            {
                "pattern": r"^[^\w\s]+$",
                "error_type": "only_symbols",
                "message": "Ho ricevuto solo simboli. Puoi scrivere la tua richiesta in parole?"
            },
            {
                "pattern": r"^.{1,2}$",
                "error_type": "too_short",
                "message": "Il messaggio è troppo breve. Puoi essere più specifico?"
            },
            {
                "pattern": r"^.{500,}$",
                "error_type": "too_long",
                "message": "Il messaggio è troppo lungo. Puoi essere più conciso?"
            }
        ]
    
    def _detect_complex_prediction_patterns(self, message: str) -> bool:
        """Phase 1: Enhanced complex pattern recognition for elaborate prediction requests"""
        msg_lower = message.lower()
        
        # Complex patterns that might be misinterpreted as team names
        complex_patterns = [
            # Elaborate request patterns
            r"(?:vorrei|voglio|mi\s+piacerebbe|potresti|puoi)\s+(?:vedere|avere|ottenere|sapere|conoscere)\s+(?:le\s+)?(?:predizioni?|pronostic[io]|previsioni?)",
            r"(?:mi\s+(?:dai|fornisci|mostri)|mostrami|fammi\s+vedere)\s+(?:le\s+)?(?:predizioni?|pronostic[io]|previsioni?)",
            r"(?:che\s+cosa|cosa|quali)\s+(?:sono|ci\s+sono)\s+(?:le\s+)?(?:predizioni?|pronostic[io]|previsioni?)",
            r"(?:dimmi|raccontami|spiegami)\s+(?:le\s+)?(?:predizioni?|pronostic[io]|previsioni?)",
            r"(?:mi\s+interessano|sono\s+interessato\s+alle?|vorrei\s+sapere\s+delle?)\s+(?:predizioni?|pronostic[io]|previsioni?)",
            r"(?:hai|ci\s+sono|esistono)\s+(?:delle?\s+)?(?:predizioni?|pronostic[io]|previsioni?)",
            # Context-aware patterns
            r"(?:predizioni?|pronostic[io]|previsioni?)\s+(?:sportive?|calcistiche?|di\s+calcio|football)",
            r"(?:analisi|studio|valutazione)\s+(?:delle?\s+)?partite?\s+(?:di\s+)?(?:oggi|domani|questa\s+settimana)",
            r"(?:consigli|suggerimenti)\s+(?:per\s+)?(?:scommesse?|bet|betting)",
            # Profit-related patterns
            r"(?:partite?|scommesse?|bet)\s+(?:profittevoli|redditizie|con\s+guadagno)",
            r"(?:quali|che)\s+(?:sono\s+)?(?:le\s+)?(?:partite?|scommesse?)\s+(?:più\s+)?(?:profittevoli|redditizie)",
            r"(?:migliori|miglior)\s+(?:partite?|scommesse?)\s+(?:per\s+)?(?:profitto|guadagno)",
            r"(?:scommesse?|bet)\s+(?:con\s+)?(?:alto|miglior)\s+(?:profitto|guadagno)",
            r"(?:partite?|match)\s+(?:da\s+)?(?:scommettere|giocare)\s+(?:per\s+)?(?:profitto|guadagno)",
            # Temporal patterns with predictions
            r"(?:predizioni?|pronostic[io]|previsioni?)\s+(?:per\s+)?(?:questa\s+settimana|settimana|week)",
            r"(?:predizioni?|pronostic[io]|previsioni?)\s+(?:bundesliga|liga|premier|serie\s+a|champions)",
        ]
        
        for pattern in complex_patterns:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                return True
        
        return False

    def _initialize_ambiguity_resolvers(self) -> Dict[str, List[str]]:
        """Inizializza i risolutori di ambiguità"""
        return {
            "bet_type": [
                "Che tipo di scommessa ti interessa? (singola, multipla, sistema)",
                "Vuoi analizzare una scommessa singola, multipla o un sistema?",
                "Specifica il tipo di scommessa: singola, multipla o sistema?"
            ],
            "team_or_match": [
                "Per quale squadra o partita vuoi informazioni?",
                "Specifica la squadra o la partita che ti interessa.",
                "Di quale squadra o partita stai parlando?"
            ],
            "destination": [
                "In quale sezione vuoi navigare?",
                "Specifica la pagina di destinazione.",
                "Dove vuoi andare?"
            ]
        }
    
    def normalize_text(self, text: str) -> str:
        """Normalizza il testo per il confronto"""
        if not text:
            return ""
        
        # Converti in minuscolo e rimuovi accenti
        normalized = text.lower()
        normalized = normalized.replace('à', 'a').replace('è', 'e').replace('é', 'e')
        normalized = normalized.replace('ì', 'i').replace('ò', 'o').replace('ù', 'u')
        
        # Rimuovi caratteri speciali e normalizza spazi
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _is_vague_request(self, message: str) -> bool:
        """Rileva se una richiesta è troppo vaga e richiede specificità (REGOLA 7)"""
        msg_lower = message.lower()
        
        # Pattern per richieste troppo vaghe
        vague_patterns = [
            # Richieste generiche di scommesse senza specificità
            r"^(?:best|migliori?|buone?)\s+(?:scommesse?|bet)\s*$",
            r"^(?:scommesse?|bet)\s+(?:oggi|today|stasera|ora)\s*$", 
            r"^(?:dammi|mostra|fammi vedere)\s+(?:scommesse?|bet)\s*$",
            r"^(?:che|quali)\s+(?:scommesse?|bet)\s*\??\s*$",
            
            # Richieste di statistiche troppo generiche
            r"(?:dammi|mostra|fammi vedere)\s+(?:stats?|statistiche?)\s+(?:match|partite?)\s+\w+\s+(?:anno scorso|l'anno scorso)\s*$",
            r"(?:statistiche?|stats?)\s+(?:match|partite?)\s+\w+\s+(?:anno scorso|l'anno scorso)\s*$",
            r"(?:statistiche?|stats?)\s+(?:di\s+)?\w+\s+(?:anno scorso|l'anno scorso)\s*$",
            
            # Richieste generiche di predizioni senza dettagli
            r"^(?:predizioni?|predictions?)\s*\??\s*$",
            r"^(?:pronostic[io]|previsioni?)\s*\??\s*$",
            r"^(?:chi vince|vincerà)\s*\??\s*$",
            
            # CICLO 3: Richieste vaghe su squadre senza specificità  
            r"(?:come va|come sta|come si trova|che ne pensi di|parlami di|dimmi di)\s+(?:la\s+)?(?:juventus|inter|milan|napoli|roma|lazio|atalanta|barcelona|barcellona|real madrid|manchester|chelsea|arsenal|liverpool|tottenham|bayern|psg|dortmund)\s+(?:ultimamente|recentemente|in questo periodo|quest'anno|di recente)\s*\??\s*$",
            r"^(?:la\s+)?(?:juventus|inter|milan|napoli|roma|lazio|atalanta|barcelona|barcellona|real madrid|manchester|chelsea|arsenal|liverpool|tottenham|bayern|psg|dortmund)\s+(?:come va|come sta|ultimamente|recentemente)\s*\??\s*$",
            r"^(?:statistiche?|info|informazioni)\s+(?:sulla\s+|della\s+|di\s+)?(?:juventus|inter|milan|napoli|roma|lazio|atalanta|barcelona|barcellona|real madrid|manchester|chelsea|arsenal|liverpool|tottenham|bayern|psg|dortmund)\s*\??\s*$",
        ]
        
        # Test per pattern vaghi
        for pattern in vague_patterns:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                logger.info(f"[VAGUE DETECTION] Matched pattern: {pattern} for message: {message}")
                return True
        
        # Test speciale per richieste con "anno scorso" senza specificità
        if any(phrase in msg_lower for phrase in ["anno scorso", "l'anno scorso", "last year"]):
            if not re.search(r"\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}", msg_lower):  # Nessuna data specifica
                logger.info(f"[VAGUE DETECTION] Year reference without specific date: {message}")
                return True
        
        return False
    
    def detect_errors(self, text: str) -> Optional[IntentMatch]:
        """Rileva errori nel testo di input"""
        normalized = self.normalize_text(text)
        
        for error_pattern in self.error_patterns:
            if re.match(error_pattern["pattern"], text):
                return IntentMatch(
                    intent_type=IntentType.ERROR,
                    confidence=1.0,
                    entities={"error_type": error_pattern["error_type"]},
                    original_text=text,
                    normalized_text=normalized,
                    patterns_matched=[error_pattern["pattern"]],
                    error_type=error_pattern["error_type"]
                )
        
        return None
    
    def extract_section_from_text(self, text: str) -> str:
        """Estrae la sezione richiesta dal testo"""
        text_lower = text.lower()
        
        # Mappa delle sezioni disponibili
        section_mapping = {
            'classifica': 'standings',
            'standings': 'standings',
            'quote': 'odds',
            'odds': 'odds',
            'formazioni': 'lineups',
            'lineups': 'lineups',
            # Statistiche squadre (stagionali)
            'statistiche': 'teamstats',
            'stats': 'teamstats',
            'statistiche squadre': 'teamstats',
            'statistiche stagionali': 'teamstats',

            'scontri diretti': 'h2h',
            'scontri': 'h2h',
            'head to head': 'h2h',
            'h2h': 'h2h',
            'overview': 'overview',
            'panoramica': 'overview'
        }
        
        # Cerca la sezione nel testo
        for section_name, section_key in section_mapping.items():
            if section_name in text_lower:
                return section_key
        
        return 'overview'  # Default

    def extract_entities(self, text: str, patterns: List[str], entity_names: List[str]) -> Dict[str, Any]:
        """Estrae entità dal testo usando i pattern"""
        entities = {}
        normalized = self.normalize_text(text)
        print(f"[DEBUG ENTITIES] Testo normalizzato: '{normalized}'")
        print(f"[DEBUG ENTITIES] Pattern da testare: {patterns}")
        
        # Controllo speciale per LEAGUE_STANDINGS - PRIORITÀ ALTA
        if "league_name" in entity_names:
            # Pattern specifici per estrarre il nome del campionato
            league_patterns = [
                r"(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1|champions\s+league|europa\s+league|conference\s+league|coppa\s+italia|copa\s+del\s+rey|fa\s+cup)",
                r"(?:classifica|standings)\s+(?:di\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1|champions\s+league|europa\s+league|conference\s+league|coppa\s+italia)",
                r"(?:situazione|posizione)\s+(?:della\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1|champions\s+league|europa\s+league|conference\s+league)",
                r"(?:analisi|analizza)\s+(?:la\s+)?(?:situazione|classifica)\s+(?:della\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1|champions\s+league|europa\s+league)",
                r"(?:forniscimi|dammi)\s+(?:un\s+)?(?:analisi|quadro)\s+(?:dettagliato|completo)\s+(?:della\s+)?(?:situazione|classifica)\s+(?:attuale\s+)?(?:della\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1|champions\s+league|europa\s+league)",
                r"(?:squadre|team)\s+(?:più\s+)?(?:performanti|in\s+forma)\s+(?:della\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1|champions\s+league|europa\s+league)",
                r"(?:prestazioni|performance)\s+(?:delle\s+)?(?:squadre|team)\s+(?:principali\s+)?(?:della\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1|champions\s+league|europa\s+league)",
                # Pattern più specifici per evitare conflitti con team_comparison
                r"(?:situazione\s+attuale\s+della\s+)(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1|champions\s+league|europa\s+league)",
                r"(?:analisi\s+dettagliata\s+della\s+situazione\s+attuale\s+della\s+)(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1|champions\s+league|europa\s+league)",
                r"(?:forniscimi\s+un\s+analisi\s+dettagliata\s+della\s+situazione\s+attuale\s+della\s+)(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)"
            ]
            
            for pattern in league_patterns:
                match = re.search(pattern, normalized, re.IGNORECASE)
                if match:
                    league_name = match.group(0).strip()
                    # Normalizza il nome del campionato
                    league_name = re.sub(r'^(?:la\s+|il\s+|del\s+|della\s+|di\s+)', '', league_name, flags=re.IGNORECASE).strip()
                    entities["league_name"] = league_name
                    print(f"[DEBUG ENTITIES] Estratto league_name: '{league_name}' da frase: '{normalized}'")
                    break
            
            if "league_name" not in entities:
                # Fallback: cerca qualsiasi menzione di campionati
                fallback_patterns = [
                    r"(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)",
                    r"(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)\s+(?:classifica|standings|situazione|posizione|analisi|quadro)",
                    r"(?:classifica|standings|situazione|posizione|analisi|quadro)\s+(?:di\s+)?(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)"
                ]
                
                for pattern in fallback_patterns:
                    match = re.search(pattern, normalized, re.IGNORECASE)
                    if match:
                        league_name = match.group(0).strip()
                        # Normalizza il nome del campionato
                        league_name = re.sub(r'^(?:la\s+|il\s+|del\s+|della\s+|di\s+)', '', league_name, flags=re.IGNORECASE).strip()
                        entities["league_name"] = league_name
                        print(f"[DEBUG ENTITIES] Estratto league_name (fallback): '{league_name}' da frase: '{normalized}'")
                        break
            
            return entities
        
        # Controllo speciale per OPEN_EVENT con due squadre separate
        if "team_or_match" in entity_names and any("vs" in pattern or "contro" in pattern or "e " in pattern for pattern in patterns):
            # Pattern per estrarre due squadre separate per eventi
            team_patterns = [
                r"(?:mostrami|mostra|parlami|parla)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:del|della|di)\s+([A-Z][\w\s]+)\s+(?:vs|contro)\s+([A-Z][\w\s]+)",
                r"(?:mostrami|mostra|parlami|parla)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:tra|fra)\s+([A-Z][\w\s]+)\s+(?:e|ed)\s+([A-Z][\w\s]+)",
                r"(?:apri|mostra|aprimi|mostrami)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:del|della|di)\s+([A-Z][\w\s]+)\s+(?:vs|contro)\s+([A-Z][\w\s]+)",
                r"(?:apri|mostra|aprimi|mostrami)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:tra|fra)\s+([A-Z][\w\s]+)\s+(?:e|ed)\s+([A-Z][\w\s]+)",
            ]
            
            for pattern in team_patterns:
                match = re.search(pattern, normalized, re.IGNORECASE)
                if match and len(match.groups()) >= 2:
                    team1 = match.group(1).strip()
                    team2 = match.group(2).strip()
                    
                    # Pulizia dei nomi delle squadre
                    team1 = re.sub(r'^(?:la|il|del|della|di)\s+', '', team1, flags=re.IGNORECASE).strip()
                    team2 = re.sub(r'^(?:la|il|del|della|di)\s+', '', team2, flags=re.IGNORECASE).strip()
                    
                    # Crea la stringa team_or_match nel formato "Squadra1 vs Squadra2"
                    team_or_match = f"{team1} vs {team2}"
                    entities["team_or_match"] = team_or_match
                    print(f"[DEBUG ENTITIES] Estratto team_or_match: '{team_or_match}' da frase: '{normalized}'")
                    return entities
        
        # Controllo speciale per TEAM_COMPARISON - PRIORITÀ BASSA
        if "team1" in entity_names and "team2" in entity_names:
            # Pattern specifici per estrarre due squadre
            team_patterns = [
                r"informazioni\s+(?:tra|su)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                r"(?:analisi|confronto|statistiche)\s+(?:tra|di)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                r"(?:forma|stato)\s+(?:di|delle)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                r"(?:infortuni|giocatori)\s+(?:di|delle)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                r"(?:come\s+stanno|situazione)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)",
                r"(.+?)\s+(?:vs|contro)\s+(.+?)\s+(?:informazioni|statistiche|analisi)",
                r"che\s+(?:informazioni|dati)\s+(?:abbiamo|hai)\s+(?:su|tra)\s+(.+?)\s+(?:e|vs|contro)\s+(.+)"
            ]
            
            for pattern in team_patterns:
                match = re.search(pattern, normalized, re.IGNORECASE)
                if match and len(match.groups()) >= 2:
                    team1 = match.group(1).strip()
                    team2 = match.group(2).strip()
                    
                    # Pulizia dei nomi delle squadre
                    team1 = re.sub(r'^(?:la|il|del|della|di)\s+', '', team1, flags=re.IGNORECASE).strip()
                    team2 = re.sub(r'^(?:la|il|del|della|di)\s+', '', team2, flags=re.IGNORECASE).strip()
                    
                    # Rimuovi informazioni sulla lega dai nomi delle squadre
                    team1 = re.sub(r'\s+(?:in|della|di)\s+(?:serie\s+a|champions\s+league|europa\s+league|coppa\s+italia).*$', '', team1, flags=re.IGNORECASE).strip()
                    team2 = re.sub(r'\s+(?:in|della|di)\s+(?:serie\s+a|champions\s+league|europa\s+league|coppa\s+italia).*$', '', team2, flags=re.IGNORECASE).strip()
                    
                    # Verifica che non siano richieste di campionati
                    if not any(league in team1.lower() or league in team2.lower() for league in ['serie a', 'premier league', 'la liga', 'bundesliga', 'ligue 1', 'champions league', 'europa league']):
                        # Verifica aggiuntiva: escludi pattern che contengono "situazione attuale della" + campionato
                        if not re.search(r'situazione\s+attuale\s+della\s+(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)', normalized, re.IGNORECASE):
                            # Verifica aggiuntiva: escludi pattern che contengono "analisi dettagliata della situazione attuale della" + campionato
                            if not re.search(r'analisi\s+dettagliata\s+della\s+situazione\s+attuale\s+della\s+(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)', normalized, re.IGNORECASE):
                                # Verifica aggiuntiva: escludi pattern che contengono "forniscimi un'analisi" + campionato
                                if not re.search(r'forniscimi\s+un\s+analisi\s+dettagliata\s+della\s+situazione\s+attuale\s+della\s+(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)', normalized, re.IGNORECASE):
                                    # Verifica aggiuntiva: escludi pattern che contengono "situazione attuale del" + campionato
                                    if not re.search(r'situazione\s+attuale\s+del\s+(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)', normalized, re.IGNORECASE):
                                        # Verifica aggiuntiva: escludi pattern che contengono "analisi dettagliata della situazione attuale del" + campionato
                                        if not re.search(r'analisi\s+dettagliata\s+della\s+situazione\s+attuale\s+del\s+(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)', normalized, re.IGNORECASE):
                                            # Verifica aggiuntiva: escludi pattern che contengono "forniscimi un'analisi" + campionato
                                            if not re.search(r'forniscimi\s+un\s+analisi\s+dettagliata\s+della\s+situazione\s+attuale\s+del\s+(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)', normalized, re.IGNORECASE):
                                                # Verifica aggiuntiva: escludi pattern che contengono "situazione attuale del" + squadra + "includendo"
                                                if not re.search(r'situazione\s+attuale\s+del\s+[a-z]+\s+includendo', normalized, re.IGNORECASE):
                                                    # Verifica aggiuntiva: escludi pattern che contengono "situazione attuale della" + squadra + "includendo"
                                                    if not re.search(r'situazione\s+attuale\s+della\s+[a-z]+\s+includendo', normalized, re.IGNORECASE):
                                                        # Verifica aggiuntiva: escludi pattern che contengono "situazione attuale del" + squadra + "includendo"
                                                        if not re.search(r'situazione\s+attuale\s+del\s+[a-z]+\s+includendo', normalized, re.IGNORECASE):
                                                            # Verifica aggiuntiva: escludi pattern che contengono "situazione attuale della" + squadra + "includendo"
                                                            if not re.search(r'situazione\s+attuale\s+della\s+[a-z]+\s+includendo', normalized, re.IGNORECASE):
                                                                if team1 and team2 and len(team1) > 1 and len(team2) > 1:
                                                                    entities["team1"] = team1
                                                                    entities["team2"] = team2
                                                                    print(f"[DEBUG ENTITIES] Estratte squadre - Team1: '{team1}', Team2: '{team2}'")
                                                                    # Estrai anche la lega se presente
                                                                    league_match = re.search(r'(?:in|della|di)\s+(serie\s+a|champions\s+league|europa\s+league|coppa\s+italia)', normalized, re.IGNORECASE)
                                                                    if league_match:
                                                                        entities["league"] = league_match.group(1).strip()
                                                                    return entities  # Ritorna subito per evitare sovrascritture
        
        # Controllo speciale per TEAM_INFO
        if "team_name" in entity_names:
            # Pattern specifici per estrarre nome squadra singola
            team_info_patterns = [
                r"(?:parlami|parla)\s+(?:di\s+)?(?:squadra|team)\s+([\w\s]+)",
                r"(?:mostrami|mostra)\s+(?:la\s+)?(?:squadra|team)\s+([\w\s]+)",
                r"(?:mostrami|mostra)\s+(?:le\s+)?(?:statistiche|stats)\s+(?:della\s+)?(?:squadra|team)\s+([\w\s]+)",
                r"(?:dammi|dai)\s+(?:le\s+)?(?:statistiche|stats)\s+(?:della\s+)?(?:squadra|team)\s+([\w\s]+)",
                r"(?:mostrami|mostra)\s+(?:le\s+)?(?:ultime\s+)?(?:statistiche|stats)\s+(?:della\s+)?(?:squadra|team)\s+([\w\s]+)",
                r"(?:informazioni|info)\s+(?:sulla\s+)?(?:squadra|team)\s+([\w\s]+)",
                r"(?:analisi|analizza)\s+(?:la\s+)?(?:squadra|team)\s+([\w\s]+)",
                r"(?:come\s+sta|situazione)\s+(?:la\s+)?(?:squadra|team)\s+([\w\s]+)",
                r"(?:forma|stato)\s+(?:della\s+)?(?:squadra|team)\s+([\w\s]+)",
                r"(?:infortuni|giocatori)\s+(?:della\s+)?(?:squadra|team)\s+([\w\s]+)",
                r"(?:parlami|parla)\s+(?:di\s+)?([A-Z][\w\s]+)(?:\s+(?:squadra|team))?",
                r"(?:mostrami|mostra)\s+(?:la\s+)?([A-Z][\w\s]+)(?:\s+(?:squadra|team))?",
                r"(?:statistiche|stats)\s+(?:di|della)\s+([A-Z][\w\s]+)",
                r"(?:analisi|analizza)\s+([A-Z][\w\s]+)",
                r"(?:squadra|team)\s+([A-Z][\w\s]+)",
                r"([A-Z][\w\s]+)\s+(?:squadra|team)"
            ]
            
            for pattern in team_info_patterns:
                match = re.search(pattern, normalized, re.IGNORECASE)
                if match and len(match.groups()) >= 1:
                    team_name = match.group(1).strip()
                    
                    # Pulizia del nome della squadra
                    team_name = re.sub(r'^(?:la|il|del|della|di)\s+', '', team_name, flags=re.IGNORECASE).strip()
                    team_name = re.sub(r'\s+(?:squadra|team)$', '', team_name, flags=re.IGNORECASE).strip()
                    
                    # Rimuovi informazioni sulla lega dal nome della squadra
                    team_name = re.sub(r'\s+(?:in|della|di)\s+(?:serie\s+a|champions\s+league|europa\s+league|coppa\s+italia).*$', '', team_name, flags=re.IGNORECASE).strip()
                    
                    # Verifica che non sia una richiesta di campionato
                    if not any(league in team_name.lower() for league in ['serie a', 'premier league', 'la liga', 'bundesliga', 'ligue 1', 'champions league', 'europa league']):
                        # Verifica aggiuntiva: escludi pattern che contengono "situazione attuale del" + campionato
                        if not re.search(r'situazione\s+attuale\s+del\s+(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)', normalized, re.IGNORECASE):
                            # Verifica aggiuntiva: escludi pattern che contengono "analisi dettagliata della situazione attuale del" + campionato
                            if not re.search(r'analisi\s+dettagliata\s+della\s+situazione\s+attuale\s+del\s+(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)', normalized, re.IGNORECASE):
                                # Verifica aggiuntiva: escludi pattern che contengono "forniscimi un'analisi" + campionato
                                if not re.search(r'forniscimi\s+un\s+analisi\s+dettagliata\s+della\s+situazione\s+attuale\s+del\s+(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)', normalized, re.IGNORECASE):
                                    # Verifica aggiuntiva: escludi pattern che contengono "situazione attuale della" + campionato
                                    if not re.search(r'situazione\s+attuale\s+della\s+(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)', normalized, re.IGNORECASE):
                                        # Verifica aggiuntiva: escludi pattern che contengono "analisi dettagliata della situazione attuale della" + campionato
                                        if not re.search(r'analisi\s+dettagliata\s+della\s+situazione\s+attuale\s+della\s+(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)', normalized, re.IGNORECASE):
                                            # Verifica aggiuntiva: escludi pattern che contengono "forniscimi un'analisi" + campionato
                                            if not re.search(r'forniscimi\s+un\s+analisi\s+dettagliata\s+della\s+situazione\s+attuale\s+della\s+(?:serie\s+a|premier\s+league|la\s+liga|bundesliga|ligue\s+1)', normalized, re.IGNORECASE):
                                                # Verifica aggiuntiva: escludi pattern che contengono "situazione attuale del" + squadra + "includendo"
                                                if not re.search(r'situazione\s+attuale\s+del\s+[a-z]+\s+includendo', normalized, re.IGNORECASE):
                                                    # Verifica aggiuntiva: escludi pattern che contengono "situazione attuale della" + squadra + "includendo"
                                                    if not re.search(r'situazione\s+attuale\s+della\s+[a-z]+\s+includendo', normalized, re.IGNORECASE):
                                                        # Verifica aggiuntiva: escludi pattern che contengono "situazione attuale del" + squadra + "includendo"
                                                        if not re.search(r'situazione\s+attuale\s+del\s+[a-z]+\s+includendo', normalized, re.IGNORECASE):
                                                            # Verifica aggiuntiva: escludi pattern che contengono "situazione attuale della" + squadra + "includendo"
                                                            if not re.search(r'situazione\s+attuale\s+della\s+[a-z]+\s+includendo', normalized, re.IGNORECASE):
                                                                if team_name and len(team_name) > 1:
                                                                    entities["team_name"] = team_name
                                                                    print(f"[DEBUG ENTITIES] Estratto nome squadra: '{team_name}'")
                                                                    return entities  # Ritorna subito per evitare sovrascritture
        
        # Logica originale per altri tipi di entità
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                print(f"[DEBUG ENTITIES] Pattern matched: '{pattern}'")
                print(f"[DEBUG ENTITIES] Match trovati: {matches}")
                for i, entity_name in enumerate(entity_names):
                    if i < len(matches):
                        if isinstance(matches[i], tuple):
                            print(f"[DEBUG ENTITIES] Match è una tupla: {matches[i]}")
                            # Se abbiamo due gruppi di cattura (team1 vs team2)
                            if len(matches[i]) == 2:
                                team1 = matches[i][0].strip()
                                team2 = matches[i][1].strip()
                                print(f"[DEBUG ENTITIES] Team1 grezzo: '{team1}', Team2 grezzo: '{team2}'")
                                
                                # Pulizia dei nomi delle squadre
                                team1 = re.sub(r'^(?:Apri|Mostrami|la|pagina|evento|per|del|match|di)\s+', '', team1, flags=re.IGNORECASE).strip()
                                team2 = re.sub(r'\s+(?:vs|VS|Vs|\-|–).*$', '', team2, flags=re.IGNORECASE).strip()
                                
                                # Rimuovi parole comuni che potrebbero essere rimaste
                                common_words = ["l'evento", "evento", "per", "del", "di", "la", "il", "un", "una"]
                                for word in common_words:
                                    team1 = team1.replace(word, "").strip()
                                    team2 = team2.replace(word, "").strip()
                                
                                print(f"[DEBUG ENTITIES] Team1 pulito: '{team1}', Team2 pulito: '{team2}'")
                                
                                if team1 and team2 and len(team1) > 2 and len(team2) > 2:
                                    entities[entity_name] = f"{team1} vs {team2}"
                                    print(f"[DEBUG ENTITIES] Estratto team_or_match: '{entities[entity_name]}' da '{text}'")
                                    break
                            else:
                                # Fallback per tuple con un solo elemento
                                entities[entity_name] = matches[i][0].strip()
                                print(f"[DEBUG ENTITIES] Estratta entità da tupla singola: '{entities[entity_name]}'")
                        else:
                            value = matches[i].strip()
                            print(f"[DEBUG ENTITIES] Match singolo: '{value}'")
                            # Mappa le destinazioni specifiche
                            if entity_name == "destination":
                                value = self.map_destination(value)
                                print(f"[DEBUG ENTITIES] Destinazione mappata: '{value}'")
                            entities[entity_name] = value
                            print(f"[DEBUG ENTITIES] Entità assegnata: {entity_name} = '{value}'")
                break
        
        print(f"[DEBUG ENTITIES] Entità finali estratte: {entities}")
        return entities
    
    def map_destination(self, destination: str) -> str:
        """Mappa le destinazioni specifiche ai valori corretti"""
        destination_lower = destination.lower()
        
        # Mappa per destinazioni specifiche
        destination_mapping = {
            "partite": "matches",
            "simulatore": "simulator",
            "notizie": "news",
            "funzionalita": "features",
            "homepage": "homepage",
            "matches": "matches",
            "news": "news",
            "simulator": "simulator",
            "features": "features",
            "betbuilder": "betbuilder",
            "schedina": "betbuilder"
        }
        
        return destination_mapping.get(destination_lower, destination)
    
    def detect_intent(self, text: str) -> IntentMatch:
        """Rileva l'intent principale dal testo"""
        if not text or not text.strip():
            return IntentMatch(
                intent_type=IntentType.ERROR,
                confidence=0.0,
                entities={},
                original_text=text,
                normalized_text="",
                patterns_matched=[],
                error_type="empty_input"
            )
        
        # Prima controlla se ci sono errori
        error_match = self.detect_errors(text)
        if error_match:
            return error_match
        
        normalized = self.normalize_text(text)
        best_match = None
        highest_confidence = 0.0
        
        # Controllo speciale per OPEN_EVENT quando c'è "vs" o "contro" - PRIORITÀ ALTA
        if any(word in normalized for word in [' vs ', ' contro ', ' e ', ' ed ']):
            # Pattern specifici per OPEN_EVENT con due squadre
            open_event_patterns = [
                r"(?:mostrami|mostra|parlami|parla)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:del|della|di)\s+([A-Z][\w\s]+)\s+(?:vs|contro)\s+([A-Z][\w\s]+)",
                r"(?:mostrami|mostra|parlami|parla)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:tra|fra)\s+([A-Z][\w\s]+)\s+(?:e|ed)\s+([A-Z][\w\s]+)",
                r"(?:apri|mostra|aprimi|mostrami)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:del|della|di)\s+([A-Z][\w\s]+)\s+(?:vs|contro)\s+([A-Z][\w\s]+)",
                r"(?:apri|mostra|aprimi|mostrami)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:tra|fra)\s+([A-Z][\w\s]+)\s+(?:e|ed)\s+([A-Z][\w\s]+)",
                # Pattern specifici per "Mostrami la partita tra Napoli vs Pisa"
                r"(?:mostrami|mostra|parlami|parla)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:tra|fra)\s+([A-Z][\w\s]+)\s+(?:vs|contro)\s+([A-Z][\w\s]+)",
                r"(?:apri|mostra|aprimi|mostrami)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:tra|fra)\s+([A-Z][\w\s]+)\s+(?:vs|contro)\s+([A-Z][\w\s]+)",
            ]
            
            for pattern in open_event_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    entities = self.extract_entities(text, [pattern], ["team_or_match"])
                    if entities and entities.get("team_or_match"):
                        print(f"[DEBUG INTENT] OPEN_EVENT priority match: '{pattern}'")
                        return IntentMatch(
                            intent_type=IntentType.OPEN_EVENT,
                            confidence=1.0,
                            entities=entities,
                            original_text=text,
                            normalized_text=normalized,
                            patterns_matched=[pattern]
                        )
        
        # CICLO 4: PRIORITÀ ASSOLUTA per VAGUE_REQUEST - Fix T26
        if self._is_vague_request(text):
            print(f"[DEBUG INTENT] FORCED VAGUE_REQUEST detected for: {text}")
            return IntentMatch(
                intent=IntentType.VAGUE_REQUEST.value,
                confidence=0.9,  # Alta confidenza per forzare la priorità
                entities={},
                needs_clarification=True,
                is_compromise=False,
                ambiguity_suggestions=[],
                compromise_suggestions=[]
            )
        
        # Cerca il miglior match tra tutti gli intent
        for intent_type, patterns_list in self.intent_patterns.items():
            for pattern_config in patterns_list:
                for pattern in pattern_config["patterns"]:
                    if re.search(pattern, text, re.IGNORECASE):
                        confidence = pattern_config["confidence"].value
                        
                        # Bonus per match esatti
                        if re.match(pattern, text, re.IGNORECASE):
                            confidence += 0.1
                        
                        print(f"[DEBUG INTENT] Pattern matched: '{pattern}' for intent {intent_type}")
                        print(f"[DEBUG INTENT] Entities to extract: {pattern_config['entities']}")
                        entities = self.extract_entities(
                            text, 
                            [pattern], 
                            pattern_config["entities"]
                        )
                        print(f"[DEBUG INTENT] Extracted entities: {entities}")
                        
                        # Bonus per intent con entità estratte (più specifici)
                        if entities and any(entities.values()):
                            confidence += 0.2
                            print(f"[DEBUG INTENT] Bonus for entities: +0.2, new confidence: {confidence}")
                        
                        # Bonus speciale per LEAGUE_STANDINGS per dargli priorità sui conflitti con TEAM_COMPARISON
                        if intent_type == IntentType.LEAGUE_STANDINGS:
                            confidence += 0.3
                            print(f"[DEBUG INTENT] Bonus for LEAGUE_STANDINGS: +0.3, new confidence: {confidence}")
                        
                        # Bonus speciale per TEAM_INFO per dargli priorità sui conflitti con TEAM_COMPARISON
                        if intent_type == IntentType.TEAM_INFO:
                            confidence += 0.25
                            print(f"[DEBUG INTENT] Bonus for TEAM_INFO: +0.25, new confidence: {confidence}")
                        
                        if confidence > highest_confidence:
                            print(f"[DEBUG INTENT] New best match: {intent_type} with confidence {confidence}")
                            best_match = IntentMatch(
                                intent_type=intent_type,
                                confidence=min(confidence, 1.0),
                                entities=entities,
                                original_text=text,
                                normalized_text=normalized,
                                patterns_matched=[pattern]
                            )
                            highest_confidence = confidence
                        else:
                            print(f"[DEBUG INTENT] Not better than current best: {confidence} <= {highest_confidence}")
        
        if best_match:
            # Aggiungi logica per "tra poco" se l'intent è GENERIC_MATCH_REQUEST
            if best_match.intent_type == IntentType.GENERIC_MATCH_REQUEST:
                time_reference_patterns = [
                    r"(?:tra\s+poco|imminenti|prossime|presto|a\s+breve)",
                    r"(?:che\s+iniziano\s+)?(?:tra\s+poco|presto|a\s+breve)",
                    r"(?:ci\s+stanno|ci\s+sono)\s+(?:tra\s+poco|imminenti|prossime)"
                ]
                
                for pattern in time_reference_patterns:
                    time_match = re.search(pattern, text.lower())
                    if time_match:
                        best_match.entities["time_reference"] = "tra_poco"
                        best_match.entities["urgency"] = "high"
                        print(f"[DEBUG INTENT] Estratto time_reference: 'tra_poco' e urgency: 'high' da frase: '{text}'")
                        break
            
            return best_match
        
        # Se non trova match, è sconosciuto
        return IntentMatch(
            intent_type=IntentType.UNKNOWN,
            confidence=0.0,
            entities={},
            original_text=text,
            normalized_text=normalized,
            patterns_matched=[]
        )
    
    def resolve_ambiguity(self, intent_match: IntentMatch) -> List[str]:
        """Risolve ambiguità nell'intent rilevato"""
        suggestions = []
        
        # Se mancano entità critiche, suggerisci opzioni
        if intent_match.intent_type == IntentType.BET_ANALYSIS and not intent_match.entities.get("bet_type"):
            suggestions.extend(self.ambiguity_resolvers["bet_type"])
        
        elif intent_match.intent_type in [IntentType.ODDS_QUERY, IntentType.CHART_REQUEST, IntentType.STATISTICS, IntentType.OPEN_EVENT]:
            if not intent_match.entities.get("team_or_match"):
                suggestions.extend(self.ambiguity_resolvers["team_or_match"])
        
        elif intent_match.intent_type == IntentType.NAVIGATION and not intent_match.entities.get("destination"):
            suggestions.extend(self.ambiguity_resolvers["destination"])
        
        # Se l'intent è ambiguo, suggerisci intent simili
        elif intent_match.intent_type == IntentType.UNKNOWN:
            suggestions = [
                "Posso aiutarti con:",
                "- Analisi di scommesse (singole, multiple, sistemi)",
                "- Consultazione quote e grafici",
                "- Navigazione tra le sezioni",
                "- Statistiche e informazioni"
            ]
        
        return suggestions
    
    def get_compromise_suggestions(self, intent_match: IntentMatch) -> List[str]:
        """Genera suggerimenti di compromesso per match parziali"""
        suggestions = []
        
        if intent_match.confidence < ConfidenceLevel.MEDIUM.value:
            if intent_match.intent_type == IntentType.BET_ANALYSIS:
                suggestions = [
                    "Forse ti interessa:",
                    "- Analizzare una scommessa singola",
                    "- Trovare la miglior scommessa multipla",
                    "- Consigliare un sistema di scommesse"
                ]
            elif intent_match.intent_type == IntentType.ODDS_QUERY:
                suggestions = [
                    "Posso aiutarti con:",
                    "- Consultare le quote di una squadra",
                    "- Mostrare il grafico delle quote",
                    "- Analizzare le statistiche"
                ]
        
        return suggestions
    
    def process_intent(self, message: str) -> Dict[str, Any]:
        msg = message.lower()
        entities = {}
        patterns_matched = []
        import re
        
        # CONTROLLO PRIORITARIO: Verifica se è una richiesta di sezione
        section_keywords = ["classifica", "standings", "formazioni", "lineups", "scontri diretti", "scontri", "h2h", "overview", "panoramica"]
        action_keywords = ["apri", "aprimi", "mostra", "mostrami", "vai", "naviga", "spostami", "torna", "ritorna", "riportami"]

        # GESTIONE SPECIALE PER QUOTE: Se contiene "quote" o "odds" con parole come "migliori", "best", "oggi", ecc., NON è una richiesta di sezione
        quote_info_keywords = ["migliori", "best", "oggi", "domani", "settimana", "weekend", "ieri", "today", "tomorrow", "yesterday", "buone", "top"]
        has_quote_info = any(quote in msg for quote in ["quote", "odds"]) and any(info in msg for info in quote_info_keywords)

        # Se contiene parole di azione E parole di sezione (ma NON è una richiesta info quote), è probabilmente una richiesta di sezione
        has_action = any(action in msg for action in action_keywords)
        has_section = any(section in msg for section in section_keywords)

        # Escludi "quote"/"odds" dalle section_keywords se è una richiesta info
        if has_quote_info:
            section_keywords = [s for s in section_keywords if s not in ["quote", "odds"]]
        
        if has_action and has_section:
            # Estrai la sezione
            section = self.extract_section_from_text(message)
            if section:
                entities["section"] = section
            
            # Cerca se c'è un evento specificato
            # Pattern per "di [squadra1] vs [squadra2]"
            match_di_vs = re.search(r"(?:di|per)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:vs|VS|Vs)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)", message, re.IGNORECASE)
            if match_di_vs:
                team1 = match_di_vs.group(1).strip()
                team2 = match_di_vs.group(2).strip()
                if team1 and team2:
                    entities["team_or_match"] = f"{team1} vs {team2}"
            
            # Se non c'è evento specificato, non estrarre entità generiche
            if not entities.get("team_or_match"):
                # Non estrarre "classifica" come team_or_match
                return {
                    "intent": "open_event_section",
                    "confidence": 0.9,
                    "entities": entities,
                    "source": "intent_detection"
                }
        
        # CONTROLLO PRIMA PRIORITÀ: Richieste di quote (deve essere prima delle sezioni)
        if any(x in msg for x in ["quota", "quote", "odds", "migliori quote", "best odds", "bookmaker", "scommessa", "scommesse", "quote migliori"]):
            return {
                "intent": "odds_query",
                "confidence": 0.9,
                "entities": entities,
                "source": "intent_detection"
            }

        # Estrai riferimento temporale per "tra poco", "imminenti", etc.
        # Questa logica è ora gestita nel metodo detect_intent

        # Estrai solo la sottostringa che corrisponde a 'Xxx Xxx Xxx (Yyy)' dalla frase ORIGINALE
        league_match = re.search(r'([A-Z][a-zA-Z0-9\-]+(?:\s+[A-Z][a-zA-Z0-9\-]+)+\s*\([A-Za-z0-9\s\-]+\))', message)
        if league_match:
            entities["league"] = league_match.group(1).strip()
            print(f"[DEBUG INTENT] Estratta league: '{entities['league']}' da frase: '{message}'")
        else:
            # Fallback: cerca la parte dopo 'del', 'della', ecc. minuscolo
            match = re.search(r"(?:del|della|di|per)\s*([a-zA-Z0-9\s\-]+\([a-zA-Z0-9\s\-]+\))", message.lower())
            if match:
                entities["league"] = match.group(1).strip()
                print(f"[DEBUG INTENT] Estratta league: '{entities['league']}' da frase: '{message}'")
            else:
                # Fallback: estrai solo la parte dopo 'del', 'di', 'per', ecc.
                match = re.search(r"(?:del|di|per|della|dello|dell'|delle|dell)\s+([a-zA-ZÀ-ÿ0-9'\-\.\s]{3,})", message, re.IGNORECASE)
                if match:
                    candidate = match.group(1).strip()
                    words = re.findall(r"[a-zA-ZÀ-ÿ0-9'\-]{3,}", candidate)
                    banned_words = set([
                        "classifica","standings","quote","odds","formazioni","lineups","statistiche","stats",
                        "scontri","diretti","h2h","overview","panoramica","mercato","quota","schedina","betbuilder",
                        "partita","match","insieme","del","della","dei","degli","dello","delle","di","per"
                    ])
                    if words:
                        filtered = [w for w in words if w.lower() not in banned_words]
                        if filtered:
                            # Prendi tutte le parole filtrate, non solo l'ultima
                            team_entity = " ".join(filtered)
                            team_entity_norm = team_entity.lower()
                            for suffix in [" w", " women", " femminile", " ladies", " girls"]:
                                if team_entity_norm.endswith(suffix):
                                    team_entity = team_entity_norm.replace(suffix, "") + " w"
                            entities["team_or_match"] = team_entity
                            print(f"[DEBUG PROCESS_INTENT] Estratto team_or_match: '{team_entity}' da pattern 'dell'")
                    else:
                        # Controlla anche il candidato completo
                        section_keywords = ["classifica", "standings", "quote", "odds", "formazioni", "lineups", "statistiche", "stats", "scontri", "diretti", "h2h", "overview", "panoramica"]
                        if candidate.lower() not in section_keywords and candidate.lower() not in banned_words:
                            entities["team_or_match"] = candidate
                            print(f"[DEBUG PROCESS_INTENT] Estratto team_or_match: '{candidate}' da candidato completo")
        # --- Nuovo pattern: estrai 'team_or_match' da frasi con 'vs', 'contro' o '-' ---
        # Pattern più specifico per estrarre solo i nomi delle squadre
        match_vs = re.search(r"(?:tra|contro)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:e|vs|VS|Vs|\-|–)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)", message, re.IGNORECASE)
        if match_vs:
            team1 = match_vs.group(1).strip()
            team2 = match_vs.group(2).strip()
            if team1 and team2:
                entities["team_or_match"] = f"{team1} vs {team2}"
        
        # Pattern aggiuntivi più robusti per eventi
        if not entities.get("team_or_match"):
            # Pattern per "apri evento [squadra1] vs [squadra2]"
            match_apri_evento = re.search(r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\'\s]+)?(?:evento|partita|match)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:vs|contro|VS|Vs)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)", message, re.IGNORECASE)
            if match_apri_evento:
                team1 = match_apri_evento.group(1).strip()
                team2 = match_apri_evento.group(2).strip()
                if team1 and team2:
                    entities["team_or_match"] = f"{team1} vs {team2}"
                    print(f"[DEBUG INTENT] Estratto team_or_match da 'apri evento': '{entities['team_or_match']}'")
        else:
            # Pattern specifico per "Mostrami la partita tra Napoli vs Pisa"
            match_partita_tra = re.search(r"(?:mostrami|mostra|parlami|parla)\s+(?:la\s+)?(?:partita|evento|match)\s+(?:tra|fra)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:vs|contro)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)", message, re.IGNORECASE)
            if match_partita_tra:
                team1 = match_partita_tra.group(1).strip()
                team2 = match_partita_tra.group(2).strip()
                if team1 and team2:
                    entities["team_or_match"] = f"{team1} vs {team2}"
                    print(f"[DEBUG INTENT] Estratto team_or_match da 'partita tra': '{entities['team_or_match']}'")
            else:
                # Pattern specifico per "Apri l'evento [Team1] contro [Team2]"
                match_contro = re.search(r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\'\s]+)?(?:evento|partita|match)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+contro\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)", message, re.IGNORECASE)
                if match_contro:
                    team1 = match_contro.group(1).strip()
                    team2 = match_contro.group(2).strip()
                    if team1 and team2:
                        entities["team_or_match"] = f"{team1} vs {team2}"
                else:
                    # Pattern per "di [squadra1] vs [squadra2]"
                    match_di_vs = re.search(r"(?:di|per)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:vs|VS|Vs)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)", message, re.IGNORECASE)
                    if match_di_vs:
                        team1 = match_di_vs.group(1).strip()
                        team2 = match_di_vs.group(2).strip()
                        if team1 and team2:
                            entities["team_or_match"] = f"{team1} vs {team2}"
                    else:
                         # Pattern alternativo per "vs" senza "tra" - approccio più robusto
                         match_vs_alt = re.search(r"([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:vs|VS|Vs|\-|–)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)", message, re.IGNORECASE)
                    if match_vs_alt:
                        team1 = match_vs_alt.group(1).strip()
                        team2 = match_vs_alt.group(2).strip()
                        
                        # Rimuovi parole comuni dal nome della squadra
                        team1 = re.sub(r'^(?:Apri|Mostrami|la|pagina|evento|per|del|match|di)\s+', '', team1, flags=re.IGNORECASE).strip()
                        team2 = re.sub(r'\s+(?:vs|VS|Vs|\-|–).*$', '', team2, flags=re.IGNORECASE).strip()
                        
                        # Se team1 è ancora troppo lungo, cerca di estrarre solo l'ultima parola significativa
                        if len(team1) > 20:
                            words = team1.split()
                            # Prendi l'ultima parola significativa (non "per", "del", etc.)
                            significant_words = [w for w in words if w.lower() not in ['per', 'del', 'di', 'la', 'pagina', 'evento', 'match']]
                            if significant_words:
                                team1 = significant_words[-1]
                        # Se team1 contiene ancora "evento per", rimuovilo
                        if "evento per" in team1.lower():
                            team1 = re.sub(r'.*evento per\s+', '', team1, flags=re.IGNORECASE).strip()
                        
                        # Se team2 è ancora troppo lungo, cerca di estrarre solo la prima parola significativa
                        if len(team2) > 20:
                            words = team2.split()
                            # Prendi la prima parola significativa
                            significant_words = [w for w in words if w.lower() not in ['vs', 'VS', 'Vs', 'Real', 'Madrid', 'Barcelona', 'Juventus', 'Milan', 'Roma', 'Lazio']]
                            if significant_words:
                                team2 = significant_words[0]
                        
                        if team1 and team2 and len(team1) > 2 and len(team2) > 2:
                            entities["team_or_match"] = f"{team1} vs {team2}"
        # League extraction fallback: parole chiave
        if not entities.get("league"):
            for kw in ["world cup", "fifa", "world", "club world cup"]:
                if kw in msg:
                    entities["league"] = "FIFA Club World Cup (World)"
        # League extraction per i campionati più famosi
        for league in ["serie a", "premier league", "bundesliga", "la liga", "ligue 1", "champions league", "europa league", "conference league", "coppa italia", "copa del rey", "fa cup"]:
            if league in msg:
                entities["league"] = league
        
        # Team extraction for predictions - common Italian and European teams
        common_teams = [
            "juventus", "inter", "milan", "napoli", "roma", "lazio", "fiorentina", "atalanta", "torino", "genoa",
            "manchester united", "manchester city", "liverpool", "chelsea", "arsenal", "tottenham",
            "barcelona", "real madrid", "atletico madrid", "valencia", "sevilla",
            "bayern munich", "borussia dortmund", "leipzig", "bayer leverkusen",
            "psg", "marseille", "lyon", "monaco", "lille"
        ]
        for team in common_teams:
            if team in msg:
                entities["team"] = team.title()
                logger.info(f"[ENTITY EXTRACTION] Found team: {team.title()}")
                break
        
        # Past date detection - predictions are only for future matches
        past_date_keywords = ["ieri", "yesterday", "scorsa settimana", "last week", "la settimana scorsa", "passata", "passato"]
        for past_keyword in past_date_keywords:
            if past_keyword in msg:
                entities["past_date_request"] = True
                logger.info(f"[ENTITY EXTRACTION] Detected past date request: {past_keyword}")
                break

        # Outcome 1X2/DoubleChance esplicito (es. "quota 1", "segno X", "mercato 2", "quota 1X", "segno X2", "quota 12")
        market_match = re.search(r"(?:mercato|segno|quota)\s*(1x|x2|12|1|x|2)", message, re.IGNORECASE)
        if market_match:
            mo = market_match.group(1).upper()
            if mo in ["1", "X", "2", "1X", "X2", "12"]:
                entities["market_outcome"] = mo
        # Date extraction
        if "oggi" in msg:
            entities["date"] = "today"
        elif "domani" in msg:
            entities["date"] = "tomorrow"
        else:
            date_match = re.findall(r"\d{1,2}/\d{1,2}/\d{2,4}", msg)
            if date_match:
                entities["date"] = date_match[0]
        # Offset temporali (es. 'prossim[ei] (\d{1,2}) ore', 'tra (\d{1,2}) giorni', 'tra (\d{1,2}) ore')
        offset_match = re.search(r"prossim[ei] (\d{1,2}) ore", msg)
        if offset_match:
            entities["hours_offset"] = int(offset_match.group(1))
        offset_match = re.search(r"tra (\d{1,2}) giorni", msg)
        if offset_match:
            entities["days_offset"] = int(offset_match.group(1))
        offset_match = re.search(r"tra (\d{1,2}) ore", msg)
        if offset_match:
            entities["hours_offset"] = int(offset_match.group(1))
        # Bet type extraction
        if "multipla" in msg:
            entities["bet_type"] = "multipla"
        elif "singola" in msg:
            entities["bet_type"] = "singola"
        elif "sistema" in msg:
            entities["bet_type"] = "sistema"
        
        # Section extraction per OPEN_EVENT_SECTION
        section = self.extract_section_from_text(message)
        if section:
            entities["section"] = section
        
        # INTENT DETECTION
        # Pattern per navigazione di ritorno e homepage
        if any(x in msg for x in ["torna", "ritorna", "tornare", "ritornare"]) and any(x in msg for x in ["homepage", "home", "principale", "inizio", "pagina principale"]):
            intent = "navigation"
            entities["destination"] = "homepage"
            confidence = 0.95
            patterns_matched.append("return_navigation")
        elif any(x in msg for x in ["torna", "ritorna", "tornare", "ritornare"]) and any(x in msg for x in ["indietro", "back", "precedente"]):
            intent = "navigation"
            entities["destination"] = "back"
            confidence = 0.9
            patterns_matched.append("back_navigation")
        # Pattern per apertura di pagine specifiche
        elif any(x in msg for x in ["apri", "aprimi", "mostra", "mostrami", "vai", "naviga", "spostami", "portami"]) and any(x in msg for x in ["homepage", "home", "principale", "inizio", "pagina principale"]):
            intent = "navigation"
            entities["destination"] = "homepage"
            confidence = 0.9
            patterns_matched.append("homepage_navigation")
        elif any(x in msg for x in ["apri", "aprimi", "mostra", "mostrami", "vai", "naviga", "spostami", "portami"]) and any(x in msg for x in ["simulatore", "simulator"]):
            intent = "navigation"
            entities["destination"] = "simulator"
            confidence = 0.9
            patterns_matched.append("simulator_navigation")
        elif any(x in msg for x in ["apri", "aprimi", "mostra", "mostrami", "vai", "naviga", "spostami", "portami"]) and any(x in msg for x in ["betbuilder", "schedina"]):
            intent = "navigation"
            entities["destination"] = "betbuilder"
            confidence = 0.95
            patterns_matched.append("betbuilder_navigation")
        elif any(x in msg for x in ["apri", "aprimi", "mostra", "mostrami", "vai", "naviga", "spostami", "portami"]) and any(x in msg for x in ["partite", "matches", "calendario"]):
            intent = "navigation"
            entities["destination"] = "matches"
            confidence = 0.9
            patterns_matched.append("matches_navigation")
        elif any(x in msg for x in ["apri", "aprimi", "mostra", "mostrami", "vai", "naviga", "spostami", "portami"]) and any(x in msg for x in ["notizie", "news"]):
            intent = "navigation"
            entities["destination"] = "news"
            confidence = 0.9
            patterns_matched.append("news_navigation")
        elif any(x in msg for x in ["apri", "aprimi", "mostra", "mostrami", "vai", "naviga", "spostami", "portami"]) and any(x in msg for x in ["funzionalità", "funzionalita", "features"]):
            intent = "navigation"
            entities["destination"] = "features"
            confidence = 0.9
            patterns_matched.append("features_navigation")
        # Pattern per eventi e sezioni specifiche
        elif any(x in msg for x in ["apri", "aprimi", "mostra", "mostrami", "puoi", "vai", "naviga", "spostami", "portami"]) and any(x in msg for x in ["evento", "partita", "match", "pagina"]):
            # Controlla se è una richiesta di sezione specifica (deve contenere esplicitamente "sezione" o parole di sezione)
            if ("sezione" in msg and any(x in msg for x in ["classifica", "quote", "formazioni", "scontri diretti", "scontri", "overview", "panoramica"])) or \
               (any(x in msg for x in ["apri la classifica", "mostra la classifica", "apri le quote", "mostra le quote", "apri le formazioni", "mostra le formazioni"])):
                intent = "open_event_section"
                confidence = 0.9
            else:
                intent = "open_event"
                confidence = 0.8
        # Pattern per apertura eventi con nomi squadre diretti (es: "Apri Sabah FA vs Petrocub")
        elif any(x in msg for x in ["apri", "aprimi", "mostra", "mostrami"]) and "vs" in msg:
            # Cerca pattern "Squadra1 vs Squadra2" o "Squadra1 VS Squadra2"
            match_vs = re.search(r"([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:vs|VS|Vs)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)", msg, re.IGNORECASE)
            if match_vs:
                team1 = match_vs.group(1).strip()
                team2 = match_vs.group(2).strip()
                
                # Rimuovi le parole di azione dal team1
                action_words = ["apri", "aprimi", "mostra", "mostrami", "vai", "naviga", "spostami", "portami", "l'evento", "evento", "per", "del", "di"]
                for word in action_words:
                    if team1.lower().startswith(word.lower()):
                        team1 = team1[len(word):].strip()
                        break
                
                # Rimuovi anche parole comuni dal team2
                for word in action_words:
                    if team2.lower().endswith(word.lower()):
                        team2 = team2[:-len(word)].strip()
                        break
                
                # Pulizia aggiuntiva: rimuovi parole comuni che potrebbero essere rimaste
                common_words = ["l'evento", "evento", "per", "del", "di", "la", "il", "un", "una"]
                for word in common_words:
                    team1 = team1.replace(word, "").strip()
                    team2 = team2.replace(word, "").strip()
                
                if team1 and team2 and len(team1) > 2 and len(team2) > 2:
                    # Mantieni il case originale per i nomi delle squadre
                    entities["team_or_match"] = f"{team1} vs {team2}"
                    intent = "open_event"
                    confidence = 0.9
                    patterns_matched.append("direct_team_match")
                    print(f"[DEBUG INTENT] Estratto team_or_match: '{entities['team_or_match']}' da '{msg}'")
        elif any(x in msg for x in ["apri", "aprimi", "mostra", "mostrami", "puoi"]) and any(x in msg for x in ["classifica", "quote", "formazioni", "scontri diretti", "scontri", "overview", "panoramica"]):
            # Richiesta di sezione senza specificare evento (usa contesto)
            intent = "open_event_section"
            confidence = 0.85
        elif any(x in msg for x in ["vai", "naviga", "spostami"]) and any(x in msg for x in ["classifica", "quote", "formazioni", "scontri diretti", "scontri", "overview", "panoramica"]):
            # Navigazione verso sezione specifica
            intent = "open_event_section"
            confidence = 0.85
        elif "puoi aprirmi" in msg and any(x in msg for x in ["classifica", "quote", "formazioni", "scontri diretti", "scontri", "overview", "panoramica"]):
            # Pattern specifico per "puoi aprirmi la sezione X"
            intent = "open_event_section"
            confidence = 0.9
        elif any(x in msg for x in ["grafico", "chart"]):
            intent = "chart_request"
            patterns_matched.append("chart")
        elif any(x in msg for x in ["probabilit", "consiglio", "advice"]):
            intent = "odds_query"
            patterns_matched.append("prediction")
        elif (any(x in msg for x in ["analizza", "multipla", "singola", "sistema", "betbuilder", "schedina", "miglior multipla", "aggiungi", "inserisci", "metti"])):
            intent = "bet_analysis"
            # Estrarre outcome richiesto se presente (quota 1/X/2 o 1X/X2/12)
            mm = re.search(r"(?:quota|segno|mercato)\s*(1x|x2|12|1|x|2)", message, re.IGNORECASE)
            if mm:
                mo = mm.group(1).upper()
                entities["market_outcome"] = mo
            patterns_matched.append("bet_analysis")
        elif any(x in msg for x in ["statistica", "statistiche", "stats"]):
            intent = "statistics"
            patterns_matched.append("statistics")
        # CONTROLLO PRIORITARIO: Richieste di partite hanno priorità su predizioni
        elif any(x in msg for x in ["partite", "incontri", "matches", "giochi"]) and any(x in msg for x in ["oggi", "today", "domani", "tomorrow", "questa settimana", "this week", "ci sono", "sono in programma", "sono programmate"]):
            # Richiesta generica di partite per un periodo temporale
            intent = "generic_match_request"
            confidence = 0.9
            patterns_matched.append("generic_matches")
        elif any(x in msg for x in ["che partite", "quali partite", "che incontri", "quali incontri", "che giochi", "quali giochi", "che match", "quali match"]) and any(x in msg for x in ["oggi", "today", "domani", "tomorrow", "ci sono"]):
            # Pattern specifico italiano per richieste di partite
            intent = "generic_match_request"
            confidence = 0.95
            patterns_matched.append("generic_matches_italian")
        elif any(x in msg for x in ["predizioni", "predictions", "pronostico", "previsioni", "chi vince", "vincerà", "analisi", "migliori predizioni", "predizioni migliori", "profittevoli", "profitto", "guadagni", "guadagno", "redditizio", "redditizi", "vincita", "vincite"]) or self._detect_complex_prediction_patterns(msg):
            # Predizioni - escluse le richieste di partite con "importanti"
            intent = "predictions"
            patterns_matched.append("predictions")
        elif any(x in msg for x in ["quando gioca", "calendario"]):
            # Navigazione solo per richieste esplicite di calendario/"quando gioca" (senza destinazione specifica sarà gestito a livello superiore)
            intent = "navigation"
            patterns_matched.append("navigation")
        # CONTROLLO PRIORITARIO: Se contiene parole chiave calcistiche, NON classificare come greeting
        elif any(x in msg for x in ["ciao", "buongiorno", "salve", "hello", "hi", "come stai", "come va"]) and not any(x in msg for x in ["partite", "incontri", "matches", "campionati", "squadre", "calcio", "football", "serie a", "premier", "liga", "bundesliga", "champions", "europa", "mondiali", "qualificazioni", "predizioni", "quote", "statistiche", "importanti"]):
            intent = "greeting"
            patterns_matched.append("greeting")
        elif any(x in msg for x in ["aiuto", "help", "come funziona"]):
            intent = "help"
            patterns_matched.append("help")
            # Richiesta generica di partite per un periodo temporale
            intent = "generic_match_request"
            confidence = 0.9
            patterns_matched.append("generic_matches")
        elif any(x in msg for x in ["che partite", "quali partite", "che incontri", "quali incontri", "che giochi", "quali giochi", "che match", "quali match"]) and any(x in msg for x in ["oggi", "today", "domani", "tomorrow", "ci sono"]):
            # Pattern specifico italiano per richieste di partite
            intent = "generic_match_request"
            confidence = 0.95
            patterns_matched.append("generic_matches_italian")
        # REGOLA 7: Riconoscimento richieste troppo vaghe
        elif self._is_vague_request(msg):
            intent = "vague_request"
            patterns_matched.append("vague_request")
            needs_clarification = True
        else:
            intent = "unknown"
        confidence = 1.0 if intent != "unknown" else 0.5
        needs_clarification = intent == "vague_request"
        # Chiedi chiarimenti se manca entità chiave per intent
        if intent in ["odds_query", "statistics", "chart_request", "open_event"] and not entities.get("team_or_match"):
            needs_clarification = True
        elif intent == "open_event_section" and not entities.get("team_or_match") and not entities.get("section"):
            needs_clarification = True
        elif intent == "open_event_section" and entities.get("section") and not entities.get("team_or_match"):
            # Per open_event_section, se c'è la sezione ma non l'evento, va bene (usa contesto)
            needs_clarification = False
        elif intent == "bet_analysis" and not entities.get("bet_type"):
            needs_clarification = True
        elif intent == "predictions":
            # Per predictions, non richiedere chiarimenti se mancano entità specifiche
            # Le predizioni possono essere generali (es. "predizioni di oggi") o specifiche
            needs_clarification = False
        return {
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "patterns_matched": patterns_matched,
            "needs_clarification": needs_clarification
        }