from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FIP Odds Tracker - SIMPLIFIED",
    description="Simplified version for testing",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "FIP Odds Tracker - SIMPLIFIED VERSION", "status": "running"}

@app.get("/api/v1/test")
async def test_endpoint():
    return {"test": "OK", "message": "Simplified version is working"}

@app.on_event("startup")
async def startup_event():
    logger.info("🔧 SIMPLIFIED VERSION STARTED")
    logger.info("✅ Testing basic functionality - no automatic jobs")
