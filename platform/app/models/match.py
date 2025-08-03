from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any

class MicrogameOdd(BaseModel):
    id: int
    name: str = Field(..., alias='n')
    odd: float = Field(..., alias='o')
    handicap: Optional[float] = Field(None, alias='hn')

class EnrichedOdd(MicrogameOdd):
    market_name: str
    market_desc: str
    outcome_name: str

class MicrogameEvent(BaseModel):
    # Dati diretti dall'oggetto 'ev'
    event_id: int = Field(..., alias='id')
    composite_event_id: Optional[str] = Field(None, alias='compositeEventId')
    description: str = Field(..., alias='n')
    start_date: Optional[str] = Field(None, alias='d')
    start_time: Optional[str] = Field(None, alias='h')
    is_live: Optional[bool] = Field(None, alias='live')
    manifestation_id: Optional[int] = Field(None, alias='mid')
    
    # Campi che arricchiremo noi
    sport_name: Optional[str] = None
    manifestation_name: Optional[str] = None
    enriched_odds: List[EnrichedOdd] = []

    class Config:
        populate_by_name = True # Permette di usare sia 'event_id' che 'id'

# Modello per la risposta finale
class SoccerEventResponse(BaseModel):
    description: str
    start_time: str
    sport: Optional[str]
    manifestation: Optional[str]
    odds_1x2: Dict[str, float] = {}

class MicrogameBet(BaseModel):
    bet_name: str
    bet_description: str
    odds: List[MicrogameOdd]

class GroupedMatchesResponse(BaseModel):
    # Struttura da definire in base a come vogliamo raggruppare i dati per il frontend
    # Esempio: Dict[str, Dict[str, List[MicrogameEvent]]] # Sport -> Nazione -> Eventi
    pass 