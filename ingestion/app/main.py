import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FIP Odds Tracker - API PLACEHOLDERS",
    description="Full API structure with placeholder responses",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "FIP Odds Tracker API",
        "status": "running",
        "mode": "Railway cron",
        "version": "2.0.0 - API Placeholders"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "api-placeholders"}

# ========================================
# JOB ENDPOINTS - PLACEHOLDER RESPONSES
# ========================================

@app.post("/api/v1/admin/job/results-check")
async def job_results_check():
    """Job D: Results checker - Always runs every 30 min"""
    return {
        "success": True,
        "message": "Results check completed (placeholder)",
        "matches_checked": 5,
        "accuracy_updated": 3,
        "timestamp": "2025-11-16T15:00:00Z"
    }

@app.post("/api/v1/admin/job/odds-update")
async def job_odds_update():
    """Job C: Odds update - Every 3 hours"""
    return {
        "success": True,
        "message": "Odds update completed (placeholder)",
        "odds_collected": 25,
        "fixtures_processed": 8,
        "timestamp": "2025-11-16T15:00:00Z"
    }

@app.post("/api/v1/admin/job/fixtures-daily")
async def job_fixtures_daily():
    """Job A: Fixtures collection - Every 6 hours"""
    return {
        "success": True,
        "message": "Fixtures collection completed (placeholder)",
        "fixtures_collected": 15,
        "new_fixtures": 12,
        "timestamp": "2025-11-16T15:00:00Z"
    }

@app.post("/api/v1/admin/job/predictions-update")
async def job_predictions_update():
    """Job B: Predictions update - Every 6 hours"""
    return {
        "success": True,
        "message": "Predictions update completed (placeholder)",
        "predictions_collected": 30,
        "predictions_updated": 8,
        "timestamp": "2025-11-16T15:00:00Z"
    }

# ========================================
# DATA ENDPOINTS - SAMPLE RESPONSES
# ========================================

@app.get("/api/v1/predictions/upcoming")
async def get_predictions(days_ahead: int = 1, limit: int = 10):
    """Get upcoming predictions"""
    return [
        {
            "fixture_id": 12345,
            "home_team": "Juventus",
            "away_team": "Inter Milan",
            "match_date": "2025-11-17T20:45:00Z",
            "prediction": "Over 2.5 Goals",
            "prediction_advice": "Both teams have strong attacking lines",
            "confidence": 0.75,
            "collected_at": "2025-11-16T14:30:00Z"
        },
        {
            "fixture_id": 12346,
            "home_team": "Manchester City",
            "away_team": "Liverpool",
            "match_date": "2025-11-17T17:30:00Z",
            "prediction": "Manchester City to win",
            "prediction_advice": "Home advantage and better form",
            "confidence": 0.82,
            "collected_at": "2025-11-16T14:30:00Z"
        }
    ][:limit]

@app.get("/api/v1/fixtures/upcoming")
async def get_fixtures(days_ahead: int = 1, limit: int = 10):
    """Get upcoming fixtures"""
    return [
        {
            "fixture_id": 12345,
            "home_team": "Juventus",
            "away_team": "Inter Milan",
            "league": "Serie A",
            "match_date": "2025-11-17T20:45:00Z",
            "venue": "Allianz Stadium",
            "status": "Not Started"
        },
        {
            "fixture_id": 12346,
            "home_team": "Manchester City",
            "away_team": "Liverpool",
            "league": "Premier League",
            "match_date": "2025-11-17T17:30:00Z",
            "venue": "Etihad Stadium",
            "status": "Not Started"
        }
    ][:limit]

@app.get("/api/v1/test")
async def test_endpoint():
    """Test endpoint to verify API is working"""
    return {
        "test": "OK",
        "message": "API is functioning correctly",
        "endpoints_available": [
            "/api/v1/admin/job/results-check",
            "/api/v1/admin/job/odds-update", 
            "/api/v1/admin/job/fixtures-daily",
            "/api/v1/admin/job/predictions-update",
            "/api/v1/predictions/upcoming",
            "/api/v1/fixtures/upcoming"
        ]
    }

# Railway port configuration
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Starting API placeholder server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
