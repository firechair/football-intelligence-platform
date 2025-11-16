import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import datetime for cron scheduling
from datetime import datetime

# Initialize database connection - Railway optimized (lazy initialization)
from app.core.database import init_database, get_db
from app.models import Base

# Create FastAPI app - DATABASE TEST VERSION
app = FastAPI(
    title="FIP Database Test",
    description="Testing database connections with Railway optimizations",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global database status
db_initialized = False
db_error_message = None

# Startup event - safe database initialization
@app.on_event("startup")
async def startup_event():
    """Initialize database safely without blocking startup"""
    global db_initialized, db_error_message

    logger.info("🚀 Starting FIP with database initialization...")

    try:
        # Initialize database with timeout (5 seconds max)
        import asyncio
        db_task = asyncio.create_task(init_db_async())
        await asyncio.wait_for(db_task, timeout=5.0)
        db_initialized = True
        logger.info("✅ Database initialized successfully")

    except asyncio.TimeoutError:
        db_error_message = "Database initialization timeout (>5s)"
        logger.warning(f"⚠️ {db_error_message} - continuing without database")
    except Exception as e:
        db_error_message = f"Database initialization failed: {str(e)}"
        logger.error(f"❌ {db_error_message} - continuing without database")

    logger.info("🎯 Service ready (database may or may not be available)")

async def init_db_async():
    """Initialize database asynchronously"""
    try:
        # Initialize engine
        engine = init_database()

        # Create tables (this can be slow, but we have timeout protection)
        Base.metadata.create_all(bind=engine)

        # Test connection quickly
        db = next(get_db())
        db.execute("SELECT 1")  # Simple test query
        db.close()

        return True
    except Exception as e:
        raise e

# No sample data needed for diagnostic version

@app.get("/")
async def root():
    """Root endpoint with database status"""
    return {
        "message": "FIP Database Test",
        "status": "running",
        "version": "1.0.0",
        "database": "initialized" if db_initialized else "failed",
        "database_error": db_error_message
    }

@app.get("/health")
async def health():
    """Health check with database status"""
    return {
        "status": "healthy",
        "version": "database-test",
        "database": "initialized" if db_initialized else "failed",
        "database_error": db_error_message,
        "timestamp": datetime.now().isoformat()
    }

# Simple job endpoints - no database
@app.post("/api/v1/admin/job/fixtures-daily")
async def job_fixtures_daily():
    """Simple Job A response"""
    return {
        "success": True,
        "message": "Fixtures job (diagnostic - no database)",
        "fixtures_collected": 0,
        "database": "disabled"
    }

@app.post("/api/v1/admin/job/predictions-update")
async def job_predictions_update():
    """Simple Job B response"""
    return {
        "success": True,
        "message": "Predictions job (diagnostic - no database)",
        "predictions_collected": 0,
        "database": "disabled"
    }

@app.post("/api/v1/admin/job/results-check")
async def job_results_check():
    """Simple Job D response"""
    return {
        "success": True,
        "message": "Results check job (diagnostic - no database)",
        "matches_checked": 0,
        "database": "disabled"
    }

@app.post("/api/v1/admin/job/odds-update")
async def job_odds_update():
    """Simple Job C response"""
    return {
        "success": True,
        "message": "Odds job (diagnostic - no database)",
        "odds_collected": 0,
        "database": "disabled"
    }

# Data endpoints with safe database fallback
@app.get("/api/v1/predictions/upcoming")
async def get_predictions(days_ahead: int = 1, limit: int = 10):
    """Predictions with database fallback"""
    if not db_initialized:
        return [
            {
                "fixture_id": 12345,
                "fixture_date": "2025-11-17T20:45:00Z",
                "league_name": "Serie A",
                "winner_team_name": "Juventus",
                "advice": f"Sample data - database not initialized: {db_error_message}",
                "collected_at": datetime.now().isoformat(),
                "database_status": "fallback"
            }
        ]

    # If database is available, return sample data for now (we'll add real queries later)
    return [
        {
            "fixture_id": 12345,
            "fixture_date": "2025-11-17T20:45:00Z",
            "league_name": "Serie A",
            "winner_team_name": "Juventus",
            "advice": "Sample data - database connected but no real data yet",
            "collected_at": datetime.now().isoformat(),
            "database_status": "connected"
        }
    ]

@app.get("/api/v1/fixtures/upcoming")
async def get_fixtures(days_ahead: int = 1, limit: int = 10):
    """Fixtures with database fallback"""
    if not db_initialized:
        return [
            {
                "fixture_id": 12345,
                "fixture_date": "2025-11-17T20:45:00Z",
                "league_name": "Serie A",
                "home_team": "Juventus",
                "away_team": "Inter Milan",
                "venue": "Allianz Stadium",
                "status": "Not Started",
                "database_status": "fallback"
            }
        ]

    # If database is available, return sample data for now
    return [
        {
            "fixture_id": 12345,
            "fixture_date": "2025-11-17T20:45:00Z",
            "league_name": "Serie A",
            "home_team": "Juventus",
            "away_team": "Inter Milan",
            "venue": "Allianz Stadium",
            "status": "Not Started",
            "database_status": "connected"
        }
    ]

@app.get("/api/v1/test")
async def test_endpoint():
    """Test endpoint with database status"""
    return {
        "test": "OK",
        "message": "Database test API working",
        "database_status": "initialized" if db_initialized else "failed",
        "database_error": db_error_message,
        "available_endpoints": [
            "/", "/health", "/api/v1/test", "/api/v1/db-test",
            "/api/v1/admin/job/fixtures-daily",
            "/api/v1/admin/job/predictions-update",
            "/api/v1/admin/job/odds-update",
            "/api/v1/admin/job/results-check",
            "/api/v1/predictions/upcoming",
            "/api/v1/fixtures/upcoming"
        ]
    }

@app.get("/api/v1/db-test")
async def db_test_endpoint():
    """Database connectivity test"""
    if not db_initialized:
        return {
            "database": "not_initialized",
            "error": db_error_message,
            "status": "failed"
        }

    try:
        # Quick database test (should complete in <1 second)
        db = next(get_db())
        result = db.execute("SELECT 1 as test").fetchone()
        db.close()

        return {
            "database": "connected",
            "test_query": result[0] if result else "failed",
            "status": "success",
            "response_time": "< 1 second"
        }
    except Exception as e:
        return {
            "database": "connection_failed",
            "error": str(e),
            "status": "failed"
        }

# ========================================
# PHASE 5: AUTOMATED JOB SCHEDULING
# ========================================

@app.post("/api/v1/admin/cron/every-30-minutes")
async def cron_every_30_minutes():
    """Simple cron endpoint for testing"""
    # Simple logic to determine which jobs would run (no datetime needed)
    jobs_to_run = ["Job D"]  # Always run

    return {
        "success": True,
        "message": "Diagnostic cron executed",
        "jobs_would_run": jobs_to_run,
        "database": "disabled"
    }

# Real job processing is handled by the service classes

# Railway port configuration
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Starting fast response server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
