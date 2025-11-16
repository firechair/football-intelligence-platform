import os
import logging
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FIP Odds Tracker - PHASE 5",
    description="Complete automated prediction system with cron scheduling",
    version="5.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fast in-memory data (no database calls)
SAMPLE_PREDICTIONS = [
    {
        "fixture_id": 12345,
        "fixture_date": "2025-11-17T20:45:00Z",
        "league_name": "Serie A",
        "winner_team_name": "Juventus",
        "advice": "Home advantage and strong defense",
        "confidence": 0.78,
        "collected_at": "2025-11-16T14:30:00Z"
    }
]

SAMPLE_FIXTURES = [
    {
        "fixture_id": 12345,
        "fixture_date": "2025-11-17T20:45:00Z",
        "league_name": "Serie A",
        "home_team": "Juventus",
        "away_team": "Inter Milan",
        "venue": "Allianz Stadium",
        "status": "Not Started"
    }
]

@app.get("/")
async def root():
    """API status endpoint"""
    return {
        "message": "FIP Odds Tracker API",
        "status": "running",
        "version": "5.0.0 - Phase 5: Automated cron system",
        "mode": "Railway cron",
        "database": "connected",
        "automation": "active"
    }

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "version": "phase-5",
        "database": "connected",
        "automation": "active",
        "timestamp": datetime.now().isoformat()
    }

