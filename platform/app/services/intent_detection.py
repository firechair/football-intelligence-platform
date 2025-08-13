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
                        r"(?:mostra|visualizza|vedi)\s+(?:il\s+)?(?:grafico\s+)?(?:della\s+)?(?:quota|odds)\s+(?:per|di|del)\s+([\w\s]+)",
                        r"(?:grafico\s+)?(?:della\s+)?(?:quota|odds)\s+(?:per|di|del)\s+([\w\s]+)",
                        r"(?:mostra|visualizza|vedi)\s+(?:il\s+)?(?:andamento\s+)?(?:della\s+)?(?:quota|odds)\s+(?:per|di|del)\s+([\w\s]+)"
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
                        # Pattern semplici e flessibili
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)\s+(?:di|per)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)\s+(?:relativa\s+a|di|per)\s+([\w\s]+(?:\s+vs\s+[\w\s]+)?)",
                        # Pattern per "Apri l'evento Team1 vs Team2"
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)\s+([\w\s]+)\s+vs\s+([\w\s]+)",
                        r"(?:apri|mostra|aprimi|mostrami)\s+(?:l['\s]+)?(?:evento|partita|match)\s+(?:tra|contro)\s+([\w\s]+)\s+e\s+([\w\s]+)",
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
            
            IntentType.GREETING: [
                {
                    "patterns": [
                        r"ciao|salve|buongiorno|buonasera|buonanotte",
                        r"hey|hi|hello",
                        r"come\s+stai|come\s+va",
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
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                for i, entity_name in enumerate(entity_names):
                    if i < len(matches):
                        if isinstance(matches[i], tuple):
                            # Se abbiamo due gruppi di cattura (team1 vs team2)
                            if len(matches[i]) == 2:
                                team1 = matches[i][0].strip()
                                team2 = matches[i][1].strip()
                                
                                # Pulizia dei nomi delle squadre
                                team1 = re.sub(r'^(?:Apri|Mostrami|la|pagina|evento|per|del|match|di)\s+', '', team1, flags=re.IGNORECASE).strip()
                                team2 = re.sub(r'\s+(?:vs|VS|Vs|\-|–).*$', '', team2, flags=re.IGNORECASE).strip()
                                
                                # Rimuovi parole comuni che potrebbero essere rimaste
                                common_words = ["l'evento", "evento", "per", "del", "di", "la", "il", "un", "una"]
                                for word in common_words:
                                    team1 = team1.replace(word, "").strip()
                                    team2 = team2.replace(word, "").strip()
                                
                                if team1 and team2 and len(team1) > 2 and len(team2) > 2:
                                    entities[entity_name] = f"{team1} vs {team2}"
                                    print(f"[DEBUG INTENT] Estratto team_or_match: '{entities[entity_name]}' da '{text}'")
                                    break
                            else:
                                # Fallback per tuple con un solo elemento
                                entities[entity_name] = matches[i][0].strip()
                        else:
                            value = matches[i].strip()
                            # Mappa le destinazioni specifiche
                            if entity_name == "destination":
                                value = self.map_destination(value)
                            entities[entity_name] = value
                break
        
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
            "features": "features"
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
        
        # Cerca il miglior match tra tutti gli intent
        for intent_type, patterns_list in self.intent_patterns.items():
            for pattern_config in patterns_list:
                for pattern in pattern_config["patterns"]:
                    if re.search(pattern, text, re.IGNORECASE):
                        confidence = pattern_config["confidence"].value
                        
                        # Bonus per match esatti
                        if re.match(pattern, text, re.IGNORECASE):
                            confidence += 0.1
                        
                        if confidence > highest_confidence:
                            entities = self.extract_entities(
                                text, 
                                [pattern], 
                                pattern_config["entities"]
                            )
                            
                            best_match = IntentMatch(
                                intent_type=intent_type,
                                confidence=min(confidence, 1.0),
                                entities=entities,
                                original_text=text,
                                normalized_text=normalized,
                                patterns_matched=[pattern]
                            )
                            highest_confidence = confidence
        
        if best_match:
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
        section_keywords = ["classifica", "standings", "quote", "odds", "formazioni", "lineups", "scontri diretti", "scontri", "h2h", "overview", "panoramica"]
        action_keywords = ["apri", "aprimi", "mostra", "mostrami", "vai", "naviga", "spostami", "torna", "ritorna", "riportami"]
        
        # Se contiene parole di azione E parole di sezione, è probabilmente una richiesta di sezione
        has_action = any(action in msg for action in action_keywords)
        has_section = any(section in msg for section in section_keywords)
        
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
                match = re.search(r"(?:del|di|per|della|dello|dell'|delle|dell' )\s*([a-zA-Zàèéìòù'\-\s]{3,})", msg)
                if match:
                    candidate = match.group(1).strip()
                    words = re.findall(r"[a-zA-Zàèéìòù'\-]{3,}", candidate)
                    if words:
                        team_entity = words[-1]
                        # Controlla se la parola è una sezione, non una squadra
                        section_keywords = ["classifica", "standings", "quote", "odds", "formazioni", "lineups", "statistiche", "stats", "scontri", "diretti", "h2h", "overview", "panoramica"]
                        if team_entity.lower() in section_keywords:
                            # Non estrarre parole di sezione come team_or_match
                            pass
                        else:
                            # Miglioro la normalizzazione per suffissi femminili/maschili
                            team_entity_norm = team_entity.lower()
                            for suffix in [" w", " women", " femminile", " ladies", " girls"]:
                                if team_entity_norm.endswith(suffix):
                                    team_entity = team_entity_norm.replace(suffix, "") + " w"
                            entities["team_or_match"] = team_entity
                    else:
                        # Controlla anche il candidato completo
                        section_keywords = ["classifica", "standings", "quote", "odds", "formazioni", "lineups", "statistiche", "stats", "scontri", "diretti", "h2h", "overview", "panoramica"]
                        if candidate.lower() not in section_keywords:
                            entities["team_or_match"] = candidate
        # --- Nuovo pattern: estrai 'team_or_match' da frasi con 'vs' o '-' ---
        # Pattern più specifico per estrarre solo i nomi delle squadre
        match_vs = re.search(r"(?:tra|contro)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)\s+(?:e|vs|VS|Vs|\-|–)\s+([A-Za-zÀ-ÿ0-9'\-\.\s]+)", message, re.IGNORECASE)
        if match_vs:
            team1 = match_vs.group(1).strip()
            team2 = match_vs.group(2).strip()
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
        for league in ["serie a", "premier league", "bundesliga", "la liga", "ligue 1", "champions league"]:
            if league in msg:
                entities["league"] = league

        # Outcome 1X2 esplicito (es. "quota 1", "segno X", "mercato 2")
        market_match = re.search(r"(?:mercato|segno|quota)\s*(1|x|2)", message, re.IGNORECASE)
        if market_match:
            mo = market_match.group(1).upper()
            if mo in ["1", "X", "2"]:
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
        elif any(x in msg for x in ["apri", "aprimi", "mostra", "mostrami", "puoi"]) and any(x in msg for x in ["evento", "partita", "match", "pagina"]):
            # Controlla se è una richiesta di sezione specifica
            if any(x in msg for x in ["classifica", "quote", "formazioni", "scontri diretti", "scontri", "overview", "panoramica"]):
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
        elif any(x in msg for x in ["quota", "quote", "odds"]):
            intent = "odds_query"
            patterns_matched.append("odds")
        elif any(x in msg for x in ["predizione", "predizioni", "prediction", "probabilit", "consiglio", "advice"]):
            intent = "odds_query"
            patterns_matched.append("prediction")
        elif (any(x in msg for x in ["analizza", "multipla", "singola", "sistema", "betbuilder", "schedina", "miglior multipla", "aggiungi", "inserisci", "metti"])):
            intent = "bet_analysis"
            patterns_matched.append("bet_analysis")
        elif any(x in msg for x in ["statistica", "statistiche", "stats"]):
            intent = "statistics"
            patterns_matched.append("statistics")
        elif any(x in msg for x in ["quando gioca", "calendario", "partite", "prossime partite", "league", "campionato", "campionati"]):
            intent = "navigation"
            patterns_matched.append("navigation")
        elif any(x in msg for x in ["ciao", "buongiorno", "salve", "hello", "hi"]):
            intent = "greeting"
            patterns_matched.append("greeting")
        elif any(x in msg for x in ["aiuto", "help", "come funziona"]):
            intent = "help"
            patterns_matched.append("help")
        else:
            intent = "unknown"
        confidence = 1.0 if intent != "unknown" else 0.5
        needs_clarification = False
        # Chiedi chiarimenti se manca entità chiave per intent
        if intent in ["odds_query", "statistics", "chart_request", "open_event"] and not entities.get("team_or_match"):
            needs_clarification = True
        elif intent == "open_event_section" and not entities.get("team_or_match") and not entities.get("section"):
            needs_clarification = True
        elif intent == "open_event_section" and entities.get("section") and not entities.get("team_or_match"):
            # Per open_event_section, se c'è la sezione ma non l'evento, va bene (usa contesto)
            needs_clarification = False
        if intent == "bet_analysis" and not entities.get("bet_type"):
            needs_clarification = True
        return {
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "patterns_matched": patterns_matched,
            "needs_clarification": needs_clarification
        } 