import uuid
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import and_, or_

from app.db.models import Session as SessionModel, User
from app.models.session import SessionCreate, SessionOut, SessionUpdate
from app.services.security import security_service

logger = logging.getLogger(__name__)

class SessionManager:
    """Gestisce le sessioni utente con tracking avanzato e cleanup automatico"""
    
    def __init__(self):
        self._session_expire_hours = 24 * 7  # 7 giorni default
        self._max_sessions_per_user = 10
        self._cleanup_interval = 3600  # 1 ora
        self._last_cleanup = datetime.utcnow()
        self._lock = threading.Lock()
        
        # Avvia thread di cleanup in background
        self._start_cleanup_thread()
    
    def create_session(
        self,
        db: DBSession,
        user_id: int,
        user_agent: str,
        ip_address: str,
        refresh_token_jti: str,
        device_info: Optional[Dict[str, Any]] = None
    ) -> Optional[SessionOut]:
        """Crea nuova sessione utente"""
        try:
            with self._lock:
                # Genera session ID univoco
                session_id = str(uuid.uuid4())
                
                # Parse device info se non fornito
                if not device_info:
                    device_info = self._parse_device_info(user_agent)
                
                # Calcola scadenza
                expires_at = datetime.utcnow() + timedelta(hours=self._session_expire_hours)
                
                # Verifica limite sessioni per utente
                active_sessions = self._get_user_active_sessions_count(db, user_id)
                if active_sessions >= self._max_sessions_per_user:
                    # Termina la sessione più vecchia
                    self._terminate_oldest_session(db, user_id)
                
                # Crea nuova sessione
                session = SessionModel(
                    session_id=session_id,
                    user_id=user_id,
                    refresh_token_jti=refresh_token_jti,
                    device_info=device_info,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    expires_at=expires_at,
                    is_active=True
                )
                
                db.add(session)
                db.commit()
                db.refresh(session)
                
                logger.info(f"Session created: {session_id} for user {user_id}")
                return self._session_to_out(session)
                
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            db.rollback()
            return None
    
    def get_user_sessions(
        self,
        db: DBSession,
        user_id: int,
        include_inactive: bool = False
    ) -> List[SessionOut]:
        """Ottieni tutte le sessioni dell'utente"""
        try:
            query = db.query(SessionModel).filter(SessionModel.user_id == user_id)
            
            if not include_inactive:
                query = query.filter(
                    and_(
                        SessionModel.is_active == True,
                        SessionModel.expires_at > datetime.utcnow()
                    )
                )
            
            sessions = query.order_by(SessionModel.last_activity.desc()).all()
            return [self._session_to_out(session) for session in sessions]
            
        except Exception as e:
            logger.error(f"Error getting user sessions: {e}")
            return []
    
    def get_session_by_id(self, db: DBSession, session_id: str) -> Optional[SessionOut]:
        """Ottieni sessione per ID"""
        try:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            
            return self._session_to_out(session) if session else None
            
        except Exception as e:
            logger.error(f"Error getting session by ID: {e}")
            return None
    
    def get_session_by_jti(self, db: DBSession, jti: str) -> Optional[SessionOut]:
        """Ottieni sessione per refresh token JTI"""
        try:
            session = db.query(SessionModel).filter(
                SessionModel.refresh_token_jti == jti
            ).first()
            
            return self._session_to_out(session) if session else None
            
        except Exception as e:
            logger.error(f"Error getting session by JTI: {e}")
            return None
    
    def update_activity(self, db: DBSession, session_id: str) -> bool:
        """Aggiorna ultima attività della sessione"""
        try:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            
            if session and self.is_session_active(session):
                session.last_activity = datetime.utcnow()
                db.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating session activity: {e}")
            db.rollback()
            return False
    
    def terminate_session(
        self,
        db: DBSession,
        session_id: str,
        reason: str = "user_logout"
    ) -> bool:
        """Termina sessione specifica"""
        try:
            session = db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            
            if session:
                session.is_active = False
                session.termination_reason = reason
                db.commit()
                
                logger.info(f"Session terminated: {session_id}, reason: {reason}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error terminating session: {e}")
            db.rollback()
            return False
    
    def terminate_user_sessions(
        self,
        db: DBSession,
        user_id: int,
        reason: str = "logout_all",
        exclude_session_id: Optional[str] = None
    ) -> int:
        """Termina tutte le sessioni dell'utente"""
        try:
            query = db.query(SessionModel).filter(
                and_(
                    SessionModel.user_id == user_id,
                    SessionModel.is_active == True
                )
            )
            
            if exclude_session_id:
                query = query.filter(SessionModel.session_id != exclude_session_id)
            
            sessions = query.all()
            terminated_count = 0
            
            for session in sessions:
                session.is_active = False
                session.termination_reason = reason
                terminated_count += 1
            
            db.commit()
            logger.info(f"Terminated {terminated_count} sessions for user {user_id}")
            return terminated_count
            
        except Exception as e:
            logger.error(f"Error terminating user sessions: {e}")
            db.rollback()
            return 0
    
    def is_session_active(self, session: SessionModel) -> bool:
        """Verifica se la sessione è ancora attiva"""
        if not session:
            return False
        
        return (
            session.is_active and
            session.expires_at > datetime.utcnow()
        )
    
    def cleanup_expired_sessions(self, db: DBSession) -> int:
        """Rimuovi sessioni scadute dal database"""
        try:
            # Trova sessioni scadute
            expired_sessions = db.query(SessionModel).filter(
                or_(
                    SessionModel.expires_at <= datetime.utcnow(),
                    SessionModel.is_active == False
                )
            ).all()
            
            count = len(expired_sessions)
            
            if count > 0:
                # Elimina sessioni scadute
                for session in expired_sessions:
                    db.delete(session)
                
                db.commit()
                logger.info(f"Cleaned up {count} expired sessions")
            
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            db.rollback()
            return 0
    
    def _get_user_active_sessions_count(self, db: DBSession, user_id: int) -> int:
        """Conta sessioni attive dell'utente"""
        return db.query(SessionModel).filter(
            and_(
                SessionModel.user_id == user_id,
                SessionModel.is_active == True,
                SessionModel.expires_at > datetime.utcnow()
            )
        ).count()
    
    def _terminate_oldest_session(self, db: DBSession, user_id: int) -> None:
        """Termina la sessione più vecchia dell'utente"""
        oldest_session = db.query(SessionModel).filter(
            and_(
                SessionModel.user_id == user_id,
                SessionModel.is_active == True
            )
        ).order_by(SessionModel.last_activity.asc()).first()
        
        if oldest_session:
            self.terminate_session(db, oldest_session.session_id, "max_sessions_exceeded")
    
    def _session_to_out(self, session: SessionModel) -> SessionOut:
        """Converte SessionModel a SessionOut"""
        return SessionOut(
            session_id=session.session_id,
            user_id=session.user_id,
            device_info=session.device_info or {},
            ip_address=session.ip_address or "",
            user_agent=session.user_agent or "",
            created_at=session.created_at,
            last_activity=session.last_activity,
            expires_at=session.expires_at,
            is_active=session.is_active,
            termination_reason=session.termination_reason
        )
    
    def _parse_device_info(self, user_agent: str) -> Dict[str, str]:
        """Estrae info basilari su device/browser da user agent"""
        device_info = {
            "browser": "Unknown",
            "os": "Unknown",
            "device_type": "Unknown"
        }
        
        if not user_agent:
            return device_info
        
        ua_lower = user_agent.lower()
        
        # Browser detection
        if "chrome" in ua_lower:
            device_info["browser"] = "Chrome"
        elif "firefox" in ua_lower:
            device_info["browser"] = "Firefox"
        elif "safari" in ua_lower and "chrome" not in ua_lower:
            device_info["browser"] = "Safari"
        elif "edge" in ua_lower:
            device_info["browser"] = "Edge"
        
        # OS detection
        if "windows" in ua_lower:
            device_info["os"] = "Windows"
        elif "mac" in ua_lower:
            device_info["os"] = "macOS"
        elif "linux" in ua_lower:
            device_info["os"] = "Linux"
        elif "android" in ua_lower:
            device_info["os"] = "Android"
        elif "ios" in ua_lower or "iphone" in ua_lower or "ipad" in ua_lower:
            device_info["os"] = "iOS"
        
        # Device type detection
        if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
            device_info["device_type"] = "Mobile"
        elif "tablet" in ua_lower or "ipad" in ua_lower:
            device_info["device_type"] = "Tablet"
        else:
            device_info["device_type"] = "Desktop"
        
        return device_info
    
    def _start_cleanup_thread(self):
        """Avvia thread di cleanup automatico in background"""
        def cleanup_worker():
            while True:
                try:
                    # Sleep per intervallo di cleanup
                    threading.Event().wait(self._cleanup_interval)
                    
                    # Importa qui per evitare circular import
                    from app.db import get_db
                    
                    # Esegui cleanup se necessario
                    if (datetime.utcnow() - self._last_cleanup).seconds >= self._cleanup_interval:
                        db = next(get_db())
                        try:
                            cleaned = self.cleanup_expired_sessions(db)
                            if cleaned > 0:
                                logger.info(f"Automatic cleanup: removed {cleaned} expired sessions")
                            self._last_cleanup = datetime.utcnow()
                        finally:
                            db.close()
                            
                except Exception as e:
                    logger.error(f"Error in session cleanup thread: {e}")
        
        # Avvia thread daemon
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("Session cleanup thread started")

# Singleton instance
session_manager = SessionManager()
