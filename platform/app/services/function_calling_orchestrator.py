"""
Function Calling Orchestrator for Autonomous AI Agent

This orchestrator enables the LLM to autonomously decide when and how to call
external tools (APIs, databases, services) to answer user queries.

Key Features:
- Multi-turn function calling (LLM can call multiple tools in sequence)
- Automatic tool result integration into conversation
- Error handling and fallback strategies
- Conversation history management
- Tool execution logging and metrics
"""

import logging
import json
import httpx
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.tools.football_tools import FootballTools

logger = logging.getLogger(__name__)

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "mistralai/devstral-2512:free")
HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://example.invalid")
X_TITLE = os.getenv("OPENROUTER_TITLE", "FIP")


class FunctionCallingOrchestrator:
    """
    Orchestrates autonomous function calling for the AI agent.

    This class manages the full lifecycle of function calling:
    1. Send user message + tool definitions to LLM
    2. LLM decides which tools to call (if any)
    3. Execute tool calls and collect results
    4. Send tool results back to LLM
    5. LLM formulates final response
    6. Repeat if LLM requests more tool calls
    """

    def __init__(self):
        self.football_tools = FootballTools()
        self.max_iterations = 5  # Prevent infinite loops
        self.tool_definitions = self.football_tools.get_tool_definitions()

    async def process_message(
        self,
        message: str,
        user_id: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        model: str = DEFAULT_MODEL,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a user message with autonomous function calling.

        Args:
            message: User's message
            user_id: Unique user identifier
            conversation_history: Previous conversation messages
            model: OpenRouter model to use
            session_id: Optional session ID for tracking

        Returns:
            Dictionary containing:
            - reply: Final text response to user
            - tool_calls_made: List of tools that were called
            - conversation_history: Updated conversation history
            - metadata: Additional information about the interaction
        """
        try:
            # Initialize conversation history
            if conversation_history is None:
                conversation_history = []

            # Add system prompt with FIP context
            messages = self._build_messages(message, conversation_history)

            # Track function calling iterations
            iteration = 0
            tool_calls_made = []
            total_start_time = datetime.now()

            logger.info(f"[ORCHESTRATOR] Starting autonomous processing for user {user_id}")

            while iteration < self.max_iterations:
                iteration += 1
                logger.info(f"[ORCHESTRATOR] Iteration {iteration}/{self.max_iterations}")

                # Call LLM with tool definitions
                llm_response = await self._call_llm_with_tools(
                    messages=messages,
                    model=model,
                    user_id=user_id,
                    session_id=session_id
                )

                # Check if LLM returned an error
                if "error" in llm_response:
                    logger.error(f"[ORCHESTRATOR] LLM error: {llm_response['error']}")
                    return {
                        "reply": "Mi dispiace, si è verificato un errore. Riprova tra poco.",
                        "tool_calls_made": tool_calls_made,
                        "conversation_history": conversation_history,
                        "metadata": {
                            "error": llm_response["error"],
                            "iterations": iteration
                        }
                    }

                # Extract tool calls from response
                tool_calls = llm_response.get("tool_calls", [])

                # If no tool calls, LLM has provided final answer
                if not tool_calls:
                    final_response = llm_response.get("content", "")
                    logger.info(f"[ORCHESTRATOR] Final response ready after {iteration} iterations")

                    # Add assistant message to history
                    conversation_history.append({
                        "role": "assistant",
                        "content": final_response
                    })

                    total_time = (datetime.now() - total_start_time).total_seconds()

                    return {
                        "reply": final_response,
                        "tool_calls_made": tool_calls_made,
                        "conversation_history": conversation_history,
                        "metadata": {
                            "iterations": iteration,
                            "total_tools_used": len(tool_calls_made),
                            "processing_time_seconds": total_time,
                            "model_used": model
                        }
                    }

                # Execute tool calls
                logger.info(f"[ORCHESTRATOR] LLM requested {len(tool_calls)} tool calls")
                tool_results = await self._execute_tools(tool_calls)

                # Track which tools were called
                for tool_call in tool_calls:
                    tool_calls_made.append({
                        "tool": tool_call["function"]["name"],
                        "arguments": tool_call["function"]["arguments"],
                        "iteration": iteration
                    })

                # Add assistant message with tool calls to conversation
                messages.append({
                    "role": "assistant",
                    "content": llm_response.get("content") or "",
                    "tool_calls": tool_calls
                })

                # Add tool results to conversation
                for i, result in enumerate(tool_results):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_calls[i]["id"],
                        "content": json.dumps(result)
                    })

                # Continue loop - LLM will now see tool results and can:
                # 1. Call more tools if needed
                # 2. Provide final answer based on results

            # Max iterations reached
            logger.warning(f"[ORCHESTRATOR] Max iterations ({self.max_iterations}) reached")
            return {
                "reply": "Mi dispiace, la richiesta è troppo complessa. Prova a semplificarla.",
                "tool_calls_made": tool_calls_made,
                "conversation_history": conversation_history,
                "metadata": {
                    "error": "max_iterations_reached",
                    "iterations": iteration,
                    "tool_calls": len(tool_calls_made)
                }
            }

        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Unexpected error: {str(e)}", exc_info=True)
            return {
                "reply": "Mi dispiace, si è verificato un errore imprevisto.",
                "tool_calls_made": [],
                "conversation_history": conversation_history or [],
                "metadata": {
                    "error": str(e)
                }
            }

    def _build_messages(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Build messages array for LLM with system prompt and history.
        """
        messages = []

        # System prompt with FIP context and guidelines
        system_prompt = """Sei FIP, un assistente esperto di scommesse calcistiche.

Obiettivo: Aiutare gli utenti a prendere decisioni informate sulle scommesse fornendo:
- Analisi dettagliate delle partite
- Quote comparate tra diversi bookmaker
- Predizioni basate su statistiche e intelligenza artificiale
- Statistiche approfondite su squadre e giocatori

Hai accesso a questi strumenti per recuperare dati in tempo reale:
1. **get_match_odds**: Recupera quote da vari bookmaker
2. **get_predictions**: Ottieni predizioni AI con analisi statistica
3. **search_matches**: Cerca partite per squadra, campionato o data
4. **get_team_stats**: Recupera statistiche dettagliate di una squadra

Linee guida:
- Usa gli strumenti AUTOMATICAMENTE quando necessario per rispondere
- Fornisci sempre analisi basate su dati reali, non opinioni
- Confronta sempre le quote quando possibile per trovare il miglior valore
- Includi disclaimer sul gioco responsabile quando appropriato
- Rispondi in italiano in modo chiaro e professionale
- Se l'utente chiede informazioni su una partita specifica, USA search_matches per trovarla
- Se l'utente chiede quote, USA get_match_odds
- Se l'utente chiede predizioni o analisi, USA get_predictions

IMPORTANTE: Ricordati SEMPRE il gioco responsabile. Non incoraggiare mai scommesse eccessive."""

        messages.append({
            "role": "system",
            "content": system_prompt
        })

        # Add conversation history (limit to last 10 messages to avoid token limits)
        recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        messages.extend(recent_history)

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        return messages

    async def _call_llm_with_tools(
        self,
        messages: List[Dict[str, str]],
        model: str,
        user_id: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call OpenRouter LLM with tool definitions.

        Returns:
            Dictionary with either:
            - content: Text response
            - tool_calls: List of tool calls to execute
            - error: Error message
        """
        try:
            if not OPENROUTER_API_KEY:
                logger.error("[ORCHESTRATOR] Missing OPENROUTER_API_KEY")
                return {"error": "API key not configured"}

            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": HTTP_REFERER,
                "X-Title": X_TITLE,
            }

            payload = {
                "model": model,
                "messages": messages,
                "tools": self.tool_definitions,
                "tool_choice": "auto",  # Let LLM decide when to use tools
                "temperature": 0.7
            }

            # Add session tracking if provided
            if session_id:
                payload["session_id"] = session_id[:128]
            if user_id:
                payload["user"] = user_id[:128]

            logger.info(f"[ORCHESTRATOR] Calling {model} with {len(self.tool_definitions)} tools available")

            timeout = httpx.Timeout(60.0, connect=10.0)

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload
                )

                logger.info(f"[ORCHESTRATOR] OpenRouter response status: {response.status_code}")

                if response.status_code != 200:
                    error_text = response.text
                    logger.error(f"[ORCHESTRATOR] API error: {error_text}")
                    return {"error": f"API returned {response.status_code}"}

                data = response.json()

                # Check for API errors
                if "error" in data:
                    error_msg = data["error"].get("message", "Unknown error")
                    logger.error(f"[ORCHESTRATOR] API error: {error_msg}")
                    return {"error": error_msg}

                # Extract response
                if "choices" not in data or len(data["choices"]) == 0:
                    logger.error("[ORCHESTRATOR] No choices in response")
                    return {"error": "No response from LLM"}

                choice = data["choices"][0]
                message = choice.get("message", {})

                # Check if LLM wants to call tools
                if "tool_calls" in message and message["tool_calls"]:
                    logger.info(f"[ORCHESTRATOR] LLM requested {len(message['tool_calls'])} tool calls")
                    return {
                        "content": message.get("content"),
                        "tool_calls": message["tool_calls"]
                    }

                # LLM provided direct response
                content = message.get("content", "")
                logger.info(f"[ORCHESTRATOR] LLM provided direct response ({len(content)} chars)")
                return {"content": content}

        except httpx.TimeoutException:
            logger.error("[ORCHESTRATOR] Request timeout")
            return {"error": "Request timeout"}
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Unexpected error calling LLM: {str(e)}", exc_info=True)
            return {"error": str(e)}

    async def _execute_tools(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute multiple tool calls and return results.

        Args:
            tool_calls: List of tool call objects from LLM

        Returns:
            List of tool execution results
        """
        results = []

        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]

            # Parse arguments (they come as JSON string)
            try:
                arguments = json.loads(tool_call["function"]["arguments"])
            except json.JSONDecodeError as e:
                logger.error(f"[ORCHESTRATOR] Failed to parse tool arguments: {str(e)}")
                results.append({
                    "error": "Invalid tool arguments format"
                })
                continue

            logger.info(f"[ORCHESTRATOR] Executing tool: {function_name}")
            logger.debug(f"[ORCHESTRATOR] Arguments: {arguments}")

            # Execute the tool
            result = await self.football_tools.execute_tool(function_name, arguments)

            logger.info(f"[ORCHESTRATOR] Tool {function_name} executed, success: {result.get('success', False)}")

            results.append(result)

        return results

    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get status of the function calling system.

        Returns:
            Dictionary with system health information
        """
        return {
            "status": "operational",
            "tools_available": len(self.tool_definitions),
            "tools": [tool["function"]["name"] for tool in self.tool_definitions],
            "max_iterations": self.max_iterations,
            "model": DEFAULT_MODEL,
            "api_configured": bool(OPENROUTER_API_KEY)
        }
