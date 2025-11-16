# Forza il caricamento delle variabili d'ambiente PRIMA di qualsiasi altro import
import os
from dotenv import load_dotenv

# 🚨 CRITICAL FOR RAILWAY: Set default port if not specified
if not os.getenv('PORT'):
    os.environ['PORT'] = '8080'

# Carica il file .env appropriato basato sulla variabile ENVIRONMENT
env_file = ".env.test" if os.getenv("ENVIRONMENT") == "test" else ".env"
load_dotenv(env_file, override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from datetime import datetime

from app.core.config import settings
from app.api import historical, charts, admin, predictions, homepage, fixtures, odds, assets, database_admin, team_stats
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
app.include_router(team_stats.router, prefix="/api")

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

    # 🚀 AUTOMATIC JOB SCHEDULING BASED ON TIME (Railway cron runs every 30 min)
    from datetime import datetime
    import asyncio
    from app.core.database import get_db

    # Get database session
    db = next(get_db())

    try:
        current_time = datetime.now()
        current_hour = current_time.hour
        current_minute = current_time.minute

        logger.info(f"⏰ Service started at {current_hour:02d}:{current_minute:02d} - checking which jobs to run...")

        # Job D: RESULTS CHECKER - Always runs (every 30 minutes)
        logger.info("✅ Job D: Results checker - Running (every 30 min)")
        try:
            from app.services.cleanup_service import cleanup_service
            cleanup_result = await cleanup_service.cleanup_finished_matches(db)
            logger.info(f"✅ Job D completed: {cleanup_result.get('matches_checked', 0)} matches checked")
        except Exception as e:
            logger.error(f"❌ Job D failed: {str(e)}")

        # Job C: ODDS UPDATE - Every 3 hours
        if current_hour % 3 == 0 and current_minute < 30:
            logger.info("🎯 Job C: Odds update - Running (every 3 hours)")
            try:
                from app.services.odds_collector import odds_collector
                from app.services.fixtures_collector import fixtures_collector
                fixture_ids = await fixtures_collector.get_daily_fixtures_for_tracking(db)
                if fixture_ids:
                    odds_result = await odds_collector.collect_odds_for_fixtures(fixture_ids, db)
                    logger.info(f"✅ Job C completed: {odds_result.get('odds_collected', 0)} odds collected")
                else:
                    logger.info("ℹ️ Job C: No fixtures to process")
            except Exception as e:
                logger.error(f"❌ Job C failed: {str(e)}")

        # Job A & B: FIXTURES + PREDICTIONS - Every 6 hours at specific times
        if current_hour in [1, 7, 13, 19] and current_minute < 30:
            logger.info(f"🏟️ Job A: Fixtures collection - Running (hour {current_hour})")

            try:
                # Job A: Collect fixtures first
                from app.services.fixtures_collector import fixtures_collector
                fixtures_result = await fixtures_collector.collect_upcoming_fixtures(days_ahead=14)
                await fixtures_collector.update_tracking_status(fixtures_result, db)
                logger.info(f"✅ Job A completed: {len(fixtures_result)} fixtures collected")

                # Wait 1 minute, then Job B
                await asyncio.sleep(60)

                logger.info(f"🔮 Job B: Predictions update - Running (hour {current_hour})")
                from app.services.predictions_collector import predictions_collector
                predictions_result = await predictions_collector.collect_daily_predictions_only(db)
                logger.info(f"✅ Job B completed: {predictions_result.get('predictions_collected', 0)} predictions collected")

            except Exception as e:
                logger.error(f"❌ Job A/B failed: {str(e)}")

        logger.info("🎯 Automatic job scheduling completed - service staying alive for Railway")

    finally:
        db.close()

    # 🚨 CRITICAL: Keep the service alive for Railway
    # Start a background task to keep the service running
    logger.info("🔄 Starting background keep-alive task...")
    asyncio.create_task(keep_service_alive())

    # Avvia monitoraggio continuo live (processo separato)
    if not live_odds_monitor.running:
        asyncio.create_task(live_odds_monitor.start())

async def keep_service_alive():
    """Keep the service alive for Railway cron jobs - runs forever"""
    logger.info("🔄 Keep-alive task started - service will stay running")
    while True:
        await asyncio.sleep(300)  # Check every 5 minutes
        logger.debug("🔄 Service keep-alive heartbeat")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down FIP Odds Tracker")
    await scheduler.stop()
    await live_odds_monitor.stop()

@app.get("/")
async def root():
    return {"message": "FIP Odds Tracker API", "status": "running"}

# 🚨 RAILWAY PORT CONFIGURATION
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    print(f"🚀 Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

