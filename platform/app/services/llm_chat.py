import os
import httpx
import asyncio
import logging
from typing import Dict, Any, Optional, List

# --- Configuration ---
# Read sensitive data from environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")
HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://example.invalid")
X_TITLE = os.getenv("OPENROUTER_TITLE", "FIP")

# OpenRouter Response API URL for advanced features
OPENROUTER_RESPONSES_URL = "https://openrouter.ai/api/v1/responses"

logger = logging.getLogger(__name__)


class OpenRouterConfig:
    """
    Advanced OpenRouter configuration with caching, session tracking, and reasoning

    Based on OpenRouter Responses API documentation
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        enable_caching: bool = True,
        reasoning_effort: str = "medium",  # none, minimal, low, medium, high, xhigh
        response_format: Optional[str] = None,  # text, json_object, json_schema
        metadata: Optional[Dict[str, str]] = None
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.enable_caching = enable_caching
        self.reasoning_effort = reasoning_effort
        self.response_format = response_format
        self.metadata = metadata or {}
        self.prompt_cache_key: Optional[str] = None
        self.previous_response_id: Optional[str] = None

    def to_payload_params(self) -> Dict[str, Any]:
        """Convert config to OpenRouter API parameters"""
        params = {}

        # Session tracking for conversation grouping
        if self.session_id:
            params["session_id"] = self.session_id[:128]  # Max 128 chars

        # User tracking for abuse prevention
        if self.user_id:
            params["user"] = self.user_id[:128]

        # Metadata for observability
        if self.metadata:
            params["metadata"] = self.metadata

        # Prompt caching for cost reduction
        if self.enable_caching and self.prompt_cache_key:
            params["prompt_cache_key"] = self.prompt_cache_key

        # Previous response linking for context continuity
        if self.previous_response_id:
            params["previous_response_id"] = self.previous_response_id

        # Reasoning configuration for better quality
        if self.reasoning_effort and self.reasoning_effort != "none":
            params["reasoning"] = {
                "effort": self.reasoning_effort,
                "enabled": True
            }

        # Response format control
        if self.response_format:
            if self.response_format == "json_object":
                params["text"] = {
                    "format": {"type": "json_object"}
                }
            elif self.response_format == "text":
                params["text"] = {
                    "format": {"type": "text"}
                }

        return params


async def send_llm_message(
    messages: List[Dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_retries: int = 3,
    config: Optional[OpenRouterConfig] = None
) -> str:
    """
    Sends messages to the OpenRouter LLM and returns the reply with enhanced features.

    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model to use (default from env)
        temperature: Sampling temperature (0-1)
        max_retries: Number of retry attempts
        config: Optional OpenRouterConfig for advanced features

    Features:
        - Session tracking for conversation grouping
        - Prompt caching for cost reduction
        - Reasoning control for response quality
        - Metadata tracking for observability
    """
    if not OPENROUTER_API_KEY:
        logger.error("[OPENROUTER] Missing OPENROUTER_API_KEY environment variable")
        return "[OpenRouter API error] Missing OPENROUTER_API_KEY env var."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": HTTP_REFERER,
        "X-Title": X_TITLE,
    }

    # Base payload
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature
    }

    # Add advanced OpenRouter features if config provided
    if config:
        advanced_params = config.to_payload_params()
        payload.update(advanced_params)

        # Log session tracking
        if config.session_id:
            logger.info(f"[OPENROUTER] Session ID: {config.session_id[:16]}...")
        if config.enable_caching and config.prompt_cache_key:
            logger.info(f"[OPENROUTER] Using prompt cache: {config.prompt_cache_key[:16]}...")
        if config.reasoning_effort != "none":
            logger.info(f"[OPENROUTER] Reasoning effort: {config.reasoning_effort}")
    
    for attempt in range(max_retries):
        try:
            logging.info(f"[OPENROUTER] Attempt {attempt + 1}/{max_retries} - Sending request to {model}")
            
            # Timeout configurabile: 60 secondi per richieste complesse
            timeout = httpx.Timeout(60.0, connect=10.0)
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
                
                # Log della risposta per debug
                logging.info(f"[OPENROUTER] Response status: {response.status_code}")
                
                # Gestione specifica degli errori HTTP
                if response.status_code == 429:
                    # Rate limiting - attendi prima di riprovare
                    wait_time = min(30, 2 ** attempt)  # Backoff esponenziale
                    logging.warning(f"[OPENROUTER] Rate limit hit, waiting {wait_time}s before retry")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return "[OpenRouter API error] Rate limit exceeded. Riprova tra qualche minuto."
                
                elif response.status_code == 401:
                    logging.error(f"[OPENROUTER] Authentication failed - check API key")
                    return "[OpenRouter API error] Autenticazione fallita. Controlla la configurazione API."
                
                elif response.status_code == 503:
                    # Servizio non disponibile - riprova
                    wait_time = min(10, 2 ** attempt)
                    logging.warning(f"[OPENROUTER] Service unavailable, waiting {wait_time}s before retry")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return "[OpenRouter API error] Servizio temporaneamente non disponibile."
                
                # Solleva eccezione per altri errori HTTP
                response.raise_for_status()
                
                # Parse della risposta JSON
                try:
                    data = response.json()
                except Exception as json_error:
                    logging.error(f"[OPENROUTER] JSON parsing error: {json_error}")
                    return "[OpenRouter API error] Risposta non valida dal servizio AI."
                
                # Validazione rigorosa della struttura della risposta secondo la documentazione OpenRouter
                if not isinstance(data, dict):
                    logging.error(f"[OPENROUTER] Response is not a valid JSON object: {type(data)}")
                    return "[OpenRouter API error] Formato risposta non valido."
                
                # Controllo presenza di errori nell'API
                if "error" in data:
                    error_info = data["error"]
                    if isinstance(error_info, dict):
                        error_msg = error_info.get("message", "Errore sconosciuto dall'API OpenRouter")
                        error_type = error_info.get("type", "unknown")
                        logging.error(f"[OPENROUTER] API error [{error_type}]: {error_msg}")
                        return f"[OpenRouter API error] {error_msg}"
                    else:
                        logging.error(f"[OPENROUTER] API error: {error_info}")
                        return f"[OpenRouter API error] {error_info}"
                
                # Validazione struttura choices secondo documentazione OpenRouter
                if "choices" not in data:
                    logging.error(f"[OPENROUTER] Missing 'choices' field in response: {list(data.keys())}")
                    return "[OpenRouter API error] Risposta malformata - campo 'choices' mancante."
                
                choices = data["choices"]
                if not isinstance(choices, list) or len(choices) == 0:
                    logging.error(f"[OPENROUTER] Invalid or empty choices array: {choices}")
                    return "[OpenRouter API error] Nessuna scelta disponibile nella risposta."
                
                # Estrazione del primo choice
                choice = choices[0]
                if not isinstance(choice, dict):
                    logging.error(f"[OPENROUTER] Invalid choice format: {type(choice)}")
                    return "[OpenRouter API error] Formato scelta non valido."
                
                # Validazione struttura message
                if "message" not in choice:
                    logging.error(f"[OPENROUTER] Missing 'message' field in choice: {list(choice.keys())}")
                    return "[OpenRouter API error] Campo 'message' mancante nella risposta."
                
                message = choice["message"]
                if not isinstance(message, dict):
                    logging.error(f"[OPENROUTER] Invalid message format: {type(message)}")
                    return "[OpenRouter API error] Formato messaggio non valido."
                
                # Estrazione contenuto
                if "content" not in message:
                    logging.error(f"[OPENROUTER] Missing 'content' field in message: {list(message.keys())}")
                    return "[OpenRouter API error] Campo 'content' mancante nel messaggio."
                
                content = message["content"]
                if not isinstance(content, str):
                    logging.error(f"[OPENROUTER] Content is not a string: {type(content)}")
                    return "[OpenRouter API error] Contenuto non è una stringa valida."
                
                if not content.strip():
                    logging.warning(f"[OPENROUTER] Empty content in response")
                    return "[OpenRouter API error] Risposta vuota dal servizio AI."
                
                # Log informazioni aggiuntive se disponibili
                if "usage" in data:
                    usage = data["usage"]
                    if isinstance(usage, dict):
                        total_tokens = usage.get("total_tokens", "N/A")
                        logging.info(f"[OPENROUTER] Token usage: {total_tokens}")
                
                logging.info(f"[OPENROUTER] Successfully received response ({len(content)} chars)")
                return content
                    
        except httpx.TimeoutException as timeout_error:
            logging.warning(f"[OPENROUTER] Timeout on attempt {attempt + 1}: {timeout_error}")
            if attempt < max_retries - 1:
                wait_time = min(5, 2 ** attempt)
                await asyncio.sleep(wait_time)
                continue
            else:
                return "[OpenRouter API error] Timeout - il servizio AI non risponde."
                
        except httpx.ConnectError as conn_error:
            logging.warning(f"[OPENROUTER] Connection error on attempt {attempt + 1}: {conn_error}")
            if attempt < max_retries - 1:
                wait_time = min(5, 2 ** attempt)
                await asyncio.sleep(wait_time)
                continue
            else:
                return "[OpenRouter API error] Impossibile connettersi al servizio AI."
                
        except Exception as e:
            logging.error(f"[OPENROUTER] Unexpected error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait_time = min(5, 2 ** attempt)
                await asyncio.sleep(wait_time)
                continue
            else:
                return f"[OpenRouter API error] Errore imprevisto: {str(e)}"
    
    # Se arriviamo qui, tutti i tentativi sono falliti
    logging.error(f"[OPENROUTER] All {max_retries} attempts failed")
    return "[OpenRouter API error] Tutti i tentativi di connessione sono falliti."