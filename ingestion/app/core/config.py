import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

# Get DATABASE_URL immediately after loading .env
_DATABASE_URL = os.getenv("DATABASE_URL")

if not _DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Configurazioni ereditate dal backend principale su Railway
class OddsTrackerSettings:
    # Database PostgreSQL condiviso (stesso del backend principale)
    DATABASE_URL: str = _DATABASE_URL
    
    # Football API (stesse credenziali del backend principale)
    FOOTBALL_API_KEY: str = os.getenv("FOOTBALL_API_KEY", 
        "REDACTED")
    FOOTBALL_API_BASE_URL: str = "https://api-football-v1.p.rapidapi.com/v3"
    FOOTBALL_API_HOST: str = "api-football-v1.p.rapidapi.com"
    
    # Rate Limiting (configurazione conservativa per evitare sovraccarico)
    MAX_CONCURRENT_REQUESTS: int = 1  # 1 richiesta alla volta
    REQUEST_SPACING: float = 2.0  # 2 secondi tra richieste
    
    # Scheduling (processo batch meno frequente)
    ODDS_COLLECTION_INTERVAL: int = 7200  # 2 ore - processo principale
    FIXTURES_SYNC_INTERVAL: int = 3600    # 1 ora - sync partite nuove
    CLEANUP_INTERVAL: int = 86400         # 1 giorno - pulizia dati vecchi
    
    # Storicizzazione
    ODDS_RETENTION_DAYS: int = 365  # Mantieni dati per 1 anno
    FIXTURE_LOOKAHEAD_DAYS: int = 10
    
    # 🆕 PREDICTIONS SETTINGS (configurazione conservativa)
    PREDICTIONS_COLLECTION_INTERVAL: int = 43200  # 12 ore
    PREDICTIONS_MAX_CONCURRENT: int = 1           # 1 richiesta alla volta
    PREDICTIONS_REQUEST_SPACING: float = 3.0      # 3 secondi tra richieste
    PREDICTIONS_RETENTION_DAYS: int = 365         # Mantieni predizioni per 1 anno
    
    # Database connection settings per PostgreSQL
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # CORS Origins (same as main backend)
    ALLOWED_ORIGINS: list = [
        "https://example.invalid",
        "http://localhost:3000",
        "http://localhost:5173"
    ]

settings = OddsTrackerSettings()

