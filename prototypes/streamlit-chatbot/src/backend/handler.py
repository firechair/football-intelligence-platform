import os
import re
import requests
import json
import streamlit as st
import traceback
from typing import Optional, Dict, Any, List, Union

class LLMHandler:
    def __init__(self):
        # OpenRouter API settings
        self.base_url = "https://openrouter.ai/api/v1"
        self.api_key = "REDACTED"
        
        # Default to Claude 3.7 Sonnet, but you can change to any model available on OpenRouter
        self.model_name = "google/gemini-2.5-pro-exp-03-25:free"
        
        # Your app info (optional but recommended for OpenRouter statistics)
        self.app_info = {
            "X-Title": "Betting Bot Assistant"  # Update with your app name
        }
        
        # Debug mode
        self.debug_mode = st.session_state.get('debug_mode', False)
        
        # Initialize the session state for caching if needed
        if 'openrouter_session' not in st.session_state:
            st.session_state.openrouter_session = {}
    
    def _get_headers(self) -> Dict[str, str]:
        """Return headers for OpenRouter API requests"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Add app info headers if available
        if self.app_info:
            headers.update(self.app_info)
            
        return headers

    def _parse_claude_style_prompt(self, prompt: str) -> List[Dict[str, str]]:
        """
        Parse Claude-style prompts with <|im_start|> and <|im_end|> tags
        into messages list for the OpenRouter API
        """
        messages = []
        
        # Extract system message for use in the first user message
        system_content = ""
        system_pattern = r"<\|im_start\|>system\n(.*?)<\|im_end\|>"
        system_matches = re.findall(system_pattern, prompt, re.DOTALL)
        if system_matches:
            system_content = "\n\n".join(system_matches)
        
        # Extract user/assistant messages
        pattern = r"<\|im_start\|>(user|assistant)\n(.*?)<\|im_end\|>"
        matches = re.findall(pattern, prompt, re.DOTALL)
        
        # Process message pairs
        for role, content in matches:
            # Add the message
            messages.append({
                "role": role,
                "content": content.strip()
            })
        
        # If there are no extracted messages, use the whole prompt
        if not messages:
            messages = [{"role": "user", "content": prompt}]
        
        # If we have system content, prepend it to the first user message
        # Since OpenRouter doesn't directly support system messages for all models
        if system_content and messages and messages[0]["role"] == "user":
            messages[0]["content"] = f"[SYSTEM INSTRUCTIONS]\n{system_content}\n\n[USER MESSAGE]\n{messages[0]['content']}"
        
        # Ensure the last message is from the user if we need to append assistant
        if not messages or messages[-1]["role"] != "assistant":
            if prompt.strip().endswith("<|im_start|>assistant"):
                # If prompt ends with assistant tag, we need to remove it and not add an empty message
                pass
            else:
                # Extract any assistant prompt at the end
                assistant_text = ""
                if "<|im_start|>assistant\n" in prompt:
                    assistant_parts = prompt.split("<|im_start|>assistant\n")
                    if len(assistant_parts) > 1 and assistant_parts[-1].strip():
                        assistant_text = assistant_parts[-1].strip()
                
                # Add assistant message if there's content
                if assistant_text:
                    messages.append({"role": "assistant", "content": assistant_text})
        
        if self.debug_mode:
            print(f"[DEBUG] Parsed messages: {json.dumps(messages, indent=2)[:500]}...")
        
        return messages
    
    def get_response(self, prompt: str, is_full_prompt: bool = False) -> str:
        """
        Get a response from the LLM via OpenRouter API
        
        Args:
            prompt (str): The user's input message
            is_full_prompt (bool): If True, assumes prompt is a full conversation;
                                   if False, wraps it as a single user message
        
        Returns:
            str: The model's response text
        """
        try:
            if self.debug_mode:
                print(f"[DEBUG] Getting response for prompt (is_full_prompt={is_full_prompt})")
                print(f"[DEBUG] Prompt first 200 chars: {prompt[:200]}...")
            
            # Construct messages in OpenAI format
            if not is_full_prompt:
                messages = [{"role": "user", "content": prompt}]
            else:
                # Parse the Claude-style prompt into messages
                messages = self._parse_claude_style_prompt(prompt)
            
            # OpenRouter API endpoint for chat completions
            endpoint = f"{self.base_url}/chat/completions"
            
            # Prepare request payload
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0.2,  # Low temperature for more deterministic responses
                "max_tokens": 8000,    # High token limit
                "top_p": 0.85,
                "repetition_penalty": 0.9
            }
            
            if self.debug_mode:
                print(f"[DEBUG] Sending request to {endpoint}")
                print(f"[DEBUG] Payload first 500 chars: {json.dumps(payload, indent=2)[:500]}...")
            
            # Send request to OpenRouter
            response = requests.post(
                endpoint,
                headers=self._get_headers(),
                json=payload
            )
            
            # Log API response for debugging
            if self.debug_mode:
                print(f"[DEBUG] API Response status: {response.status_code}")
                print(f"[DEBUG] API Response: {response.text[:500]}...")
                
            # Raise exception for bad status codes
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            
            # Extract the assistant's message content from the response
            if result and "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
                if self.debug_mode:
                    print(f"[DEBUG] Response content first 200 chars: {content[:200]}...")
                return content
            else:
                if self.debug_mode:
                    print(f"[DEBUG] Unexpected API response structure: {json.dumps(result, indent=2)}")
                return "Mi dispiace, non sono riuscito a generare una risposta. Prova a riformulare la tua domanda."
            
        except requests.exceptions.RequestException as e:
            if self.debug_mode:
                print(f"[DEBUG] API Request Error: {str(e)}")
                print(traceback.format_exc())
            return f"Errore di connessione all'API: {str(e)}"
        except json.JSONDecodeError as e:
            if self.debug_mode:
                print(f"[DEBUG] JSON Decode Error: {str(e)}")
                print(traceback.format_exc())
            return "Errore: Non sono riuscito a interpretare la risposta dell'API."
        except Exception as e:
            if self.debug_mode:
                print(f"[DEBUG] Unexpected Error: {str(e)}")
                print(traceback.format_exc())
            return f"Si è verificato un errore: {str(e)}"
    
    # Additional methods for stream mode if needed
    def get_streaming_response(self, prompt: str, is_full_prompt: bool = False):
        """
        Get a streaming response from the LLM via OpenRouter API.
        This returns a generator that yields content chunks as they arrive.
        
        Args:
            prompt (str): The user's input message
            is_full_prompt (bool): If True, assumes prompt is a full conversation;
                                if False, wraps it as a single user message
        
        Yields:
            str: Chunks of the model's response text
        """
        try:
            # Construct messages in OpenAI format
            if not is_full_prompt:
                messages = [{"role": "user", "content": prompt}]
            else:
                # Parse the Claude-style prompt into messages
                messages = self._parse_claude_style_prompt(prompt)
            
            # OpenRouter API endpoint for chat completions
            endpoint = f"{self.base_url}/chat/completions"
            
            # FIXED: Now uses the same parameters as get_response for consistency
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0.2,     # Now matches get_response
                "max_tokens": 8000,     # Now matches get_response
                "top_p": 0.85,          # Now matches get_response
                "repetition_penalty": 0.9,  # Fixed: Values > 1.0 penalize repetition
                "stream": True          # Enable streaming
            }
            
            # Send request to OpenRouter with streaming enabled
            response = requests.post(
                endpoint,
                headers=self._get_headers(),
                json=payload,
                stream=True  # Enable streaming on request
            )
            
            # Raise exception for bad status codes
            response.raise_for_status()
            
            # Process the stream
            buffer = ""
            for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                buffer += chunk
                
                while True:
                    # Find the next complete SSE line
                    line_end = buffer.find('\n')
                    if line_end == -1:
                        break
                        
                    line = buffer[:line_end].strip()
                    buffer = buffer[line_end + 1:]
                    
                    if line.startswith('data: '):
                        data = line[6:]
                        
                        if data == '[DONE]':
                            break
                            
                        try:
                            data_obj = json.loads(data)
                            content = data_obj.get("choices", [{}])[0].get("delta", {}).get("content")
                            
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            # Skip non-JSON data (like comments)
                            pass
            
        except requests.exceptions.RequestException as e:
            yield f"API Request Error: {str(e)}"
        except Exception as e:
            yield f"An error occurred: {str(e)}"