"""config.py raises without DATABASE_URL, so the environment is set before anything imports app."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("FOOTBALL_API_KEY", "test-key")
