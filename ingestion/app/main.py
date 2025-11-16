# 🚀 FIP OPERATOR - RAILWAY COMPATIBLE
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Import all routers and services
from app.api import (
    historical, charts, admin, predictions, homepage,
    fixtures, odds, assets, database_admin, team_stats
)
from app.core.config import settings

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)

# Create FastAPI app
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

# Startup event - Railway compatible (quick init, no long-running jobs)
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting FIP Odds Tracker (Railway cron mode)")

    # Load environment variables
    env_file = ".env.test" if os.getenv("ENVIRONMENT") == "test" else ".env"
    load_dotenv(env_file, override=True)

    # Quick database initialization
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL not found in environment variables")

        from sqlalchemy import create_engine
        from app.models.odds_tracking import Base as OddsBase
        from app.models.predictions import Base as PredictionsBase

        engine = create_engine(
            database_url,
            pool_size=1,
            max_overflow=2,
            pool_pre_ping=True,
            echo=False
        )

        # Create tables
        OddsBase.metadata.create_all(bind=engine)
        PredictionsBase.metadata.create_all(bind=engine)
        logger.info("✅ Database tables ready")

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        # Don't crash on DB issues - service should still start for API access

    logger.info("🎯 Service ready - waiting for Railway cron jobs or manual API calls")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down FIP Odds Tracker")
    # No long-running services to stop in Railway cron mode

@app.get("/")
async def root():
    return {"message": "FIP Odds Tracker API", "status": "running", "mode": "Railway cron"}

@app.get("/api/v1/test")
async def test_endpoint():
    """Test endpoint to verify API is working"""
    return {"test": "OK", "message": "API is functioning correctly"}

# Railway will handle the server startup
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🚀 Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

