import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import datetime for cron scheduling
from datetime import datetime

# PRODUCTION APPROACH: Assume database schema exists
# Don't try to create tables - they should already be there
from app.core.database import init_database, get_db
from sqlalchemy import text

# Global database status
db_initialized = False
db_error_message = None

# Create FastAPI app - PRODUCTION VERSION
app = FastAPI(
    title="FIP Production - Existing Schema",
    description="Production version assuming existing database schema",
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
    """Root endpoint - responds immediately"""
    return {
        "message": "FIP Production - Existing Schema",
        "status": "running",
        "version": "2.0.0",
        "database": "existing_schema_assumed"
    }

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "version": "production-existing-schema",
        "database": "existing_schema_assumed",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/db-test")
async def db_test_endpoint():
    """Database connectivity test - just test connection, don't create tables"""
    global db_initialized, db_error_message
    
    if not db_initialized:
        try:
            logger.info("🔄 Testing database connection (assuming existing schema)...")
            # Just initialize engine connection - don't create tables
            engine = init_database()
            
            # Test connection immediately - no table operations
            db = next(get_db())
            result = db.execute(text("SELECT 1 as test")).fetchone()
            db.close()
            
            db_initialized = True
            logger.info("✅ Database connection successful (existing schema)")
            
            return {
                "database": "connected_existing_schema",
                "test_query": result[0] if result else "ok",
                "status": "success",
                "schema_handling": "existing_assumed"
            }
            
        except Exception as e:
            db_error_message = f"Database connection failed: {str(e)}"
            logger.error(f"❌ Database connection failed: {e}")
            return {
                "database": "connection_failed", 
                "error": db_error_message,
                "status": "failed"
            }
    
    # Database already initialized
    try:
        db = next(get_db())
        result = db.execute(text("SELECT 1 as test")).fetchone()
        db.close()
        
        return {
            "database": "already_connected",
            "test_query": result[0] if result else "ok",
            "status": "success",
            "schema_handling": "existing_assumed"
        }
    except Exception as e:
        return {
            "database": "connection_lost",
            "error": str(e),
            "status": "failed"
        }

# JOB ENDPOINTS - Assume database schema exists
@app.post("/api/v1/admin/job/results-check")
async def job_results_check():
    """Job D: Results checker - assumes database schema exists"""
    global db_initialized
    
    if not db_initialized:
        db_test = await db_test_endpoint()
        if db_test["status"] != "success":
            return {**db_test, "job": "results_check"}
    
    try:
        from app.services.cleanup_service import cleanup_service
        db = next(get_db())
        try:
            result = await cleanup_service.cleanup_finished_matches(db)
            return {
                "success": True,
                "job": "results_check",
                "message": "Results check completed",
                "matches_checked": result.get("matches_checked", 0),
                "finished_matches": result.get("finished_matches", 0),
                "accuracy_evaluations": result.get("accuracy_evaluations", 0),
                "timestamp": datetime.now().isoformat()
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ Job D failed: {str(e)}")
        return {"success": False, "job": "results_check", "error": str(e)}

@app.post("/api/v1/admin/job/predictions-update")
async def job_predictions_update():
    """Job B: Predictions update - assumes database schema exists"""
    global db_initialized
    
    if not db_initialized:
        db_test = await db_test_endpoint()
        if db_test["status"] != "success":
            return {**db_test, "job": "predictions_update"}
    
    try:
        from app.services.predictions_collector import predictions_collector
        db = next(get_db())
        try:
            result = await predictions_collector.collect_daily_predictions_only(db)
            return {
                "success": True,
                "job": "predictions_update",
                "message": "Predictions updated",
                "predictions_collected": result.get("predictions_collected", 0),
                "predictions_updated": result.get("predictions_updated", 0),
                "processed_fixtures": result.get("processed_count", 0),
                "timestamp": datetime.now().isoformat()
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ Job B failed: {str(e)}")
        return {"success": False, "job": "predictions_update", "error": str(e)}

# DATA ENDPOINTS - Assume database schema exists
@app.get("/api/v1/predictions/upcoming")
async def get_predictions(days_ahead: int = 1, limit: int = 10):
    """Predictions - assumes database schema exists"""
    global db_initialized
    
    if not db_initialized:
        db_test = await db_test_endpoint()
        if db_test["status"] != "success":
            return [{"database_status": "not_ready", "error": db_test.get("error")}]
    
    try:
        from app.models.predictions import MatchPredictions
        from sqlalchemy import and_
        from datetime import datetime, timedelta
        
        db = next(get_db())
        try:
            now = datetime.utcnow()
            end_date = now + timedelta(days=days_ahead)
            
            predictions = db.query(MatchPredictions).filter(
                and_(MatchPredictions.fixture_date >= now, MatchPredictions.fixture_date <= end_date)
            ).order_by(MatchPredictions.fixture_date).limit(limit).all()
            
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
            
            return result if result else [{"database_status": "no_data"}]
        finally:
            db.close()
    except Exception as e:
        return [{"database_status": "error", "error": str(e)}]

# Railway port configuration
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🚀 Starting FIP PRODUCTION version - existing schema assumed on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
