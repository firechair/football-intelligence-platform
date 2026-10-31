"""
Compliance and Responsible Gambling Service

Ensures FIP operates within responsible gambling guidelines and regulations.

Key Responsibilities:
- Detect problematic gambling patterns in user messages
- Intervene when risky behavior is detected
- Block harmful or addiction-encouraging responses
- Provide gambling addiction resources when needed
- Track user behavior for risk assessment
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class ComplianceService:
    """
    Service for responsible gambling compliance and user protection.

    Implements:
    1. Message screening for addiction indicators
    2. Response filtering to prevent harmful suggestions
    3. Intervention triggers for high-risk behavior
    4. Regulatory compliance checks
    5. User risk tracking
    """

    SAFE_RESPONSE = "Mi dispiace, non posso consigliare strategie di scommessa aggressive. Gioca sempre responsabilmente e scommetti solo importi che puoi permetterti di perdere."

    def __init__(self):
        # Addiction risk patterns (Italian and English)
        self.addiction_patterns = [
            # Financial distress
            r"devo\s+recuperare",  # "I need to recover"
            r"recuperare\s+(le\s+)?perdite",  # "recover the losses"
            r"ultimo\s+tentativo",  # "last attempt"
            r"senza\s+soldi",  # "no money"
            r"debiti?\s+(di|per|col|con)\s+(il\s+)?(gioco|scommess|giocare)",  # "gambling debts"
            r"prestito\s+per\s+(giocare|scommettere)",  # "loan to gamble"
            r"need\s+to\s+win\s+back",
            r"chase.*loss",

            # Emotional distress
            r"disperato",  # "desperate"
            r"non\s+posso\s+smettere",  # "can't stop"
            r"dipenden[tz]a",  # "addiction"
            r"aiut(o|atemi)\s+(con|per|a\s+smettere)\s+(il\s+|di\s+)?(gioco|giocare|scommesse|scommettere)",  # "help with gambling"
            r"mi\s+sono\s+rovinato",  # "I've ruined myself"

            # Excessive betting
            r"(scommett|punt|gioc)\w*\s+tutto",  # "bet everything"
            r"\ball[\s-]?in\b",
            r"ultima\s+possibilità",  # "last chance"
            r"non\s+posso\s+perdere",  # "can't lose"
        ]

        # Thoughts of self-harm take priority over every other pattern
        self.crisis_patterns = [
            r"suicid",
            r"farla\s+finita",  # "end it all"
            r"togliermi\s+la\s+vita",  # "take my life"
            r"uccidermi",  # "kill myself"
        ]

        # Patterns that should trigger warnings but not blocks
        self.warning_patterns = [
            r"scommessa\s+grossa",  # "big bet"
            r"vincita\s+facile",  # "easy win"
            r"sistema\s+infallibile",  # "infallible system"
            r"garanzia",  # "guarantee"
            r"sicuro\s+al\s+100%",  # "100% sure"
        ]

        # Harmful response patterns to filter out
        self.harmful_response_patterns = [
            r"sicuramente\s+vinc",  # "surely win"
            r"garantito",  # "guaranteed"
            r"non\s+puoi\s+perdere",  # "you can't lose"
            r"scommetti\s+tutto",  # "bet everything"
            r"raddoppia\s+la\s+posta",  # "double the bet"
        ]

        # User risk tracking (in-memory for now, should be database in production)
        self.user_risk_scores = defaultdict(float)
        self.user_message_history = defaultdict(list)
        self.intervention_history = defaultdict(list)

        # Italian gambling addiction resources
        self.help_resources = {
            "it": {
                "helpline": "800 55 88 22 (Numero Verde Gioco Responsabile)",
                "website": "https://www.giocaresponsabile.it",
                "chat": "https://www.adm.gov.it/portale/assistenza",
                "organizations": [
                    "Giocatori Anonimi Italia",
                    "Consulta Nazionale Antiusura"
                ]
            },
            "en": {
                "helpline": "1-800-GAMBLER",
                "website": "https://www.ncpgambling.org",
                "organizations": ["Gamblers Anonymous"]
            }
        }

    async def check_user_message(
        self,
        message: str,
        user_id: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Screen user message for addiction/risk indicators.

        Args:
            message: User's message
            user_id: User identifier
            conversation_history: Recent conversation history

        Returns:
            Dictionary containing:
            - should_block: Whether to block processing
            - risk_level: none, low, medium, high, critical
            - intervention_type: Type of intervention needed
            - intervention_message: Message to show user
            - compliance_notes: Internal notes for logging
        """
        try:
            logger.info(f"[COMPLIANCE] Checking message for user {user_id}")

            # Initialize result
            result = {
                "should_block": False,
                "risk_level": "none",
                "intervention_type": None,
                "intervention_message": None,
                "compliance_notes": [],
                "help_resources": None
            }

            message_lower = message.lower()

            # Check for self-harm before anything else
            crisis_match = self._check_patterns(message_lower, self.crisis_patterns)
            if crisis_match:
                result["should_block"] = True
                result["risk_level"] = "critical"
                result["intervention_type"] = "crisis"
                result["intervention_message"] = self._get_intervention_message("crisis")
                result["compliance_notes"].append(f"Crisis pattern matched: {crisis_match}")
                await self._log_intervention(user_id, "crisis", crisis_match)
                logger.warning(f"[COMPLIANCE] Crisis message from user {user_id}")
                return result

            # Check for critical addiction patterns
            critical_match = self._check_patterns(message_lower, self.addiction_patterns)
            if critical_match:
                result["should_block"] = True
                result["risk_level"] = "critical"
                result["intervention_type"] = "addiction_risk"
                result["intervention_message"] = self._get_intervention_message("critical")
                result["help_resources"] = self.help_resources["it"]
                result["compliance_notes"].append(f"Critical pattern matched: {critical_match}")

                # Log intervention
                await self._log_intervention(user_id, "critical", critical_match)

                logger.warning(f"[COMPLIANCE] Critical risk detected for user {user_id}")
                return result

            # Check for warning patterns
            warning_match = self._check_patterns(message_lower, self.warning_patterns)
            if warning_match:
                result["risk_level"] = "medium"
                result["intervention_type"] = "warning"
                result["intervention_message"] = self._get_intervention_message("warning")
                result["compliance_notes"].append(f"Warning pattern matched: {warning_match}")

                logger.info(f"[COMPLIANCE] Warning level risk for user {user_id}")

            # Analyze conversation history for behavioral patterns
            if conversation_history:
                history_risk = await self._analyze_conversation_history(
                    user_id,
                    conversation_history
                )
                if history_risk["risk_level"] != "none":
                    result["risk_level"] = max(
                        result["risk_level"],
                        history_risk["risk_level"],
                        key=lambda x: ["none", "low", "medium", "high", "critical"].index(x)
                    )
                    result["compliance_notes"].extend(history_risk["notes"])

            # Update user risk score
            await self._update_user_risk_score(user_id, result["risk_level"])

            # Check if accumulated risk is high
            if self.user_risk_scores[user_id] >= 10.0:
                result["should_block"] = True
                result["risk_level"] = "high"
                result["intervention_type"] = "accumulated_risk"
                result["intervention_message"] = self._get_intervention_message("high")
                result["help_resources"] = self.help_resources["it"]

                logger.warning(f"[COMPLIANCE] High accumulated risk for user {user_id}: {self.user_risk_scores[user_id]}")

            return result

        except Exception as e:
            logger.error(f"[COMPLIANCE] Error checking message: {str(e)}", exc_info=True)
            # Fail safe - allow message but log error
            return {
                "should_block": False,
                "risk_level": "none",
                "compliance_notes": [f"Error during compliance check: {str(e)}"]
            }

    async def filter_ai_response(
        self,
        response: str,
        user_id: str,
        tool_calls_made: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[str, List[str]]:
        """
        Filter AI response to remove harmful or non-compliant content.

        Args:
            response: AI's generated response
            user_id: User identifier
            tool_calls_made: Tools that were called (for context)

        Returns:
            Tuple of (filtered_response, list_of_violations)
        """
        try:
            violations = []
            filtered_response = response

            # A harmful sentence cannot be repaired by swapping words: the whole response goes
            for pattern in self.harmful_response_patterns:
                if re.search(pattern, filtered_response.lower()):
                    violations.append(f"Harmful pattern: {pattern}")
                    logger.warning(f"[COMPLIANCE] Harmful pattern detected in response for user {user_id}")
            if violations:
                logger.warning(f"[COMPLIANCE] Response filtered for user {user_id}: {violations}")
                return self.SAFE_RESPONSE, violations

            # Ensure responsible gambling disclaimer is present for betting advice
            betting_advice_keywords = ["scommetti", "punta", "consiglio", "bet", "dovrest"]
            if any(keyword in response.lower() for keyword in betting_advice_keywords):
                if "responsabil" not in response.lower() and "disclaimer" not in response.lower():
                    # Add disclaimer
                    disclaimer = "\n\n⚠️ **Gioca responsabilmente**: Le scommesse comportano rischi. Scommetti solo ciò che puoi permetterti di perdere."
                    filtered_response += disclaimer
                    logger.info(f"[COMPLIANCE] Added responsible gambling disclaimer for user {user_id}")

            # Check if response encourages excessive betting
            if "all-in" in response.lower() or "tutto su" in response.lower():
                violations.append("Encourages excessive betting")
                filtered_response = self.SAFE_RESPONSE

            # Log violations
            if violations:
                logger.warning(f"[COMPLIANCE] Response filtered for user {user_id}: {violations}")

            return filtered_response, violations

        except Exception as e:
            logger.error(f"[COMPLIANCE] Error filtering response: {str(e)}", exc_info=True)
            # Return original response on error
            return response, [f"Filter error: {str(e)}"]

    def _check_patterns(self, text: str, patterns: List[str]) -> Optional[str]:
        """Check if text matches any pattern in the list."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return pattern
        return None

    def _get_intervention_message(self, risk_level: str) -> str:
        """Get appropriate intervention message based on risk level."""
        messages = {
            "crisis": """Mi dispiace che tu stia così male. Grazie per avermelo scritto.

Non devi affrontare tutto questo senza aiuto: parla subito con qualcuno.

- 📞 Emergenza: **112**
- 📞 Telefono Amico Italia: **02 2327 2327**

Anche i debiti di gioco si possono affrontare, con il giusto aiuto:
- 📞 Numero Verde: **800 55 88 22** (Gioco Responsabile)""",

            "critical": """🚨 **Rilevato comportamento a rischio**

Mi preoccupo per te. Il tuo messaggio suggerisce che potresti avere difficoltà con il gioco.

**Aiuto immediato:**
- 📞 Numero Verde: **800 55 88 22** (Gioco Responsabile)
- 🌐 Sito web: https://www.giocaresponsabile.it
- 💬 Chat assistenza: https://www.adm.gov.it/portale/assistenza

**Risorse:**
- Giocatori Anonimi Italia
- Consulta Nazionale Antiusura

Non sei solo. Chiedi aiuto a un professionista.

Non posso continuare questa conversazione, ma sono qui se vuoi parlare d'altro.""",

            "high": """⚠️ **Attenzione: Gioco Responsabile**

Ho notato che stai scommettendo frequentemente o con importi significativi.

**Ricordati:**
- Gioca solo per divertimento
- Scommetti solo ciò che puoi permetterti di perdere
- Fai pause regolari
- Non cercare di recuperare le perdite

**Se hai bisogno di aiuto:**
📞 Numero Verde: **800 55 88 22**

Vuoi che parliamo di qualcos'altro o desideri informazioni sul gioco responsabile?""",

            "warning": """💡 **Promemoria: Gioco Responsabile**

Ricorda che le scommesse devono essere un'attività ricreativa, non un modo per guadagnare denaro.

**Consigli:**
- Stabilisci un budget e rispettalo
- Non scommettere sotto pressione emotiva
- Le probabilità sono sempre a favore del bookmaker

Posso aiutarti con analisi e informazioni, ma la decisione finale è sempre tua!"""
        }

        return messages.get(risk_level, "")

    async def _analyze_conversation_history(
        self,
        user_id: str,
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Analyze conversation history for behavioral risk patterns.

        Patterns to detect:
        - Frequency of betting queries (too many in short time)
        - Escalating bet amounts
        - Emotional language
        - Loss-chasing behavior
        """
        result = {
            "risk_level": "none",
            "notes": []
        }

        # Count betting-related messages in history
        betting_messages = 0
        for msg in conversation_history[-10:]:  # Last 10 messages
            if msg["role"] == "user":
                content_lower = msg.get("content", "").lower()
                betting_keywords = ["scommetti", "punta", "quota", "bet", "odds"]
                if any(keyword in content_lower for keyword in betting_keywords):
                    betting_messages += 1

        # High frequency of betting queries
        if betting_messages >= 7:
            result["risk_level"] = "medium"
            result["notes"].append(f"High frequency: {betting_messages}/10 messages about betting")

        # Check for emotional escalation
        recent_user_messages = [
            msg["content"]
            for msg in conversation_history[-5:]
            if msg["role"] == "user"
        ]

        emotional_keywords = ["devo", "bisogno", "urgente", "subito", "ora"]
        emotional_count = sum(
            1 for msg in recent_user_messages
            if any(keyword in msg.lower() for keyword in emotional_keywords)
        )

        if emotional_count >= 3:
            result["risk_level"] = max(result["risk_level"], "medium", key=lambda x: ["none", "low", "medium"].index(x))
            result["notes"].append("Emotional language pattern detected")

        return result

    async def _update_user_risk_score(self, user_id: str, risk_level: str):
        """Update user's accumulated risk score."""
        risk_points = {
            "none": 0,
            "low": 1,
            "medium": 3,
            "high": 5,
            "critical": 10
        }

        points = risk_points.get(risk_level, 0)
        self.user_risk_scores[user_id] += points

        logger.debug(f"[COMPLIANCE] User {user_id} risk score: {self.user_risk_scores[user_id]}")

    async def _log_intervention(self, user_id: str, risk_level: str, pattern: str):
        """Log intervention for compliance records."""
        intervention = {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "risk_level": risk_level,
            "pattern_matched": pattern
        }

        self.intervention_history[user_id].append(intervention)

        logger.warning(
            f"[COMPLIANCE] INTERVENTION logged - "
            f"User: {user_id}, Risk: {risk_level}, Pattern: {pattern}"
        )

    async def get_user_risk_assessment(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive risk assessment for a user.

        Returns:
            Dictionary with risk score, intervention history, and recommendations
        """
        return {
            "user_id": user_id,
            "risk_score": self.user_risk_scores.get(user_id, 0),
            "risk_category": self._get_risk_category(self.user_risk_scores.get(user_id, 0)),
            "interventions_count": len(self.intervention_history.get(user_id, [])),
            "last_intervention": (
                self.intervention_history[user_id][-1]
                if self.intervention_history.get(user_id)
                else None
            ),
            "recommendations": self._get_recommendations(user_id)
        }

    def _get_risk_category(self, score: float) -> str:
        """Convert numeric risk score to category."""
        if score >= 15:
            return "critical"
        elif score >= 10:
            return "high"
        elif score >= 5:
            return "medium"
        elif score >= 2:
            return "low"
        else:
            return "none"

    def _get_recommendations(self, user_id: str) -> List[str]:
        """Get recommendations based on user's risk profile."""
        score = self.user_risk_scores.get(user_id, 0)
        recommendations = []

        if score >= 10:
            recommendations.append("Consider implementing betting limits")
            recommendations.append("Suggest self-exclusion options")
            recommendations.append("Provide gambling addiction resources")
        elif score >= 5:
            recommendations.append("Display responsible gambling reminders more frequently")
            recommendations.append("Monitor for escalation")
        elif score >= 2:
            recommendations.append("Continue normal monitoring")

        return recommendations

    async def reset_user_risk_score(self, user_id: str, reason: str):
        """
        Reset user's risk score (e.g., after successful self-exclusion period).

        Args:
            user_id: User identifier
            reason: Reason for reset (for logging)
        """
        old_score = self.user_risk_scores.get(user_id, 0)
        self.user_risk_scores[user_id] = 0

        logger.info(
            f"[COMPLIANCE] Risk score reset for user {user_id}. "
            f"Old score: {old_score}, Reason: {reason}"
        )
