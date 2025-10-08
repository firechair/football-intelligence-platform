# Import all models to ensure they are registered with SQLAlchemy
from app.db.models import User, Session
# from .chat_memory import ChatMemory  # Only Pydantic models, no SQLAlchemy
# from .match import Match  # Only Pydantic models, no SQLAlchemy
# from .research import Research  # Only Pydantic models, no SQLAlchemy
from .match_predictions import MatchPrediction

# Export all models
__all__ = [
    "User",
    "Session",
    # "ChatMemory",  # Only Pydantic models
    # "Match",  # Only Pydantic models
    # "Research",  # Only Pydantic models
    "MatchPrediction"
]
