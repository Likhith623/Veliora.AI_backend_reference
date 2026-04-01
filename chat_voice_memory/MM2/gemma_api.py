from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
from MM2.gemma_handler import GemmaHandler
import logging
import re

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Gemma handler
gemma = GemmaHandler()


def clean_response(text: str) -> str:
    """Clean and validate model response"""
    if not text or not isinstance(text, str):
        return "I apologize, but I couldn't generate a proper response."
    
    # Remove excessive repetition
    text = re.sub(r'(.)\1{10,}', r'\1', text)  # Remove 10+ repeated chars
    text = re.sub(r'(\w+\s+)\1{5,}', r'\1', text)  # Remove repeated words
    
    # Remove special tokens that might leak through
    text = re.sub(r'<\|.*?\|>', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    
    # Clean whitespace
    text = ' '.join(text.split())
    
    # Ensure reasonable length
    if len(text) > 2000:
        text = text[:2000] + "..."
    
    return text.strip()


# Define a Message model for better OpenAPI docs and validation
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    max_new_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    repetition_penalty: Optional[float] = 1.1

class TextRequest(BaseModel):
    prompt: str
    max_new_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    repetition_penalty: Optional[float] = 1.1

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint for Gemma LLM.
    
    Args:
        request: ChatRequest object containing messages and optional parameters
        
    Returns:
        Generated response
    """
    try:
        # Build parameters dict with better defaults
        params = {
            'max_new_tokens': request.max_new_tokens,
            'temperature': request.temperature,
            'top_p': request.top_p,
            'do_sample': True,
            'pad_token_id': gemma.tokenizer.pad_token_id if gemma.tokenizer.pad_token_id is not None else gemma.tokenizer.eos_token_id,
            'eos_token_id': gemma.tokenizer.eos_token_id,
            'repetition_penalty': request.repetition_penalty
        }

        # Call GemmaHandler.chat (should be synchronous)
        response = gemma.chat(
            messages=[msg.dict() for msg in request.messages],
            params=params
        )
        
        # Clean the response
        cleaned_response = clean_response(response)
        
        return {"response": cleaned_response}
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate")
async def generate_endpoint(request: TextRequest):
    """
    Text generation endpoint for Gemma LLM.
    
    Args:
        request: TextRequest object containing prompt and optional parameters
        
    Returns:
        Generated text
    """
    try:
        # Build parameters dict with better defaults
        params = {
            'max_new_tokens': request.max_new_tokens,
            'temperature': request.temperature,
            'top_p': request.top_p,
            'do_sample': True,
            'pad_token_id': gemma.tokenizer.pad_token_id if gemma.tokenizer.pad_token_id is not None else gemma.tokenizer.eos_token_id,
            'eos_token_id': gemma.tokenizer.eos_token_id,
            'repetition_penalty': request.repetition_penalty
        }

        # Call GemmaHandler.generate_text (should be synchronous)
        response = gemma.generate_text(
            prompt=request.prompt,
            params=params
        )
        
        # Clean the response
        cleaned_response = clean_response(response)
        
        return {"response": cleaned_response}
    except Exception as e:
        logger.error(f"Error in generate endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
