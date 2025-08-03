import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Database Configuration ---
# Support both local SQLite and Railway PostgreSQL
def get_database_url():
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
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "REDACTED")

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# CORS Configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

class Settings:
    DATABASE_URL: str = DATABASE_URL
    RAILWAY_ENVIRONMENT: str = RAILWAY_ENVIRONMENT
    PORT: int = PORT
    FOOTBALL_API_KEY: str = FOOTBALL_API_KEY
    SECRET_KEY: str = SECRET_KEY
    ALGORITHM: str = ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES: int = ACCESS_TOKEN_EXPIRE_MINUTES
    ALLOWED_ORIGINS: list = ALLOWED_ORIGINS

settings = Settings() 