from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func, DECIMAL, JSON, Index

# Importiamo il Base condiviso
from . import Base

class FinishedFixtures(Base):
    """Risultati delle partite finite"""
    __tablename__ = "finished_fixtures"

    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, nullable=False, unique=True, index=True)

    # Informazioni partita
    fixture_date = Column(DateTime, nullable=False, index=True)
    league_id = Column(Integer, nullable=True, index=True)
    league_name = Column(String(200), nullable=True)
    country_name = Column(String(100), nullable=True)
    home_team = Column(String(100), nullable=False)
    away_team = Column(String(100), nullable=False)

    # Risultato finale
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    winner = Column(String(10), nullable=True)  # "home", "away", "draw"

    # Statistiche partita
    halftime_home_score = Column(Integer, nullable=True)
    halftime_away_score = Column(Integer, nullable=True)
    total_goals = Column(Integer, nullable=True)

    # Stato e metadata
    status = Column(String(20), default="FT", index=True)  # FT = Full Time
    collected_at = Column(DateTime, server_default=func.now())

    # Indici
    __table_args__ = (
        Index('idx_fixture_date_status', 'fixture_date', 'status'),
        Index('idx_league_date_finished', 'league_id', 'fixture_date'),
    )

class PredictionAccuracy(Base):
    """Accuratezza delle predizioni per partite finite"""
    __tablename__ = "prediction_accuracy"

    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, nullable=False, unique=True, index=True)

    # Risultato reale
    actual_home_score = Column(Integer, nullable=True)
    actual_away_score = Column(Integer, nullable=True)
    actual_winner = Column(String(10), nullable=True)  # "home", "away", "draw"
    actual_total_goals = Column(Integer, nullable=True)

    # Predizione fatta
    predicted_winner_id = Column(Integer, nullable=True)
    predicted_winner_name = Column(String(100), nullable=True)
    predicted_win_or_draw = Column(Boolean, nullable=True)
    predicted_under_over = Column(String(10), nullable=True)
    predicted_goals_home = Column(String(10), nullable=True)
    predicted_goals_away = Column(String(10), nullable=True)
    prediction_advice = Column(Text, nullable=True)

    # Accuratezza calcolata
    winner_accuracy = Column(Boolean, nullable=True)  # True se vincitore corretto
    goals_accuracy = Column(Boolean, nullable=True)   # True se under/over corretto
    total_goals_accuracy = Column(Boolean, nullable=True)  # True se totale gol corretto
    win_draw_accuracy = Column(Boolean, nullable=True)  # True se win/draw corretto

    # Punteggi di accuratezza (0-100)
    winner_score = Column(DECIMAL(5,2), nullable=True)  # Percentuale accuratezza vincitore
    goals_score = Column(DECIMAL(5,2), nullable=True)   # Percentuale accuratezza gol
    overall_score = Column(DECIMAL(5,2), nullable=True) # Punteggio complessivo

    # Metadata
    fixture_date = Column(DateTime, nullable=False, index=True)
    league_id = Column(Integer, nullable=True, index=True)
    league_name = Column(String(200), nullable=True)
    home_team = Column(String(100), nullable=False)
    away_team = Column(String(100), nullable=False)

    evaluated_at = Column(DateTime, server_default=func.now())
    prediction_collected_at = Column(DateTime, nullable=True)

    # Indici
    __table_args__ = (
        Index('idx_fixture_date_accuracy', 'fixture_date', 'evaluated_at'),
        Index('idx_league_accuracy_score', 'league_id', 'overall_score'),
        Index('idx_winner_accuracy', 'winner_accuracy', 'fixture_date'),
    )

class AccuracyStatistics(Base):
    """Statistiche aggregate di accuratezza per periodi/leagues"""
    __tablename__ = "accuracy_statistics"

    id = Column(Integer, primary_key=True, index=True)

    # Periodo di riferimento
    period_type = Column(String(20), nullable=False, index=True)  # "daily", "weekly", "monthly", "league"
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)

    # Filtri applicati
    league_id = Column(Integer, nullable=True, index=True)
    league_name = Column(String(200), nullable=True)

    # Statistiche calcolate
    total_predictions = Column(Integer, default=0)
    winner_correct = Column(Integer, default=0)
    goals_correct = Column(Integer, default=0)
    win_draw_correct = Column(Integer, default=0)

    winner_accuracy_percent = Column(DECIMAL(5,2), nullable=True)
    goals_accuracy_percent = Column(DECIMAL(5,2), nullable=True)
    win_draw_accuracy_percent = Column(DECIMAL(5,2), nullable=True)
    overall_accuracy_percent = Column(DECIMAL(5,2), nullable=True)

    average_winner_score = Column(DECIMAL(5,2), nullable=True)
    average_goals_score = Column(DECIMAL(5,2), nullable=True)
    average_overall_score = Column(DECIMAL(5,2), nullable=True)

    # Metadata
    calculated_at = Column(DateTime, server_default=func.now())
    fixtures_analyzed = Column(JSON, nullable=True)  # Lista fixture_id analizzati

    # Indici
    __table_args__ = (
        Index('idx_period_league_stats', 'period_type', 'league_id', 'period_start'),
        Index('idx_calculated_at_stats', 'calculated_at', 'period_type'),
    )
