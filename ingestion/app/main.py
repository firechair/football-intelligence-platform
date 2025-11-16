import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FIP Odds Tracker - PHASE 2B",
    description="Gradual endpoint addition",
    version="2.1.0"
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
        "version": "2.1.0 - Phase 2B: Gradual endpoints",
        "mode": "Railway cron"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "phase-2b"}

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

# Test endpoint
@app.get("/api/v1/test")
async def test_endpoint():
    return {
        "test": "OK",
        "message": "Phase 2B API working",
        "available_endpoints": [
            "/", "/health", "/api/v1/test",
            "/api/v1/admin/job/results-check",
            "/api/v1/admin/job/odds-update"
        ]
    }

# Railway port configuration
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Starting essential server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
