#bettingbot/src/backend/handler.py
from transformers import pipeline
import torch
from huggingface_hub import InferenceClient, login
import os
import streamlit as st

class LLMHandler:
    def __init__(self):
        self.model_name = "meta-llama/Llama-3.3-70B-Instruct"
        self.hf_token = os.getenv('HUGGINGFACE_TOKEN')
        # Initialize the client only once
        if 'inference_client' not in st.session_state:
            st.session_state.inference_client = InferenceClient(token=self.hf_token)

    @st.cache_resource
    def get_model(_self):
        try:
            if _self.hf_token:
                login(token=_self.hf_token)
            return pipeline(
                "text-generation",
                model=_self.model_name,
                device_map="auto",
                torch_dtype=torch.float16,
                trust_remote_code=True,
                token=_self.hf_token
            )
        except Exception as e:
            print(f"Error initializing model: {str(e)}")
            raise

    def get_response(self, prompt, is_full_prompt=False):
        """
        If is_full_prompt=False, we wrap 'prompt' in <|im_start|>user ... <|im_end|>,
        otherwise we assume 'prompt' is a fully constructed conversation string
        ending with <|im_start|>assistant
        """
        try:
            if not is_full_prompt:
                # Single-turn approach
                formatted_prompt = (
                    f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant"
                )
            else:
                # If the caller built the entire conversation
                formatted_prompt = prompt

            # Generate a response using the InferenceClient
            response = st.session_state.inference_client.text_generation(
                formatted_prompt,
                model=self.model_name,
                max_new_tokens=512,
                temperature=0.35,
                top_p=0.9,
                repetition_penalty=1.1
            )

            # Extract text after <|im_start|>assistant
            response = response.split("<|im_start|>assistant")[-1].strip()
            if "<|im_end|>" in response:
                response = response.split("<|im_end|>")[0].strip()

            return response

        except Exception as e:
            return f"An error occurred: {str(e)}"
        
    
    def rename_chat(self, chat_id, new_chat_name):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE chats
            SET chat_name = ?
            WHERE chat_id = ?
        ''', (new_chat_name, chat_id))
        self.conn.commit()
