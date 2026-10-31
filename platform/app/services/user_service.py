from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from app.db import models

def update_user_profile(
    db: Session, 
    user: models.User, 
    full_name: Optional[str], 
    preferences: Optional[Dict[str, Any]]
) -> models.User:
    """
    Updates a user's profile information.
    """
    updated = False
    if full_name is not None and user.full_name != full_name:
        user.full_name = full_name
        updated = True
    
    if preferences is not None and user.preferences != preferences:
        # This basic check doesn't cover deep equality, but it's a start.
        # For more complex preference structures, a better merge strategy might be needed.
        user.preferences = preferences
        updated = True

    if updated:
        db.add(user)
        db.commit()
        db.refresh(user)
        
    return user 