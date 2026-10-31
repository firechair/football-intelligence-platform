from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Engine globale - sarà inizializzato dinamicamente
engine = None
SessionLocal = None

def init_database():
    """Inizializza l'engine del database con l'URL corrente - Railway optimized"""
    global engine, SessionLocal

    # Usa il DATABASE_URL configurato (PostgreSQL in produzione, SQLite solo se esplicitamente configurato)
    database_url = settings.DATABASE_URL

    if database_url.startswith("sqlite"):
        # Configurazione SQLite
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            echo=False
        )
    else:
        # Configurazione PostgreSQL ottimizzata per Railway
        engine = create_engine(
            database_url,
            pool_size=1,        # Ridotto per Railway (da 10)
            max_overflow=2,     # Ridotto per Railway (da 20)
            pool_timeout=10,    # Timeout connessione 10 secondi
            pool_pre_ping=True,
            echo=False
        )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine

# RIMOSSO: Inizializzazione globale che causava timeout su Railway
# init_database()  # Non chiamare automaticamente

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

