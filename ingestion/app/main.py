import os
import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import datetime for cron scheduling
from datetime import datetime

# PRODUCTION APPROACH: Create database schema if missing
from app.core.database import init_database, get_db
from sqlalchemy import text
from sqlalchemy.orm import Session

# Global database status
db_initialized = False
db_error_message = None

# Create FastAPI app - PRODUCTION VERSION
app = FastAPI(
    title="FIP Production - Auto Schema",
    description="Production version with automatic schema creation",
    version="2.0.1"
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
        "version": "production-auto-schema",
        "database": "auto_schema_create",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/db-test")
async def db_test_endpoint():
    """Database connectivity test - create schema if missing"""
    global db_initialized, db_error_message

    if not db_initialized:
        try:
            logger.info("🔄 Testing database connection and creating schema if needed...")
            # Initialize engine connection
            engine = init_database()

            # Test basic connection
            db = next(get_db())
            result = db.execute(text("SELECT 1 as test")).fetchone()

            # Try to create tables if they don't exist
            try:
                from app.models.odds_tracking import Base
                from app.models.predictions import MatchPredictions
                logger.info("📋 Creating database tables if missing...")
                Base.metadata.create_all(bind=engine)
                logger.info("✅ Database tables created/verified")
            except Exception as schema_error:
                logger.warning(f"⚠️ Schema creation issue: {schema_error}")

            db.close()

            db_initialized = True
            logger.info("✅ Database connection and schema setup successful")

            return {
                "database": "connected_with_schema",
                "test_query": result[0] if result else "ok",
                "status": "success",
                "schema_handling": "auto_create"
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

@app.post("/api/v1/migrate")
async def run_database_migration():
    """Run database migrations to update schema"""
    try:
        logger.info("Running database migrations...")
        import subprocess
        import sys
        import os

        # Get current working directory and check if alembic is available
        current_dir = os.getcwd()
        logger.info(f"Current working directory: {current_dir}")

        # Try to find alembic.ini
        alembic_ini_path = os.path.join(current_dir, "alembic.ini")
        if not os.path.exists(alembic_ini_path):
            return {
                "success": False,
                "error": f"alembic.ini not found at {alembic_ini_path}",
                "message": "Migration failed - alembic config not found"
            }

        # Run alembic upgrade head
        cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
        logger.info(f"Running command: {' '.join(cmd)} in {current_dir}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=current_dir
        )

        logger.info(f"Migration result code: {result.returncode}")
        logger.info(f"Migration stdout: {result.stdout}")
        logger.info(f"Migration stderr: {result.stderr}")

        if result.returncode == 0:
            return {
                "success": True,
                "message": "Database migrations completed successfully",
                "output": result.stdout,
                "directory": current_dir
            }
        else:
            return {
                "success": False,
                "error": result.stderr,
                "stdout": result.stdout,
                "message": "Migration failed",
                "directory": current_dir
            }
    except Exception as e:
        logger.error(f"Migration error: {e}")
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "message": "Migration failed with exception"
        }

@app.post("/api/v1/init-database")
async def init_database_schema():
    """Initialize the database schema by running the init script"""
    try:
        logger.info("Running database initialization script...")

        # Run the init_db.py script
        import subprocess
        import sys
        import os

        script_path = os.path.join(os.path.dirname(__file__), "init_db.py")
        logger.info(f"Running script: {script_path}")

        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__)
        )

        logger.info(f"Script exit code: {result.returncode}")
        logger.info(f"Script stdout: {result.stdout}")
        logger.info(f"Script stderr: {result.stderr}")

        if result.returncode == 0:
            return {
                "success": True,
                "message": "Database schema initialized successfully",
                "script_output": result.stdout,
                "script_path": script_path
            }
        else:
            return {
                "success": False,
                "error": result.stderr,
                "stdout": result.stdout,
                "message": "Database initialization script failed",
                "script_path": script_path
            }

    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "message": "Database initialization failed with exception"
        }

@app.post("/api/v1/fix-schema")
async def fix_database_schema(db: Session = Depends(get_db)):
    """Manually fix database schema by adding missing columns"""
    try:
        logger.info("Manually fixing database schema...")

        # Add missing columns to fixture_tracking_status table
        from sqlalchemy import text

        # Check if columns already exist and add them if missing
        alter_commands = [
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS league_id INTEGER",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS league_name VARCHAR(200)",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS country_name VARCHAR(100)",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS home_team VARCHAR(100)",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS away_team VARCHAR(100)",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS fixture_date TIMESTAMP",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS home_team_logo VARCHAR(500)",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS away_team_logo VARCHAR(500)",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS league_logo VARCHAR(500)",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS tracking_status VARCHAR(20) DEFAULT 'pending'",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS first_odds_collected_at TIMESTAMP",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS last_odds_collected_at TIMESTAMP",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS total_collections INTEGER DEFAULT 0",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS failed_collections INTEGER DEFAULT 0",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS available_markets JSON",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS bookmakers_found JSON",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE fixture_tracking_status ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "CREATE INDEX IF NOT EXISTS ix_fixture_tracking_status_league_id ON fixture_tracking_status(league_id)",
            "CREATE INDEX IF NOT EXISTS ix_fixture_tracking_status_fixture_date ON fixture_tracking_status(fixture_date)",
            "CREATE INDEX IF NOT EXISTS ix_fixture_tracking_status_tracking_status ON fixture_tracking_status(tracking_status)"
        ]

        executed_commands = []
        for cmd in alter_commands:
            try:
                logger.info(f"Executing: {cmd}")
                db.execute(text(cmd))
                executed_commands.append(cmd)
            except Exception as cmd_error:
                logger.warning(f"Command failed (might already exist): {cmd} - {cmd_error}")
                executed_commands.append(f"FAILED: {cmd}")

        # Also add fixture_date column to match_predictions if missing
        prediction_commands = [
            "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS fixture_date TIMESTAMP",
            "CREATE INDEX IF NOT EXISTS idx_predictions_fixture_date ON match_predictions(fixture_date)"
        ]

        for cmd in prediction_commands:
            try:
                logger.info(f"Executing: {cmd}")
                db.execute(text(cmd))
                executed_commands.append(cmd)
            except Exception as cmd_error:
                logger.warning(f"Command failed (might already exist): {cmd} - {cmd_error}")
                executed_commands.append(f"FAILED: {cmd}")

        db.commit()

        return {
            "success": True,
            "message": "Database schema fixed successfully",
            "executed_commands": executed_commands
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Schema fix error: {e}")
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "message": "Schema fix failed"
        }

# Railway port configuration
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🚀 Starting FIP PRODUCTION version - existing schema assumed on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
