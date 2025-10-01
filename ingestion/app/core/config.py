import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables FIRST - check for test environment
env_file = ".env.test" if os.getenv("ENVIRONMENT") == "test" else ".env"
load_dotenv(env_file, override=True)

# Get DATABASE_URL immediately after loading .env
_DATABASE_URL = os.getenv("DATABASE_URL")

if not _DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Configurazioni ereditate dal backend principale su Railway
class OddsTrackerSettings:
    # Database PostgreSQL condiviso (stesso del backend principale)
    DATABASE_URL: str = _DATABASE_URL
    
    # Football API (stesse credenziali del backend principale)
    # FIXED: Remove FOOTBALL_API_HOST - not needed for direct API-Football integration
    FOOTBALL_API_KEY: str = os.getenv("FOOTBALL_API_KEY", 
        "REDACTED")
    FOOTBALL_API_BASE_URL: str = "https://v3.football.api-sports.io"
    
    # Rate Limiting (configurazione coordinata con backend - totale 3 req/secondo)
    MAX_CONCURRENT_REQUESTS: int = 2  # 2 richieste contemporanee (backend usa 1)
    REQUEST_SPACING: float = 1.0  # 1 secondo tra richieste (1 req/secondo per operator)
    
    # Scheduling (processo batch meno frequente)
    ODDS_COLLECTION_INTERVAL: int = 14400  # 4 ore - processo principale
    DAILY_ODDS_COLLECTION_INTERVAL: int = 1800  # 30 minuti - partite giornaliere
    FIXTURES_SYNC_INTERVAL: int = 7200    # 2 ore - sync partite nuove
    CLEANUP_INTERVAL: int = 86400         # 1 giorno - pulizia dati vecchi
    
    # Storicizzazione
    ODDS_RETENTION_DAYS: int = 7    # Mantieni dati per 7 giorni (invece di 365)
    FIXTURE_LOOKAHEAD_DAYS: int = 10
    
    # 🆕 PREDICTIONS SETTINGS (configurazione ottimizzata)
    PREDICTIONS_COLLECTION_INTERVAL: int = 43200  # 12 ore
    PREDICTIONS_MAX_CONCURRENT: int = 1           # 1 richiesta alla volta
    PREDICTIONS_REQUEST_SPACING: float = 2.0      # 2 secondi tra richieste (0.5 req/sec)
    PREDICTIONS_RETENTION_DAYS: int = 30          # Mantieni predizioni per 30 giorni (invece di 365)
    
    # Database connection settings per PostgreSQL
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # 🔴 REDIS CACHE (opzionale - fallback a in-memory se non disponibile)
    REDIS_URL: str = os.getenv("REDIS_URL", "")  # es: redis://red-abc123:6379
    
    # CORS Origins (production domains + local development)
    ALLOWED_ORIGINS: list = [
        "https://example.invalid",  # Operator production URL
        "https://example.invalid",  # Main backend production URL
        "http://localhost:3000",  # Local frontend development
        "http://localhost:3001",  # Frontend di test
        "http://localhost:5173",  # Vite dev server
        "http://localhost:8080",  # Local operator
        "*"  # Allow all origins for development (will be restricted in production by Railway env)
    ]

settings = OddsTrackerSettings()

