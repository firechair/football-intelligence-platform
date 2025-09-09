# Forza il caricamento delle variabili d'ambiente PRIMA di qualsiasi altro import
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from datetime import datetime

from app.core.config import settings
from app.api import historical, charts, admin, predictions, homepage, fixtures, odds, assets  # 🆕 fixtures & odds API + assets
from app.core.scheduler import scheduler

# Logging setup
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FIP Odds Tracker",
    description="Backend per la storicizzazione delle quote scommesse",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(historical.router)
app.include_router(charts.router)
app.include_router(admin.router)
app.include_router(predictions.router)  # 🆕 NUOVO
app.include_router(homepage.router)     # 🆕 Homepage API
app.include_router(fixtures.router)     # 🆕 Fixtures API
app.include_router(odds.router)         # 🆕 Odds API
app.include_router(assets.router)       # 🆕 Assets/Logo Proxy API

# Startup e shutdown events
@app.on_event("startup")
async def startup_event():
    logger.info("Starting FIP Odds Tracker")
    
    # Forza ricaricamento .env e ricrea engine
    load_dotenv(override=True)
    
    # Inizializza database
    try:
        # Ottieni DATABASE_URL direttamente dal .env
        import os
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
    if not scheduler.running:
        asyncio.create_task(scheduler.start())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down FIP Odds Tracker")
    await scheduler.stop()

@app.get("/")
async def root():
    return {"message": "FIP Odds Tracker API", "status": "running"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "scheduler_running": scheduler.running
    }

