import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import accuracy, fixtures as fixtures_api, assets as assets_api

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import datetime for cron scheduling
from datetime import datetime

# PRODUCTION APPROACH: Create database schema if missing
from app.core.database import init_database, get_db
from app.core.config import settings
from app.core.scheduler import scheduler
from sqlalchemy import text

# Global database status
db_initialized = False
db_error_message = None

"""
FIP Operator - Main Application
Version: 2025.11.30 - Accuracy System Fix Deployed
"""
# Initialize database immediately on startup
logger.info("🚀 Initializing database on application startup...")
try:
    engine = init_database()
    db_initialized = True
    logger.info("✅ Database initialized successfully on startup")

    # Run schema fix automatically on startup
    logger.info("🔧 Running automatic schema fix...")
    try:
        from sqlalchemy import create_engine, text

        # Use the same database URL that was just initialized
        database_url = settings.DATABASE_URL
        engine_fix = create_engine(database_url)

        with engine_fix.connect() as conn:
            # Check if we have the correct modern schema (with proper column names)
            required_columns = [
                'league_name', 'winner_team_id', 'winner_team_name', 'winner_comment',
                'win_or_draw', 'under_over', 'goals_home', 'goals_away', 'advice',
                'percent_home', 'percent_draw', 'percent_away', 'is_prediction_available'
            ]

            existing_columns_result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'match_predictions'
            """))
            existing_columns = [row[0] for row in existing_columns_result.fetchall()]

            missing_columns = [col for col in required_columns if col not in existing_columns]

            if missing_columns:
                logger.info(f"📋 Adding missing columns to match_predictions table: {missing_columns}")

                # Add missing columns with proper names
                columns_to_add = [
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS league_name VARCHAR(200)",
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS winner_team_id INTEGER",
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS winner_team_name VARCHAR(100)",
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS winner_comment VARCHAR(100)",
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS win_or_draw BOOLEAN",
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS under_over VARCHAR(10)",
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS goals_home VARCHAR(10)",
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS goals_away VARCHAR(10)",
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS advice TEXT",
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS percent_home VARCHAR(10)",
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS percent_draw VARCHAR(10)",
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS percent_away VARCHAR(10)",
                    "ALTER TABLE match_predictions ADD COLUMN IF NOT EXISTS is_prediction_available BOOLEAN DEFAULT TRUE"
                ]

                for sql in columns_to_add:
                    try:
                        conn.execute(text(sql))
                        logger.info(f"✅ Executed: {sql.split('ADD COLUMN')[1].strip()}")
                    except Exception as col_e:
                        logger.warning(f"⚠️  Column might already exist: {col_e}")

                # Create indexes
                indexes_to_create = [
                    "CREATE INDEX IF NOT EXISTS idx_predictions_fixture_date ON match_predictions(fixture_date)",
                    "CREATE INDEX IF NOT EXISTS idx_predictions_league_id ON match_predictions(league_id)",
                    "CREATE INDEX IF NOT EXISTS idx_predictions_winner_team_id ON match_predictions(winner_team_id)",
                    "CREATE INDEX IF NOT EXISTS idx_predictions_available ON match_predictions(is_prediction_available)"
                ]

                for sql in indexes_to_create:
                    try:
                        conn.execute(text(sql))
                        logger.info(f"✅ Created index: {sql.split(' ON ')[1].split('(')[0]}")
                    except Exception as idx_e:
                        logger.warning(f"⚠️  Index might already exist: {idx_e}")

                conn.commit()
                logger.info("🎉 Schema fix completed successfully!")
            else:
                logger.info("✅ Schema already up to date - all required columns present")

    except Exception as fix_e:
        logger.warning(f"⚠️  Schema fix failed, but continuing: {fix_e}")

    # Start the data collection scheduler on startup
    logger.info("🚀 Starting data collection scheduler...")
    try:
        # Run scheduler in background task (non-blocking)
        import asyncio
        asyncio.create_task(scheduler.start())
        
        # 🚫 DISABLED: Live Odds Monitor (to avoid hitting daily API limits)
        # asyncio.create_task(live_odds_monitor.start())
        
        logger.info("✅ Data collection scheduler started successfully")
        logger.info("⚠️  Live Odds Monitor DISABLED (to preserve API limits)")
    except Exception as sched_e:
        logger.warning(f"⚠️  Scheduler failed to start: {sched_e}")

except Exception as e:
    db_error_message = str(e)
    logger.error(f"❌ Database initialization failed on startup: {e}")

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

# Include routers
app.include_router(accuracy.router, prefix="/api/v1/accuracy", tags=["accuracy"])
app.include_router(fixtures_api.router, prefix="/api/v1")
app.include_router(assets_api.router, prefix="/api/v1")

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

async def db_test_endpoint() -> dict:
    """Database connectivity test - create schema if missing. Internal, no longer a route."""
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
        from datetime import datetime, timedelta
        
        db = next(get_db())
        try:
            now = datetime.utcnow()
            end_date = now + timedelta(days=days_ahead)

            # Use raw SQL to match database column names (check both old and new columns)
            from sqlalchemy import text
            query = text("""
                SELECT
                    fixture_id,
                    fixture_date,
                    COALESCE(winner_team_name, prediction_winner, '') as winner_team_name,
                    COALESCE(advice, prediction_advice, '') as advice,
                    COALESCE(collected_at, created_at, updated_at) as collected_at,
                    COALESCE(is_prediction_available, true) as is_prediction_available
                FROM match_predictions
                WHERE fixture_date >= :fixture_date_1 AND fixture_date <= :fixture_date_2
                ORDER BY fixture_date
                LIMIT :param_1
            """)

            predictions = db.execute(query, {
                "fixture_date_1": now,
                "fixture_date_2": end_date,
                "param_1": limit
            }).fetchall()

            result = []
            for pred in predictions:
                result.append({
                    "fixture_id": pred[0],
                    "fixture_date": pred[1].isoformat() if pred[1] else None,
                    "winner_team_name": pred[2],
                    "advice": pred[3],
                    "collected_at": pred[4].isoformat() if pred[4] else None,
                    "is_prediction_available": pred[5],
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
