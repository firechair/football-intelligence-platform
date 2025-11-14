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
    
    # Football API Configuration
    FOOTBALL_API_KEY: str = "REDACTED"
    FOOTBALL_API_BASE_URL: str = "https://v3.football.api-sports.io"
    
    # Rate Limiting Configuration - Aggiornato per 5 req/sec supportate dal provider
    MAX_CONCURRENT_REQUESTS: int = 5
    REQUEST_SPACING: float = 0.2

    # Data Retention
    ODDS_RETENTION_DAYS: int = 7
    PREDICTIONS_RETENTION_DAYS: int = 30
    FIXTURE_LOOKAHEAD_DAYS: int = 10

    # Predictions Configuration - Ottimizzato per 5 req/sec
    PREDICTIONS_MAX_CONCURRENT: int = 3
    PREDICTIONS_REQUEST_SPACING: float = 0.5
    
    # Database Configuration
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Redis Cache (optional)
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    
    # CORS Configuration
    ALLOWED_ORIGINS: list = [
        "https://example.invalid",
        "https://example.invalid",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://localhost:8080",
        "*"
    ]

settings = OddsTrackerSettings()

