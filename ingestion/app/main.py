import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FIP Odds Tracker - ESSENTIAL",
    description="Essential endpoints only",
    version="1.5.0"
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
        "version": "1.5.0 - Essential endpoints",
        "mode": "Railway cron"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "essential"}

# Only add ONE job endpoint to test
@app.post("/api/v1/admin/job/results-check")
async def job_results_check():
    """Job D: Results checker - Always runs every 30 min"""
    return {
        "success": True,
        "message": "Results check completed (placeholder)",
        "matches_checked": 5,
        "timestamp": "2025-11-16T15:00:00Z"
    }

# Only add ONE data endpoint to test
@app.get("/api/v1/test")
async def test_endpoint():
    """Test endpoint to verify API is working"""
    return {
        "test": "OK",
        "message": "Essential API is functioning correctly",
        "available_endpoints": [
            "/",
            "/health",
            "/api/v1/test",
            "/api/v1/admin/job/results-check"
        ]
    }

# Railway port configuration
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Starting essential server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
