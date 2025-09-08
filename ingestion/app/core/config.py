import os
from pathlib import Path

# Configurazioni ereditate dal backend principale su Railway
class OddsTrackerSettings:
    # Database PostgreSQL condiviso (stesso del backend principale)
    DATABASE_URL: str = os.getenv("DATABASE_URL", 
        "postgresql://postgres:REDACTED@example.invalid:5432/railway")
    
    # Football API (stesse credenziali del backend principale)
    FOOTBALL_API_KEY: str = os.getenv("FOOTBALL_API_KEY", 
        "REDACTED")
    FOOTBALL_API_BASE_URL: str = "https://api-football-v1.p.rapidapi.com/v3"
    FOOTBALL_API_HOST: str = "api-football-v1.p.rapidapi.com"
    
    # Rate Limiting (configurazione reale)
    MAX_CONCURRENT_REQUESTS: int = 3  # 3 richieste contemporanee/secondo
    REQUEST_SPACING: float = 0.33  # 330ms tra richieste nel batch
    
    # Scheduling (processo batch orario)
    ODDS_COLLECTION_INTERVAL: int = 3600  # 1 ora - processo principale
    FIXTURES_SYNC_INTERVAL: int = 1800    # 30 minuti - sync partite nuove
    CLEANUP_INTERVAL: int = 86400         # 1 giorno - pulizia dati vecchi
    
    # Storicizzazione
    ODDS_RETENTION_DAYS: int = 365  # Mantieni dati per 1 anno
    FIXTURE_LOOKAHEAD_DAYS: int = 10
    
    # 🆕 PREDICTIONS SETTINGS
    PREDICTIONS_COLLECTION_INTERVAL: int = 21600  # 6 ore
    PREDICTIONS_MAX_CONCURRENT: int = 1           # 1 richiesta/secondo
    PREDICTIONS_REQUEST_SPACING: float = 1.0      # 1 secondo tra richieste
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

