# Importiamo il Base dal modulo locale (sarà integrato con il backend principale su Railway)
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, func, JSON, Boolean, DECIMAL, Index
from sqlalchemy.orm import relationship
from datetime import datetime

class ExtendedOddsHistory(Base):
    """Estensione del modello OddsHistory per supportare tutti i mercati"""
    __tablename__ = "extended_odds_history"
    
    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, nullable=False, index=True)
    
    # Identificazione mercato
    market_name = Column(String(100), nullable=False, index=True)  # "1", "X", "2", "Over2.5", "1+Over2.5", etc.
    market_type = Column(String(50), nullable=False, index=True)   # "1x2", "over_under", "combined", etc.
    market_subtype = Column(String(50), nullable=True)            # "2.5", "1.5", "3.5" per over/under
    
    # Bookmaker e quota
    bookmaker_id = Column(Integer, nullable=False, index=True)
    bookmaker_name = Column(String(100), nullable=False, index=True)
    odd_value = Column(DECIMAL(8,3), nullable=False)
    
    # Metadati
    collected_at = Column(DateTime, server_default=func.now())
    fixture_date = Column(DateTime, nullable=False, index=True)
    is_pre_match = Column(Boolean, default=True, index=True)
    minutes_to_kickoff = Column(Integer, nullable=True)
    
    # Stato della quota
    is_available = Column(Boolean, default=True)
    is_best_odd = Column(Boolean, default=False, index=True)
    
    # Indici composti per performance
    __table_args__ = (
        Index('idx_fixture_market_bookmaker', 'fixture_id', 'market_name', 'bookmaker_id'),
        Index('idx_market_date_bookmaker', 'market_name', 'fixture_date', 'bookmaker_id'),
        Index('idx_collected_at_market', 'collected_at', 'market_name'),
    )

class BookmakerInfo(Base):
    """Informazioni sui bookmaker supportati"""
    __tablename__ = "bookmaker_info"
    
    id = Column(Integer, primary_key=True)
    api_id = Column(Integer, nullable=False, unique=True, index=True)  # ID dall'API
    name = Column(String(100), nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    supported_markets = Column(JSON, nullable=True)  # Lista mercati supportati
    reliability_score = Column(DECIMAL(3,2), default=1.00)  # Score affidabilità
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class FixtureTrackingStatus(Base):
    """Stato del tracking per ogni partita"""
    __tablename__ = "fixture_tracking_status"
    
    id = Column(Integer, primary_key=True)
    fixture_id = Column(Integer, nullable=False, unique=True, index=True)
    
    # Metadata partita
    league_id = Column(Integer, nullable=True, index=True)
    league_name = Column(String(200), nullable=True)
    home_team = Column(String(100), nullable=False)
    away_team = Column(String(100), nullable=False)
    fixture_date = Column(DateTime, nullable=False, index=True)
    
    # Stato tracking
    tracking_status = Column(String(20), default="pending", index=True)  # pending, active, completed, failed
    first_odds_collected_at = Column(DateTime, nullable=True)
    last_odds_collected_at = Column(DateTime, nullable=True)
    total_collections = Column(Integer, default=0)
    failed_collections = Column(Integer, default=0)
    
    # Mercati trovati
    available_markets = Column(JSON, nullable=True)  # Lista mercati disponibili
    bookmakers_found = Column(JSON, nullable=True)   # Lista bookmaker con quote
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
