import os
import httpx
import asyncio
import logging
from fastapi import HTTPException, status

# --- Configuration ---
# Read sensitive data from environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")
HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://example.invalid")
X_TITLE = os.getenv("OPENROUTER_TITLE", "FIP")

async def send_llm_message(messages, model: str = DEFAULT_MODEL, temperature=0.7, max_retries: int = 3):
    """
    Sends messages to the OpenRouter LLM and returns the reply.
    Includes improved error handling, timeout, and retry logic.
    """
    if not OPENROUTER_API_KEY:
        logging.error("[OPENROUTER] Missing OPENROUTER_API_KEY environment variable")
        return "[OpenRouter API error] Missing OPENROUTER_API_KEY env var."

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": HTTP_REFERER,
        "X-Title": X_TITLE,
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature
    }
    
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