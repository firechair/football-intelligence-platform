# Creiamo un Base condiviso per tutti i modelli
from sqlalchemy.ext.declarative import declarative_base

# Base condiviso per tutti i modelli
Base = declarative_base()

# Importiamo i modelli DOPO aver definito il Base
from .odds_tracking import ExtendedOddsHistory, BookmakerInfo, FixtureTrackingStatus
from .predictions import MatchPredictions
from .accuracy_tracking import FinishedFixtures, PredictionAccuracy, AccuracyStatistics

__all__ = [
    "Base",
    "ExtendedOddsHistory", "BookmakerInfo", "FixtureTrackingStatus",
    "MatchPredictions",
    "FinishedFixtures", "PredictionAccuracy", "AccuracyStatistics"
]
