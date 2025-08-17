"""
Conversation Memory Service - Gestisce la memoria conversazionale temporanea per utenti non registrati
"""

import time
import logging
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json
import threading

logger = logging.getLogger(__name__)

@dataclass
class ChatMessage:
    """Rappresenta un messaggio nella conversazione"""
    role: str  # "user" | "assistant"
    content: str
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class ConversationContext:
    """Contesto di una conversazione"""
    session_id: str
    messages: List[ChatMessage]
    created_at: float
    last_activity: float
    user_preferences: Dict[str, Any]
    extracted_entities: Dict[str, Any]  # Entità estratte durante la conversazione
    conversation_topics: List[str]  # Argomenti discussi
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "session_id": self.session_id,
            "messages": [asdict(msg) for msg in self.messages],
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "user_preferences": self.user_preferences,
            "extracted_entities": self.extracted_entities,
            "conversation_topics": self.conversation_topics
        }

class ConversationMemoryService:
    """Servizio per gestire la memoria conversazionale temporanea"""
    
    def __init__(self):
        # In-memory storage per conversazioni temporanee
        self._conversations: Dict[str, ConversationContext] = {}
        self._lock = threading.RLock()
        
        # Configurazione
        self.MAX_MESSAGES_PER_CONVERSATION = 50  # Limita numero messaggi
        self.CONVERSATION_TTL = 2 * 60 * 60  # 2 ore TTL
        self.CLEANUP_INTERVAL = 15 * 60  # Cleanup ogni 15 minuti
        
        # Avvia cleanup automatico
        self._start_cleanup_task()
        
        logger.info("ConversationMemoryService initialized")
    
    def _start_cleanup_task(self):
        """Avvia il task di cleanup automatico delle conversazioni scadute"""
        def cleanup_expired():
            while True:
                try:
                    time.sleep(self.CLEANUP_INTERVAL)
                    self.cleanup_expired_conversations()
                except Exception as e:
                    logger.error(f"[MEMORY] Error in cleanup task: {e}")
        
        # Avvia thread di cleanup in background
        cleanup_thread = threading.Thread(target=cleanup_expired, daemon=True)
        cleanup_thread.start()
    
    def get_or_create_conversation(self, session_id: str) -> ConversationContext:
        """Ottiene o crea una nuova conversazione"""
        with self._lock:
            current_time = time.time()
            
            if session_id in self._conversations:
                # Aggiorna last_activity
                conversation = self._conversations[session_id]
                conversation.last_activity = current_time
                logger.debug(f"[MEMORY] Retrieved existing conversation for {session_id}")
                return conversation
            else:
                # Crea nuova conversazione
                conversation = ConversationContext(
                    session_id=session_id,
                    messages=[],
                    created_at=current_time,
                    last_activity=current_time,
                    user_preferences={},
                    extracted_entities={},
                    conversation_topics=[]
                )
                self._conversations[session_id] = conversation
                logger.info(f"[MEMORY] Created new conversation for {session_id}")
                return conversation
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Aggiunge un messaggio alla conversazione"""
        with self._lock:
            conversation = self.get_or_create_conversation(session_id)
            
            # Crea il messaggio
            message = ChatMessage(
                role=role,
                content=content,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            # Aggiunge il messaggio
            conversation.messages.append(message)
            conversation.last_activity = time.time()
            
            # Limita il numero di messaggi (FIFO)
            if len(conversation.messages) > self.MAX_MESSAGES_PER_CONVERSATION:
                removed = conversation.messages.pop(0)
                logger.debug(f"[MEMORY] Removed oldest message from {session_id}")
            
            logger.debug(f"[MEMORY] Added {role} message to {session_id} (total: {len(conversation.messages)})")
    
    def get_conversation_history(self, session_id: str, limit: Optional[int] = None) -> List[ChatMessage]:
        """Ottiene la storia della conversazione"""
        with self._lock:
            if session_id not in self._conversations:
                return []
            
            messages = self._conversations[session_id].messages
            if limit:
                return messages[-limit:]
            return messages.copy()
    
    def get_recent_context(self, session_id: str, max_messages: int = 10) -> str:
        """Ottiene il contesto recente della conversazione come stringa"""
        messages = self.get_conversation_history(session_id, max_messages)
        
        if not messages:
            return ""
        
        context_parts = []
        for msg in messages[-max_messages:]:
            timestamp_str = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M")
            role_label = "👤 Utente" if msg.role == "user" else "🤖 Assistente"
            context_parts.append(f"[{timestamp_str}] {role_label}: {msg.content}")
        
        return "\n".join(context_parts)
    
    def update_conversation_entities(self, session_id: str, entities: Dict[str, Any]):
        """Aggiorna le entità estratte nella conversazione"""
        with self._lock:
            conversation = self.get_or_create_conversation(session_id)
            
            # Merge delle entità (mantiene quelle esistenti, aggiunge nuove)
            for key, value in entities.items():
                if key in conversation.extracted_entities:
                    # Se è una lista, estendi
                    if isinstance(conversation.extracted_entities[key], list) and isinstance(value, list):
                        # Aggiungi elementi unici
                        for item in value:
                            if item not in conversation.extracted_entities[key]:
                                conversation.extracted_entities[key].append(item)
                    else:
                        # Sovrascrivi con valore più recente
                        conversation.extracted_entities[key] = value
                else:
                    conversation.extracted_entities[key] = value
            
            conversation.last_activity = time.time()
            logger.debug(f"[MEMORY] Updated entities for {session_id}: {entities}")
    
    def add_conversation_topic(self, session_id: str, topic: str):
        """Aggiunge un argomento alla conversazione"""
        with self._lock:
            conversation = self.get_or_create_conversation(session_id)
            
            # Aggiungi topic se non già presente
            if topic not in conversation.conversation_topics:
                conversation.conversation_topics.append(topic)
                # Mantieni solo gli ultimi 10 topic
                if len(conversation.conversation_topics) > 10:
                    conversation.conversation_topics.pop(0)
                
                logger.debug(f"[MEMORY] Added topic '{topic}' to {session_id}")
    
    def get_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """Ottiene un riassunto della conversazione"""
        with self._lock:
            if session_id not in self._conversations:
                return {}
            
            conversation = self._conversations[session_id]
            
            # Statistiche messaggi
            user_messages = [m for m in conversation.messages if m.role == "user"]
            assistant_messages = [m for m in conversation.messages if m.role == "assistant"]
            
            # Durata conversazione
            duration_seconds = conversation.last_activity - conversation.created_at
            duration_minutes = int(duration_seconds / 60)
            
            return {
                "session_id": session_id,
                "message_count": len(conversation.messages),
                "user_messages": len(user_messages),
                "assistant_messages": len(assistant_messages),
                "duration_minutes": duration_minutes,
                "topics": conversation.conversation_topics,
                "entities": conversation.extracted_entities,
                "created_at": datetime.fromtimestamp(conversation.created_at).isoformat(),
                "last_activity": datetime.fromtimestamp(conversation.last_activity).isoformat()
            }
    
    def delete_conversation(self, session_id: str) -> bool:
        """Cancella una conversazione"""
        with self._lock:
            if session_id in self._conversations:
                del self._conversations[session_id]
                logger.info(f"[MEMORY] Deleted conversation {session_id}")
                return True
            return False
    
    def cleanup_expired_conversations(self):
        """Rimuove conversazioni scadute"""
        current_time = time.time()
        expired_sessions = []
        
        with self._lock:
            for session_id, conversation in self._conversations.items():
                if current_time - conversation.last_activity > self.CONVERSATION_TTL:
                    expired_sessions.append(session_id)
        
        # Rimuovi conversazioni scadute
        for session_id in expired_sessions:
            self.delete_conversation(session_id)
        
        if expired_sessions:
            logger.info(f"[MEMORY] Cleaned up {len(expired_sessions)} expired conversations")
    
    def get_active_conversations_count(self) -> int:
        """Ottiene il numero di conversazioni attive"""
        with self._lock:
            return len(self._conversations)
    
    def extract_conversation_insights(self, session_id: str) -> Dict[str, Any]:
        """Estrae insights dalla conversazione per migliorare le risposte"""
        messages = self.get_conversation_history(session_id)
        
        if not messages:
            return {}
        
        insights = {
            "user_interests": [],
            "frequent_questions": [],
            "preferred_teams": [],
            "bet_preferences": [],
            "conversation_style": "neutral"
        }
        
        # Analizza i messaggi utente
        user_messages = [m.content.lower() for m in messages if m.role == "user"]
        
        # Rileva interessi comuni
        sports_keywords = ["calcio", "football", "serie a", "champions", "europa league"]
        bet_keywords = ["quota", "scommessa", "bet", "schedina", "pronostico"]
        team_keywords = ["milan", "inter", "juventus", "napoli", "roma", "lazio", "atalanta"]
        
        for msg in user_messages:
            # Interessi sportivi
            for keyword in sports_keywords:
                if keyword in msg and keyword not in insights["user_interests"]:
                    insights["user_interests"].append(keyword)
            
            # Preferenze scommesse
            for keyword in bet_keywords:
                if keyword in msg and keyword not in insights["bet_preferences"]:
                    insights["bet_preferences"].append(keyword)
            
            # Squadre preferite
            for team in team_keywords:
                if team in msg and team not in insights["preferred_teams"]:
                    insights["preferred_teams"].append(team)
        
        # Determina stile conversazione
        if len(user_messages) > 5:
            total_length = sum(len(msg) for msg in user_messages)
            avg_length = total_length / len(user_messages)
            
            if avg_length > 100:
                insights["conversation_style"] = "detailed"
            elif avg_length < 30:
                insights["conversation_style"] = "concise"
        
        return insights

# Singleton instance
_conversation_memory_service = None

def get_conversation_memory_service() -> ConversationMemoryService:
    """Ottiene l'istanza singleton del servizio memoria conversazionale"""
    global _conversation_memory_service
    if _conversation_memory_service is None:
        _conversation_memory_service = ConversationMemoryService()
    return _conversation_memory_service