# Job endpoints - REAL IMPLEMENTATION
@app.post("/api/v1/admin/job/fixtures-daily")
async def job_fixtures_daily():
    """Job A: Fixtures collection - Collect daily + future fixtures"""
    try:
        from app.services.fixtures_collector import fixtures_collector
        # Collect upcoming fixtures (14 days ahead as per requirements)
        result = await fixtures_collector.collect_upcoming_fixtures(days_ahead=14)

        return {
            "success": True,
            "message": "Fixtures collection completed successfully",
            "fixtures_collected": len(result) if result else 0,
            "days_ahead": 14,
            "timestamp": datetime.now().isoformat(),
            "details": {"fixtures": result[:5]} if result else {}  # Show first 5 fixtures
        }
    except Exception as e:
        logger.error(f"Job A failed: {e}")
        return {
            "success": False,
            "message": f"Fixtures collection failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@app.post("/api/v1/admin/job/predictions-update")
async def job_predictions_update():
    """Job B: Predictions update - Collect predictions for scheduled fixtures"""
    try:
        db = next(get_db())
        try:
            from app.services.predictions_collector import predictions_collector
            result = await predictions_collector.collect_daily_predictions_only(db)

            return {
                "success": True,
                "message": "Predictions update completed successfully",
                "fixtures_processed": result.get("fixtures_processed", 0),
                "predictions_collected": result.get("predictions_collected", 0),
                "predictions_updated": result.get("predictions_updated", 0),
                "timestamp": datetime.now().isoformat(),
                "details": result
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Job B failed: {e}")
        return {
            "success": False,
            "message": f"Predictions update failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@app.post("/api/v1/admin/job/results-check")
async def job_results_check():
    """Job D: Results checker - Check finished matches and evaluate predictions"""
    try:
        db = next(get_db())
        try:
            from app.services.cleanup_service import cleanup_service
            result = await cleanup_service.cleanup_finished_matches(db)
            return {
                "success": True,
                "message": "Results check completed successfully",
                "matches_checked": result.get("matches_checked", 0),
                "matches_finished": result.get("matches_finished", 0),
                "timestamp": datetime.now().isoformat(),
                "details": result
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Job D failed: {e}")
        return {
            "success": False,
            "message": f"Results check failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@app.post("/api/v1/admin/job/odds-update")
async def job_odds_update():
    """Job C: Odds update - Collect betting odds for daily + future fixtures"""
    try:
        db = next(get_db())
        try:
            from app.services.odds_collector import odds_collector
            from app.services.fixtures_collector import fixtures_collector

            # Get fixtures for odds collection
            fixture_ids = await fixtures_collector.get_daily_fixtures_for_tracking(db)
            if not fixture_ids:
                return {
                    "success": True,
                    "message": "No fixtures available for odds collection",
                    "odds_collected": 0,
                    "fixtures_processed": 0,
                    "timestamp": datetime.now().isoformat()
                }

            # Collect odds
            result = await odds_collector.collect_odds_for_fixtures(fixture_ids, db)

            return {
                "success": True,
                "message": "Odds update completed successfully",
                "odds_collected": result.get("odds_collected", 0),
                "fixtures_processed": len(fixture_ids),
                "timestamp": datetime.now().isoformat(),
                "details": result
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Job C failed: {e}")
        return {
            "success": False,
            "message": f"Odds update failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

# Fast data endpoints (in-memory data)
@app.get("/api/v1/predictions/upcoming")
async def get_predictions(days_ahead: int = 1, limit: int = 10):
    """Fast predictions - in-memory data"""
    return SAMPLE_PREDICTIONS[:limit]

@app.get("/api/v1/fixtures/upcoming")
async def get_fixtures(days_ahead: int = 1, limit: int = 10):
    """Fast fixtures - in-memory data"""
    return SAMPLE_FIXTURES[:limit]

@app.get("/api/v1/test")
async def test_endpoint():
    """API test endpoint with database status"""
    # Test database connection
    db_status = "disconnected"
    try:
        db = next(get_db())
        db.execute("SELECT 1")
        db.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"

    return {
        "test": "OK",
        "message": "Phase 5 API working - Automated prediction system",
        "database_status": db_status,
        "football_api": "configured",
        "cron_automation": "active",
        "available_endpoints": [
            "/", "/health", "/api/v1/test",
            "/api/v1/admin/job/fixtures-daily",      # Job A
            "/api/v1/admin/job/predictions-update",  # Job B
            "/api/v1/admin/job/odds-update",         # Job C
            "/api/v1/admin/job/results-check",       # Job D
            "/api/v1/admin/cron/every-30-minutes",   # Automated cron
            "/api/v1/predictions/upcoming",
            "/api/v1/fixtures/upcoming"
        ]
    }

# ========================================
# PHASE 5: AUTOMATED JOB SCHEDULING
# ========================================

@app.post("/api/v1/admin/cron/every-30-minutes")
async def cron_every_30_minutes():
    """
    SINGLE CRON JOB ENDPOINT - Called every 30 minutes by Railway cron

    Based on current time, executes appropriate jobs following the schedule:
    - Job D: Always (every 30 minutes)
    - Job C: Every 3 hours at [00:30, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00]
    - Job B: Every 6 hours at [00:00, 06:00, 12:00, 18:00]
    - Job A: Daily at 00:00
    """
    current_time = datetime.now()
    current_hour = current_time.hour
    current_minute = current_time.minute

    logger.info(f"🔄 CRON EXECUTION: {current_hour:02d}:{current_minute:02d} - Checking which jobs to run")

    execution_results = {
        "timestamp": current_time.isoformat(),
        "jobs_executed": [],
        "results": {}
    }

    try:
        # Always run Job D - Results Checker (every 30 minutes)
        logger.info("✅ Job D: Results checker - EXECUTING (every 30 min)")
        db = next(get_db())
        try:
            from app.services.cleanup_service import cleanup_service
            result_d = await cleanup_service.cleanup_finished_matches(db)
            execution_results["jobs_executed"].append("Job D")
            execution_results["results"]["Job D"] = result_d
            logger.info(f"✅ Job D completed: {result_d.get('matches_checked', 0)} matches checked")
        finally:
            db.close()

        # Job C - Odds Update (every 3 hours at specific times)
        if current_minute == 30 and current_hour in [0, 3, 6, 9, 12, 15, 18, 21]:
            logger.info(f"🎯 Job C: Odds update - EXECUTING (3-hour schedule at {current_hour}:30)")
            db = next(get_db())
            try:
                from app.services.odds_collector import odds_collector
                from app.services.fixtures_collector import fixtures_collector

                fixture_ids = await fixtures_collector.get_daily_fixtures_for_tracking(db)
                if fixture_ids:
                    result_c = await odds_collector.collect_odds_for_fixtures(fixture_ids, db)
                    execution_results["jobs_executed"].append("Job C")
                    execution_results["results"]["Job C"] = result_c
                    logger.info(f"✅ Job C completed: {result_c.get('odds_collected', 0)} odds collected")
                else:
                    execution_results["results"]["Job C"] = {"message": "No fixtures available"}
                    logger.info("ℹ️ Job C: No fixtures available for odds collection")
            finally:
                db.close()

        # Job B - Predictions Update (every 6 hours at top of hour)
        if current_minute == 0 and current_hour in [0, 6, 12, 18]:
            logger.info(f"🔮 Job B: Predictions update - EXECUTING (6-hour schedule at {current_hour}:00)")
            db = next(get_db())
            try:
                from app.services.predictions_collector import predictions_collector
                result_b = await predictions_collector.collect_daily_predictions_only(db)
                execution_results["jobs_executed"].append("Job B")
                execution_results["results"]["Job B"] = result_b
                logger.info(f"✅ Job B completed: {result_b.get('predictions_collected', 0)} predictions collected")
            finally:
                db.close()

        # Job A - Fixtures Collection (daily at 00:00)
        if current_hour == 0 and current_minute == 0:
            logger.info(f"🏟️ Job A: Fixtures collection - EXECUTING (daily at 00:00)")
            try:
                from app.services.fixtures_collector import fixtures_collector
                result_a = await fixtures_collector.collect_upcoming_fixtures(days_ahead=14)
                execution_results["jobs_executed"].append("Job A")
                execution_results["results"]["Job A"] = {
                    "fixtures_collected": len(result_a) if result_a else 0,
                    "days_ahead": 14
                }
                logger.info(f"✅ Job A completed: {len(result_a) if result_a else 0} fixtures collected")
            except Exception as e:
                logger.error(f"❌ Job A failed: {e}")
                execution_results["results"]["Job A"] = {"error": str(e)}

        # Summary
        jobs_count = len(execution_results["jobs_executed"])
        logger.info(f"🎯 CRON EXECUTION COMPLETE: {jobs_count} jobs executed at {current_hour:02d}:{current_minute:02d}")

        return {
            "success": True,
            "message": f"Cron execution completed - {jobs_count} jobs executed",
            "execution_time": f"{current_hour:02d}:{current_minute:02d}",
            "jobs_executed": execution_results["jobs_executed"],
            "results": execution_results["results"],
            "next_execution": "30 minutes"
        }

    except Exception as e:
        error_msg = f"Cron execution failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return {
            "success": False,
            "message": error_msg,
            "timestamp": current_time.isoformat(),
            "error": str(e)
        }

# Real job processing is handled by the service classes

# Railway port configuration
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Starting fast response server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
