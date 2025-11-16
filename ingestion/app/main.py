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
    """Job A: Fixtures collection (daily + future) - REAL IMPLEMENTATION"""
    try:
        # Job A always runs regardless of database status
        # Import real fixtures collector
        from app.services.fixtures_collector import fixtures_collector

        # Collect both daily and future fixtures
        logger.info("🏟️ Job A: Starting fixtures collection...")

        # Collect future fixtures (7-14 days ahead)
        future_fixtures = await fixtures_collector.collect_upcoming_fixtures(days_ahead=14)

        if db_initialized:
            # Collect daily fixtures and save to database
            db = next(get_db())
            try:
                daily_fixtures = await fixtures_collector.get_daily_fixtures_for_tracking(db)
                return {
                    "success": True,
                    "message": f"Fixtures collection completed successfully",
                    "future_fixtures_collected": len(future_fixtures) if future_fixtures else 0,
                    "daily_fixtures_found": len(daily_fixtures) if daily_fixtures else 0,
                    "database_status": "saved",
                    "timestamp": datetime.now().isoformat()
                }
            finally:
                db.close()
        else:
            return {
                "success": True,
                "message": f"Future fixtures collected (database not available)",
                "future_fixtures_collected": len(future_fixtures) if future_fixtures else 0,
                "daily_fixtures_found": 0,
                "database_status": "unavailable",
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        logger.error(f"❌ Job A failed: {str(e)}")
        return {
            "success": False,
            "message": f"Fixtures collection failed: {str(e)}",
            "fixtures_collected": 0,
            "error": str(e)
        }

@app.post("/api/v1/admin/job/predictions-update")
async def job_predictions_update():
    """Job B: Predictions update (every 6 hours) - REAL IMPLEMENTATION"""
    try:
        if not db_initialized:
            return {
                "success": False,
                "message": "Predictions update failed - database not initialized",
                "error": db_error_message,
                "predictions_collected": 0,
                "predictions_updated": 0
            }

        # Import real predictions collector
        from app.services.predictions_collector import predictions_collector

        # Execute real predictions collection
        db = next(get_db())
        try:
            result = await predictions_collector.collect_daily_predictions_only(db)
            return {
                "success": True,
                "message": f"Predictions update completed successfully",
                "predictions_collected": result.get("predictions_collected", 0),
                "predictions_updated": result.get("predictions_updated", 0),
                "processed_fixtures": result.get("processed_count", 0),
                "timestamp": datetime.now().isoformat()
            }
        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ Job B failed: {str(e)}")
        return {
            "success": False,
            "message": f"Predictions update failed: {str(e)}",
            "predictions_collected": 0,
            "predictions_updated": 0,
            "error": str(e)
        }

@app.post("/api/v1/admin/job/results-check")
async def job_results_check():
    """Job D: Results checker (every 30 minutes) - REAL IMPLEMENTATION"""
    try:
        if not db_initialized:
            return {
                "success": False,
                "message": "Results check failed - database not initialized",
                "error": db_error_message,
                "matches_checked": 0,
                "accuracy_evaluated": 0
            }

        # Import real cleanup service
        from app.services.cleanup_service import cleanup_service

        # Execute real results checking and accuracy evaluation
        db = next(get_db())
        try:
            result = await cleanup_service.cleanup_finished_matches(db)
            return {
                "success": True,
                "message": f"Results check completed successfully",
                "matches_checked": result.get("matches_checked", 0),
                "finished_matches": result.get("finished_matches", 0),
                "accuracy_evaluations": result.get("accuracy_evaluations", 0),
                "timestamp": datetime.now().isoformat()
            }
        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ Job D failed: {str(e)}")
        return {
            "success": False,
            "message": f"Results check failed: {str(e)}",
            "matches_checked": 0,
            "accuracy_evaluated": 0,
            "error": str(e)
        }

@app.post("/api/v1/admin/job/odds-update")
async def job_odds_update():
    """Job C: Odds update (every 3 hours) - REAL IMPLEMENTATION"""
    try:
        if not db_initialized:
            return {
                "success": False,
                "message": "Odds update failed - database not initialized",
                "error": db_error_message,
                "odds_collected": 0,
                "fixtures_processed": 0
            }

        # Import real services
        from app.services.odds_collector import odds_collector
        from app.services.fixtures_collector import fixtures_collector

        # Get daily fixtures for odds collection
        db = next(get_db())
        try:
            fixture_ids = await fixtures_collector.get_daily_fixtures_for_tracking(db)

            if not fixture_ids:
                return {
                    "success": True,
                    "message": "No fixtures available for odds collection",
                    "odds_collected": 0,
                    "fixtures_processed": 0,
                    "timestamp": datetime.now().isoformat()
                }

            # Collect odds for the fixtures
            result = await odds_collector.collect_odds_for_fixtures(fixture_ids, db)
            return {
                "success": True,
                "message": f"Odds update completed successfully",
                "odds_collected": result.get("odds_collected", 0),
                "fixtures_processed": len(fixture_ids),
                "odds_updated": result.get("odds_updated", 0),
                "timestamp": datetime.now().isoformat()
            }
        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ Job C failed: {str(e)}")
        return {
            "success": False,
            "message": f"Odds update failed: {str(e)}",
            "odds_collected": 0,
            "fixtures_processed": 0,
            "error": str(e)
        }

# Data endpoints with real database queries
@app.get("/api/v1/predictions/upcoming")
async def get_predictions(days_ahead: int = 1, limit: int = 10):
    """Real predictions from database"""
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

    try:
        # Query real predictions from database
        from app.models.predictions import MatchPredictions
        from sqlalchemy import and_, or_

        db = next(get_db())
        try:
            # Calculate date range
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            end_date = now + timedelta(days=days_ahead)

            # Query upcoming predictions
            predictions = db.query(MatchPredictions).filter(
                and_(
                    MatchPredictions.fixture_date >= now,
                    MatchPredictions.fixture_date <= end_date
                )
            ).order_by(MatchPredictions.fixture_date).limit(limit).all()

            # Format results
            result = []
            for pred in predictions:
                result.append({
                    "fixture_id": pred.fixture_id,
                    "fixture_date": pred.fixture_date.isoformat(),
                    "league_name": pred.league_name,
                    "winner_team_name": pred.winner_team_name,
                    "advice": pred.advice,
                    "collected_at": pred.collected_at.isoformat(),
                    "database_status": "real_data"
                })

            return result if result else [
                {
                    "fixture_id": 0,
                    "fixture_date": datetime.now().isoformat(),
                    "league_name": "No Data",
                    "winner_team_name": "No predictions available",
                    "advice": "Database connected but no upcoming predictions found",
                    "collected_at": datetime.now().isoformat(),
                    "database_status": "no_data"
                }
            ]

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error fetching predictions: {e}")
        return [
            {
                "fixture_id": 0,
                "fixture_date": datetime.now().isoformat(),
                "league_name": "Error",
                "winner_team_name": "Database query failed",
                "advice": f"Error: {str(e)}",
                "collected_at": datetime.now().isoformat(),
                "database_status": "error"
            }
        ]

@app.get("/api/v1/fixtures/upcoming")
async def get_fixtures(days_ahead: int = 1, limit: int = 10):
    """Real fixtures from database"""
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

    try:
        # Query real fixtures from database
        from app.models.fixtures import MatchFixtures
        from sqlalchemy import and_

        db = next(get_db())
        try:
            # Calculate date range
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            end_date = now + timedelta(days=days_ahead)

            # Query upcoming fixtures
            fixtures = db.query(MatchFixtures).filter(
                and_(
                    MatchFixtures.fixture_date >= now,
                    MatchFixtures.fixture_date <= end_date
                )
            ).order_by(MatchFixtures.fixture_date).limit(limit).all()

            # Format results
            result = []
            for fix in fixtures:
                result.append({
                    "fixture_id": fix.fixture_id,
                    "fixture_date": fix.fixture_date.isoformat(),
                    "league_name": fix.league_name,
                    "home_team": fix.home_team,
                    "away_team": fix.away_team,
                    "venue": fix.venue,
                    "status": fix.status,
                    "database_status": "real_data"
                })

            return result if result else [
                {
                    "fixture_id": 0,
                    "fixture_date": datetime.now().isoformat(),
                    "league_name": "No Data",
                    "home_team": "No fixtures available",
                    "away_team": "No fixtures available",
                    "venue": "N/A",
                    "status": "No Data",
                    "database_status": "no_data"
                }
            ]

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error fetching fixtures: {e}")
        return [
            {
                "fixture_id": 0,
                "fixture_date": datetime.now().isoformat(),
                "league_name": "Error",
                "home_team": "Database query failed",
                "away_team": "Database query failed",
                "venue": "N/A",
                "status": f"Error: {str(e)}",
                "database_status": "error"
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
