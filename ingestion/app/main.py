import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FIP Odds Tracker - PHASE 2C",
    description="Complete API structure with sample data",
    version="2.2.0"
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
        "version": "2.2.0 - Phase 2C: Complete API structure",
        "mode": "Railway cron"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "phase-2c"}

# Job endpoints (gradual addition)
@app.post("/api/v1/admin/job/results-check")
async def job_results_check():
    """Job D: Results checker"""
    return {
        "success": True,
        "message": "Results check completed",
        "matches_checked": 5,
        "timestamp": "2025-11-16T15:00:00Z"
    }

@app.post("/api/v1/admin/job/odds-update")
async def job_odds_update():
    """Job C: Odds update"""
    return {
        "success": True,
        "message": "Odds update completed",
        "odds_collected": 25,
        "fixtures_processed": 8
    }

# Data endpoints (sample data for testing)
@app.get("/api/v1/predictions/upcoming")
async def get_predictions(days_ahead: int = 1, limit: int = 10):
    """Get upcoming predictions (sample data)"""
    sample_predictions = [
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
        },
        {
            "fixture_id": 12347,
            "home_team": "Barcelona",
            "away_team": "Real Madrid",
            "match_date": "2025-11-18T21:00:00Z",
            "prediction": "Draw",
            "prediction_advice": "Historically close matches between these rivals",
            "confidence": 0.68,
            "collected_at": "2025-11-16T14:30:00Z"
        }
    ]
    return sample_predictions[:limit]

@app.get("/api/v1/fixtures/upcoming")
async def get_fixtures(days_ahead: int = 1, limit: int = 10):
    """Get upcoming fixtures (sample data)"""
    sample_fixtures = [
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
        },
        {
            "fixture_id": 12347,
            "home_team": "Barcelona",
            "away_team": "Real Madrid",
            "league": "La Liga",
            "match_date": "2025-11-18T21:00:00Z",
            "venue": "Camp Nou",
            "status": "Not Started"
        }
    ]
    return sample_fixtures[:limit]

# Test endpoint with updated endpoint list
@app.get("/api/v1/test")
async def test_endpoint():
    return {
        "test": "OK",
        "message": "Phase 2C API working - Complete endpoint structure with sample data",
        "available_endpoints": [
            "/", "/health", "/api/v1/test",
            "/api/v1/admin/job/results-check",
            "/api/v1/admin/job/odds-update",
            "/api/v1/predictions/upcoming",
            "/api/v1/fixtures/upcoming"
        ]
    }

# Railway port configuration
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Starting essential server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
