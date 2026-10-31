"""
Tests for session manager service
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from app.services.session_manager import session_manager
from app.db import models


class TestSessionCreation:
    def test_create_session_success(self, db_session, test_user):
        """Test successful session creation"""
        user_agent = "Mozilla/5.0 (Test Browser)"
        ip_address = "192.168.1.100"
        jti = "test_jti_123"
        
        session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent=user_agent,
            ip_address=ip_address,
            refresh_token_jti=jti
        )
        
        assert session is not None
        assert session.user_id == test_user.id
        assert session.ip_address == ip_address
        assert session.user_agent == user_agent
        assert session.is_active is True
        assert session.device_info is not None
        assert isinstance(session.device_info, dict)
    
    def test_create_session_with_device_info(self, db_session, test_user):
        """Test session creation with custom device info"""
        device_info = {
            "browser": "Chrome",
            "os": "Windows",
            "device_type": "Desktop"
        }
        
        session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Chrome/90.0.4430.93",
            ip_address="127.0.0.1",
            refresh_token_jti="test_jti",
            device_info=device_info
        )
        
        assert session.device_info == device_info
    
    def test_create_session_user_agent_parsing(self, db_session, test_user):
        """Test session creation with user agent parsing"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/91.0.4472.124",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Firefox/89.0"
        ]
        
        for user_agent in user_agents:
            session = session_manager.create_session(
                db=db_session,
                user_id=test_user.id,
                user_agent=user_agent,
                ip_address="127.0.0.1",
                refresh_token_jti=f"jti_{hash(user_agent)}"
            )
            
            assert session.device_info["browser"] != "Unknown"
            assert session.device_info["os"] != "Unknown"
            assert session.device_info["device_type"] != "Unknown"


class TestSessionRetrieval:
    def test_get_user_sessions(self, db_session, test_user):
        """Test retrieving user sessions"""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = session_manager.create_session(
                db=db_session,
                user_id=test_user.id,
                user_agent=f"Browser {i}",
                ip_address=f"192.168.1.{i+1}",
                refresh_token_jti=f"jti_{i}"
            )
            sessions.append(session)
        
        # Retrieve sessions
        retrieved_sessions = session_manager.get_user_sessions(db_session, test_user.id)
        
        assert len(retrieved_sessions) == 3
        for session in retrieved_sessions:
            assert session.user_id == test_user.id
            assert session.is_active is True
    
    def test_get_user_sessions_include_inactive(self, db_session, test_user):
        """Test retrieving user sessions including inactive ones"""
        # Create active session
        active_session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Active Browser",
            ip_address="192.168.1.1",
            refresh_token_jti="active_jti"
        )
        
        # Create and terminate inactive session
        inactive_session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Inactive Browser",
            ip_address="192.168.1.2",
            refresh_token_jti="inactive_jti"
        )
        session_manager.terminate_session(db_session, inactive_session.session_id)
        
        # Test with include_inactive=False (default)
        active_only = session_manager.get_user_sessions(db_session, test_user.id)
        assert len(active_only) == 1
        assert active_only[0].session_id == active_session.session_id
        
        # Test with include_inactive=True
        all_sessions = session_manager.get_user_sessions(db_session, test_user.id, include_inactive=True)
        assert len(all_sessions) == 2
    
    def test_get_session_by_id(self, db_session, test_user):
        """Test retrieving session by ID"""
        created_session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Test Browser",
            ip_address="192.168.1.1",
            refresh_token_jti="test_jti"
        )
        
        retrieved_session = session_manager.get_session_by_id(db_session, created_session.session_id)
        
        assert retrieved_session is not None
        assert retrieved_session.session_id == created_session.session_id
        assert retrieved_session.user_id == test_user.id
    
    def test_get_session_by_jti(self, db_session, test_user):
        """Test retrieving session by JTI"""
        jti = "unique_jti_123"
        created_session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Test Browser",
            ip_address="192.168.1.1",
            refresh_token_jti=jti
        )
        
        retrieved_session = session_manager.get_session_by_jti(db_session, jti)
        
        assert retrieved_session is not None
        assert retrieved_session.session_id == created_session.session_id


class TestSessionActivityUpdate:
    def test_update_activity(self, db_session, test_user):
        """Test updating session activity"""
        session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Test Browser",
            ip_address="192.168.1.1",
            refresh_token_jti="test_jti"
        )
        
        original_activity = session.last_activity
        
        # Wait a moment and update activity
        import time
        time.sleep(0.1)
        
        success = session_manager.update_activity(db_session, session.session_id)
        
        assert success is True
        
        # Verify activity was updated
        updated_session = session_manager.get_session_by_id(db_session, session.session_id)
        assert updated_session.last_activity > original_activity
    
    def test_update_activity_inactive_session(self, db_session, test_user):
        """Test updating activity of inactive session"""
        session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Test Browser",
            ip_address="192.168.1.1",
            refresh_token_jti="test_jti"
        )
        
        # Terminate session
        session_manager.terminate_session(db_session, session.session_id)
        
        # Try to update activity
        success = session_manager.update_activity(db_session, session.session_id)
        
        assert success is False


