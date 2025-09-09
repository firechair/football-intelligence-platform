import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Engine globale - sarà inizializzato dinamicamente
engine = None
SessionLocal = None

def init_database():
    """Inizializza l'engine del database con l'URL corrente"""
    global engine, SessionLocal
    
    # Configurazione specifica per tipo di database
    if settings.DATABASE_URL.startswith("sqlite"):
        # Configurazione SQLite
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=False
        )
    else:
        # Configurazione PostgreSQL
        engine = create_engine(
            settings.DATABASE_URL,
            pool_size=0,
            max_overflow=0,
            poolclass=None,
            pool_pre_ping=True,
            echo=False
        )
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine

# Inizializzazione di default (può essere sovrascritta)
init_database()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

