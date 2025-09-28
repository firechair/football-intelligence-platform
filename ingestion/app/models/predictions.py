from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func, Index
from datetime import datetime

# Importiamo il Base condiviso
from . import Base

class MatchPredictions(Base):
    """Predizioni per le partite - Semplificato (solo dati predictions)"""
    __tablename__ = "match_predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, nullable=False, unique=True, index=True)
    fixture_date = Column(DateTime, nullable=False, index=True)
    
    # League context
    league_id = Column(Integer, nullable=True, index=True)
    league_name = Column(String(200), nullable=True)
    
    # Prediction core data
    winner_team_id = Column(Integer, nullable=True, index=True)
    winner_team_name = Column(String(100), nullable=True)
    winner_comment = Column(String(100), nullable=True)  # "Win or draw", etc.
    win_or_draw = Column(Boolean, nullable=True)
    under_over = Column(String(10), nullable=True)
    
    # Goals predictions
    goals_home = Column(String(10), nullable=True)
    goals_away = Column(String(10), nullable=True)
    
    # Advice and percentages
    advice = Column(Text, nullable=True)
    percent_home = Column(String(10), nullable=True)
    percent_draw = Column(String(10), nullable=True)
    percent_away = Column(String(10), nullable=True)
    
    # Metadata
    collected_at = Column(DateTime, server_default=func.now())
    is_prediction_available = Column(Boolean, default=True, index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_fixture_date_collected', 'fixture_date', 'collected_at'),
        Index('idx_league_date', 'league_id', 'fixture_date'),
    )
