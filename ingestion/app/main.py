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
    
    # Inizializza database
    try:
        from app.core.database import engine
        from app.models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
    
    # Avvia scheduler in background
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

