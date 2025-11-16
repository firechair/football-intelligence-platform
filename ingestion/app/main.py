import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FIP Diagnostic",
    description="Diagnostic version without database",
    version="3.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Diagnostic startup - no database connection")
    logger.info("✅ Service should stay online")

@app.get("/")
async def root():
    return {
        "message": "FIP Diagnostic API",
        "status": "running",
        "version": "3.1.0 - Diagnostic (no database)",
        "database": "disabled for testing"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "diagnostic", "database": "disabled"}

@app.get("/api/v1/test")
async def test_endpoint():
    return {
        "test": "OK",
        "message": "Diagnostic mode - no database connection",
        "database_status": "disabled",
        "available_endpoints": ["/", "/health", "/api/v1/test"]
    }

# Railway port configuration
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Starting diagnostic server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
