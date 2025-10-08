from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, func, JSON, Boolean, DECIMAL, Index
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    hashed_password = Column(String(128), nullable=False)
    full_name = Column(String(120), nullable=True)
    preferences = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # 2FA fields
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(255), nullable=True)
    backup_codes = Column(JSON, nullable=True)
    
    # Email verification fields  
    email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String(255), nullable=True)
    email_verification_expires = Column(DateTime, nullable=True)
    
    # Password recovery fields
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    
    chat_conversations = relationship("ChatConversation", back_populates="user")

class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=True)  # Titolo generato automaticamente
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True, index=True)
    
    # Relationship
    user = relationship("User", back_populates="chat_conversations")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    message_metadata = Column(JSON, nullable=True)  # Per salvare intent, confidence, etc.
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationship
    conversation = relationship("ChatConversation", back_populates="messages") 

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(String(512), nullable=False)
    start_time = Column(DateTime, nullable=False)
    is_live = Column(Boolean, default=False)
    category = Column(JSON, nullable=True) # E.g., ["Calcio", "Italia", "Serie A"]
    manifestazione = Column(String(255), nullable=True)
    raw_data = Column(JSON, nullable=False) # Store the full event JSON from the API
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now()) 

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_jti = Column(String(255), unique=True, nullable=False, index=True)
    device_info = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)  # Support both IPv4 and IPv6
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    last_activity = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    termination_reason = Column(String(100), nullable=True)
    
    # Relationship
    user = relationship("User", backref="sessions")

# New models for intelligent odds and bookmaker analytics

class BookmakerStats(Base):
    __tablename__ = "bookmaker_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    bookmaker = Column(String(100), nullable=False, index=True)
    sport = Column(String(50), nullable=False, index=True)
    league = Column(String(200), nullable=True)
    market_type = Column(String(100), nullable=False, index=True)
    best_odds_count = Column(Integer, default=0)
    total_markets = Column(Integer, default=0)
    win_percentage = Column(DECIMAL(5,2), nullable=True)
    average_margin = Column(DECIMAL(5,3), nullable=True)
    consistency_score = Column(DECIMAL(3,2), nullable=True)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())

class OddsHistory(Base):
    __tablename__ = "odds_history"
    
    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, nullable=False, index=True)
    market_name = Column(String(100), nullable=False)
    market_type = Column(String(50), nullable=True, index=True)  # "1x2", "over_under", "both_teams_to_score", etc.
    bookmaker = Column(String(100), nullable=False, index=True)
    bookmaker_id = Column(Integer, nullable=True, index=True)
    odd_value = Column(DECIMAL(8,3), nullable=False)
    timestamp = Column(DateTime, server_default=func.now())
    collected_at = Column(DateTime, server_default=func.now())  # When the odd was actually collected
    is_best_odd = Column(Boolean, default=False, index=True)
    is_live = Column(Boolean, default=False, index=True)  # Whether this is a live/pre-match odd
    minutes_elapsed = Column(Integer, nullable=True)  # For live odds: minutes played
    
    # Index for efficient querying by fixture and timestamp
    __table_args__ = (
        Index('ix_odds_history_fixture_timestamp', 'fixture_id', 'timestamp'),
        Index('ix_odds_history_bookmaker_market', 'bookmaker', 'market_name', 'timestamp'),
    )

class UserBettingPreferences(Base):
    __tablename__ = "user_betting_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    preferred_sports = Column(JSON, nullable=True)
    preferred_markets = Column(JSON, nullable=True)
    preferred_bookmakers = Column(JSON, nullable=True)
    risk_tolerance = Column(String(20), nullable=True)  # 'low', 'medium', 'high'
    avg_stake = Column(DECIMAL(10,2), nullable=True)
    success_rate = Column(DECIMAL(5,2), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationship
    user = relationship("User", backref="betting_preferences")

class SmartAlerts(Base):
    __tablename__ = "smart_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)  # 'value_bet', 'odds_drop', 'bookmaker_special'
    criteria = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    last_triggered = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationship
    user = relationship("User", backref="smart_alerts")
