# Creiamo un Base locale per ora, poi potremo integrarlo con quello esistente su Railway
from sqlalchemy.ext.declarative import declarative_base
from .odds_tracking import ExtendedOddsHistory, BookmakerInfo, FixtureTrackingStatus
from .predictions import MatchPredictions, Base as PredictionsBase  # 🆕 NUOVO

# Per ora creiamo il nostro Base, poi lo integreremo con il backend principale
Base = declarative_base()

# Per le predizioni usiamo il Base separato temporaneamente
__all__ = [
    "Base", 
    "ExtendedOddsHistory", "BookmakerInfo", "FixtureTrackingStatus",  # Existing
    "MatchPredictions", "PredictionsBase"  # 🆕 NUOVO
]
