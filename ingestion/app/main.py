# Forza il caricamento delle variabili d'ambiente PRIMA di qualsiasi altro import
import os
from dotenv import load_dotenv

# Carica il file .env appropriato basato sulla variabile ENVIRONMENT
env_file = ".env.test" if os.getenv("ENVIRONMENT") == "test" else ".env"
load_dotenv(env_file, override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from datetime import datetime

from app.core.config import settings
from app.api import historical, charts, admin, predictions, homepage, fixtures, odds, assets, database_admin
from app.core.scheduler import scheduler, live_odds_monitor

# Logging setup
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FIP Odds Tracker",
    description="Backend per la storicizzazione delle quote scommesse",
    version="1.0.0"
)

# CORS - Use production-safe configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # Use configured origins instead of "*"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# API Routers
app.include_router(historical.router, prefix="/api/v1")
app.include_router(charts.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")
app.include_router(homepage.router, prefix="/api/v1")
app.include_router(fixtures.router, prefix="/api/v1")
app.include_router(odds.router, prefix="/api/v1")
app.include_router(assets.router, prefix="/api/v1")
app.include_router(database_admin.router, prefix="/api/v1")

# Startup e shutdown events
@app.on_event("startup")
async def startup_event():
    import os
    logger.info("Starting FIP Odds Tracker")
    
    # Forza ricaricamento .env e ricrea engine
    env_file = ".env.test" if os.getenv("ENVIRONMENT") == "test" else ".env"
    load_dotenv(env_file, override=True)
    
    # Inizializza database
    try:
        # Ottieni DATABASE_URL direttamente dal .env
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            raise ValueError("DATABASE_URL not found in environment variables")
        
        logger.info(f"Direct DATABASE_URL from env: {database_url.replace(database_url.split('@')[0].split(':')[-1], '***') if '@' in database_url else database_url}")
        
        # Crea engine direttamente con URL dal .env
        from sqlalchemy import create_engine
        engine = create_engine(
            database_url,
            pool_size=0,
            max_overflow=0,
            poolclass=None,
            pool_pre_ping=True,
            echo=False
        )
        
        from app.models.odds_tracking import Base as OddsBase
        from app.models.predictions import Base as PredictionsBase
        
        # Log dell'URL per debug
        logger.info(f"Using database URL: {str(engine.url).replace(engine.url.password or '', '***')}")
        
        # Crea tutte le tabelle da entrambi i Base
        OddsBase.metadata.create_all(bind=engine)
        PredictionsBase.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
    
    # Avvia scheduler in background senza bloccarlo
            # Avvia scheduler giornaliero
            if not scheduler.running:
                asyncio.create_task(scheduler.start())

            # Avvia monitoraggio continuo live (processo separato)
            if not live_odds_monitor.running:
                asyncio.create_task(live_odds_monitor.start())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down FIP Odds Tracker")
    await scheduler.stop()
    await live_odds_monitor.stop()

@app.get("/")
async def root():
    return {"message": "FIP Odds Tracker API", "status": "running"}

