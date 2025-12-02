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

# ==========================================
# IMPORTAZIONE MODELLI ESISTENTI - Non duplicare!
# ==========================================

# I modelli vengono importati da app.models per evitare conflitti
# MatchPrediction è già definito in app.models.match_predictions

# ==========================================
# OPERATOR TABLES - Required for prediction system
# ==========================================

class FinishedFixtures(Base):
    """Results of completed matches for accuracy tracking"""
    __tablename__ = "finished_fixtures"
    
    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, nullable=False, unique=True, index=True)
    
    # Match information
    fixture_date = Column(DateTime, nullable=False, index=True)
    league_id = Column(Integer, nullable=True, index=True)
    league_name = Column(String(200), nullable=True)
    country_name = Column(String(100), nullable=True)
    home_team = Column(String(100), nullable=False)
    away_team = Column(String(100), nullable=False)
    
    # Final results
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    winner = Column(String(10), nullable=True)  # "home", "away", "draw"
    
    # Statistics
    halftime_home_score = Column(Integer, nullable=True)
    halftime_away_score = Column(Integer, nullable=True)
    total_goals = Column(Integer, nullable=True)
    
    # Status and metadata
    status = Column(String(20), default="FT", index=True)  # FT = Full Time
    collected_at = Column(DateTime, server_default=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_fixture_date_status', 'fixture_date', 'status'),
        Index('idx_league_date_finished', 'league_id', 'fixture_date'),
    )

class PredictionAccuracy(Base):
    """Accuracy evaluations for predictions on finished matches"""
    __tablename__ = "prediction_accuracy"
    
    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, nullable=False, unique=True, index=True)
    
    # Actual results
    actual_home_score = Column(Integer, nullable=True)
    actual_away_score = Column(Integer, nullable=True)
    actual_winner = Column(String(10), nullable=True)  # "home", "away", "draw"
    actual_total_goals = Column(Integer, nullable=True)
    
    # Predictions made
    predicted_winner_id = Column(Integer, nullable=True)
    predicted_winner_name = Column(String(100), nullable=True)
    predicted_win_or_draw = Column(Boolean, nullable=True)
    predicted_under_over = Column(String(10), nullable=True)
    predicted_goals_home = Column(String(10), nullable=True)
    predicted_goals_away = Column(String(10), nullable=True)
    prediction_advice = Column(Text, nullable=True)
    
    # Accuracy calculations
    winner_accuracy = Column(Boolean, nullable=True)  # True if winner correct
    goals_accuracy = Column(Boolean, nullable=True)   # True if under/over correct
    total_goals_accuracy = Column(Boolean, nullable=True)  # True if goals correct
    win_draw_accuracy = Column(Boolean, nullable=True)  # True if win/draw correct
    
    # Accuracy scores (0-100)
    winner_score = Column(DECIMAL(5,2), nullable=True)  # Winner prediction score
    goals_score = Column(DECIMAL(5,2), nullable=True)   # Goals prediction score
    overall_score = Column(DECIMAL(5,2), nullable=True) # Overall accuracy score
    
    # Metadata
    fixture_date = Column(DateTime, nullable=False, index=True)
    league_id = Column(Integer, nullable=True, index=True)
    league_name = Column(String(200), nullable=True)
    home_team = Column(String(100), nullable=False)
    away_team = Column(String(100), nullable=False)
    
    evaluated_at = Column(DateTime, server_default=func.now())
    prediction_collected_at = Column(DateTime, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_fixture_date_accuracy', 'fixture_date', 'evaluated_at'),
        Index('idx_league_accuracy_score', 'league_id', 'overall_score'),
        Index('idx_winner_accuracy', 'winner_accuracy', 'fixture_date'),
    )

class AccuracyStatistics(Base):
    """Aggregated accuracy statistics by period/league"""
    __tablename__ = "accuracy_statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Time period
    period_type = Column(String(20), nullable=False, index=True)  # "daily", "weekly", "monthly", "league"
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)
    
    # Filters
    league_id = Column(Integer, nullable=True, index=True)
    league_name = Column(String(200), nullable=True)
    
    # Statistics
    total_predictions = Column(Integer, default=0)
    winner_correct = Column(Integer, default=0)
    goals_correct = Column(Integer, default=0)
    win_draw_correct = Column(Integer, default=0)
    
    winner_accuracy_percent = Column(DECIMAL(5,2), nullable=True)
    goals_accuracy_percent = Column(DECIMAL(5,2), nullable=True)
    win_draw_accuracy_percent = Column(DECIMAL(5,2), nullable=True)
    overall_accuracy_percent = Column(DECIMAL(5,2), nullable=True)
    
    average_winner_score = Column(DECIMAL(5,2), nullable=True)
    average_goals_score = Column(DECIMAL(5,2), nullable=True)
    average_overall_score = Column(DECIMAL(5,2), nullable=True)
    
    # Metadata
    calculated_at = Column(DateTime, server_default=func.now())
    fixtures_analyzed = Column(JSON, nullable=True)  # List of fixture_ids analyzed
    
    # Indexes
    __table_args__ = (
        Index('idx_period_league_stats', 'period_type', 'league_id', 'period_start'),
        Index('idx_calculated_at_stats', 'calculated_at', 'period_type'),
    )

class FixtureTrackingStatus(Base):
    """Status tracking for fixture data collection"""
    __tablename__ = "fixture_tracking_status"
    
    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, nullable=False, unique=True, index=True)
    
    # Status flags
    predictions_collected = Column(Boolean, default=False)
    odds_collected = Column(Boolean, default=False)
    results_checked = Column(Boolean, default=False)
    
    # Timestamps
    predictions_last_updated = Column(DateTime, nullable=True)
    odds_last_updated = Column(DateTime, nullable=True)
    results_last_checked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Metadata
    collection_attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)
    
    # Match info for live queries
    tracking_status = Column(String(50), nullable=True, index=True)
    league_name = Column(String(255), nullable=True)
    home_team = Column(String(255), nullable=True)
    away_team = Column(String(255), nullable=True)
    fixture_date = Column(DateTime, nullable=True, index=True)
    home_team_logo = Column(String(500), nullable=True)
    away_team_logo = Column(String(500), nullable=True)
    league_logo = Column(String(500), nullable=True)
    
    __table_args__ = (
        Index('ix_fixture_tracking_status_live', 'tracking_status', 'fixture_date'),
    )
