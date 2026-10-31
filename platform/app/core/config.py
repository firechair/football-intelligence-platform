import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Database Configuration ---
# Support both local SQLite and Railway PostgreSQL
def get_database_url() -> str:
    # Production: Railway PostgreSQL
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    
    # Development: Local SQLite
    return f"sqlite:///{BASE_DIR.joinpath('test.db')}"

DATABASE_URL = get_database_url()

# Railway Configuration
RAILWAY_ENVIRONMENT = os.getenv("RAILWAY_ENVIRONMENT", "development")
PORT = int(os.getenv("PORT", 8000))

# Football API Configuration
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "")

# JWT Configuration: no defaults, a known signing key would let anyone forge tokens
def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} environment variable is required")
    return value


SECRET_KEY = _required("SECRET_KEY")
REFRESH_SECRET_KEY = _required("REFRESH_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30))

# Email Configuration
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@example.invalid")
FROM_NAME = os.getenv("FROM_NAME", "FIP")
BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")

# Redis Configuration (for rate limiting)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# OpenRouter Configuration (handled in llm_chat.py)
# OPENROUTER_API_KEY should be set as environment variable

# CORS Configuration
DEFAULT_ORIGINS = "http://localhost:3000,http://localhost:5173,https://example.invalid"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",") if o.strip()]

# Ensure production frontend domain is allowed if present in env
FRONTEND_DOMAIN = os.getenv("FRONTEND_DOMAIN")
if FRONTEND_DOMAIN and FRONTEND_DOMAIN not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(FRONTEND_DOMAIN)

class Settings:
    DATABASE_URL: str = DATABASE_URL
    RAILWAY_ENVIRONMENT: str = RAILWAY_ENVIRONMENT
    PORT: int = PORT
    FOOTBALL_API_KEY: str = FOOTBALL_API_KEY
    SECRET_KEY: str = SECRET_KEY
    REFRESH_SECRET_KEY: str = REFRESH_SECRET_KEY
    ALGORITHM: str = ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES: int = ACCESS_TOKEN_EXPIRE_MINUTES
    REFRESH_TOKEN_EXPIRE_DAYS: int = REFRESH_TOKEN_EXPIRE_DAYS
    ALLOWED_ORIGINS: list = ALLOWED_ORIGINS
    SENDGRID_API_KEY: str = SENDGRID_API_KEY
    FROM_EMAIL: str = FROM_EMAIL
    FROM_NAME: str = FROM_NAME
    BASE_URL: str = BASE_URL
    REDIS_URL: str = REDIS_URL

settings = Settings() 