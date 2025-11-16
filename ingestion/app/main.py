import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app - DIAGNOSTIC VERSION
app = FastAPI(
    title="FIP Diagnostic - NO DATABASE",
    description="Diagnostic version without database dependencies",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# No sample data needed for diagnostic version

@app.get("/")
async def root():
    """Simple root endpoint"""
    return {
        "message": "FIP Diagnostic - NO DATABASE",
        "status": "running",
        "version": "0.1.0",
        "database": "disabled"
    }

@app.get("/health")
async def health():
    """Simple health check"""
    return {
        "status": "healthy",
        "version": "diagnostic",
        "database": "disabled"
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

# Simple data endpoints
@app.get("/api/v1/predictions/upcoming")
async def get_predictions(days_ahead: int = 1, limit: int = 10):
    """Simple predictions response"""
    return [
        {
            "fixture_id": 12345,
            "fixture_date": "2025-11-17T20:45:00Z",
            "league_name": "Serie A",
            "winner_team_name": "Juventus",
            "advice": "Sample data - database disabled",
            "collected_at": "2025-11-16T14:30:00Z"
        }
    ]

@app.get("/api/v1/fixtures/upcoming")
async def get_fixtures(days_ahead: int = 1, limit: int = 10):
    """Simple fixtures response"""
    return [
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

@app.get("/api/v1/test")
async def test_endpoint():
    """Simple test endpoint"""
    return {
        "test": "OK",
        "message": "Diagnostic API working - database disabled",
        "database_status": "disabled",
        "available_endpoints": [
            "/", "/health", "/api/v1/test",
            "/api/v1/admin/job/fixtures-daily",
            "/api/v1/admin/job/predictions-update",
            "/api/v1/admin/job/odds-update",
            "/api/v1/admin/job/results-check",
            "/api/v1/predictions/upcoming",
            "/api/v1/fixtures/upcoming"
        ]
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
