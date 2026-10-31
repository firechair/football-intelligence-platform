"""
Intent Router - Routes messages to appropriate handlers

This module determines which handler should process a message based on:
- Intent detection
- Message content
- User context
"""

import logging
from typing import Dict, Any
from dataclasses import dataclass
from ..intent_detection import IntentDetector

logger = logging.getLogger(__name__)


@dataclass
class RouteDecision:
    """Represents a routing decision"""
    handler: str  # "parlant", "football", "llm", "direct"
    should_fetch_data: bool
    intent_data: Dict[str, Any]
    confidence: float


class IntentRouter:
    """Routes messages to appropriate handlers based on intent and content"""

    def __init__(self):
        """Initialize the intent router"""
        self.intent_detector = IntentDetector()

    def route_message(self, message: str, user_context: Dict[str, Any] = None) -> RouteDecision:
        """
        Route a message to the appropriate handler

        Args:
            message: The user's message
            user_context: Optional user context

        Returns:
            RouteDecision: The routing decision with handler and metadata
        """
        # Detect intent
        intent_match = self.intent_detector.detect_intent(message)

        # Convert IntentMatch to dict for backward compatibility
        intent_data = {
            "intent": intent_match.intent_type.value if hasattr(intent_match.intent_type, 'value') else str(intent_match.intent_type),
            "confidence": intent_match.confidence,
            "entities": intent_match.entities,
            "original_message": intent_match.original_text
        }

        intent_type = intent_data.get("intent", "unknown")
        confidence = intent_data.get("confidence", 0.0)

        # Check if this is a greeting or help request
        if self._is_greeting_or_help(message, intent_type):
            return RouteDecision(
                handler="parlant",
                should_fetch_data=False,
                intent_data=intent_data,
                confidence=confidence
            )

        # Check if this is a football query
        if self._should_fetch_football_data(message, intent_data):
            return RouteDecision(
                handler="football",
                should_fetch_data=True,
                intent_data=intent_data,
                confidence=confidence
            )

        # Check if this is a vague/unknown query (use Parlant)
        if intent_type in ["vague_request", "unknown", "help"]:
            return RouteDecision(
                handler="parlant",
                should_fetch_data=False,
                intent_data=intent_data,
                confidence=confidence
            )

        # Default: use direct LLM
        return RouteDecision(
            handler="llm",
            should_fetch_data=False,
            intent_data=intent_data,
            confidence=confidence
        )

    def _is_greeting_or_help(self, message: str, intent_type: str) -> bool:
        """
        Check if message is a greeting or help request

        Args:
            message: The user's message
            intent_type: Detected intent type

        Returns:
            bool: True if greeting or help
        """
        message_lower = message.lower()

        # Check for greetings
        greeting_patterns = ['ciao', 'salve', 'hello', 'hi', 'buongiorno', 'buonasera', 'hey']
        if any(pattern in message_lower for pattern in greeting_patterns):
            return True

        # Check for capabilities questions
        capability_patterns = ['cosa sai fare', 'che funzionalità hai', 'chi sei', 'capabilities', 'features', 'cosa puoi fare']
        if any(pattern in message_lower for pattern in capability_patterns):
            return True

        # Check intent type
        if intent_type in ["greeting", "help"]:
            return True

        return False

    def _should_fetch_football_data(self, message: str, intent_data: Dict[str, Any]) -> bool:
        """
        Determine if we should fetch football data

        Args:
            message: The user's message
            intent_data: Detected intent data

        Returns:
            bool: True if should fetch football data
        """
        message_lower = message.lower()
        intent_type = intent_data.get("intent", "")
        entities = intent_data.get("entities", {})

        # Don't fetch for greetings or help
        if intent_type in ["greeting", "help", "navigation"]:
            return False

        # Don't fetch for messages that are only symbols or all uppercase
        if message.isupper() or not any(c.isalpha() for c in message):
            return False

        # Fetch for specific football queries
        football_keywords = [
            'partite', 'matches', 'predizioni', 'predictions', 'pronostici',
            'quote', 'odds', 'squadre', 'teams', 'campionato', 'league',
            'serie a', 'premier league', 'champions league', 'juventus',
            'inter', 'milan', 'napoli', 'roma', 'lazio', 'atalanta',
            'oggi', 'domani', 'today', 'tomorrow'  # Temporal keywords
        ]

        has_football_keywords = any(keyword in message_lower for keyword in football_keywords)

        # Fetch if there are team entities
        has_team_entities = bool(entities.get("team1") or entities.get("team_or_match"))

        # Fetch for recognized football intents
        is_football_intent = intent_type in [
            "generic_match_request", "match_request", "bet_analysis",
            "odds_query", "statistics", "predictions"
        ]

        should_fetch = has_football_keywords or has_team_entities or is_football_intent

        logger.info(f"[ROUTE] Intent: {intent_type}, Keywords: {has_football_keywords}, "
                   f"Entities: {has_team_entities}, Football intent: {is_football_intent}, "
                   f"Fetch: {should_fetch}")

        return should_fetch
