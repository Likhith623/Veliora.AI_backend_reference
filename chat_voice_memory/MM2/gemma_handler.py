import os
from huggingface_hub import login

# Get HF token from environment and login
hf_token = os.getenv("HF_TOKEN")
if hf_token and hf_token.startswith("hf_"):
    login(token=hf_token)
else:
    print(f"Warning: HF_TOKEN is not set or invalid: {hf_token}")

from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from accelerate import disk_offload
from typing import List, Dict, Optional
import logging

class GemmaHandler:
    def __init__(
        self,
        model_name: str = "distilgpt2",
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        max_length: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.95
    ):
        """
        Initialize the Gemma model handler.
        
        Args:
            model_name: Name of the Gemma model to use
            device: Device to run the model on ('cuda' or 'cpu')
            max_length: Maximum length of generated text
            temperature: Sampling temperature (higher = more random)
            top_p: Nucleus sampling parameter
        """
        self.device = device
        self.max_length = max_length
        self.temperature = temperature
        self.top_p = top_p
        
        # Load model and tokenizer with explicit token
        token = os.environ.get("HF_TOKEN")
        print("[DEBUG] HF_TOKEN used for Gemma:", token)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=token)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto",
            token=token
        )
        # Disk offloading removed for faster inference with small models like distilgpt2

    def generate_text(
        self,
        prompt: str,
        params: Optional[Dict] = None
    ) -> str:
        """
        Generate text based on the given prompt.
        Args:
            prompt: Input text prompt
            params: Optional dictionary for generation parameters
        Returns:
            Generated text
        """
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        # Build generation parameters
        generation_params = {
            'max_new_tokens': self.max_length,
            'temperature': self.temperature,
            'top_p': self.top_p,
            'do_sample': True,
            'pad_token_id': self.tokenizer.eos_token_id
        }
        # Update with any provided parameters
        if params:
            generation_params.update(params)
        outputs = self.model.generate(
            **inputs,
            **generation_params
        )
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    def chat(
        self,
        messages: List[dict],
        params: Optional[Dict] = None
    ) -> str:
        """
        Generate a chat response based on conversation history.
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            params: Optional dictionary for generation parameters
        Returns:
            Generated response
        """
        # Format conversation history
        formatted_prompt = ""
        for message in messages:
            role = message.get('role', 'user')
            content = message.get('content', '')
            formatted_prompt += f"{role}: {content}\n"
        formatted_prompt += "assistant: "
        return self.generate_text(
            formatted_prompt,
            params=params
        )