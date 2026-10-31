from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create the SQLAlchemy engine using the URL from the central settings
db_url = settings.DATABASE_URL

# Apply SQLite-specific connect args only when using SQLite
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) 

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 