class TestSessionTermination:
    def test_terminate_session(self, db_session, test_user):
        """Test terminating a session"""
        session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Test Browser",
            ip_address="192.168.1.1",
            refresh_token_jti="test_jti"
        )
        
        success = session_manager.terminate_session(db_session, session.session_id, "test_termination")
        
        assert success is True
        
        # Verify session is terminated
        terminated_session = session_manager.get_session_by_id(db_session, session.session_id)
        assert terminated_session.is_active is False
        assert terminated_session.termination_reason == "test_termination"
    
    def test_terminate_user_sessions(self, db_session, test_user):
        """Test terminating all user sessions"""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = session_manager.create_session(
                db=db_session,
                user_id=test_user.id,
                user_agent=f"Browser {i}",
                ip_address=f"192.168.1.{i+1}",
                refresh_token_jti=f"jti_{i}"
            )
            sessions.append(session)
        
        # Terminate all sessions
        terminated_count = session_manager.terminate_user_sessions(
            db_session, test_user.id, "mass_termination"
        )
        
        assert terminated_count == 3
        
        # Verify all sessions are terminated
        all_sessions = session_manager.get_user_sessions(db_session, test_user.id, include_inactive=True)
        for session in all_sessions:
            assert session.is_active is False
            assert session.termination_reason == "mass_termination"
    
    def test_terminate_user_sessions_with_exclusion(self, db_session, test_user):
        """Test terminating all user sessions except one"""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = session_manager.create_session(
                db=db_session,
                user_id=test_user.id,
                user_agent=f"Browser {i}",
                ip_address=f"192.168.1.{i+1}",
                refresh_token_jti=f"jti_{i}"
            )
            sessions.append(session)
        
        # Terminate all except the first one
        excluded_session = sessions[0]
        terminated_count = session_manager.terminate_user_sessions(
            db_session, 
            test_user.id, 
            "selective_termination", 
            exclude_session_id=excluded_session.session_id
        )
        
        assert terminated_count == 2
        
        # Verify excluded session is still active
        excluded = session_manager.get_session_by_id(db_session, excluded_session.session_id)
        assert excluded.is_active is True
        
        # Verify others are terminated
        active_sessions = session_manager.get_user_sessions(db_session, test_user.id)
        assert len(active_sessions) == 1
        assert active_sessions[0].session_id == excluded_session.session_id


class TestSessionValidation:
    def test_is_session_active_valid(self, db_session, test_user):
        """Test session activity validation for valid session"""
        session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Test Browser",
            ip_address="192.168.1.1",
            refresh_token_jti="test_jti"
        )
        
        # Get the SQLAlchemy model directly
        db_session = db_session.query(models.Session).filter(
            models.Session.session_id == session.session_id
        ).first()
        
        assert session_manager.is_session_active(db_session) is True
    
    def test_is_session_active_terminated(self, db_session, test_user):
        """Test session activity validation for terminated session"""
        session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Test Browser",
            ip_address="192.168.1.1",
            refresh_token_jti="test_jti"
        )
        
        # Terminate session
        session_manager.terminate_session(db_session, session.session_id)
        
        # Get the updated SQLAlchemy model
        db_session_model = db_session.query(models.Session).filter(
            models.Session.session_id == session.session_id
        ).first()
        
        assert session_manager.is_session_active(db_session_model) is False
    
    def test_is_session_active_expired(self, db_session, test_user):
        """Test session activity validation for expired session"""
        session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Test Browser",
            ip_address="192.168.1.1",
            refresh_token_jti="test_jti"
        )
        
        # Manually set expiration to past
        db_session_model = db_session.query(models.Session).filter(
            models.Session.session_id == session.session_id
        ).first()
        db_session_model.expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()
        
        assert session_manager.is_session_active(db_session_model) is False


class TestSessionCleanup:
    def test_cleanup_expired_sessions(self, db_session, test_user):
        """Test cleanup of expired sessions"""
        # Create active session
        active_session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Active Browser",
            ip_address="192.168.1.1",
            refresh_token_jti="active_jti"
        )
        
        # Create expired session
        expired_session = session_manager.create_session(
            db=db_session,
            user_id=test_user.id,
            user_agent="Expired Browser",
            ip_address="192.168.1.2",
            refresh_token_jti="expired_jti"
        )
        
        # Manually expire the session
        db_session_model = db_session.query(models.Session).filter(
            models.Session.session_id == expired_session.session_id
        ).first()
        db_session_model.expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()
        
        # Run cleanup
        cleaned_count = session_manager.cleanup_expired_sessions(db_session)
        
        assert cleaned_count == 1
        
        # Verify expired session is gone
        remaining_sessions = session_manager.get_user_sessions(db_session, test_user.id, include_inactive=True)
        assert len(remaining_sessions) == 1
        assert remaining_sessions[0].session_id == active_session.session_id
