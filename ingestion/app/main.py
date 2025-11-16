import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FIP Odds Tracker - MINIMAL",
    description="Minimal working version for Railway deployment",
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

@app.get("/")
async def root():
    return {"message": "FIP Odds Tracker - MINIMAL VERSION", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "minimal"}

# Railway port configuration
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Starting minimal server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
