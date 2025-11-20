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
from app.core.config import settings
from app.core.scheduler import scheduler
from sqlalchemy import text
from sqlalchemy.orm import Session

# Global database status
db_initialized = False
db_error_message = None

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
        logger.info("✅ Data collection scheduler started successfully")
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

            # Use raw SQL to avoid schema issues - match actual database column names
            from sqlalchemy import text
            query = text("""
                SELECT
                    fixture_id,
                    fixture_date,
                    prediction_winner as winner_team_name,
                    prediction_advice as advice,
                    created_at as collected_at,
                    1 as is_prediction_available
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

@app.get("/api/v1/debug-fixtures")
async def debug_fixture_collection():
    """Debug the fixture collection process step by step"""
    try:
        from app.services.fixtures_collector import fixtures_collector
        from app.utils.football_api import football_api

        debug_info = {
            "step1_api_available": True,
            "step2_fixture_collection": False,
            "step3_database_save": False
        }

        # Step 1: Test if we can call the API
        try:
            test_fixtures = await football_api.get_fixtures_by_date_range("2025-11-18", "2025-11-18")
            debug_info["step1_api_result"] = f"Got {len(test_fixtures)} fixtures from API"
            debug_info["step1_api_available"] = len(test_fixtures) > 0
        except Exception as e:
            debug_info["step1_api_result"] = f"API call failed: {str(e)}"
            debug_info["step1_api_available"] = False

        # Step 2: Test fixture collection
        if debug_info["step1_api_available"]:
            try:
                collected = await fixtures_collector.collect_upcoming_fixtures(days_ahead=1)
                debug_info["step2_fixture_collection"] = True
                debug_info["step2_result"] = f"Collected {len(collected)} upcoming fixtures"
            except Exception as e:
                debug_info["step2_result"] = f"Collection failed: {str(e)}"

        # Step 3: Test database save (if we have fixtures)
        if debug_info.get("step2_fixture_collection"):
            try:
                # Initialize database if not already done
                from app.core.database import init_database, SessionLocal
                debug_info["step3_init_check"] = f"SessionLocal is None: {SessionLocal is None}"

                if SessionLocal is None:
                    debug_info["step3_init_attempt"] = "Calling init_database()"
                    try:
                        engine = init_database()
                        debug_info["step3_init_result"] = f"Engine created: {engine is not None}"
                        debug_info["step3_sessionlocal_check"] = f"SessionLocal after init: {SessionLocal is not None}"
                    except Exception as init_error:
                        debug_info["step3_init_error"] = str(init_error)
                        raise
                else:
                    debug_info["step3_init_result"] = "SessionLocal already initialized"

                db = SessionLocal()
                fixtures_collector.update_tracking_status(collected, db)
                db.commit()
                debug_info["step3_database_save"] = True
                debug_info["step3_result"] = f"Saved {len(collected)} fixtures to database"
                db.close()
            except Exception as e:
                debug_info["step3_result"] = f"Database save failed: {str(e)}"
                import traceback
                debug_info["step3_traceback"] = traceback.format_exc()

        return {
            "success": debug_info["step1_api_available"] and debug_info["step2_fixture_collection"] and debug_info["step3_database_save"],
            "debug_info": debug_info,
            "message": "Fixture collection debug completed"
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "message": "Debug process failed"
        }

@app.get("/api/v1/test-api")
async def test_api_connection():
    """Test the football API connection"""
    try:
        import httpx
        from app.core.config import settings

        # Test direct API call
        headers = {"x-apisports-key": settings.FOOTBALL_API_KEY}
        url = f"{settings.FOOTBALL_API_BASE_URL}/fixtures"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params={"date": "2025-11-18"})
            response.raise_for_status()
            data = response.json()

        return {
            "success": True,
            "message": "API connection successful",
            "fixtures_count": len(data.get("response", [])),
            "api_key_configured": bool(settings.FOOTBALL_API_KEY),
            "api_key_prefix": settings.FOOTBALL_API_KEY[:10] + "..." if settings.FOOTBALL_API_KEY else None,
            "base_url": settings.FOOTBALL_API_BASE_URL,
            "response_keys": list(data.keys()) if isinstance(data, dict) else "not_dict"
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "message": "API connection failed",
            "api_key_configured": bool(settings.FOOTBALL_API_KEY),
            "base_url": settings.FOOTBALL_API_BASE_URL
        }

@app.post("/api/v1/recreate-tables")
async def recreate_tables(db: Session = Depends(get_db)):
    """Drop and recreate all tables with correct schema"""
    try:
        logger.info("Recreating database tables with correct schema...")

        # Drop existing tables if they exist
        from sqlalchemy import text

        drop_commands = [
            "DROP TABLE IF EXISTS fixture_tracking_status CASCADE",
            "DROP TABLE IF EXISTS match_predictions CASCADE",
            "DROP TABLE IF EXISTS extended_odds_history CASCADE",
            "DROP TABLE IF EXISTS bookmaker_info CASCADE"
        ]

        for cmd in drop_commands:
            try:
                logger.info(f"Executing: {cmd}")
                db.execute(text(cmd))
            except Exception as e:
                logger.warning(f"Drop command failed: {cmd} - {e}")

        # Create tables with correct schema
        from app.models.odds_tracking import Base
        from app.models.predictions import MatchPredictions

        logger.info("Creating tables with correct schema...")
        Base.metadata.create_all(bind=db.bind)

        # Verify tables were created
        tables_created = []
        test_queries = [
            ("fixture_tracking_status", "SELECT COUNT(*) FROM fixture_tracking_status"),
            ("match_predictions", "SELECT COUNT(*) FROM match_predictions"),
            ("extended_odds_history", "SELECT COUNT(*) FROM extended_odds_history"),
            ("bookmaker_info", "SELECT COUNT(*) FROM bookmaker_info")
        ]

        for table_name, query in test_queries:
            try:
                result = db.execute(text(query)).scalar()
                tables_created.append(f"✅ {table_name}: {result} rows")
            except Exception as e:
                tables_created.append(f"❌ {table_name}: ERROR - {e}")

        db.commit()

        return {
            "success": True,
            "message": "Database tables recreated with correct schema",
            "tables_created": tables_created
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Table recreation error: {e}")
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "message": "Table recreation failed"
        }

@app.get("/api/v1/check-predictions-schema")
async def check_predictions_schema(db: Session = Depends(get_db)):
    """Check what columns exist in match_predictions table"""
    try:
        from sqlalchemy import text

        # Check what columns exist in match_predictions table
        result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'match_predictions' ORDER BY column_name"))
        columns = [row[0] for row in result.fetchall()]

        # Check if we have any predictions
        predictions_count = db.execute(text("SELECT COUNT(*) FROM match_predictions")).scalar()

        return {
            "success": True,
            "match_predictions_columns": columns,
            "predictions_count": predictions_count,
            "missing_columns": [col for col in ['league_id', 'league_name', 'fixture_date'] if col not in columns]
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.post("/api/v1/fix-schema")
async def fix_database_schema(db: Session = Depends(get_db)):
    """Manually fix database schema by adding missing columns"""
    try:
        logger.info("Manually fixing database schema...")

        # Try individual ALTER TABLE commands for PostgreSQL compatibility
        from sqlalchemy import text

        # First check what columns exist
        try:
            result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'fixture_tracking_status'"))
            existing_columns = [row[0] for row in result.fetchall()]
            logger.info(f"Existing columns in fixture_tracking_status: {existing_columns}")
        except Exception as e:
            logger.warning(f"Could not check existing columns: {e}")
            existing_columns = []

        # Add missing columns individually
        columns_to_add = {
            'league_id': 'INTEGER',
            'league_name': 'VARCHAR(200)',
            'country_name': 'VARCHAR(100)',
            'home_team': 'VARCHAR(100)',
            'away_team': 'VARCHAR(100)',
            'fixture_date': 'TIMESTAMP',
            'home_team_logo': 'VARCHAR(500)',
            'away_team_logo': 'VARCHAR(500)',
            'league_logo': 'VARCHAR(500)',
            'tracking_status': "VARCHAR(20) DEFAULT 'pending'",
            'first_odds_collected_at': 'TIMESTAMP',
            'last_odds_collected_at': 'TIMESTAMP',
            'total_collections': 'INTEGER DEFAULT 0',
            'failed_collections': 'INTEGER DEFAULT 0',
            'available_markets': 'JSON',
            'bookmakers_found': 'JSON',
            'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }

        executed_commands = []
        for column_name, column_type in columns_to_add.items():
            if column_name not in existing_columns:
                cmd = f"ALTER TABLE fixture_tracking_status ADD COLUMN {column_name} {column_type}"
                try:
                    logger.info(f"Executing: {cmd}")
                    db.execute(text(cmd))
                    executed_commands.append(cmd)
                except Exception as cmd_error:
                    logger.warning(f"Command failed: {cmd} - {cmd_error}")
                    executed_commands.append(f"FAILED: {cmd}")

        # Create indexes
        index_commands = [
            "CREATE INDEX IF NOT EXISTS ix_fixture_tracking_status_league_id ON fixture_tracking_status(league_id)",
            "CREATE INDEX IF NOT EXISTS ix_fixture_tracking_status_fixture_date ON fixture_tracking_status(fixture_date)",
            "CREATE INDEX IF NOT EXISTS ix_fixture_tracking_status_tracking_status ON fixture_tracking_status(tracking_status)"
        ]

        for cmd in index_commands:
            try:
                logger.info(f"Executing: {cmd}")
                db.execute(text(cmd))
                executed_commands.append(cmd)
            except Exception as cmd_error:
                logger.warning(f"Index creation failed: {cmd} - {cmd_error}")

        # Also check and fix match_predictions table
        try:
            # Check what columns exist in match_predictions
            pred_result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'match_predictions'"))
            pred_columns = [row[0] for row in pred_result.fetchall()]

            # Add missing columns to match_predictions
            pred_columns_to_add = {
                'league_id': 'INTEGER',
                'league_name': 'VARCHAR(200)',
                'fixture_date': 'TIMESTAMP',
                'winner_team_id': 'INTEGER',
                'winner_team_name': 'VARCHAR(100)',
                'winner_comment': 'VARCHAR(100)',
                'win_or_draw': 'BOOLEAN',
                'under_over': 'VARCHAR(10)',
                'goals_home': 'VARCHAR(10)',
                'goals_away': 'VARCHAR(10)',
                'advice': 'TEXT',
                'percent_home': 'VARCHAR(10)',
                'percent_draw': 'VARCHAR(10)',
                'percent_away': 'VARCHAR(10)',
                'collected_at': 'TIMESTAMP',
                'is_prediction_available': 'BOOLEAN DEFAULT TRUE'
            }

            for col_name, col_type in pred_columns_to_add.items():
                if col_name not in pred_columns:
                    cmd = f"ALTER TABLE match_predictions ADD COLUMN {col_name} {col_type}"
                    try:
                        db.execute(text(cmd))
                        executed_commands.append(f"match_predictions: {cmd}")
                        logger.info(f"Added column {col_name} to match_predictions")
                    except Exception as col_error:
                        executed_commands.append(f"FAILED match_predictions {col_name}: {col_error}")
                        logger.warning(f"Failed to add {col_name} to match_predictions: {col_error}")

            # Create indexes for match_predictions
            pred_indexes = [
                "CREATE INDEX IF NOT EXISTS idx_predictions_fixture_date ON match_predictions(fixture_date)",
                "CREATE INDEX IF NOT EXISTS idx_predictions_league_id ON match_predictions(league_id)",
                "CREATE INDEX IF NOT EXISTS idx_predictions_winner_team_id ON match_predictions(winner_team_id)",
                "CREATE INDEX IF NOT EXISTS idx_predictions_available ON match_predictions(is_prediction_available)"
            ]

            for idx_cmd in pred_indexes:
                try:
                    db.execute(text(idx_cmd))
                    executed_commands.append(f"match_predictions: {idx_cmd}")
                    logger.info(f"Created index: {idx_cmd}")
                except Exception as idx_error:
                    logger.warning(f"Failed to create index {idx_cmd}: {idx_error}")

        except Exception as pred_error:
            executed_commands.append(f"match_predictions schema check failed: {pred_error}")
            logger.warning(f"match_predictions schema check failed: {pred_error}")

        db.commit()

        return {
            "success": True,
            "message": "Database schema fixed successfully",
            "executed_commands": executed_commands,
            "existing_columns": existing_columns
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
