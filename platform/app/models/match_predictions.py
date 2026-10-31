"""
Match Predictions Model
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from app.db.models import Base

class MatchPrediction(Base):
    """Modello per salvare le predizioni delle partite"""
    __tablename__ = "match_predictions"

    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, unique=True, index=True, nullable=False)

    # Dati della predizione
    prediction_advice = Column(Text, nullable=True)
    prediction_winner = Column(String(100), nullable=True)
    prediction_percent_home = Column(Float, nullable=True)
    prediction_percent_draw = Column(Float, nullable=True)
    prediction_percent_away = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<MatchPrediction(fixture_id={self.fixture_id}, winner={self.prediction_winner})>"
