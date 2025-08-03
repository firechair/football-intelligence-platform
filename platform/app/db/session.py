import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create the SQLAlchemy engine using the URL from the central settings
engine = create_engine(
    settings.DATABASE_URL, 
    # This argument is required for SQLite to allow multiple threads to access it,
    # which is what FastAPI does.
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) 

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 