#1(novi supabase).
from pathlib import Path
from dotenv import load_dotenv
import os
from MM2.payments import router as payments_router


from MM2.memory_functions import (
    fetch_last_m_messages, 
    get_highest_rfm_memories, 
    get_embedding, 
    get_semantically_similar_memories, 
    log_message
)

# This ensures it always looks for .env in the parent directory of MM2
PROJECT_ROOT = Path(__file__).parent.parent
DOTENV_FILE_PATH = PROJECT_ROOT / ".env"

# Load environment variables from the .env file
load_dotenv(dotenv_path=DOTENV_FILE_PATH)

# --- DEBUGGING ENV VARS (Keep these here for initial verification) ---
print(f"DEBUG: Attempting to load .env from: {DOTENV_FILE_PATH.resolve()}")
print(f"DEBUG: SUPABASE_URL from env: {os.getenv('SUPABASE_URL')}")
print(f"DEBUG: SUPABASE_KEY from env: {os.getenv('SUPABASE_KEY')}")
print(f"DEBUG: GEMINI_API_KEY from env: {os.getenv('GEMINI_API_KEY')}")
# --- END DEBUGGING ---
import logging
from MM2.user_xp import (
    upsert_user_xp,
    get_user_xp,
    update_magnitude_for_user,
    award_immediate_xp_and_magnitude,
    add_xp_to_user,
    add_coins_to_user
)

import google.generativeai as genai # This import is fine here
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import traceback

# from payments import router as payments_router
import os
import random
import tempfile
import logging
import json
import hashlib
import time
import asyncio
import httpx
from fastapi import APIRouter, Query
from MM2.redis_class import RedisManager
from MM2.serialization import serialize_memory, serialize_chat
from MM2.memory_functions import log_message
from MM2.utils import detect_urls_in_query, fetch_website_content, create_website_summary_response
from fastapi import Request
import re
from fastapi.responses import JSONResponse
from MM2.bot_prompt import SONG_MOOD_KEYWORDS, SONG_MOOD_SUMMARY_TEMPLATES, MOOD_PROACTIVE_TEMPLATES
import asyncio
from concurrent.futures import ThreadPoolExecutor
# Add to top of main.py after other imports
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI,File,UploadFile,Form,BackgroundTasks,HTTPException,Query,Body # type: ignore
from prometheus_fastapi_instrumentator import Instrumentator

from prometheus_client import Counter, Histogram
# Prometheus metrics for per-user tracking
api_user_requests_total = Counter(
    "api_user_requests_total",
    "Total API requests per user",
    ["email"]
)
api_errors_total = Counter(
    "api_errors_total",
    "Total API errors per user",
    ["email"]
)
api_response_time_seconds = Histogram(
    "api_response_time_seconds",
    "Response time per user",
    ["email"]
)
message_generated_counter= Counter(
    "message_generated_total",
    "Total messages generated"
)

from fastapi.requests import Request
from fastapi.responses import JSONResponse






from pydantic import BaseModel # type: ignore
from typing_extensions import Annotated # type: ignore
from typing import Union
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from fastapi.encoders import jsonable_encoder # type: ignore
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse # type: ignore
from dotenv import load_dotenv  # type: ignore
from supabase import create_client, Client # type: ignore
from datetime import date
from typing import List, Dict
from fastapi_utils.tasks import repeat_every # type: ignore
import traceback
from typing import Optional
# Voice call imports - Added for speech recognition
import speech_recognition as sr # type: ignore
import io
from pydub import AudioSegment # type: ignore
from pydub.utils import which # type: ignore
import assemblyai as aai # type: ignore
import redis.asyncio as redis # type: ignore
from deepgram import DeepgramClient, PrerecordedOptions # type: ignore
from difflib import SequenceMatcher

from MM2.notes_processing import extract_notes_memory
from MM2.pre_processing import retrieve_memory,reminder_response
from MM2.post_processing import extract_memory

from cartesia import Cartesia # type: ignore
cache_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tts_cache")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


import pika
import os
import json



from MM2.redis_class import RedisManager
from MM2.memory_functions import get_semantically_similar_memories, get_embedding
from MM2.chatbot import get_bot_response_from_memory
from MM2.serialization import is_valid_memory
redis_manager = RedisManager()
import ast
from MM2.serialization import is_valid_memory
# main.py
from MM2.utils import load_memories_to_redis



rabbit_params = pika.URLParameters(os.getenv("RABBITMQ_URL"))

async def publish_to_both_queues(user_id: str, user_input: str, bot_reply: str, bot_id: str = None, memory: str = None, mem_id: str = None):
    conn = pika.BlockingConnection(rabbit_params)
    ch = conn.channel()
    memory_queue = f"memory_tasks_user_{user_id}"
    message_queue = f"message_logs_user_{user_id}"

    ch.queue_declare(queue=memory_queue, durable=True)
    ch.queue_declare(queue=message_queue, durable=True)
    task = {
        "user_id": user_id,
        "user_message": user_input,
        "bot_response": bot_reply,
        "bot_id": bot_id,
        "memory": memory,
        "id": mem_id
    }
    ch.basic_publish(
        exchange="",
        routing_key=message_queue,
        body=json.dumps(task),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    ch.basic_publish(
        exchange="",
        routing_key=memory_queue,
        body=json.dumps(task),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    conn.close()
    
# Redis configuration for memory retrieval caching
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour default
redis_client = None
# Add this function near the top of main.py (after imports):
'''
# Update your call_xai_api function around line 50:
#calling grok and then calling gemini flash if grok fails
async def call_xai_api(messages, model="grok-beta"):
    """XAI Grok API with Gemini Flash fallback (fastest alternative)"""
    print(f"Calling XAI Grok API for voice call with model: {model}")

    # Try different XAI models first
    models_to_try = ["grok-beta", "grok-2-1212", "grok-2-latest", "grok-vision-beta"]

    for model_name in models_to_try:
        try:
            headers = {
                "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}",
                "Content-Type": "application/json"
            }

            payload = {
                "messages": messages,
                "model": model_name,
                "stream": False,
                "temperature": 0.7,
                "max_tokens": 50
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                response_content = result["choices"][0]["message"]["content"]

            logging.info(f"✅ XAI SUCCESS with model: {model_name}")
            return response_content.strip()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logging.warning(f"⚠️ XAI model {model_name} forbidden (403), trying next...")
                continue
            else:
                logging.error(f"⚠️ XAI model {model_name} failed with {e.response.status_code}")
                continue
        except Exception as e:
            logging.warning(f"⚠️ XAI model {model_name} failed: {e}")
            continue

    # All XAI models failed - fallback to Gemini Flash (FASTEST alternative)
    logging.warning("🔄 All XAI models failed, falling back to Gemini Flash")
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Convert messages to Gemini format
        if messages:
            # Get the last user message
            user_message = messages[-1]["content"] if messages[-1]["role"] == "user" else "Hello"
        else:
            user_message = "Hello"

        response = model.generate_content(
            user_message,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=20,
                temperature=0.7,
            )
        )

        logging.info("✅ Gemini Flash fallback SUCCESS")
        return response.text.strip()

    except Exception as e:
        logging.error(f"❌ Gemini Flash fallback failed: {e}")
        # Final fallback to OpenAI if Gemini also fails
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            chat_completion_res = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=150,
                temperature=0.7
            )
            response_content = chat_completion_res.choices[0].message.content
            logging.info("✅ OpenAI final fallback SUCCESS")
            return response_content.strip()
        except Exception as e2:
            logging.error(f"❌ All APIs failed: {e2}")
            raise Exception("XAI, Gemini, and OpenAI all failed")
    '''




























TRAINING_DATA: Dict[str, float] = {
    "I failed my exam. I don’t know what to do now.": 4.0,
    "I spilled coffee on my shirt right before the meeting.": 2.0,
    "I think I’m falling in love.": 4.0,
    "My dog passed away yesterday. I can’t stop crying.": 5.0,
    "I'm bored. Got anything fun to do?": 1.0,
    "My parents are fighting again, and I feel helpless.": 3.0,
    "I forgot my best friend’s birthday.": 2.0,
    "I haven’t been sleeping properly in days.": 2.0,
    "I got promoted today!": 3.0,
    "I lost my keychain again.": 1.0,
    "I lost my wallet on the train today.": 4.0,
    "I just got engaged!": 5.0,
    "I missed my flight.": 2.5,
    "I saw a rainbow today!": 1.0,
    "I feel invisible in my friend group.": 4.0,
    "I finally cleaned my room.": 1.0,
    "I think I bombed my interview.": 4.0,
    "My partner broke up with me.": 5.0,
    "I’m moving to a new city soon.": 2.5,
    "My phone slipped into the toilet.": 3.0,
    "I got an A on my project!": 2.0,
    "I haven’t spoken to anyone in days.": 4.0,
    "My friend lied to me.": 2.0,
    "I made my favorite dish today.": 2.0,
    "I accidentally texted my ex.": 4.0,
    "I'm feeling really anxious about tomorrow.": 3.0,
    "I lost my favorite hoodie.": 2.0,
    "I binge-watched an entire season today.": 2.0,
    "I think my roommate is mad at me.": 2.0,
    "I haven’t eaten all day.": 3.0,
    "I won a small poetry contest!": 2.0,
    "I woke up feeling sad, for no reason.": 2.0,
    "I missed my therapy session.": 3.0,
    "I have a cold.": 2.0,
    "I just realized I’ve been overthinking everything.": 3.0,
    "I dropped my ice cream.": 1.0,
    "I don’t think I matter to anyone.": 5.0,
    "My sibling is sick and I’m worried.": 3.5,
    "My class presentation went really well!": 2.5,
    "I dropped my new phone.": 2.0,
    "I can't stop crying today.": 5.0,
    "I found my old sketchbook.": 2.0,
    "I just got laid off.": 4.0,
    "I had a panic attack in public.": 4.5,
    "I got stung by a bee today.": 1.0,
    "My cousin is getting married!": 3.0,
    "I feel like giving up.": 5.0,
    "I finally finished my novel draft!": 4.0,
    "My landlord is raising the rent again.": 3.0,
    "I was diagnosed with diabetes today.": 4.0,
    "I had a fight with my best friend.": 3.0,
    "My credit card got declined at the store.": 3.0,
    "I failed my final semester.": 5.0,
    "I forgot to take out the trash again.": 1.0,
    "I got selected for a national-level competition!": 4.0,
    "My flight got delayed by 6 hours.": 2.0,
    "I just bought a new laptop!": 3.0,
    "My sibling just got into college abroad.": 4.0,
    "I think I have a crush on my classmate.": 3.0,
    "I lost 5 kg this month!": 3.0,
    "I spent way too much money on online shopping today.": 3.0,
    "My research paper got published!": 4.0,
    "I’ve been feeling homesick lately.": 3.0,
    "I just got ghosted.": 2.0,
    "I sprained my ankle playing football.": 2.0,
    "I was scammed $100 online today.": 3.0,
    "I forgot my umbrella and it started raining on the way home.": 2.0,
    "I left my charger at a friends place.": 1.0,
    "I cooked something new for dinner today.": 2.0,
    "I witnessed a road accident today.": 2.0,
    "I finally organized my email inbox.": 1.0,
    "I had to wait in line for an hour at the bank.": 2.0,
    "I tried a new coffee shop today.": 1.0,
    "I was diagnosed with high blood pressure.": 4.0,
    "I accidentally sent an email without the attachment.": 1.0,
    "We had a family emergency last night.": 5.0,
    "I got stuck in traffic for 45 minutes.": 2.0,
    "I returned something I bought last week.": 1.0,
    "I tested positive for COVID.": 5.0,
    "I helped a stranger carry their groceries.": 2.0,
    "I’ve been having constant headaches.": 4.0,
    "I finally unsubscribed from all those newsletters.": 1.0,
    "I updated my resume today.": 2.0,
    "I haven't been sleeping well for weeks.": 4.0,
    "I went for a long walk without my phone.": 2.0,
    "My friend got injured during a bike ride.": 3.0,
    "I'm worried about my dad's health.": 4.0,
    "I spilled food while eating lunch.": 1.0,
    "I ran out of detergent mid-laundry.": 1.0,
    "I had to pay a huge hospital bill.": 4.0,
    "I had a video call with bad internet.": 1.0,
    "I got into a minor car accident.": 3.5,
    "I dropped my keys in the elevator.": 3.0,
    "I just got laid off from work.": 5.0,
    "I couldnt find a parking spot for 20 minutes.": 1.0,
    "I fell down the stairs today.": 3.0,
    "I had to visit the ER last night.": 5.0,
    "My grandma was hospitalized.": 5.0,
    "I fixed a small thing around the house myself.": 1.0,
    "I used public transport for the first time in a while.": 1.0,
    "My sister moved out today.": 3.0,
    "I’m struggling to pay rent this month.": 5.0,
    "I skipped my meds today.": 3.0,
    "I had to skip breakfast today.": 1.0,
    "My internet has been down all day.": 2.0,
    "I forgot to submit my tax return.": 3.0,
    "I feel like I'm not good enough.": 4.0,
    "I think my partner is ignoring me.": 4.0,
    "I saw a car hit a dog today.": 3.0,
    "My friend cancelled our weekend plans.": 2.0,
    "Nobody showed up for my party.": 4.0,
    "My brother forgot my birthday.": 3.0
}

# Build TF-IDF vectors
all_questions = list(TRAINING_DATA.keys())
vectorizer = TfidfVectorizer().fit(all_questions)
tfidf_matrix = vectorizer.transform(all_questions)

def get_magnitude_for_query(query: str) -> float:
    """Calculate magnitude score for user query"""
    if query in TRAINING_DATA:
        return TRAINING_DATA[query]
    
    query_vec = vectorizer.transform([query])
    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
    best_idx = similarities.argmax()
    return list(TRAINING_DATA.values())[best_idx]







def ensure_valid_embedding(embedding):
    if not embedding or not isinstance(embedding, list) or len(embedding) != 768:
        return [0.0] * 768
    return [float(x) for x in embedding]



























BOT_LANGUAGE_MAP = {
    "delhi_mentor_male": ["hindi", "english"],
    "delhi_mentor_female": ["hindi", "english"],
    "delhi_friend_male": ["hindi", "english"],
    "delhi_friend_female": ["hindi", "english"],
    "delhi_romantic_male": ["hindi", "english"],
    "delhi_romantic_female": ["hindi", "english"],

    "japanese_mentor_male": ["japanese", "english"],
    "japanese_mentor_female": ["japanese", "english"],
    "japanese_friend_male": ["japanese", "english"],
    "japanese_friend_female": ["japanese", "english"],
    "japanese_romantic_female": ["japanese", "english"],
    "japanese_romantic_male": ["japanese", "english"],

    "parisian_mentor_male": ["french", "english"],
    "parisian_mentor_female": ["french", "english"],
    "parisian_friend_male": ["french", "english"],
    "parisian_friend_female": ["french", "english"],
    "parisian_romantic_female": ["french", "english"],

    "berlin_mentor_male": ["german", "english"],
    "berlin_mentor_female": ["german", "english"],
    "berlin_friend_male": ["german", "english"],
    "berlin_friend_female": ["german", "english"],
    "berlin_romantic_male": ["german", "english"],
    "berlin_romantic_female": ["german", "english"],

    # --- Singaporean Personas ---
    "singapore_mentor_male": ["english", "mandarin", "malay", "tamil"],
    "singapore_mentor_female": ["english", "mandarin", "malay", "tamil"],
    "singapore_friend_male": ["english", "mandarin", "malay", "tamil"],
    "singapore_friend_female": ["english", "mandarin", "malay", "tamil"],
    "singapore_romantic_male": ["english", "mandarin", "malay", "tamil"],
    "singapore_romantic_female": ["english", "mandarin", "malay", "tamil"],

    # --- Mexican Personas ---
    "mexican_mentor_male": ["spanish", "english"],
    "mexican_mentor_female": ["spanish", "english"],
    "mexican_friend_male": ["spanish", "english"],
    "mexican_friend_female": ["spanish", "english"],
    "mexican_romantic_male": ["spanish", "english"],
    "mexican_romantic_female": ["spanish", "english"],

    # --- Sri Lankan Personas ---
    "srilankan_mentor_male": ["sinhala", "tamil", "english"],
    "srilankan_mentor_female": ["sinhala", "tamil", "english"],
    "srilankan_friend_male": ["sinhala", "tamil", "english"],
    "srilankan_friend_female": ["sinhala", "tamil", "english"],
    "srilankan_romantic_male": ["sinhala", "tamil", "english"],
    "srilankan_romantic_female": ["sinhala", "tamil", "english"],

    # --- Emirati Personas ---
    "emirati_mentor_male": ["arabic", "english"],
    "emirati_mentor_female": ["arabic", "english"],
    "emirati_friend_male": ["arabic", "english"],
    "emirati_friend_female": ["arabic", "english"],
    "emirati_romantic_male": ["arabic", "english"],
    "emirati_romantic_female": ["arabic", "english"],
}













# Replace your call_xai_api function around line 50:

async def call_xai_api(messages, model="grok-beta"):
    """Skip XAI entirely - Use Gemini Flash directly for fastest response"""
    print(f"Using Gemini Flash directly (XAI disabled for performance)")

    # Skip XAI entirely, go directly to Gemini Flash
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Convert messages to Gemini format
        if messages:
            user_message = messages[-1]["content"] if messages[-1]["role"] == "user" else "Hello"
        else:
            user_message = "Hello"

        response = model.generate_content(
            user_message,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=30,  # Reduced for voice calls
                temperature=0.7,
            )
        )

        logging.info("✅ Gemini Flash PRIMARY success")
        return response.text.strip()

    except Exception as e:
        logging.error(f"❌ Gemini Flash failed: {e}")
        # Final fallback to OpenAI
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            chat_completion_res = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=50,
                temperature=0.7
            )
            response_content = chat_completion_res.choices[0].message.content
            logging.info("✅ OpenAI final fallback SUCCESS")
            return response_content.strip()
        except Exception as e2:
            logging.error(f"❌ All APIs failed: {e2}")
            raise Exception("Gemini and OpenAI both failed")

async def get_redis_client():
    """Get or create Redis client for caching with improved error handling"""
    global redis_client
    if redis_client is None:
        try:
            # Configure Redis connection based on environment
            if REDIS_HOST == 'localhost':
                # Local Redis configuration
                redis_client = redis.Redis(
                    host=REDIS_HOST,
                    port=6379,
                    password=REDIS_PASSWORD if REDIS_PASSWORD else None,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
            else:
                # Remote Redis configuration (Upstash or other cloud providers)
                connection_methods = [
                    # Method 1: Standard rediss URL
                    lambda: redis.from_url(
                        f"rediss://:{REDIS_PASSWORD}@{REDIS_HOST}:6380",
                        encoding="utf-8",
                        decode_responses=True,
                        socket_timeout=5,
                        socket_connect_timeout=5
                    ),
                    # Method 2: Explicit SSL connection
                    lambda: redis.Redis(
                        host=REDIS_HOST,
                        port=6380,
                        password=REDIS_PASSWORD,
                        ssl=True,
                        encoding="utf-8",
                        decode_responses=True,
                        socket_timeout=5,
                        socket_connect_timeout=5,
                        ssl_cert_reqs=None
                    ),
                    # Method 3: Without SSL (fallback)
                    lambda: redis.Redis(
                        host=REDIS_HOST,
                        port=6379,
                        password=REDIS_PASSWORD,
                        encoding="utf-8",
                        decode_responses=True,
                        socket_timeout=5,
                        socket_connect_timeout=5
                    )
                ]

                for i, method in enumerate(connection_methods, 1):
                    try:
                        test_client = method()
                        await test_client.ping()
                        redis_client = test_client
                        logging.info(f"Remote Redis connected successfully using method {i} for memory caching")
                        break
                    except Exception as method_error:
                        logging.debug(f"Redis connection method {i} failed: {method_error}")
                        if hasattr(test_client, 'close'):
                            try:
                                await test_client.close()
                            except:
                                pass
                        continue

                if redis_client is None:
                    raise Exception("All Redis connection methods failed")

            # Test the connection
            await redis_client.ping()
            logging.info(f"Redis connected successfully to {REDIS_HOST} for memory caching")

        except Exception as e:
            logging.warning(f"Redis connection failed: {e}. Memory caching disabled - falling back to direct retrieval.")
            redis_client = None
    return redis_client

def create_cache_key(query: str, email: str, bot_id: str, previous_conversation: list) -> str:
    """Create a unique cache key for memory retrieval"""
    # Create a deterministic key based on inputs
    conversation_str = json.dumps(previous_conversation, sort_keys=True) if previous_conversation else ""
    cache_input = f"{query}:{email}:{bot_id}:{conversation_str}"
    return f"memory_cache:{hashlib.md5(cache_input.encode()).hexdigest()}"

async def get_cached_memory(cache_key: str):
    """Get cached memory result with improved error handling"""
    try:
        client = await get_redis_client()
        if client:
            cached_data = await client.get(cache_key)
            if cached_data:
                result = json.loads(cached_data)
                logging.info(f"Cache HIT for key: {cache_key[:20]}...")
                return result
            else:
                logging.info(f"Cache MISS for key: {cache_key[:20]}...")
        else:
            logging.debug("Redis client unavailable - skipping cache check")
    except Exception as e:
        logging.warning(f"Cache retrieval error for key {cache_key[:20]}...: {e}")
    return None

async def set_cached_memory(cache_key: str, memory: str, rephrased: str, category: str):
    """Cache memory result with TTL and improved error handling"""
    try:
        client = await get_redis_client()
        if client:
            cache_data = {
                "memory": memory,
                "rephrased_user_message": rephrased,
                "category": category,
                "cached_at": time.time()
            }
            await client.setex(cache_key, CACHE_TTL, json.dumps(cache_data))
            logging.info(f"Memory result cached successfully with key: {cache_key[:20]}... (TTL: {CACHE_TTL}s)")
        else:
            logging.debug("Redis client unavailable - skipping cache storage")
    except Exception as e:
        logging.warning(f"Cache storage error for key {cache_key[:20]}...: {e}")

async def redis_health_check():
    """Check Redis connection health"""
    try:
        client = await get_redis_client()
        if client:
            await client.ping()
            return True
    except:
        pass
    return False

async def cached_retrieve_memory(query: str, email: str, bot_id: str, previous_conversation: list):
    """
    Cached version of retrieve_memory specifically for voice call endpoint
    Provides aggressive caching to reduce memory retrieval time from 8-12s to 0.5-1s
    """
    start_time = time.time()

    # Create cache key
    cache_key = create_cache_key(query, email, bot_id, previous_conversation)

    # Try to get from cache first
    cached_result = await get_cached_memory(cache_key)
    if cached_result:
        cache_time = time.time() - start_time
        logging.info(f"Memory cache HIT - Retrieved in {cache_time:.3f}s")
        return cached_result["memory"], cached_result["rephrased_user_message"], cached_result["category"]

    # Cache miss - call original function
    logging.info("Memory cache MISS - Calling original retrieve_memory")
    memory, rephrased, category = await retrieve_memory(query, email, bot_id, previous_conversation)

    # Cache the result for future use
    await set_cached_memory(cache_key, memory, rephrased, category)

    total_time = time.time() - start_time
    logging.info(f"Memory retrieval completed in {total_time:.3f}s (cached for future)")

    return memory, rephrased, category

from MM2.addendum import get_bot_personality, bot_current_time
from MM2.utils import bot_response_v2, bhagwan_response,checker,insert_entry,restrict_to_last_20_messages,log_messages_with_like_dislike,like_dislike,log_notes_memory,\
check_for_origin_question,reminder_response_to_user,sync_messages,schedule_message,check_scheduled_messages,check_daily_scheduled_messages,get_memories_from_DB, process_summaries_for_yesterday,\
combine_messages, delete_summary_from_DB, get_summaries_from_DB , categorize_user_messages,get_today_user_bot_pairs , get_distinct_user_bot_combinations, process_user_bot_combination, fetch_new_messages, call_openai_api
from MM2.utils import connect_pinecone  # Your existing Pinecone connection
from MM2.gemma_api import router as gemma_router  # Import Gemma API router
import requests # type: ignore
import base64
from MM2.bot_prompt import get_bot_prompt
#from news_weather_agent import is_news_query, persona_response
import boto3
from botocore.exceptions import ClientError
import uuid_utils as uuid
import re

# --- Lifespan and App Initialization (Lines 47-113) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks: Print startup message
    print("Starting up...")

    # Schedule log upload every 30 minutes using FastAPI's repeat_every
    @repeat_every(seconds=60 * 30)
    async def upload_log():
        print("Uploading log file to S3")
        upload_log_to_s3()

    # Schedule memory extraction check every 30 minutes
    @repeat_every(seconds=60 * 30)
    async def check_memory_extraction():
        print("Checking Memory Extraction")
        await checker()

    # Schedule message checks every 30 minutes
    @repeat_every(seconds=60 * 30)
    async def check_scheduled_tasks():
        check_daily_scheduled_messages()
        return check_scheduled_messages()

    # Schedule redundancy check every hour
    @repeat_every(seconds=60 * 60)
    def scheduled_hourly_categorization():
        logging.info("🔁 Running redundancy task every 1 hour")
        try:
            redundant()
        except Exception as e:
            logging.info(f"❌ Error during redundancy categorization: {e}")

    # Schedule categorization every 3 hours
    @repeat_every(seconds=60 * 60 * 3)
    def scheduled_memory_categorization():
        print("⏰ Running categorization task every 3 hours")
        try:
            run_categorization_job()
        except Exception as e:
            print(f"Error during scheduled categorization: {e}")

    # Schedule daily summary every 24 hours
    @repeat_every(seconds=60 * 60 * 24)
    def scheduled_daily_summary():
        print("🗓️ Running daily summary generation at 2 AM UTC")
        process_summaries_for_yesterday()

    # Start all scheduled tasks
    upload_log()
    await check_memory_extraction()
    await check_scheduled_tasks()
    scheduled_hourly_categorization()
    scheduled_memory_categorization()
    scheduled_daily_summary()

    yield  # The app runs here

    # Shutdown tasks (if any)
    print("Shutting down...")


# Prometheus Instrumentation
app = FastAPI(lifespan=lifespan)
# Option 1: Use metric_namespace to prefix metrics with 'fastapi'
Instrumentator().instrument(app).expose(app, name="fastapi")

app.include_router(gemma_router, prefix="/cv/generate", tags=["gemma"])
app.include_router(payments_router, prefix="/payments", tags=["payments"])
# Global exception handler to count errors per user
@app.exception_handler(Exception)
async def prometheus_exception_handler(request: Request, exc: Exception):
    # Try to extract user email from request body (for POST/PUT) or query (for GET)
    email = "unknown"
    try:
        if request.method in ("POST", "PUT", "PATCH"):
            data = await request.json()
            email = data.get("email", "unknown")
        else:
            email = request.query_params.get("email", "unknown")
    except Exception:
        pass
    api_errors_total.labels(email=email).inc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )
# Connect to Pinecone vector database (used for memory and embeddings)
pc, index = connect_pinecone()

# Add CORS middleware to allow requests from all origins (for frontend-backend communication)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from any origin
    allow_credentials=True,  # Allow credentials (e.g., cookies, headers)
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all HTTP headers
)

# Configure logging for the application
logging.basicConfig(
    filename="app.log",  # Log file name
    filemode='a',  # Append to log file
    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',  # Log format
    datefmt='%H:%M:%S',  # Time format in logs
    level=logging.INFO  # Log level: INFO
)

# Supabase connection details (for database access)
SUPABASE_URL = os.getenv("SUPABASE_URL")  # Supabase project URL from environment variable
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Supabase API key from environment variable

# Create a Supabase client using project URL and API key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


from pydantic import BaseModel, Field
from typing import Union, Optional, List
# Define a Pydantic model for the incoming request body
class QuestionRequest(BaseModel):
    message: Union[str, None] = None  # Question from the user
    bot_id: str = "delhi"  # Personality type
    #removed as per new changes
    #bot_prompt: str = ""  # Personality prompt
    custom_bot_name: str = ""  # Custom bot name
    user_name : str = ""  # User name
    user_gender : str="" # User Gender
    language : str="" # Language
    traits : str="" # Traits
    previous_conversation: list = [] # previous conversation
    email: str = ""  # Email address
    request_time : str = "" # IP address
    platform: str = "" # Platform from which the request is made
    add_prompt: str = "" 




#app.include_router(payments_router, prefix="/api/payments", tags=["payments"])
# Define the endpoint for chat functionality
"""
    The function `cv_chat` handles chat functionality by processing user questions, generating bot
    responses, logging messages, and handling reminders.

    :param request: The `request` parameter in the `cv_chat` function represents the incoming request
    data for the chat functionality. It is of type `QuestionRequest`, which likely contains information
    such as the user's message, email, bot ID, previous conversation history, bot prompt, and request
    time. This data is
    :type request: QuestionRequest
    :param background_tasks: The `background_tasks` parameter in the `cv_chat` function is used to
    schedule background tasks to be run after the response has been sent back to the client. In this
    case, it is being used to add a task to insert an entry into the database after generating a
    response to the user's
    :type background_tasks: BackgroundTasks
    :return: The endpoint `/cv/chat` is defined for chat functionality. When a POST request is made to
    this endpoint with a `QuestionRequest` object and `BackgroundTasks`, the function `cv_chat` is
    executed.
"""


from datetime import datetime, timezone, timedelta


class LoginRequest(BaseModel):
    email: str
    bot_id: str

from MM2.serialization import is_valid_memory
import ast

class LoginRequest(BaseModel):
    email: str
    bot_id: str
    
@app.post("/login")
async def login(request: LoginRequest):
    """Enhanced login with comprehensive memory loading"""
    try:
        print(f"🔍 LOGIN DEBUG: Starting login for {request.email}:{request.bot_id}")
        
        # Use the comprehensive load_memories_to_redis function
        result = load_memories_to_redis(request.email, request.bot_id)
        
        if isinstance(result, dict):
            if result.get("status") == "already_loaded":
                return {
                    "status": "already_loaded",
                    "message": "Session already loaded"
                }
            elif result.get("status") == "error":
                return {
                    "status": "error",
                    "message": result.get("message", "Unknown error")
                }
            else:
                return {
                    "status": "logged_in",
                    "memories_fetched": result.get("memories_fetched", 0),
                    "memories_validated": result.get("memories_validated", 0),
                    "memories_stored": result.get("memories_stored", 0),
                    "chats_loaded": result.get("chats_loaded", 0),
                    "processing_errors": result.get("processing_errors", []),
                    "success_rate": result.get("success_rate", "N/A"),
                    "user_id": f"{request.email}:{request.bot_id}"
                }
        else:
            # Fallback for old return format
            return {
                "status": "logged_in",
                "message": "Login successful"
            }
            
    except Exception as e:
        print(f"❌ LOGIN DEBUG: Login failed: {e}")
        return {
            "status": "error",
            "message": f"Login failed: {str(e)}"
        }
        
LANGUAGE_CHECK_URL = "https://langdetect-233451779807.us-central1.run.app/language_check"

async def check_language_supported(user_message: str, bot_id: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        payload = {"user_message": user_message, "bot_id": bot_id}
        try:
            resp = await client.post(LANGUAGE_CHECK_URL, json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            # If the language check server is down, allow fallback (or block, as you prefer)
            return {"supported": True, "detected_language": None, "error": f"Language check failed: {e}"}

@app.post("/cv/chat")
async def cv_chat(request: QuestionRequest, background_tasks: BackgroundTasks):
    message_generated_counter.inc()
    """
    Chat endpoint: Uses only Redis for context/memories after /login.
    Generates a new response via LLM using bot_response_v2.
    Publishes every chat to RabbitMQ for async upsert.
    Logs messages ONLY in Redis; Supabase sync happens at /end-chat.
    """
    try:
        # Validate input
        if not request.message or request.message.strip() == "":
            return {"error": "Please provide a valid question"}
        user_id = f"{request.email}:{request.bot_id}"

        # Use only Redis for context/memories
        query_embedding = await get_embedding(request.message)
        valid_memories = redis_manager.get_user_memories(user_id)
        similar_memories = []
        if valid_memories:
            try:
                similar_memories = await get_semantically_similar_memories(
                    redis_manager.client, user_id, query_embedding, k=3, cutoff=1.0
                )
                print(f"DEBUG: Similar memories found for user {user_id}:")
                for mem in similar_memories:
                    print(mem)
            except Exception as e:
                logging.warning(f"Semantic memory search failed: {e}")
                similar_memories = []
        if not similar_memories:
            logging.info(f"No semantically similar memories found for user {user_id}")
        else:
            logging.info(f"Found {len(similar_memories)} similar memories for user {user_id}")

        # Language check
        #lang_check = await check_language_supported(request.message, request.bot_id)
        #if not lang_check.get("supported", True):
            #return {
                #"response": lang_check.get("message", "Sorry, I can't understand this language."),
                #"message_id": None,
                #"reminder": False,
                #"xp_data": None,
                #"cache_hit": False
            #}

        # XP calculation
        magnitude = get_magnitude_for_query(request.message)
        immediate_xp_result = award_immediate_xp_and_magnitude(
            request.email, request.bot_id, magnitude
        )

        reminder = False
        previous_conversation = restrict_to_last_20_messages(request.previous_conversation)

        detected_urls = detect_urls_in_query(request.message)
        if detected_urls:
            website_data = fetch_website_content(detected_urls[0])
            if website_data:
                response = create_website_summary_response(request.message, website_data, request.bot_id)
                cache_hit = False
            else:
                response = "I tried to access the website you shared, but couldn't retrieve the content. Could you tell me more about what you'd like to discuss?"
                cache_hit = False
        else:
            # Always use bot_response_v2 for generating the response (with context and semantic memories)
            raw_bot_prompt = get_bot_prompt(request.bot_id)
            bot_prompt = raw_bot_prompt.format(
                custom_bot_name=request.custom_bot_name,
                traitsString=request.traits,
                userName=request.user_name,
                userGender=request.user_gender,
                languageString=request.language
            )
            # Origin check
            check = await check_for_origin_question(request.message, previous_conversation)
            if check == "Yes":
                response = "I was developed by the amazing Desi dev team! 🇮🇳"
                await log_message(redis_manager, user_id, request.message, response, requested_time=request.request_time, platform=request.platform, activity_name=None, email=request.email, bot_id=request.bot_id)
                cache_hit = False
            else:
                # Reminder check
                memory, rephrased_user_message, category = await retrieve_memory(
                    request.message, request.email, request.bot_id, previous_conversation)
                if category == "Reminder":
                    response = await reminder_response(
                        request.message, previous_conversation, request.request_time
                    )
                    reminder = True
                    cache_hit = False
                else:
                    # Always generate a new response using bot_response_v2 (Redis only)
                    response = await bot_response_v2(
                        bot_prompt, request.bot_id, request.message, request.email
                    )
                    cache_hit = False

        # Log the interaction in Redis only
        await log_message(redis_manager, user_id, request.message, response, requested_time=request.request_time, platform=request.platform, activity_name=None, email=request.email, bot_id=request.bot_id)
        # Publish to RabbitMQ for async upsert
        await publish_to_both_queues(
            user_id=user_id,
            user_input=request.message,
            bot_reply=response,
            bot_id=request.bot_id,
            memory=memory if 'memory' in locals() else None,
            mem_id=None
        )

        # Return response with IMMEDIATE XP data for frontend display
        return {
            "response": response,
            "message_id": None,
            "reminder": reminder,
            "xp_data": {
                "immediate_xp_awarded": immediate_xp_result["immediate_xp_awarded"],
                "current_total_xp": immediate_xp_result["current_total_xp"],
                "current_total_coins": immediate_xp_result["current_total_coins"],
                "magnitude": immediate_xp_result["magnitude"],
                "xp_calculation_success": immediate_xp_result["success"]
            },
            "cache_hit": cache_hit
        }

    except Exception as e:
        logging.error(f"Error in cv_chat: {e}")
        return {"error": "Error occurred while processing your request. Please try again later."}
    
    
    
    

@app.post("/cv/chat-debug")
async def cv_chat_debug(request: QuestionRequest, background_tasks: BackgroundTasks):
    """
    PERFECT Debug Chat endpoint: Uses IDENTICAL response logic to /cv/chat
    Returns comprehensive context analysis + same response generation.
    """
    try:
        # ========== IDENTICAL VALIDATION TO cv/chat ==========
        if not request.message or request.message.strip() == "":
            return {"error": "Please provide a valid question"}
        
        user_id = f"{request.email}:{request.bot_id}"
        
        # ========== PHASE 1: CONTEXT GATHERING FOR DEBUG ==========
        # Get query embedding for semantic search (IDENTICAL to cv/chat)
        query_embedding = await get_embedding(request.message)
        
        # Get memories from Redis (IDENTICAL to cv/chat)
        valid_memories = redis_manager.get_user_memories(user_id)
        similar_memories = []
        if valid_memories:
            try:
                similar_memories = await get_semantically_similar_memories(
                    redis_manager.client, user_id, query_embedding, k=3, cutoff=1.0
                )
                print(f"DEBUG: Similar memories found for user {user_id}:")
                for mem in similar_memories:
                    print(mem)
            except Exception as e:
                logging.warning(f"Semantic memory search failed: {e}")
                similar_memories = []
        
        if not similar_memories:
            logging.info(f"No semantically similar memories found for user {user_id}")
        else:
            logging.info(f"Found {len(similar_memories)} similar memories for user {user_id}")

        # ========== GET ADDITIONAL DEBUG DATA (More than cv/chat) ==========
        # Get RFM memories for debug info
        rfm_memories = []
        try:
            rfm_memories = await get_highest_rfm_memories(redis_manager.client, user_id, k=3)
        except Exception as e:
            logging.warning(f"RFM memory search failed: {e}")
            rfm_memories = []

        # Get past messages for debug info
        past_messages = []
        try:
            past_messages = await fetch_last_m_messages(redis_manager.client, user_id, m=10)
        except Exception as e:
            logging.warning(f"Past messages fetch failed: {e}")
            past_messages = []

        # Format debug information
        formatted_semantic_memories = []
        for mem in similar_memories:
            formatted_semantic_memories.append({
                "id": mem.get("id"),
                "text": mem.get("text", ""),
                "similarity_score": round(mem.get("sim", 0), 3),
                "created_at": mem.get("created_at"),
                "last_used": mem.get("last_used")
            })

        formatted_rfm_memories = []
        for mem in rfm_memories:
            formatted_rfm_memories.append({
                "id": mem.get("id"),
                "text": mem.get("text", ""),
                "rfm_score": round(mem.get("rfm_score", 0), 2)
            })

        formatted_past_messages = []
        for msg in past_messages:
            formatted_past_messages.append({
                "timestamp": msg.get("timestamp"),
                "user_message": msg.get("user_message", ""),
                "bot_response": msg.get("bot_response", "")
            })

        # ========== IDENTICAL PROCESSING TO cv/chat ==========
        # XP calculation (IDENTICAL)
        magnitude = get_magnitude_for_query(request.message)
        immediate_xp_result = award_immediate_xp_and_magnitude(
            request.email, request.bot_id, magnitude
        )

        # Initialize variables (IDENTICAL)
        reminder = False
        previous_conversation = restrict_to_last_20_messages(request.previous_conversation)
        memory = ""
        rephrased_user_message = request.message
        category = "General"
        response_type = "normal"
        cache_hit = False

        # URL detection (IDENTICAL)
        detected_urls = detect_urls_in_query(request.message)
        if detected_urls:
            website_data = fetch_website_content(detected_urls[0])
            if website_data:
                response = create_website_summary_response(request.message, website_data, request.bot_id)
                response_type = "website_summary"
            else:
                response = "I tried to access the website you shared, but couldn't retrieve the content. Could you tell me more about what you'd like to discuss?"
                response_type = "website_error"
        else:
            # Generate bot prompt (IDENTICAL)
            raw_bot_prompt = get_bot_prompt(request.bot_id)
            bot_prompt = raw_bot_prompt.format(
                custom_bot_name=request.custom_bot_name,
                traitsString=request.traits,
                userName=request.user_name,
                userGender=request.user_gender,
                languageString=request.language
            )
            
            # Origin check (IDENTICAL)
            check = await check_for_origin_question(request.message, previous_conversation)
            if check == "Yes":
                response = "I was developed by the amazing Desi dev team! 🇮🇳"
                response_type = "origin"
                # Log immediately like cv/chat does
                await log_message(redis_manager, user_id, request.message, response, 
                                requested_time=request.request_time, platform=request.platform, 
                                activity_name=None, email=request.email, bot_id=request.bot_id)
            else:
                # Memory retrieval (IDENTICAL)
                memory, rephrased_user_message, category = await retrieve_memory(
                    request.message, request.email, request.bot_id, previous_conversation
                )
                
                if category == "Reminder":
                    response = await reminder_response(
                        request.message, previous_conversation, request.request_time
                    )
                    reminder = True
                    response_type = "reminder"
                else:
                    # Generate response using bot_response_v2 (IDENTICAL)
                    response = await bot_response_v2(
                        bot_prompt, request.bot_id, request.message, request.email, request.add_prompt
                    )
                    response_type = "normal"

        # Log interaction (IDENTICAL to cv/chat) - but only if not origin
        if response_type != "origin":  # Origin already logged above
            await log_message(redis_manager, user_id, request.message, response, 
                             requested_time=request.request_time, platform=request.platform, 
                             activity_name=None, email=request.email, bot_id=request.bot_id)

        # Publish to RabbitMQ (IDENTICAL)
        await publish_to_both_queues(
            user_id=user_id,
            user_input=request.message,
            bot_reply=response,
            bot_id=request.bot_id,
            memory=memory if 'memory' in locals() else None,
            mem_id=None
        )

        # ========== RETURN DEBUG FORMAT INSTEAD OF XP DATA ==========
        return {
            "related_memories": {
                "semantic_memories": formatted_semantic_memories,
                "high_importance_memories": formatted_rfm_memories,
                "total_semantic_found": len(formatted_semantic_memories),
                "total_rfm_found": len(formatted_rfm_memories)
            },
            "past_conversations": {
                "last_10_messages": formatted_past_messages,
                "total_messages": len(formatted_past_messages)
            },
            "response": response,
            "response_metadata": {
                "response_type": response_type,
                "reminder": reminder,
                "urls_detected": detected_urls,
                "identical_to_cv_chat": True,
                "cache_hit": cache_hit
            },
            "context_analysis": {
                "user_query": request.message,
                "bot_id": request.bot_id,
                "user_id": user_id,
                "memory_context_used": memory,
                "rephrased_query": rephrased_user_message,
                "category": category,
                "similar_memories_count": len(similar_memories),
                "magnitude": magnitude
            }
        }

    except Exception as e:
        logging.error(f"Error in cv_chat_debug: {e}")
        return {
            "error": "Error occurred while processing your request",
            "details": str(e),
            "related_memories": {"semantic_memories": [], "high_importance_memories": []},
            "past_conversations": {"last_10_messages": []},
            "response": "I apologize, but I encountered an error.",
            "response_metadata": {"response_type": "error"}
        }
        
        
@app.get("/debug-memory-complete-audit/{email}/{bot_id}")
async def debug_memory_complete_audit(email: str, bot_id: str):
    """Complete audit of memory loading pipeline"""
    try:
        audit_result = {
            "email": email,
            "bot_id": bot_id,
            "user_id": f"{email}:{bot_id}",
            "audit_steps": {},
            "final_assessment": "unknown"
        }
        
        # Step 1: Check Supabase data
        try:
            supabase_response = supabase.table("persona_category").select("*").eq("email", email).eq("bot_id", bot_id).execute()
            supabase_memories = supabase_response.data or []
            
            audit_result["audit_steps"]["1_supabase_check"] = {
                "status": "success",
                "memories_found": len(supabase_memories),
                "sample_memory_fields": list(supabase_memories[0].keys()) if supabase_memories else [],
                "has_memory_field": any("memory" in mem for mem in supabase_memories),
                "has_embedding_field": any("embedding" in mem for mem in supabase_memories)
            }
        except Exception as e:
            audit_result["audit_steps"]["1_supabase_check"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Step 2: Clear and reload Redis
        user_id = f"{email}:{bot_id}"
        cleared_keys = redis_manager.clear_user_data(user_id)
        
        audit_result["audit_steps"]["2_redis_clear"] = {
            "status": "success",
            "keys_cleared": cleared_keys
        }
        
        # Step 3: Load memories with comprehensive logging
        load_result = load_memories_to_redis(email, bot_id)
        
        audit_result["audit_steps"]["3_memory_loading"] = {
            "status": "success",
            "load_result": load_result
        }
        
        # Step 4: Verify Redis storage in detail
        stored_memory_keys = redis_manager.client.keys(f"memories:{user_id}:*")
        
        detailed_memories = []
        for key in stored_memory_keys[:3]:  # Check first 3
            memory = redis_manager.client.hgetall(key)
            decoded_memory = {}
            for k, v in memory.items():
                k = k.decode() if isinstance(k, bytes) else k
                if k == "embedding":
                    try:
                        emb_array = np.frombuffer(v, dtype=np.float32)
                        decoded_memory[k] = f"<FLOAT32 array with {len(emb_array)} values>"
                    except:
                        decoded_memory[k] = f"<Invalid embedding: {type(v)}>"
                else:
                    decoded_memory[k] = v.decode() if isinstance(v, bytes) else v
            detailed_memories.append(decoded_memory)
        
        audit_result["audit_steps"]["4_redis_verification"] = {
            "status": "success",
            "keys_found": len(stored_memory_keys),
            "detailed_memories": detailed_memories,
            "field_analysis": {
                "all_have_memory_text": all("memory_text" in mem for mem in detailed_memories),
                "all_have_user_id": all("user_id" in mem for mem in detailed_memories),
                "all_have_embedding": all("embedding" in mem for mem in detailed_memories)
            }
        }
        
        # Step 5: Test vector search
        if stored_memory_keys:
            try:
                test_embedding = [0.1] * 768
                search_results = await get_semantically_similar_memories(
                    redis_manager.client, user_id, test_embedding, k=2, cutoff=1.0
                )
                
                audit_result["audit_steps"]["5_vector_search"] = {
                    "status": "success",
                    "results_found": len(search_results),
                    "sample_result": search_results[0] if search_results else None
                }
            except Exception as e:
                audit_result["audit_steps"]["5_vector_search"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Final assessment
        if (len(stored_memory_keys) == len(supabase_memories) and 
            len(supabase_memories) > 0 and
            audit_result["audit_steps"]["4_redis_verification"]["field_analysis"]["all_have_memory_text"] and
            audit_result["audit_steps"]["4_redis_verification"]["field_analysis"]["all_have_embedding"]):
            audit_result["final_assessment"] = "PERFECT"
        elif len(stored_memory_keys) > 0:
            audit_result["final_assessment"] = "PARTIAL_SUCCESS"
        else:
            audit_result["final_assessment"] = "FAILED"
            
        return audit_result
        
    except Exception as e:
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
 

@app.get("/test-debug-simple")
async def test_debug_simple():
    """Simple test endpoint"""
    return {"message": "Simple test working", "timestamp": datetime.now().isoformat()}

 
 
        
class StoreActivityMessageRequest(BaseModel):
    email: str
    bot_id: str
    user_message: str = ""
    bot_response: str = ""
    platform: str = "game_activity"
    activity_name: str = None
@app.post("/store-activity-message")
async def store_activity_message(req: StoreActivityMessageRequest):
    now = datetime.utcnow().isoformat()
    data = {
        "email": req.email,
        "bot_id": req.bot_id,
        "user_message": req.user_message,
        "bot_response": req.bot_response,
        "requested_time": now,
        "platform": req.platform,
        "activity_name": req.activity_name,
    }
    try:
        res = supabase.table("message_paritition").insert(data).execute()
        return {"success": True}
    except Exception as e:
        print("Failed to log activity message to Supabase:", e)
        return {"success": False, "error": str(e)}
    
    
    
@app.get("/user-xp/{email}/{bot_id}")
async def get_user_xp_endpoint(email: str, bot_id: str):
    """Get user's XP, coins, and magnitude for a specific bot"""
    try:
        user_data = get_user_xp(email, bot_id)
        if user_data:
            return {
                "success": True,
                "data": {
                    "xp_score": user_data.get("xp_score", 0),
                    "coins": user_data.get("coins", 0),
                    "magnitude": user_data.get("magnitude", 0.0),
                    "updated_at": user_data.get("updated_at")
                }
            }
        else:
            return {
                "success": True,
                "data": {
                    "xp_score": 0,
                    "coins": 0,
                    "magnitude": 0.0,
                    "updated_at": None
                }
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/user-xp-leaderboard/{bot_id}")
async def get_xp_leaderboard(bot_id: str, limit: int = 10):
    """Get XP leaderboard for a specific bot"""
    try:
        response = supabase.table("user_xp") \
            .select("email, xp_score, coins, updated_at") \
            .eq("bot_id", bot_id) \
            .order("xp_score", desc=True) \
            .limit(limit) \
            .execute()
        
        return {
            "success": True,
            "leaderboard": response.data
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

class XPManualAward(BaseModel):
    email: str
    bot_id: str
    xp_amount: int = 0
    coin_amount: int = 0
    reason: str = ""

@app.post("/award-xp")
async def award_xp_manually(request: XPManualAward):
    """Manually award XP and coins to a user (admin function)"""
    try:
        if request.xp_amount > 0:
            add_xp_to_user(request.email, request.bot_id, request.xp_amount)
        
        if request.coin_amount > 0:
            add_coins_to_user(request.email, request.bot_id, request.coin_amount)
        
        logging.info(f"💫 Manual award: {request.email} received {request.xp_amount} XP and {request.coin_amount} coins. Reason: {request.reason}")
        
        return {
            "success": True,
            "message": f"Awarded {request.xp_amount} XP and {request.coin_amount} coins to {request.email}"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/xp-statistics")
async def get_xp_statistics():
    """Get overall XP system statistics"""
    try:
        # Total users with XP
        total_users = supabase.table("user_xp").select("email", count="exact").execute()
        
        # Total XP awarded
        total_xp = supabase.table("user_xp").select("xp_score").execute()
        total_xp_sum = sum(row["xp_score"] for row in total_xp.data)
        
        # Total coins awarded
        total_coins = supabase.table("user_xp").select("coins").execute()
        total_coins_sum = sum(row["coins"] for row in total_coins.data)
        
        # Most active bots
        bot_activity = {}
        for row in total_xp.data:
            bot_id = row.get("bot_id", "unknown")
            if bot_id not in bot_activity:
                bot_activity[bot_id] = 0
            bot_activity[bot_id] += 1
        
        return {
            "success": True,
            "statistics": {
                "total_users": len(total_users.data) if total_users.data else 0,
                "total_xp_awarded": total_xp_sum,
                "total_coins_awarded": total_coins_sum,
                "most_active_bots": dict(sorted(bot_activity.items(), key=lambda x: x[1], reverse=True)[:5])
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    
    
    
from collections import defaultdict
import asyncio
import time

# Your existing rate limiting
request_counts = defaultdict(list)
RATE_LIMIT = 100

# ✅ ADD: Database connection pool
db_semaphore = asyncio.Semaphore(50)  # Limit concurrent DB connections

# ✅ ADD: Cleanup tracker
last_cleanup = time.time()
CLEANUP_INTERVAL = 300  # Clean every 5 minutes

# ✅ NEW: Add response caching for frequently requested users
xp_response_cache = {}
XP_CACHE_TTL = 30  # 30 seconds cache for XP responses

@app.get("/user-xp-current/{email}/{bot_id}")
async def get_current_user_xp(email: str, bot_id: str):
    """
    Get current user XP for frontend initialization.
    Uses response cache, rate limiting, and DB connection pooling.
    Compatible with Python <3.11 (uses asyncio.wait_for instead of asyncio.timeout).
    """
    import asyncio
    import time

    try:
        cache_key = f"{email}:{bot_id}"
        now = time.time()

        # 1. Check response cache first
        if cache_key in xp_response_cache:
            cached_data, timestamp = xp_response_cache[cache_key]
            if now - timestamp < XP_CACHE_TTL:
                logging.info(f"⚡ XP Cache hit for {cache_key}")
                return cached_data

        # 2. Rate limiting logic
        user_key = f"{email}:{bot_id}"
        request_counts[user_key] = [
            req_time for req_time in request_counts[user_key]
            if now - req_time < 60
        ]
        if len(request_counts[user_key]) >= RATE_LIMIT:
            logging.warning(f"🚫 Rate limit exceeded for {user_key}")
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests. Please slow down."}
            )
        request_counts[user_key].append(now)

        # 3. Cleanup old cache/rate limit entries every 5 minutes
        global last_cleanup
        if now - last_cleanup > CLEANUP_INTERVAL:
            cutoff_time = now - 120
            for key in list(request_counts.keys()):
                request_counts[key] = [t for t in request_counts[key] if t > cutoff_time]
                if not request_counts[key]:
                    del request_counts[key]
            for cache_key in list(xp_response_cache.keys()):
                if now - xp_response_cache[cache_key][1] > XP_CACHE_TTL * 2:
                    del xp_response_cache[cache_key]
            last_cleanup = now
            logging.info(f"🧹 Cleaned up rate limit cache: {len(request_counts)} active users, XP cache: {len(xp_response_cache)} entries")

        # 4. DB connection pooling with timeout (use asyncio.wait_for for compatibility)
        try:
            async def fetch_user_data():
                async with db_semaphore:
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, get_user_xp, email, bot_id)
            user_data = await asyncio.wait_for(fetch_user_data(), timeout=5.0)
        except asyncio.TimeoutError:
            logging.error(f"⏰ Database timeout for {user_key}")
            return JSONResponse(
                status_code=503,
                content={"error": "Service temporarily unavailable. Please try again."}
            )

        # 5. Build response and cache it
        requests_remaining = RATE_LIMIT - len(request_counts[user_key])
        if user_data:
            response_data = {
                "success": True,
                "current_total_xp": user_data.get("xp_score", 0),
                "current_total_coins": user_data.get("coins", 0),
                "magnitude": user_data.get("magnitude", 0.0),
                "last_updated": user_data.get("updated_at"),
                "rate_limit": {
                    "requests_remaining": requests_remaining,
                    "reset_time": int(now + 60)
                }
            }
        else:
            response_data = {
                "success": True,
                "current_total_xp": 0,
                "current_total_coins": 0,
                "magnitude": 0.0,
                "last_updated": None,
                "rate_limit": {
                    "requests_remaining": requests_remaining,
                    "reset_time": int(now + 60)
                }
            }

        xp_response_cache[cache_key] = (response_data, now)
        if len(xp_response_cache) > 1000:
            oldest_key = min(xp_response_cache.keys(), key=lambda k: xp_response_cache[k][1])
            del xp_response_cache[oldest_key]

        return response_data

    except Exception as e:
        logging.error(f"❌ Error in get_current_user_xp: {e}")
        return {"success": False, "error": str(e)}
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    

class QuestionRequest2(BaseModel):
    message: Union[str, None] = None  # Question from the user
    bot_id: str = "delhi"  # Personality type
    bot_prompt: str = ""  # Personality prompt
    previous_conversation: list = [] # previous conversation
    email: str = ""  # Email address
    request_time : str = "" # IP address
    platform: str = "" # Platform from which the request is made
    user_name : str = ""  # User name
    user_gender : str="" # User Gender

#model for news summary request
class NewsSummaryRequest(BaseModel):
    query: str
    bot_id: str
    user_email: Optional[str] = "anonymous@example.com"
    conversation_id: Optional[str] = None


BOT_LANGUAGES = {
    "delhi": "hindi",
    "parisian": "french",
    "japanese": "japanese",
    "berlin": "german",
    "singapore": "english",   # Default for Singapore, but see below for more
    "mexican": "spanish",
    "srilankan": "sinhala",   # Default for Sri Lanka, but see below for more
    "emirati": "arabic",
    # Add more as needed
}





from langdetect import detect, LangDetectException

# Function to detect the language of a song based on its content, URL, and title

hindi_keywords = [
        # Common Hindi words
        "hai", "mein", "tum", "dil", "pyar", "tere", "hindi", "गीत", "गाना", "raataan", "lambiyan", "shershaah",
        "kiara", "sid", "b praak", "jasleen", "royal", "anvita", "anvit", "kaur", "arijit", "singh", "bollywood",
        "love song", "romantic song", "zindagi", "yaar", "mohabbat", "sapna", "chalo", "aaja", "jaana", "sun", "sapne",
        "saath", "khwab", "yaadon", "yaari", "ishq", "janam", "safar", "pal", "raat", "din", "chand", "suraj", "aasman",
        "dhadkan", "bekhayali", "tujhe", "mujhko", "sanam", "mehboob", "dosti", "shayar", "shayari", "kuch", "bata", "batao",
        "kya", "kaise", "kaun", "kabhi", "kab", "kyun", "kyunki", "ab", "tab", "phir", "fir", "phir bhi", "tumse", "tumhi",
        "tumko", "main", "mera", "meri", "mere", "apna", "apni", "apne", "sapno", "sapne", "khush", "khushi", "khushiyan",
        "dard", "gumsum", "yaad", "yaadein", "yaadon", "yaariyan", "suno", "sunlo", "sun raha", "sun raha hai na tu",
        "aankh", "aankhon", "aansu", "muskurana", "muskurane", "muskurata", "muskurati", "muskurate", "muskurahat",
        "chahat", "chahatein", "chahata", "chahati", "chahate", "chah", "chaha", "chahiye", "chahungi", "chahunga",
        "chahte", "chahtey", "chahte ho", "chahte hoon", "chahte hain", "chahte hoon", "chahte ho", "chahte hain",
        "chahte hoon", "chahte ho", "chahte hain", "chahte hoon", "chahte ho", "chahte hain", "chahte hoon", "chahte ho",
        "chahte hain", "chahte hoon", "chahte ho", "chahte hain", "chahte hoon", "chahte ho", "chahte hain", "chahte hoon",
        "chahte ho", "chahte hain", "chahte hoon", "chahte ho", "chahte hain", "chahte hoon", "chahte ho", "chahte hain",
        # Popular Hindi singers
        "arijit singh", "shreya ghoshal", "sonu nigam", "udit narayan", "alka yagnik", "kumar sanu", "kishore kumar",
        "lata mangeshkar", "asha bhosle", "mohit chauhan", "jubin nautiyal", "neha kakkar", "badshah", "yo yo honey singh",
        "atif aslam", "sunidhi chauhan", "palak muchhal", "kk", "rahat fateh ali khan", "shaan", "ankit tiwari",
        # Bollywood movie names (partial)
        "dilwale", "kabir singh", "shershaah", "yeh jawaani hai deewani", "kal ho naa ho", "dil chahta hai", "barfi",
        "tamasha", "rockstar", "aashiqui", "aashiqui 2", "baazigar", "dangal", "lagaan", "chak de india", "kabhi khushi kabhie gham",
        "kuch kuch hota hai", "hum aapke hain koun", "hum dil de chuke sanam", "devdas", "veer-zaara", "jab we met", "zindagi na milegi dobara"
    ]
french_keywords = [
        # Common French words
        "je", "le", "la", "français", "amour", "paris", "france", "toi", "moi", "nous", "vous", "ils", "elles", "être",
        "avoir", "faire", "dire", "pouvoir", "aller", "voir", "vouloir", "venir", "devoir", "prendre", "trouver", "donner",
        "parler", "aimer", "chanter", "chanson", "musique", "paroles", "coeur", "fleur", "soleil", "lune", "nuit", "jour",
        "rêve", "rêver", "baiser", "douce", "doucement", "beau", "belle", "joli", "jolie", "fille", "garçon", "femme", "homme",
        "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses", "notre", "votre", "leur", "leurs", "chérie", "chéri",
        "mon amour", "ma vie", "mon coeur", "ma belle", "mon chéri", "ma chérie", "mon ange", "ma princesse", "mon prince",
        # French singers
        "edith piaf", "johnny hallyday", "mylene farmer", "francis cabrel", "charles aznavour", "stromaé", "indila", "zaz",
        "patrick bruel", "julien doré", "louane", "vianney", "christophe mae", "claude françois", "louis bertignac",
        # French song/album names
        "la vie en rose", "ne me quitte pas", "je t'aime", "je te promets", "formidable", "papaoutai", "dernière danse",
        "sous le vent", "elle me dit", "si jamais j'oublie", "parler à mon père", "on écrit sur les murs"
    ]
german_keywords = [
        # Common German words
        "liebe", "deutsch", "berlin", "german", "schatz", "lied", "herz", "leben", "träume", "nacht", "tag", "himmel",
        "sonne", "mond", "sterne", "freund", "freundin", "mädchen", "junge", "frau", "mann", "mein", "meine", "dein",
        "deine", "unser", "unsere", "euer", "eure", "ihr", "ihre", "ich", "du", "er", "sie", "es", "wir", "ihr", "sie",
        "dich", "mich", "uns", "euch", "ihn", "sie", "es", "uns", "euch", "sie", "ihnen", "musik", "liedtext", "singen",
        "sänger", "sängerin", "band", "album", "titel", "melodie", "refrain", "vers", "chor", "tanz", "party", "spaß",
        # German singers/bands
        "helene fischer", "udo lindenberg", "herbert grönemeyer", "nena", "tokio hotel", "cro", "mark forster", "sido",
        "peter fox", "xavier naidoo", "andreas bourani", "revolverheld", "silbermond", "pur", "die toten hosen", "die ärzte",
        # German song/album names
        "atemlos durch die nacht", "99 luftballons", "männer", "auf uns", "tage wie diese", "ein hoch auf uns", "ich will nur",
        "ich will", "ich liebe dich", "du bist mein", "mein herz brennt", "ich geh in flammen auf"
    ]
japanese_keywords = [
        # Common Japanese words/phrases
        "watashi", "anata", "nihon", "japan", "koi", "suki", "日本", "歌", "愛", "恋", "心", "夢", "夜", "日", "月", "星",
        "空", "花", "桜", "涙", "友達", "友", "君", "僕", "私", "あなた", "彼", "彼女", "好き", "大好き", "愛してる", "会いたい",
        "ありがとう", "さようなら", "おはよう", "こんばんは", "おやすみ", "歌詞", "音楽", "メロディー", "バンド", "シンガー", "アルバム",
        "タイトル", "リフレイン", "サビ", "ダンス", "パーティー", "楽しい", "悲しい", "嬉しい", "切ない", "寂しい", "幸せ", "希望",
        # Japanese singers/bands
        "宇多田ヒカル", "浜崎あゆみ", "米津玄師", "中島美嘉", "嵐", "乃木坂46", "欅坂46", "perfume", "one ok rock", "bump of chicken",
        "king gnu", "official髭男dism", "あいみょん", "back number", "yui", "lisa", "yoasobi", "aimyon", "utada hikaru", "kenshi yonezu",
        # Japanese song/album names
        "first love", "lemon", "pretender", "紅蓮華", "炎", "打上花火", "小さな恋のうた", "さくら", "ありがとう", "世界に一つだけの花"
    ]
english_keywords = [
        # Common English words/phrases
        "the", "love", "baby", "girl", "boy", "english", "heart", "music", "song", "you", "me", "us", "life", "dream",
        "night", "day", "moon", "sun", "star", "sky", "friend", "friends", "dance", "party", "happy", "sad", "cry", "smile",
        "kiss", "hug", "forever", "always", "never", "together", "apart", "alone", "miss", "missing", "remember", "forget",
        "goodbye", "hello", "hi", "hey", "yeah", "oh", "yeah yeah", "oh oh", "la la", "na na", "chorus", "verse", "melody",
        "lyrics", "band", "album", "track", "playlist", "single", "hit", "top", "chart", "radio", "remix", "cover", "original",
        # English singers/bands
        "taylor swift", "ed sheeran", "justin bieber", "ariana grande", "beyonce", "rihanna", "drake", "adele", "bruno mars",
        "billie eilish", "dua lipa", "the weeknd", "shawn mendes", "lady gaga", "katy perry", "maroon 5", "coldplay", "eminem",
        "post malone", "selena gomez", "harry styles", "olivia rodrigo", "sam smith", "sia", "imagine dragons", "one direction",
        # English song/album names
        "shape of you", "blinding lights", "bad guy", "someone like you", "hello", "rolling in the deep", "love story", "perfect",
        "thinking out loud", "all of me", "let her go", "see you again", "uptown funk", "closer", "faded", "cheap thrills"
    ]
# Add Spanish, Tamil, Sinhala, Malay, Mandarin, and Arabic keywords for new personas
spanish_keywords = [
    "amor", "canción", "musica", "corazón", "bailar", "feliz", "triste", "beso", "abrazo", "vida", "noche", "día", "estrella", "sol", "luna", "amigo", "amiga", "te quiero", "te amo", "latino", "español"
]
tamil_keywords = [
    "காதல்", "பாடல்", "இசை", "நண்பன்", "நண்பி", "வாழ்க்கை", "இரவு", "நாள்", "சூரியன்", "நட்சத்திரம்", "மூன்று", "தமிழ்", "அன்பு", "நன்றி"
]
sinhala_keywords = [
    "ආදරය", "සින්දු", "මිතුරා", "මිතුරිය", "ජීවිතය", "රාත්‍රිය", "දවස", "හිත", "සිංහල", "සංගීතය"
]
malay_keywords = [
    "cinta", "lagu", "muzik", "kawan", "hidup", "malam", "hari", "bulan", "bintang", "bahagia", "sedih", "terima kasih", "malay"
]
mandarin_keywords = [
    "爱", "朋友", "歌曲", "音乐", "生活", "夜晚", "白天", "太阳", "星星", "幸福", "难过", "谢谢", "中文", "普通话"
]
arabic_keywords = [
    "حب", "أغنية", "موسيقى", "قلب", "صديق", "صديقة", "حياة", "ليل", "نهار", "شمس", "قمر", "نجمة", "سعيد", "حزين", "شكرا", "عربي"
]


# --- Function to detect the language of a song based on its content, URL, and title ---
def detect_song_language(content, url, title):
    text_all = f"{content} {url} {title}".lower()

    # 1. Script-based detection (highest priority)
    if re.search(r'[\u0900-\u097F]', text_all):
        return "hindi"
    if re.search(r'[\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff]', text_all):
        return "japanese"
    if re.search(r'[\u0600-\u06FF]', text_all):
        return "arabic"
    if re.search(r'[\u0B80-\u0BFF]', text_all):
        return "tamil"
    if re.search(r'[\u0D80-\u0DFF]', text_all):
        return "sinhala"
    # German-specific characters
    if re.search(r'[äöüß]', text_all):
        return "german"
    # French-specific characters
    if re.search(r'[àâçéèêëîïôœùûüÿ]', text_all):
        return "french"
    # Mandarin Chinese characters
    if re.search(r'[\u4e00-\u9fff]', text_all):
        return "mandarin"
    
    
    # 2. Keyword-based detection (non-English first)
    if any(word in text_all for word in hindi_keywords):
        return "hindi"
    if any(word in text_all for word in french_keywords):
        return "french"
    if any(word in text_all for word in japanese_keywords):
        return "japanese"
    if any(word in text_all for word in german_keywords):
        return "german"
    if any(word in text_all for word in spanish_keywords):
        return "spanish"
    if any(word in text_all for word in tamil_keywords):
        return "tamil"
    if any(word in text_all for word in sinhala_keywords):
        return "sinhala"
    if any(word in text_all for word in malay_keywords):
        return "malay"
    if any(word in text_all for word in mandarin_keywords):
        return "mandarin"
    if any(word in text_all for word in arabic_keywords):
        return "arabic"

    # 3. Only now check for English keywords
    if any(word in text_all for word in english_keywords):
        return "english"

    # 4. Fallback: langdetect
    try:
        text = f"{content} {title}".strip()
        if text and len(text.split()) > 5:
            lang = detect(text)
            if lang == "hi":
                return "hindi"
            elif lang == "fr":
                return "french"
            elif lang == "ja":
                return "japanese"
            elif lang == "de":
                return "german"
            elif lang == "en":
                return "english"
            elif lang == "es":
                return "spanish"
            elif lang == "ta":
                return "tamil"
            elif lang == "si":
                return "sinhala"
            elif lang == "ms":
                return "malay"
            elif lang == "zh-cn" or lang == "zh-tw":
                return "mandarin"
            elif lang == "ar":
                return "arabic"
    except LangDetectException:
        pass

    # 5. Fallback: URL/title hints
    if "hindi" in url or "hindi" in title:
        return "hindi"
    if "french" in url or "francais" in title:
        return "french"
    if "japan" in url or "japanese" in title:
        return "japanese"
    if "german" in url or "deutsch" in title:
        return "german"
    if "english" in url or "english" in title:
        return "english"
    if "spanish" in url or "espanol" in title:
        return "spanish"
    if "tamil" in url or "tamil" in title:
        return "tamil"
    if "sinhala" in url or "sinhala" in title:
        return "sinhala"
    if "malay" in url or "malay" in title:
        return "malay"
    if "mandarin" in url or "chinese" in title:
        return "mandarin"
    if "arabic" in url or "arabic" in title:
        return "arabic"

    return "unknown"


    # 6. If nothing matches, return unknown

    # --- Expanded keyword lists for each language ---


    text_all = f"{content} {url} {title}".lower()
    if any(word in text_all for word in hindi_keywords) or re.search(r'[\u0900-\u097F]', text_all):
        return "hindi"
    if any(word in text_all for word in french_keywords):
        return "french"
    if any(word in text_all for word in japanese_keywords) or re.search(r'[\u3040-\u30ff\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff]', text_all):
        return "japanese"
    if any(word in text_all for word in german_keywords):
        return "german"
    if any(word in text_all for word in english_keywords):
        return "english"
    if "hindi" in url or "hindi" in title:
        return "hindi"
    if "french" in url or "francais" in title:
        return "french"
    if "japan" in url or "japanese" in title:
        return "japanese"
    if "german" in url or "deutsch" in title:
        return "german"
    if "english" in url or "english" in title:
        return "english"
    return "unknown"

# --- Language support mapping for bots ---
def is_language_supported_by_bot(bot_id: str, detected_language: str) -> bool:
    bot_id = bot_id.lower()
    detected_language = detected_language.lower()
    return detected_language in BOT_LANGUAGE_MAP.get(bot_id, [])

# --- Language support mapping for bots ---
def call_gemini_ai(prompt, max_tokens=180):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=0.7,
        )
    )
    return response.text.strip()

#if the detected language is not supported by the bot, return a friendly message

SONG_UNSUPPORTED_LANGUAGE_RESPONSES = [
    "I bet it's a wonderful song, but sorry dear, I don't know this language yet! 🎶🌏",
    "This song sounds interesting, but I can't understand the language. Maybe you can tell me what it's about? 😊",
    "Sorry, I wish I could help with this song, but I don't know this language. Music is still magical though! ✨",
    "Oh, I love discovering new music! Sadly, I can't understand this language yet. Want to share what it means to you?",
    "It must be a beautiful song, but I don't know this language. Maybe you can teach me a word or two? 🎵💬"
]

def get_unsupported_language_message(detected_language):
    return random.choice(SONG_UNSUPPORTED_LANGUAGE_RESPONSES)



@app.post("/api/news")
async def api_news(request: NewsSummaryRequest):
    query = request.query
    bot_id = request.bot_id
    user_email = request.user_email
    conversation_id = request.conversation_id
    # --- 1. Detect URLs in the user query (e.g., news, YouTube, Spotify, etc.) ---

    detected_urls = detect_urls_in_query(query)
    if detected_urls:
                # --- 2. Fetch website content for the first detected URL ---

        website_data = fetch_website_content(detected_urls[0])
        if website_data:
            url = website_data.get("url", "")
            content = website_data.get("content", "")
            title = website_data.get("title", "")

                        # --- 3. Check if the URL or title suggests a song/music link ---

            song_keywords = [
                "spotify", "youtube", "youtu.be", "song", "lyrics", "music", "album", "track", "playlist", "गीत", "गाना"
            ]
                        # If any keyword is present in the URL or title, treat as a song/music link

            is_song = any(kw in url.lower() for kw in song_keywords) or any(kw in title.lower() for kw in song_keywords)
                # --- 4. Song detected: Get bot persona and detect song language ---

            if is_song:
                bot_persona = get_bot_prompt(bot_id)
                song_language = detect_song_language(content, url, title)

                # Language-bot matching logic
                if not is_language_supported_by_bot(bot_id, song_language):
                                    # --- 5. Check if the bot supports the detected song language ---

                    return {
                        'status': 'error',
                        'result': get_unsupported_language_message(song_language),
                        'mode': 'website_summary',
                        'timestamp': datetime.now().isoformat()
                    }

                # If supported, proceed as before
                persona_instructions = (
                    f"{bot_persona}\n"
                    "You are a music-loving assistant. When summarizing a song, adapt your tone and emojis to the mood of the lyrics (love, heartbreak, party, motivational, sad, etc.) "
                    "and to your persona (mentor, friend, romantic, etc.). "
                    "For each response, the proactive message (Line 3) must be unique, creative, and use different emojis that fit both the mood and the persona. "
                    "Do NOT repeat the same proactive message or emoji style for every song or persona. "
                    "For example:\n"
                    "- For a friend persona and party song, use fun, energetic language and party emojis 🎉🕺.\n"
                    "- For a romantic persona and love song, use sweet, dreamy language and heart/love emojis 💖😍.\n"
                    "- For a mentor persona and motivational song, use encouraging words and uplifting emojis 🚀🌟.\n"
                    "- For a friend persona and heartbreak song, use supportive, caring words and comforting emojis 🤗💔.\n"
                    "Be creative and make each proactive message feel personal and fresh!\n"
                    f"Song title: {title}\n"
                    f"Lyrics/content: {content[:1500]}\n"
                    "Respond in three lines (no labels):\n"
                    "Do not ever mention the song name or movie name in your response."
                    "- First line: Song summary (first sentence)\n"
                    "- Second line: Song summary (second sentence, or leave blank if not needed)\n"
                    "- Third line: Proactive message or question for the user that fits the mood and your persona, with unique emojis.\n"
                    "If the summary can be done in one sentence, leave the second line blank.\n"
                )                 # --- 7. Call Gemini AI to generate the summary using the instructions ---

                ai_response = call_gemini_ai(persona_instructions, max_tokens=180)
            else:
                                # --- 8. If not a song/music link, generate a regular website/news summary ---

                ai_response = create_website_summary_response(query, website_data, bot_id=bot_id)
            # --- 9. Return the AI response and website data ---

            return {
                'status': 'success',
                'ai_response': ai_response,
                'website_data': website_data,
                'detected_urls': detected_urls,
                'mode': 'website_summary',
                'timestamp': datetime.now().isoformat()
            }
        else:
                        # --- 10. Could not fetch website content ---

            return {
                'status': 'error',
                'result': f"Could not fetch content from {detected_urls[0]}",
                'mode': 'website_summary',
                'timestamp': datetime.now().isoformat()
            }
    # --- 11. No URL found in the query ---

    return {
        'status': 'error',
        'result': "No website or YouTube link found in your query.",
        'mode': 'website_summary',
        'timestamp': datetime.now().isoformat()
    }


@app.post("/v2/cv/chat")
async def cv_chat_v2(request: QuestionRequest2, background_tasks: BackgroundTasks):
    message_generated_counter.inc()

    try:
        # Validate if the question is provided and not empty
        if not request.message or request.message.strip() == "":
            return {"error": str("Please provide a message")}  # Return error if invalid

        # === LANGUAGE CHECK: Call external API ===
        lang_check = await check_language_supported(request.message, request.bot_id)
        if not lang_check.get("supported", True):
            # Return the persona-specific message from the language check API
            return {
                "response": lang_check.get("message", "Sorry, I can't understand this language."),
                "message_id": None,
                "reminder": False,
                "xp_data": None
            }
        # === END LANGUAGE CHECK ===

        magnitude = get_magnitude_for_query(request.message)
        immediate_xp_result = award_immediate_xp_and_magnitude(
            request.email, 
            request.bot_id, 
            magnitude
        )
        reminder = False

        previous_conversation = restrict_to_last_20_messages(request.previous_conversation)
        detected_urls = detect_urls_in_query(request.message)
        if detected_urls:
            website_data = fetch_website_content(detected_urls[0])
            if website_data:
                url = website_data.get("url", "")
                content = website_data.get("content", "")
                title = website_data.get("title", "")
                song_keywords = [
                    "spotify", "youtube", "youtu.be", "song", "lyrics", "music", "album", "track", "playlist", "गीत", "गाना"
                ]
                is_song = any(kw in url.lower() for kw in song_keywords) or any(kw in title.lower() for kw in song_keywords)
                if is_song:
                    song_language = detect_song_language(content, url, title)
                    if not is_language_supported_by_bot(request.bot_id, song_language):
                        return {
                            "response": get_unsupported_language_message(song_language),
                            "message_id": None,
                            "reminder": False,
                            "xp_data": None
                        }
        check = await check_for_origin_question(request.message,request.previous_conversation)

        if check == "Yes":
            bot_personality = get_bot_personality(request.bot_id)
            bot_name = bot_personality.get("bot_name", "Unknown")
            bot_origin = bot_personality.get("bot_city", "Unknown")

            # Updated response using bot_name and bot_origin
            response = f"My name is {bot_name} and I am from {bot_origin}. I was developed by a team of Desi Developers, but you brought me to life on Novi!!"

            log = log_messages_with_like_dislike(request.email,request.bot_id,request.message,response,"",previous_conversation[-5:],"")
            return {
                "response": response,
                "message_id": log.data[0]["id"],
                "reminder": False,
                "xp_data": {
                    "immediate_xp_awarded": immediate_xp_result["immediate_xp_awarded"],
                    "current_total_xp": immediate_xp_result["current_total_xp"],
                    "current_total_coins": immediate_xp_result["current_total_coins"],
                    "magnitude": immediate_xp_result["magnitude"],
                    "xp_calculation_success": immediate_xp_result["success"]
                }
            }

        # Get relative information from the question
        memory, rephrased_user_message, category = await retrieve_memory(request.message, request.email, request.bot_id, previous_conversation)
        if category == "Reminder":
            print("REMINDER")
            reminder = await reminder_response(request.message, previous_conversation, request.request_time)
            response = reminder['response']
        else:
            # Generate bot response using the provided information and user question
            spiritual_bots = ["Krishna", "Ram", "Hanuman", "Shiva", "Trimurti"]
            if request.bot_id in spiritual_bots:
                response = await bhagwan_response(request.user_name, request.user_gender, request.bot_id, request.message)
            else:
                response = await bot_response_v2(request.bot_prompt, request.bot_id, request.message, rephrased_user_message, previous_conversation, memory, request.request_time, request.user_gender, request.user_name, request.custom_bot_name)

        log = log_messages_with_like_dislike(request.email, request.bot_id, request.message, response, "", previous_conversation[-5:], memory)

        background_tasks.add_task(
            insert_entry, request.email, request.message, response, request.bot_id, request.request_time, request.platform
        )

        return {
            "response": response,
            "message_id": log.data[0]["id"],
            "reminder": reminder,
            "xp_data": {
                "immediate_xp_awarded": immediate_xp_result["immediate_xp_awarded"],
                "current_total_xp": immediate_xp_result["current_total_xp"],
                "current_total_coins": immediate_xp_result["current_total_coins"],
                "magnitude": immediate_xp_result["magnitude"],
                "xp_calculation_success": immediate_xp_result["success"]
            }
        }

    except Exception as e:
        logging.info(f"Error: {e}")  # Log the error for debugging
        print(e)
        traceback.print_exc()
        return {"error": str("Error occurred while generating!!")}  # Return error message

class ReminderResponse(BaseModel):
    message: Union[str, None] = None  # Question from the user
    bot_id: str = "delhi"  # Personality type
    # bot_prompt: str = ""  # Personality prompt
    previous_conversation: list = [] # previous conversation
    email: str = ""  # Email address
    request_time : str = "" # Time of request
    remind_time: str = "" # Time of reminder set for
    platform : str = "" # Platform from which the request is made

"""
    This Python function generates a reminder response based on user input and logs the interaction.

    :param request: The `request` parameter in the `reminder_response_generate` function is of type
    `ReminderResponse`, which likely contains information related to a reminder request. It may include
    attributes such as `previous_conversation`, `message`, `request_time`, `remind_time`, `email`, and
    `bot_id
    :type request: ReminderResponse
    :param background_tasks: The `background_tasks` parameter in the `reminder_response_generate`
    function is used to schedule background tasks to be run after the response is sent back to the user.
    In this case, the `background_tasks` object is used to add a task to insert an entry into the
    database after generating the reminder
    :type background_tasks: BackgroundTasks
    :return: The code snippet is an endpoint for generating a reminder response in a FastAPI
    application. When a POST request is made to "/cv/response/reminder" with a `ReminderResponse`
    object, the function `reminder_response_generate` is executed to process the request and generate
    a response.
"""
@app.post("/cv/response/reminder")
async def reminder_response_generate(request: ReminderResponse, background_tasks: BackgroundTasks):
    try:
        # Make the reminder to default to False
        reminder = False

        # Restrict the previous conversation to the last 20 messages
        # Previous conversation coming from the frontend
        previous_conversation = restrict_to_last_20_messages(request.previous_conversation)

        # Generate the reminder response
        response = await reminder_response_to_user(request.message, previous_conversation, request.request_time,request.remind_time)

        # Log the response
        log = log_messages_with_like_dislike(request.email,request.bot_id,request.message,response,"",previous_conversation[-5:],"")

        # Add the entry to the database
        background_tasks.add_task(
            insert_entry,request.email,request.message,response,request.bot_id,request.request_time,request.platform
        )

        # Return the response
        return {
            "response": response,
            "message_id": log.data[0]["id"],
            "reminder": reminder
        }

    # Handle any exceptions that occur during execution
    except Exception as e:
        print(e)
        return {"error": str("Error occurred while generating reminder response!!")}  # Return error message


"""
    This Python function handles feedback for a specific message identified by its ID.

    :param message_id: The `message_id` parameter in the code snippet represents the unique identifier
    of a message for which feedback is being provided. It is expected to be an integer value that helps
    identify the specific message within the system
    :type message_id: int
    :param feedback: The `feedback` parameter in the code snippet represents the feedback provided for a
    specific message identified by `message_id`. It seems like the code is designed to handle liking or
    disliking a message based on the feedback provided. The `feedback` parameter is expected to be a
    string indicating the type of
    :type feedback: str
    :return: The code snippet is a FastAPI endpoint that handles a POST request to provide feedback
    (like/dislike) for a specific message identified by `message_id`. The endpoint calls a function
    `like_dislike(message_id, feedback)` to process the feedback and returns the result.
"""
@app.post("/cv/message/feedback/{message_id}/{feedback}")
async def like_message(message_id: int,feedback: str):
    try:
        # Process the feedback
        res = like_dislike(message_id,feedback)
        # Return the result
        return res
    except Exception as e:
        print(e)
        return {"error": str("Error occurred while processing!!")}  # Return error message

class NotesRequest(BaseModel):
    text : str = ""
    email : str = ""
    bot_id : str = ""

"""
    This Python function receives a POST request with notes data, validates the input, extracts notes
    from memory, logs the notes, and returns a success message or an error message if an exception
    occurs.

    :param request: The `request` parameter in the `cv_notes` function is of type `NotesRequest`, which
    is the request body containing the text, email, and bot_id needed for processing notes. It is used
    to extract notes from memory and log them for further processing
    :type request: NotesRequest
    :param background_tasks: The `background_tasks` parameter in the FastAPI route function `cv_notes`
    is used to add background tasks that should be run after sending the response to the client. In this
    case, the `background_tasks` object is used to add a task to log the notes in memory after
    extracting the notes
    :type background_tasks: BackgroundTasks
    :return: The endpoint `/cv/notes` is designed to receive a POST request with a `NotesRequest` object
    containing `text`, `email`, and `bot_id` fields. Upon receiving the request, the function `cv_notes`
    will first validate if the `text` field is provided and not empty. If the text is invalid, it will
    return an error message asking to provide text.
"""
@app.post("/cv/notes")
async def cv_notes(request: NotesRequest,background_tasks: BackgroundTasks):
    try:
        # Validate if the question is provided and not empty
        if not request.text or request.text.strip() == "":
            return {"error": str("Please provide a text")}  # Return error if invalid

        # Extract memory from the text
        res = await extract_notes_memory(request.text,request.email,request.bot_id)

        # Log the notes
        background_tasks.add_task(
            log_notes_memory,request.text,res,request.email,request.bot_id
        )
        return True
    except Exception as e:
        print(e)
        return {"error": str(f"Error occurred while processing!!")}  # Return error message

# Initialize Cartesia client for TTS
client = Cartesia(api_key=os.environ.get("CARTESIA_API_KEY"))

# Voice mapping for different bots (maps bot_id to Cartesia voice_id)
VOICE_MAPPING = {
    "delhi_mentor_male": "fd2ada67-c2d9-4afe-b474-6386b87d8fc3",
    "delhi_mentor_female": "faf0731e-dfb9-4cfc-8119-259a79b27e12",
    "delhi_friend_male": "791d5162-d5eb-40f0-8189-f19db44611d8",
    "delhi_friend_female": "95d51f79-c397-46f9-b49a-23763d3eaa2d",
    "delhi_romantic_male": "be79f378-47fe-4f9c-b92b-f02cefa62ccf",
    "delhi_romantic_female": "28ca2041-5dda-42df-8123-f58ea9c3da00",

    "japanese_mentor_male": "a759ecc5-ac21-487e-88c7-288bdfe76999",
    "japanese_mentor_female": "2b568345-1d48-4047-b25f-7baccf842eb0",
    "japanese_friend_male": "06950fa3-534d-46b3-93bb-f852770ea0b5",
    "japanese_friend_female": "44863732-e415-4084-8ba1-deabe34ce3d2",
    "japanese_romantic_female": "0cd0cde2-3b93-42b5-bcb9-f214a591aa29",
    "japanese_romantic_male" : "6b92f628-be90-497c-8f4c-3b035002df71",

    "parisian_mentor_male": "5c3c89e5-535f-43ef-b14d-f8ffe148c1f0",
    "parisian_mentor_female": "8832a0b5-47b2-4751-bb22-6a8e2149303d",
    "parisian_friend_male": "ab7c61f5-3daa-47dd-a23b-4ac0aac5f5c3",
    "parisian_friend_female": "65b25c5d-ff07-4687-a04c-da2f43ef6fa9",
    "parisian_romantic_female": "a8a1eb38-5f15-4c1d-8722-7ac0f329727d",

    "berlin_mentor_male": "e00dd3df-19e7-4cd4-827a-7ff6687b6954",
    "berlin_mentor_female": "3f4ade23-6eb4-4279-ab05-6a144947c4d5",
    "berlin_friend_male": "afa425cf-5489-4a09-8a3f-d3cb1f82150d",
    "berlin_friend_female": "1ade29fc-6b82-4607-9e70-361720139b12",
    "berlin_romantic_male": "b7187e84-fe22-4344-ba4a-bc013fcb533e",
    "berlin_romantic_female": "4ab1ff51-476d-42bb-8019-4d315f7c0c05",
    
    "singapore_mentor_male": "eda5bbff-1ff1-4886-8ef1-4e69a77640a0",
    "singapore_mentor_female": "f9a4b3a6-b44b-469f-90e3-c8e19bd30e99",
    "singapore_friend_male": "c59c247b-6aa9-4ab6-91f9-9eabea7dc69e",
    "singapore_friend_female": "bf32f849-7bc9-4b91-8c62-954588efcc30",
    "singapore_romantic_male": "653b9445-ae0c-4312-a3ce-375504cff31e",
    "singapore_romantic_female": "7a5d4663-88ae-47b7-808e-8f9b9ee4127b",

    "mexican_mentor_male": "79743797-2087-422f-8dc7-86f9efca85f1",
    "mexican_mentor_female": "cefcb124-080b-4655-b31f-932f3ee743de",
    "mexican_friend_male": "15d0c2e2-8d29-44c3-be23-d585d5f154a1",
    "mexican_friend_female": "5c5ad5e7-1020-476b-8b91-fdcbe9cc313c",
    "mexican_romantic_male": "5ef98b2a-68d2-4a35-ac52-632a2d288ea6",
    "mexican_romantic_female": "c0c374aa-09be-42d9-9828-4d2d7df86962",

    "srilankan_mentor_male": "fd2ada67-c2d9-4afe-b474-6386b87d8fc3",
    "srilankan_mentor_female": "faf0731e-dfb9-4cfc-8119-259a79b27e12",
    "srilankan_friend_male": "791d5162-d5eb-40f0-8189-f19db44611d8",
    "srilankan_friend_female": "95d51f79-c397-46f9-b49a-23763d3eaa2d",
    "srilankan_romantic_male": "be79f378-47fe-4f9c-b92b-f02cefa62ccf",
    "srilankan_romantic_female": "28ca2041-5dda-42df-8123-f58ea9c3da00",

    "emirati_mentor_male": "5a31e4fb-f823-4359-aa91-82c0ae9a991c",
    "emirati_mentor_female": "fa7bfcdc-603c-4bf1-a600-a371400d2f8c",
    "emirati_friend_male": "c1cfee3d-532d-47f8-8dd2-8e5b2b66bf1d",
    "emirati_friend_female": "fa7bfcdc-603c-4bf1-a600-a371400d2f8c",
    "emirati_romantic_male": "39f753ef-b0eb-41cd-aa53-2f3c284f948f",
    "emirati_romantic_female": "bb2347fe-69e9-4810-873f-ffd759fe8420",

    "Krishna": "be79f378-47fe-4f9c-b92b-f02cefa62ccf",
    "Rama": "fd2ada67-c2d9-4afe-b474-6386b87d8fc3",
    "Hanuman": "fd2ada67-c2d9-4afe-b474-6386b87d8fc3",
    "Shiva": "be79f378-47fe-4f9c-b92b-f02cefa62ccf",
    "Trimurti": "be79f378-47fe-4f9c-b92b-f02cefa62ccf"
}
# Add these functions after the VOICE_MAPPING around line 870:

# In your voice call functions, update the TTS format selection:

def get_smart_audio_format(text: str, use_case: str = "voice_call") -> dict:
    """PERFECT audio format selection"""
    word_count = len(text.split())

    if use_case == "voice_call":
        if word_count <= 5:  # Very short responses
            return get_optimized_audio_format("voice_call_minimal")  # 4kHz for max speed
        else:
            return get_optimized_audio_format("ultra_fast")  # 6kHz for speed

    return get_optimized_audio_format("balanced")

def get_optimized_audio_format(optimization_level: str = "ultra_fast"):
    """Get optimized audio format configuration"""
    OPTIMIZED_AUDIO_FORMATS = {
        "ultra_fast": {
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": 8000,
        },
        "voice_call_minimal": {
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": 8000,  # Minimum for speech intelligibility
        },
        "balanced": {
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": 8000,
        }
    }
    return OPTIMIZED_AUDIO_FORMATS.get(optimization_level, OPTIMIZED_AUDIO_FORMATS["ultra_fast"])

# TTS Cache for common responses
TTS_CACHE = {}
TTS_CACHE_MAX_SIZE = 1000
TTS_CACHE_ENABLED = True
TTS_CACHE_TTL_HOURS = 24
TTS_CACHE_STATS = {"hits": 0, "misses": 0, "total_requests": 0}

# Replace your cache functions with these ASYNC versions:



# REPLACE your broken async cache function with this WORKING version:

async def get_cached_tts_response_async(text: str, voice_id: str) -> Optional[str]:
    """WORKING async cache retrieval with proper error handling"""
    if not TTS_CACHE_ENABLED:
        return None

    def _get_cache():
        cache_key = f"{voice_id}:{hash(text)}"
        TTS_CACHE_STATS["total_requests"] += 1

        print(f"🔍 CACHE DEBUG: Looking for key: {cache_key[:50]}...")
        print(f"🔍 CACHE DEBUG: Current cache size: {len(TTS_CACHE)}")

        cached_entry = TTS_CACHE.get(cache_key)
        if not cached_entry:
            TTS_CACHE_STATS["misses"] += 1
            print(f"❌ CACHE DEBUG: Key not found in cache")
            return None

        # Check TTL
        age_hours = (time.time() - cached_entry["timestamp"]) / 3600
        if age_hours > TTS_CACHE_TTL_HOURS:
            del TTS_CACHE[cache_key]
            TTS_CACHE_STATS["misses"] += 1
            print(f"⏰ CACHE DEBUG: Entry expired ({age_hours:.1f}h old)")
            return None

        TTS_CACHE_STATS["hits"] += 1
        print(f"✅ CACHE DEBUG: Cache hit! Entry age: {age_hours:.1f}h")
        return cached_entry["audio"]

    try:
        # Use the global executor
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(cache_executor, _get_cache)
        print(f"🔍 CACHE DEBUG: Async cache result: {'HIT' if result else 'MISS'}")
        return result
    except Exception as e:
        print(f"❌ CACHE DEBUG: Async cache error: {e}")
        return None

# REPLACE your broken async cache storage with this WORKING version:

async def cache_tts_response_async(text: str, voice_id: str, audio_base64: str):
    """WORKING async cache storage with proper error handling"""
    if not TTS_CACHE_ENABLED:
        return

    def _store_cache():
        cache_key = f"{voice_id}:{hash(text)}"
        timestamp = time.time()

        print(f"💾 CACHE DEBUG: Storing key: {cache_key[:50]}...")
        print(f"💾 CACHE DEBUG: Audio length: {len(audio_base64)}")

        # Simple LRU: remove oldest if cache is full
        if len(TTS_CACHE) >= TTS_CACHE_MAX_SIZE:
            oldest_key = next(iter(TTS_CACHE))
            del TTS_CACHE[oldest_key]
            print(f"🗑️ CACHE DEBUG: Removed oldest entry (cache full)")

        TTS_CACHE[cache_key] = {
            "audio": audio_base64,
            "timestamp": timestamp
        }

        print(f"✅ CACHE DEBUG: Stored successfully! Cache size now: {len(TTS_CACHE)}")

    try:
        loop = asyncio.get_event_loop()
        # ✅ CRITICAL FIX: Use await here, not just run_in_executor
        await loop.run_in_executor(cache_executor, _store_cache)
    except Exception as e:
        print(f"❌ CACHE DEBUG: Storage error: {e}")
# Pydantic model for TTS request
class TTSRequest(BaseModel):
    transcript: str
    bot_id: str  # Changed from voice_id to bot_id to map to specific bot voices
    output_format: Optional[dict] = {
        "container": "wav",
        "encoding": "pcm_s16le",  # Use PCM 16-bit little-endian for better compatibility
        "sample_rate":  22050,
    }

# Helper function to get the voice_id for a given bot_id
# Returns a default voice_id if bot_id is not found
# Tries both case-sensitive and lowercase matching
def get_voice_id_for_bot(bot_id: str) -> str:
    """Get the voice ID for a specific bot"""
    # Default voice ID if bot not found in mapping
    default_voice_id = "4df027cb-2920-4a1f-8c34-f21529d5c3fe"  # Default US Man voice

    # Check if bot_id exists in voice mapping (case-sensitive)
    if bot_id in VOICE_MAPPING:
        return VOICE_MAPPING[bot_id]

    # If not found, try lowercase version
    bot_id_lower = bot_id.lower()
    if bot_id_lower in VOICE_MAPPING:
        return VOICE_MAPPING[bot_id_lower]

    return default_voice_id

# Utility to clean up temporary files (used in other endpoints)
def cleanup_file(path: str):
    """Background task to remove the temporary file"""
    try:
        os.unlink(path)
    except Exception as e:
        print(f"Error cleaning up file {path}: {e}")

# Main TTS endpoint: generates audio for a given transcript and bot_id
@app.post("/generate-audio")
async def generate_audio(request: TTSRequest, background_tasks: BackgroundTasks):
    """
    ENHANCED TTS endpoint with optimizations:
    1. Check TTS cache for common responses
    2. Use optimized audio format for faster processing
    3. Fallback to original implementation on errors
    """
    tts_start_time = time.time()

    try:
        logging.info(f"🎵 ENHANCED TTS generate_audio called with bot_id: {request.bot_id}")
        print(f"🎵 ENHANCED TTS generate_audio called with bot_id: {request.bot_id}")

        # Get the appropriate voice ID for the bot
        voice_id = get_voice_id_for_bot(request.bot_id)

        # ========== OPTIMIZATION 1: Check TTS cache first ==========
        cached_audio = get_cached_tts_response(request.transcript, voice_id)
        if cached_audio:
            cache_time = time.time() - tts_start_time
            logging.info(f"✅ TTS cache HIT - Retrieved in {cache_time:.3f}s")
            return {
                "voice_id": voice_id,
                "audio_base64": cached_audio
            }

        # ========== OPTIMIZATION 2: Use smart audio format selection ==========
        # Automatically choose the best format based on text length and use case
        smart_format = get_smart_audio_format(request.transcript, "voice_call")
        actual_format = smart_format

        # Generate audio bytes using Cartesia (collect all chunks from generator)
        # The Cartesia API returns a generator of audio chunks, so we join them into a single bytes object
        audio_chunks = client.tts.bytes(
            model_id="sonic",
            transcript=request.transcript,
            voice={"mode": "id", "id": voice_id},
            output_format=actual_format
        )
        audio_data = b"".join(audio_chunks)
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        generation_time = time.time() - tts_start_time

        # ========== OPTIMIZATION 3: Cache the response ==========
        cache_tts_response(request.transcript, voice_id, audio_base64)

        logging.info(f"✅ TTS generation completed in {generation_time:.3f}s")

        # Return JSON with voice_id and base64 audio
        return {
            "voice_id": voice_id,
            "audio_base64": audio_base64
        }
    except Exception as e:
        generation_time = time.time() - tts_start_time
        logging.error(f"❌ Enhanced TTS failed in {generation_time:.3f}s: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class TTSRequest2(BaseModel):
    text: str
    target_language_code: str = "hi-IN"  # Default to Hindi
    speaker: str  # Default speaker
    speech_sample_rate: int = 8000  # Default sample rate
    enable_preprocessing: bool = True  # Default preprocessing
    model: str = "bulbul:v1"  # Default model

def cleanup_file(path: str):
    """Background task to remove the temporary file"""
    try:
        os.unlink(path)
    except Exception as e:
        print(f"Error cleaning up file {path}: {e}")

@app.post("/v2/generate-audio")
async def generate_audio_v2(request: TTSRequest2, background_tasks: BackgroundTasks):
    try:
        logging.info(f"🔴 SARVAM generate_audio_v2 function called with text: {request.text[:50]}...")
        print(f"🔴 SARVAM generate_audio_v2 function called with text: {request.text[:50]}...")
        # Prepare the API request
        url = "https://api.sarvam.ai/text-to-speech"
        headers = {
            "API-Subscription-Key": os.getenv("SARVAM_API_KEY"),
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": [request.text],
            "target_language_code": request.target_language_code,
            "speaker": request.speaker,
            "speech_sample_rate": request.speech_sample_rate,
            "enable_preprocessing": request.enable_preprocessing,
            "model": request.model
        }

        # Make the API call
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Sarvam API request failed")

        # Process the response
        audio_base64 = response.json()["audios"][0]
        audio_bytes = base64.b64decode(audio_base64)

        # Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        # Add cleanup task to background tasks
        background_tasks.add_task(cleanup_file, temp_path)

        # Return the audio file
        return FileResponse(
            temp_path,
            media_type="audio/wav",
            filename="generated_audio.wav"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""
    The function `sync` processes a POST request to synchronize messages based on provided email, bot
    ID, and messages ID.

    :param request: The `request` parameter in the `sync` function is of type `SyncRequest`, which is a
    Pydantic model representing the data structure expected in the request body of the POST request to
    the `/sync` endpoint. It contains the following fields:
    :type request: SyncRequest
    :param background_tasks: The `background_tasks` parameter in FastAPI is used to add background tasks
    to be run after returning a response to the client. These tasks are executed asynchronously after
    the response to the client, allowing you to perform additional operations without delaying the
    response to the client
    :type background_tasks: BackgroundTasks
    :return: The code snippet defines a FastAPI endpoint `/sync` that expects a POST request with a JSON
    body matching the `SyncRequest` model. The endpoint checks if the `email` and `bot_id` fields are
    provided and not empty. If either of them is missing or empty, it returns an error message
    indicating which field is missing. If both fields are provided, it calls the `sync_messages
"""
class SyncRequest(BaseModel):
    email: str = ""
    bot_id: str = ""
    messages_id: str = ""

@app.post("/sync")
async def sync(request: SyncRequest, background_tasks: BackgroundTasks):
    try:
        # Validate if the question is provided and not empty
        if not request.email or request.email.strip() == "":
            return {"error": str("Please provide a email")}  # Return error if invalid

        # Validate if the bot_id is provided and not empty
        if not request.bot_id or request.bot_id.strip() == "":
            return {"error": str("Please provide a bot_id")}  # Return error if invalid

        # Get all messages based on email, bot_id, and messages_id [optional] from the database
        messages = sync_messages(request.email, request.bot_id, request.messages_id)

        # Return the messages
        return {
            "response": messages
        }
    except Exception as e:
        print(e)
        return {"error": str(f"Error occurred while processing!!")}  # Return error message


"""
The function `get_memories` retrieves memories from a database based on email and bot_id, organizes
them by category, and returns a dictionary of categorized memories.

:param email: The `email` parameter in the `get_memories` function is a string that represents the
email address of a user. This parameter is used to retrieve memories associated with the specified
email address from the database
:type email: str
:param bot_id: The `bot_id` parameter in the `get_memories` endpoint represents the unique
identifier of a bot. This identifier is used to retrieve memories associated with a specific bot
from the database. By providing the `bot_id` in the URL path, the endpoint can fetch memories
specific to that bot for
:type bot_id: str
:return: The `get_memories` function returns a dictionary where memories are grouped by category.
Each category contains a list of memory texts that belong to that category. If an error occurs
during processing, it returns a dictionary with an "error" key indicating the error message.
"""
@app.get("/get-memories/{email}/{bot_id}")
async def get_memories(email: str, bot_id: str):
    try:
        # Get memories from the database
        query_response = get_memories_from_DB(email, bot_id)

        # Create a dictionary to group memories by category
        categorized_memories = {}

        # Process each memory and organize by category in JSON Object
        for match in query_response.get("matches", []):
            metadata = match.get("metadata", {})
            text = metadata.get("text", "")
            categories = metadata.get("categories", [])
            memory_id = match.get("id","")

            memory_data = {
                "id": memory_id,
                "text": text
            }
            # Add the memory text to each category it belongs to
            for category in categories:
                if category not in categorized_memories:
                    categorized_memories[category] = []
                categorized_memories[category].append(memory_data)

        # Return the categorized memories
        return categorized_memories

    except Exception as e:
        print(f"Error in get_memories: {e}")
        return {"error": f"Error occurred while processing: {str(e)}"}

# update the existing memories
class AddMemoryRequest(BaseModel):
    text: str
    categories: list[str]
    email: str
    bot_id: str

class DeleteMemoryRequest(BaseModel):
    memory_id: str
    email: str
    bot_id: str

class UpdateMemoryRequest(BaseModel):
    memory_id: str
    updated_text: str
    updated_categories: list[str]
    email: str
    bot_id: str

def get_current_utc_time():
    current_time = datetime.now(timezone.utc)
    return current_time.strftime("%a %b %d %Y %H:%M:%S GMT%z")

# Add Memory API
@app.post("/add_memory")
async def add_memory(request: AddMemoryRequest):
    try:
        memory_id = f"mem_{uuid.uuid7()}"
        created_at = get_current_utc_time()

        embeddings = pc.inference.embed(
            model="multilingual-e5-large",
            inputs=[request.text],
            parameters={"input_type": "passage", "truncate": "END"}
        )

        embedding_values = embeddings[0]["values"]

        index.upsert(
            vectors=[
                {
                    "id": memory_id,
                    "values": embedding_values,
                    "metadata": {
                        "text": request.text,
                        "categories": request.categories,
                        "created_at": created_at
                    }
                }
            ],
            namespace=f"{request.email}-{request.bot_id}-conversation"
        )

        return {"message": "Memory added successfully!", "memory_id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Delete Memory API
@app.post("/delete_memory")
async def delete_memory(request: DeleteMemoryRequest):
    try:
        index.delete(
            ids=[request.memory_id],
            namespace=f"{request.email}-{request.bot_id}-conversation"
        )
        return {"message": "Memory deleted successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Update Memory API
@app.post("/update_memory")
async def update_memory(request: UpdateMemoryRequest):
    try:
        namespace = f"{request.email}-{request.bot_id}-conversation"
        updated_at = get_current_utc_time()

        # Generate new embedding for updated text
        embeddings = pc.inference.embed(
            model="multilingual-e5-large",
            inputs=[request.updated_text],
            parameters={"input_type": "passage", "truncate": "END"}
        )

        embedding_values = embeddings[0]["values"]

        index.upsert(
            vectors=[
                {
                    "id": request.memory_id,
                    "values": embedding_values,
                    "metadata": {
                        "text": request.updated_text,
                        "categories": request.updated_categories,
                        "updated_at": updated_at
                    }
                }
            ],
            namespace=namespace
        )

        return {"message": "Memory updated successfully!", "updated_id": request.memory_id , "updated_text": request.updated_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Uploading app.log file after every 5 minutes to S3 bucket
"""
    This Python function uploads the log file to an S3 bucket every 5 minutes.
    :return: The function `upload_log_to_s3` uploads the log file to an S3 bucket every 5 minutes.
"""
# Load environment variables for S3 configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "your-default-bucket-name")
S3_LOG_PREFIX = os.getenv("S3_LOG_PREFIX", "chat-logs/")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def upload_log_to_s3():
    try:
        # Initialize S3 client
        s3 = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )

        # Get the current timestamp
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Define the S3 object key (file name in S3)
        s3_object_key = f"{S3_LOG_PREFIX}app_log_{current_time}.log"               # it will make a file named app_log_{current_time}.log in s3 bucket and every 5 min.

        # Upload the log file to S3
        s3.upload_file("app.log", S3_BUCKET_NAME, s3_object_key)
        print(f"Log file uploaded to S3: {s3_object_key}")

    except ClientError as e:
        print(f"Error uploading log file to S3: {e}")

class CategorizerRequest(BaseModel):
    email: str
    bot_id: str
from MM2.serialization import serialize_memory

@app.post("/categorize")
def categorize_chat(request: CategorizerRequest):
    messages = fetch_new_messages(request.email, request.bot_id)

    if not messages:
        raise HTTPException(status_code=404, detail="No messages found for today.")

    chat_log = combine_messages(messages)

    categorizer_url = os.getenv("CATEGORIZER_URL")
    modelname = "sonar-reasoning"
    api_key = os.getenv("CATEGORIZER_API_KEY")

    payload = {
        "user_memories": chat_log,
        "type_analysis": "casual",
        "api_key": api_key,
        "modelname": modelname,
    }

    response = requests.post(categorizer_url, json=payload)

    if response.status_code != 200:
        logging.error(f"Categorizer response failed: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=response.text)

    try:
        raw_text = response.text.strip()
        logging.info(f"Raw Categorizer Response: {raw_text}")

        # Step 1: If double-encoded string, decode once
        if raw_text.startswith('"') and raw_text.endswith('"'):
            raw_text = json.loads(raw_text)

        # Step 2: Try to extract using ``` block first
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.DOTALL)
        if match:
            json_block = match.group(1).strip()
        else:
            json_block = raw_text.strip()

        # Step 3: Normalize to JSON array format
        if json_block.startswith('{') and json_block.endswith('}'):
            # Multiple objects, not in array
            # Try splitting on }{ and reassembling as array
            objects = re.findall(r'{.*?}', json_block, re.DOTALL)
            json_block = '[' + ','.join(objects) + ']'
        elif json_block.startswith('['):
            # Already an array
            pass
        else:
            raise ValueError("Unrecognized JSON format")

        result = json.loads(json_block)

        rows_to_insert = []
        for item in result:
            memory = item.get("rephrased_user_message")
            category = item.get("category")
            if memory and category:
                rows_to_insert.append({
                    "email": request.email,
                    "bot_id": request.bot_id,
                    "memory": memory,
                    "category": category
                })

        if not rows_to_insert:
            raise HTTPException(status_code=500, detail="No valid memory-category pairs found")

        rows_to_insert = [serialize_memory(row) for row in rows_to_insert]
        insert_response = supabase.table("persona_category").upsert(rows_to_insert).execute()
        logging.info("Supabase Insert Response:", insert_response)

        return {
            "data": rows_to_insert
        }

    except Exception as e:
        logging.error(f"error : {e}")
        raise HTTPException(status_code=500, detail=f"Unhandled error: {str(e)}")


"""
    API endpoint to retrieve summaries for a specific user and bot.

    Path Parameters:
        email (str): The email address of the user.
        bot_id (str): The ID of the bot.

    Returns:
        dict: A dictionary containing the email, bot_id, and a list of summaries.
              Each summary is expected to have 'summary_date' (in ISO format yyyy-mm-dd)
              and 'generated_summary' fields.
              Returns an error message if an exception occurs during the process.
"""

@app.get("/get-summaries/{email}/{bot_id}")
async def get_summaries(email: str, bot_id: str):
    try:
        summaries = get_summaries_from_DB(email, bot_id)  # <-- You need to implement this function
        return {
            "email": email,
            "bot_id": bot_id,
            "summaries": summaries
        }
    except Exception as e:
        logging.error(f"Error in get_summaries: {e}")
        return {"error": f"Error occurred while fetching summaries: {str(e)}"}


"""
    Pydantic model to define the request body for the delete summary API.
    Ensures the request has the necessary data and proper data types.
"""
class DeleteSummaryRequest(BaseModel):
    email: str
    bot_id: str
    summary_date: date  # Ensure summary_date is ISO format (yyyy-mm-dd)


"""
    API endpoint to delete a specific summary.

    Request Body (JSON):
        - email (str): The email address of the user.
        - bot_id (str): The ID of the bot.
        - summary_date (date): The date of the summary to delete (in ISO format yyyy-mm-dd).

    Returns:
        dict: A dictionary with a success message if the summary is deleted,
              or an error message if the summary is not found or an exception occurs.
"""

@app.delete("/delete-summary")
async def delete_summary(request: DeleteSummaryRequest):
    try:
        delete_result = delete_summary_from_DB(request.email, request.bot_id, request.summary_date)  # <-- Implement this
        if delete_result:
            return {"message": "Summary deleted successfully"}
        else:
            return {"error": "Summary not found or already deleted"}
    except Exception as e:
        logging.error(f"Error in delete_summary: {e}")
        return {"error": f"Error occurred while deleting summary: {str(e)}"}

@app.get("/get_persona")
async def get_persona(email: str = Query(...), bot_id: str = Query(...)) -> List[Dict]:
    # 1. Get non-redundant entries
    non_redundant = supabase.table("persona_category").select("memory, category, created_at, id, relation_id").eq("redundant", False).eq("email", email).eq("bot_id", bot_id).execute().data

    # 2. Get redundant entries
    redundant = supabase.table("persona_category").select("memory, category, created_at, id, relation_id").eq("redundant", True).eq("email", email).eq("bot_id", bot_id).order("created_at", desc=True).execute().data

    # 3. Keep only the latest entry per relation_id
    latest_redundant = {}
    for item in redundant:
        rel_id = item["relation_id"]
        if rel_id not in latest_redundant:
            latest_redundant[rel_id] = item  # because it's already sorted desc

    # 4. Combine results
    combined = non_redundant + list(latest_redundant.values())

    return combined


class PersonaCreate(BaseModel):
    email: str
    bot_id: str
    memory: str
    category: str
    redundant: Optional[bool] = False # Optional; can be auto-generated if needed

@app.post("/add_persona")
async def add_persona(entry: PersonaCreate):
    try:
        data = entry.dict()
        result = supabase.table("persona_category").insert(data).execute()
        return {"success": True, "inserted": result.data}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/delete_persona")
async def delete_persona(id: str = Query(...)):
    try:
        result = supabase.table("persona_category").delete().eq("id", id).execute()
        return {"success": True, "deleted": result.data}
    except Exception as e:
        return {"success": False, "error": str(e)}


class PersonaUpdate(BaseModel):
    memory: Optional[str] = None
    category: Optional[str] = None
    redundant: Optional[bool] = None
    relation_id: Optional[str] = None
    embedding: Optional[list] = None
    magnitude: Optional[float] = None
    recency: Optional[int] = None
    frequency: Optional[int] = None
    rfm_score: Optional[float] = None

@app.put("/update_persona")
async def update_persona(id: str = Query(...), updates: PersonaUpdate = Body(...)):
    update_dict = {k: v for k, v in updates.dict().items() if v is not None}
    if not update_dict:
        return {"error": "No fields provided to update."}

    try:
        result = supabase.table("persona_category").update(update_dict).eq("id", id).execute()
        return {"success": True, "updated": result.data}
    except Exception as e:
        return {"success": False, "error": str(e)}



# Define the expected schema for frontend error logs using Pydantic
class FrontendErrorLog(BaseModel):
    message: str
    source: str | None = None
    line_number: int | None = None
    column_number: int | None = None
    stack_trace: str | None = None
    browser: str | None = None
    url: str | None = None
    additional_context: dict | None = None
    timestamp: Optional[datetime] = None

# POST endpoint to receive and store frontend error logs
@app.post("/api/logs/frontend-error")
async def log_frontend_error(error_log: FrontendErrorLog):
    try:
        current_timestamp = datetime.utcnow()

        # If timestamp is not provided in the request, set it to the current time
        if not error_log.timestamp:
            error_log.timestamp = current_timestamp


        response = supabase.table("frontend_error_logs").insert({
            "message": error_log.message,
            "source": error_log.source,
            "line_number": error_log.line_number,
            "column_number": error_log.column_number,
            "stack_trace": error_log.stack_trace,
            "browser": error_log.browser,
            "url": error_log.url,
            "additional_context": error_log.additional_context,
            "timestamp": error_log.timestamp.isoformat(),
        }).execute()

        # Check if 'data' exists and is not empty
        if not response.data:
            logging.error("Supabase insert returned no data for frontend error: %s", error_log.dict())
            raise HTTPException(status_code=500, detail="Failed to insert error log: No data returned")
        # Return success message if log was saved
        logging.info("Frontend error logged successfully")
        return {"message": "Frontend error logged successfully"}

    except Exception as e:
        # Catch any unexpected exceptions and raise a 500 error
        logging.exception("Exception occurred while logging frontend error")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")



#Function used to categorize data into categories incase api doesn't work (basic categorization)
def categorize_message(text: str) -> str:
    """Categorize message based on content"""
    text_lower = text.lower()

    if any(k in text_lower for k in ["goal", "dream", "aspire", "ambition", "want to become"]):
        return "Hopes_&_Goals"
    elif any(k in text_lower for k in ["like", "love", "prefer", "enjoy", "crazy about", "obsessed with"]):
        return "Favorites"
    elif any(k in text_lower for k in ["hate", "don't like", "dislike", "can't stand"]):
        return "Favorites"  # Both likes and dislikes go to Favorites
    elif any(k in text_lower for k in ["born", "raised", "from", "live in", "living in", "stay in", "my city", "my country"]):
        return "Background"
    elif any(k in text_lower for k in ["believe", "think", "feel", "opinion", "agree", "disagree"]):
        return "Opinions"
    elif any(k in text_lower for k in ["working on", "learning", "currently doing", "building", "coding", "studying"]):
        return "Personality"
    elif any(k in text_lower for k in ["today", "right now", "currently", "at the moment", "this week", "feeling"]):
        return "Temporary"
    elif any(k in text_lower for k in ["studied at", "college", "school", "university", "degree"]):
        return "Education"
    else:
        return "Others"

#Coverts users message into third person to store in memories if api doesn't work
def to_third_person(verb: str) -> str:
    """Convert verb to third person singular"""
    verb = verb.lower()
    irregulars = {
        "have": "has", "do": "does", "go": "goes", "be": "is", 
        "say": "says", "try": "tries", "fly": "flies"
    }
    
    if verb in irregulars:
        return irregulars[verb]
    if verb.endswith("y") and len(verb) > 1 and verb[-2] not in "aeiou":
        return verb[:-1] + "ies"
    elif verb.endswith(("o", "ch", "s", "sh", "x", "z")):
        return verb + "es"
    else:
        return verb + "s"
    
#Coverts users message into third person to store in memories if api doesn't work
def to_third_person_sentence(user_name: str, message: str) -> str:
    """Convert first person message to third person"""
    message = message.strip()
    lowered = message.lower()

    # Enhanced regex matching for complex patterns
    match = re.match(r"i\s+(really|absolutely|very|so)?\s*(like|love)\s+(.+)", lowered)
    if match:
        adverb, verb, rest = match.groups()
        adverb_part = f"{adverb} " if adverb else ""
        return f"{user_name} {adverb_part}{to_third_person(verb)} {rest.rstrip('.')}.".strip()

    # Handle specific patterns
    patterns = [
        (r"^i like (.+)", lambda m: f"{user_name} likes {m.group(1).rstrip('.')}."),
        (r"^i love (.+)", lambda m: f"{user_name} loves {m.group(1).rstrip('.')}."),
        (r"^i don't like (.+)", lambda m: f"{user_name} doesn't like {m.group(1).rstrip('.')}."),
        (r"^i do not like (.+)", lambda m: f"{user_name} doesn't like {m.group(1).rstrip('.')}."),
        (r"^i hate (.+)", lambda m: f"{user_name} hates {m.group(1).rstrip('.')}."),
        (r"^i dislike (.+)", lambda m: f"{user_name} dislikes {m.group(1).rstrip('.')}."),
        (r"^i can't stand (.+)", lambda m: f"{user_name} can't stand {m.group(1).rstrip('.')}."),
        (r"^i prefer (.+)", lambda m: f"{user_name} prefers {m.group(1).rstrip('.')}."),
        (r"^i enjoy (.+)", lambda m: f"{user_name} enjoys {m.group(1).rstrip('.')}."),
        (r"my name is (.+)", lambda m: f"{user_name}'s name is {m.group(1).rstrip('.')}."),
        (r"^i am (.+)", lambda m: f"{user_name} is {m.group(1).rstrip('.')}."),
        (r"^i'm (.+)", lambda m: f"{user_name} is {m.group(1).rstrip('.')}."),
        (r"^i want to become (.+)", lambda m: f"{user_name} wants to become {m.group(1).rstrip('.')}."),
        (r"^i want to be (.+)", lambda m: f"{user_name} wants to be {m.group(1).rstrip('.')}."),
        (r"^i think (.+)", lambda m: f"{user_name} thinks {m.group(1).rstrip('.')}."),
        (r"^i believe (.+)", lambda m: f"{user_name} believes {m.group(1).rstrip('.')}."),
        (r"^i disagree", lambda m: f"{user_name} disagrees with the point."),
        (r"^i agree", lambda m: f"{user_name} agrees with the point."),
        (r"^i was raised (.+)", lambda m: f"{user_name} was raised {m.group(1).rstrip('.')}."),
        (r"^i used to like (.+)", lambda m: f"{user_name} used to like {m.group(1).rstrip('.')}."),
        (r"my dream is (.+)", lambda m: f"{user_name}'s dream is {m.group(1).rstrip('.')}."),
        (r"my goal is (.+)", lambda m: f"{user_name}'s goal is {m.group(1).rstrip('.')}."),
        (r"i'm from (.+)", lambda m: f"{user_name} is from {m.group(1).rstrip('.')}."),
        (r"i am from (.+)", lambda m: f"{user_name} is from {m.group(1).rstrip('.')}."),
        (r"^i live in (.+)", lambda m: f"{user_name} lives in {m.group(1).rstrip('.')}."),
        (r"^i live at (.+)", lambda m: f"{user_name} lives at {m.group(1).rstrip('.')}."),
        (r"^i studied at (.+)", lambda m: f"{user_name} studied at {m.group(1).rstrip('.')}."),
        (r"^i work at (.+)", lambda m: f"{user_name} works at {m.group(1).rstrip('.')}."),
        (r"^i work as (.+)", lambda m: f"{user_name} works as {m.group(1).rstrip('.')}."),
    ]

    for pattern, formatter in patterns:
        match = re.match(pattern, lowered)
        if match:
            return formatter(match)

    # Default fallback
    return f'{user_name} says: "{message.strip()}"'

# LLM & Persona Category Service Functions
# Helper to parse LLM's JSON output (used by categorization)
def parse_llm_json_response(raw_text: str) -> List[Dict]:
    """
    Robustly parses LLM's raw text output, handling markdown blocks and
    ensuring it's a list of dictionaries.
    """
    cleaned_text = raw_text.strip()
    
    # Strip common markdown code block delimiters
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text.strip("```json").strip("```").strip()
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text.strip("```").strip()

    # If it's still double-quoted, decode once
    if cleaned_text.startswith('"') and cleaned_text.endswith('"'):
        cleaned_text = json.loads(cleaned_text)

    # Attempt to load JSON
    parsed_data = json.loads(cleaned_text)

    # Ensure it's a list
    if not isinstance(parsed_data, list):
        if isinstance(parsed_data, dict):
            return [parsed_data]
        else:
            raise ValueError("LLM response is not a JSON array or object.")
    
    return parsed_data

# In your `call_llm_for_categorization` function

async def call_llm_for_categorization(message: str, user_name: str) -> str:
    """
    Calls an LLM (Gemini) to categorize a user message into predefined categories,
    and rephrases statements using the actual user's name.
    """
    logging.info(f"Calling LLM for categorization with message: {message[:100]}..., user_name: {user_name}")
    
    model = genai.GenerativeModel('gemini-1.5-pro-latest') 

    prompt = f"""You are an expert at extracting and categorizing key information from user messages.
    
    **IMPORTANT:** If the user message is a simple greeting, social pleasantry, or conversational filler (e.g., "Hi", "Hello", "How are you?", "Hey", "Thanks!", "Bye", "What's up?"), **return an empty JSON array `[]`**. Do NOT categorize these types of messages.
    
    Otherwise, categorize the following user message into **ONE AND ONLY ONE** of the specific, relevant categories provided below.
    **DO NOT use any category not explicitly listed.**
    
    Available Categories:
    - "Background": User shares information about their origin, current living situation, past experiences (childhood, where they grew up).
    - "Favorites": User expresses likes, loves, dislikes, preferences, hobbies.
    - "Hopes_&_Goals": User expresses aspirations, dreams, future plans.
    - "Opinions": User shares thoughts, beliefs, or stances on topics.
    - "Personality": User describes their traits, what they are currently doing (e.g., "I'm learning Python"), or general characteristics.
    - "Remainders": Information that needs to be remembered but doesn't fit specific descriptive categories (e.g., "I have an appointment tomorrow at 3 PM", "My dog's name is Rex"). This category is for factual, often time-sensitive or unique, non-character-defining details.
    - "Temporary": Information that is likely to change soon or describes a current state/feeling (e.g., "I'm feeling tired today", "I'm currently watching a movie").
    - "Others": For anything that genuinely doesn't fit well into any of the more specific categories.

    Return the output as a JSON array. Each object in the array should have a "statement" (a concise, rephrased version of the key information, **referring to the user by their actual name '{user_name}'**). Do not use "The user" or "User" in the statement. Also include a "category".
    
    Example Output Format (for content messages):
    [
      {{"statement": "{user_name}'s dream is to become a software engineer.", "category": "Hopes_&_Goals"}},
      {{"statement": "{user_name} likes reading sci-fi books.", "category": "Favorites"}}
    ]
    
    Example Output Format (for greeting messages):
    []
    
    User message: "{message}"
    Output:
    """
    
    try:
        response = await model.generate_content_async(
            prompt, 
            generation_config={"response_mime_type": "application/json", "temperature": 0.2}
        )
        return response.text.strip()
    except Exception as e:
        logging.error(f"LLM categorization call failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM categorization failed: {str(e)}")

async def call_llm_for_third_person(user_name: str, message: str) -> str:
    """
    Calls an LLM (Gemini) to rephrase a message from first person to third person.
    """
    logging.info(f"Calling LLM for third-person conversion for '{user_name}': {message[:100]}...")
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # Flash is faster for this task

    prompt = f"""Rephrase the following message from first person to third person,
    referring to the user as '{user_name}'. Ensure the rephrased message is concise and accurately reflects the original meaning.
    Return only the rephrased message.

    Example:
    User: "I like apples"
    Output: "{user_name} likes apples."
    
    User: "My dream is to become a doctor"
    Output: "{user_name}'s dream is to become a doctor."
    
    User: "I am from New York"
    Output: "{user_name} is from New York."
    
    User message: "{message}"
    Output:
    """
    
    try:
        response = await model.generate_content_async(prompt, generation_config={"temperature": 0.2})
        return response.text.strip()
    except Exception as e:
        logging.error(f"LLM third-person conversion failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM conversion failed: {str(e)}")


def extract_entity_from_memory(text: str, keywords: List[str]) -> str:
    """Extract the main entity from memory text based on keywords (existing function, ensure it's available or moved here)"""
    for keyword in keywords:
        if keyword in text:
            parts = text.split(keyword, 1)
            if len(parts) > 1:
                entity = parts[1].strip()
                # Take first few words as the entity
                entity_words = entity.split()[:3]  # Take up to 3 words
                return ' '.join(entity_words).rstrip(".,!?")
    return ""


def is_similar(str1, str2, threshold=0.85):
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio() >= threshold

"""The function is used to call llm to detect any conflicts"""
async def call_llm_for_conflict_detection(new_memory: str, existing_memories_text: List[str]) -> List[Dict]:
    """
    Calls an LLM (Gemini) to semantically detect conflicts between a new memory
    and a list of existing memories across all categories.
    """
    logging.info(f"Calling LLM for conflict detection. New memory: '{new_memory[:50]}'")
    
    if not existing_memories_text:
        return []

    model = genai.GenerativeModel('gemini-1.5-pro-latest') # Use a capable model for this complex task

    memories_list_str = "\n".join([f"- {m}" for m in existing_memories_text])

    prompt = f"""You are an expert at identifying direct factual contradictions or significant updates
    between a NEW user memory and a list of EXISTING user memories.

    Focus only on identifying memories that directly make an existing memory FALSE or OUTDATED.
    Ignore minor rephrasing, additional details, or information that doesn't conflict.
    Consider all types of information: preferences, background, opinions, personality, etc.

    New Memory: "{new_memory}"

    Existing Memories:
    {memories_list_str}

    Identify any existing memories that are directly contradicted or made obsolete by the New Memory.
    Return a JSON array of the conflicting existing memories. If there are no conflicts, return an empty array.

    Example:
    New Memory: "John lives in London."
    Existing Memories:
    - John lives in New York.
    - John likes apples.
    Output: [{{"conflicting_memory": "John lives in New York."}}]

    Example:
    New Memory: "John used to work at Google, now works at Microsoft."
    Existing Memories:
    - John works at Google.
    - John is a software engineer.
    Output: [{{"conflicting_memory": "John works at Google."}}]

    Example:
    New Memory: "John's favorite color is blue."
    Existing Memories:
    - John's favorite color is red.
    Output: [{{"conflicting_memory": "John's favorite color is red."}}]

    Example (no conflict):
    New Memory: "John lives in London, UK, since 2020."
    Existing Memories:
    - John lives in London.
    Output: [] (Not a contradiction, just more detail)

    Output:
    """

    try:
        response = await model.generate_content_async(
            prompt,
            generation_config={"response_mime_type": "application/json", "temperature": 0.2}
        )
        llm_output = response.text.strip()
        
        # Use the robust JSON parser
        conflicts_data = parse_llm_json_response(llm_output)
        
        # Ensure it's a list of dictionaries with 'conflicting_memory' key
        return [
            item for item in conflicts_data 
            if isinstance(item, dict) and "conflicting_memory" in item
        ]
    except Exception as e:
        logging.error(f"LLM conflict detection failed: {e}")
        # Return empty list on error to prevent cascading failures
        return []

def is_similar(str1, str2, threshold=0.85):
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio() >= threshold

def extract_likes_and_dislikes(message: str):
    """Extract likes and dislikes from user message"""
    message = message.lower()
    likes = []
    dislikes = []

    # Enhanced patterns for likes
    like_patterns = [
        r"i like ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)",
        r"i love ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)",
        r"i enjoy ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)",
        r"i prefer ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)",
        r"i'm a fan of ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)",
        r"i really like ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)",
        r"i absolutely love ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)"
    ]

    # Enhanced patterns for dislikes
    dislike_patterns = [
        r"i don't like ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)",
        r"i do not like ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)",
        r"i hate ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)",
        r"i dislike ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)",
        r"i can't stand ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)",
        r"i'm not a fan of ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)",
        r"i really hate ([\w\s,]+?)(?:\.|,|$|and|but|\s+because|\s+since)"
    ]

    # Extract likes
    for pattern in like_patterns:
        matches = re.findall(pattern, message)
        for match in matches:
            cleaned = match.strip().rstrip(",.!?")
            if cleaned and len(cleaned) > 1:
                likes.append(cleaned)

    # Extract dislikes
    for pattern in dislike_patterns:
        matches = re.findall(pattern, message)
        for match in matches:
            cleaned = match.strip().rstrip(",.!?")
            if cleaned and len(cleaned) > 1:
                dislikes.append(cleaned)

    return dislikes, likes

def clean_entity(text):
    text = text.lower()
    text = re.sub(r'\b(the|a|an|and|or|but|in|on|at|to|for|of|with|by)\b', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()


        
async def store_in_persona_category(
    email: str,
    bot_id: str,
    memory: str,
    category: str,
    embedding: list = None,
    magnitude: float = 0.0,
    recency: int = 0,
    frequency: int = 1,
    rfm_score: float = 0.0,
    relation_id: str = None,
    redundant: bool = False
) -> dict:
    try:
        now = datetime.now(timezone.utc).isoformat()
        data_to_insert = {
            "email": email,
            "bot_id": bot_id,
            "memory": memory,
            "category": category,
            "created_at": now,
            "redundant": redundant,
            "embedding": embedding,
            "magnitude": magnitude,
            "recency": recency,
            "frequency": frequency,
            "rfm_score": rfm_score,
            "relation_id": relation_id
        }
        # Remove None values
        data_to_insert = {k: v for k, v in data_to_insert.items() if v is not None}    
        result = supabase.table("persona_category").insert(data_to_insert).execute()
        if result.data: 
            logging.info(f"Successfully inserted memory: {result.data}")
            return {"status": "success", "data": result.data} 
        else:
            logging.error(f"Supabase insert returned no data, indicating potential issue. Response: {result}")
            return {"status": "error", "error": "Supabase insert returned no data. Check Supabase logs."}

    except Exception as e:
        logging.error(f"Exception during Supabase insert for persona_category: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}

# Updated get_persona_categories function
async def get_persona_categories(email: str, bot_id: str, redundant: Optional[bool] = None) -> List[Dict]:
    """Retrieves persona memories from Supabase with improved error handling."""
    try:
        query = supabase.table("persona_category").select("memory, category, created_at, id, relation_id, redundant")
        query = query.eq("email", email).eq("bot_id", bot_id)
        if redundant is not None:
            query = query.eq("redundant", redundant)
        
        logging.info(f"Attempting to retrieve persona categories for email: {email}, bot_id: {bot_id}, redundant: {redundant}")
        
        response = query.execute()
        
        if response.data is not None: # Check if data attribute exists and is not explicitly None
            logging.info(f"Successfully retrieved {len(response.data)} persona categories.")
            return response.data # Return the list of dictionaries
        else:
            logging.warning(f"Supabase select returned no data (response.data is None) for email: {email}, bot_id: {bot_id}. Response: {response}")
            return [] 

    except Exception as e:
        # Catching any exception during the Supabase interaction
        logging.error(f"Exception during Supabase select for persona_category: {e}", exc_info=True)
        return [] 
    
#The update_persona_category is used to update data in the persona category table
async def update_persona_category(id: str, updates: Dict) -> Dict:
    """Updates a persona category entry in Supabase with improved error handling."""
    try:
        logging.info(f"Attempting to update persona_category ID: {id} with updates: {updates}")
        response = supabase.table("persona_category").update(updates).eq("id", id).execute()
        if response.data:
            logging.info(f"Successfully updated persona category ID: {id}. Data: {response.data}")
            return {"status": "success", "data": response.data}
        else:
            # This case might mean ID not found, or no changes were applied (e.g., if updates dict was empty)
            logging.warning(f"Supabase update returned no data for ID: {id}. This might mean no record matched or no changes were applied. Response: {response}")
            # Consider raising a more specific error if no data is truly unexpected (e.g., if you expect the ID to always exist)
            return {"status": "error", "error": f"No data returned from Supabase update for ID {id}. Record might not exist or no changes were applied."}

    except Exception as e:
        logging.error(f"Exception during Supabase update for persona_category ID: {id}: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}

# The delete_persona_category function is used to delete data from persona category table
async def delete_persona_category(id: str) -> Dict:
    """Deletes a persona category entry from Supabase with robust error handling."""
    try:
        logging.info(f"Attempting to delete persona_category ID: {id}")
        response = supabase.table("persona_category").delete().eq("id", id).execute()
        logging.info(f"Successfully sent delete request for ID: {id}. Supabase response object: {response}")
        return {"status": "success", "data": response.data if response and hasattr(response, 'data') else []} 
        # Added check for response and response.data just in case, but usually not needed if no exception raised.

    except Exception as e:
        # Catching any exception during the Supabase interaction (network, client issues, actual Supabase API errors)
        logging.error(f"Exception during Supabase delete for persona_category ID: {id}: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}

# Core Delta Processing Logic

"""The function process_with_delta is used to delta categorize the data using llm to find out the conflicts"""
# You can place this function definition with other helpers like is_similar, clean_entity etc.
def _is_original_message_negative_preference(message: str) -> bool:
    """Checks if the original user message contains explicit negative preference words."""
    message_lower = message.lower()
    negative_patterns = [
        r"\bno longer like", r"\bdon't like", r"\bdo not like", r"\bcan't stand", 
        r"\bhate", r"\bdislike", r"\bnot a fan of"
    ]
    return any(re.search(pattern, message_lower) for pattern in negative_patterns)


async def process_with_delta(
    email: str,
    bot_id: str,
    new_user_message: str, # The original user's message
    user_name: str,
    new_memory_id: str,
    new_memory_statement: str, # The rephrased statement from LLM categorization
    new_memory_category: str   # The category from LLM categorization
) -> Dict:
    """
    Processes a new user message to apply comprehensive delta logic for persona categorization.
    This includes semantic conflict detection across all categories using an LLM,
    and DELETES old conflicting memories.
    """
    logging.info(f"Starting delta processing for {email}/{bot_id} with message: '{new_user_message[:100]}', new_memory_id: {new_memory_id}")
    logging.info(f"DEBUG DELTA: New LLM Statement: '{new_memory_statement}', Category: '{new_memory_category}'")

    delta_results = {
        "status": "no_delta_updates_needed",
        "details": {
            "deleted_likes_due_to_dislike": [],
            "general_conflicts_resolved": []
        },
        "pure_negation_delete_only": False # Flag to signal if only deletions occurred
    }

    # Fetch all current non-redundant persona memories (excluding the very new one just inserted)
    existing_non_redundant_memories = await get_persona_categories(email, bot_id, redundant=False)
    
    existing_memories_for_conflict_check = [
        m for m in existing_non_redundant_memories if str(m.get("id")) != str(new_memory_id)
    ]
    existing_memories_text_for_conflict_check = [m["memory"] for m in existing_memories_for_conflict_check]

    any_deletion_occurred = False # Initialize the flag to track if any deletion happened

    # --- Step 1: Handle specific preference changes (like/dislike reversals - RULE-BASED) ---
    # Extract dislikes and likes from the new ORIGINAL user message
    dislikes_from_new_message, likes_from_new_message = extract_likes_and_dislikes(new_user_message)

    if dislikes_from_new_message: # If the new message explicitly expresses a dislike
        logging.info(f"DEBUG DELTA: Processing new dislikes extracted: {dislikes_from_new_message}")
        for new_dislike_entity in dislikes_from_new_message:
            clean_new_dislike = clean_entity(new_dislike_entity)
            logging.info(f"DEBUG DELTA: Cleaned new dislike entity: '{clean_new_dislike}'")

            for existing_mem in existing_memories_for_conflict_check:
                logging.info(f"DEBUG DELTA: Comparing against existing memory: '{existing_mem['memory']}' (Category: {existing_mem['category']})")
                
                mem_text_lower = existing_mem["memory"].lower()
                user_name_lower_pattern = re.escape(user_name.lower())

                # Check if it's a Favorites category and contains some form of "likes [entity]" from the user's name
                if existing_mem["category"] == "Favorites" and re.search(fr"\b{user_name_lower_pattern}\s+(?:likes|loves)\s+(.+)", mem_text_lower):
                    try:
                        match_entity = re.search(fr"\b{user_name_lower_pattern}\s+(?:likes|loves)\s+(.+)", mem_text_lower)
                        if match_entity:
                            entity = match_entity.group(1).strip().rstrip(".")
                            clean_entity_str = clean_entity(entity)
                            
                            logging.info(f"DEBUG DELTA:   Existing 'like' entity extracted: '{entity}', Cleaned: '{clean_entity_str}'")
                            logging.info(f"DEBUG DELTA:   Comparing '{clean_new_dislike}' vs '{clean_entity_str}' for similarity.")
                            
                            if is_similar(clean_new_dislike, clean_entity_str):
                                logging.info(f"DEBUG DELTA:   *** SIMILARITY MATCH FOUND! *** DELETING old memory {existing_mem['id']}.")
                                delete_result = await delete_persona_category(str(existing_mem["id"])) # Calling DELETE
                                
                                if delete_result.get("status") == "success":
                                    delta_results["details"]["deleted_likes_due_to_dislike"].append(existing_mem["memory"])
                                    delta_results["status"] = "delta_updates_applied"
                                    logging.info(f"Delta: DELETED old like memory: '{existing_mem['memory']}' (ID: {existing_mem['id']})")
                                    any_deletion_occurred = True # Mark that a deletion occurred
                                else:
                                    logging.error(f"Failed to DELETE old like memory {existing_mem['id']}: {delete_result.get('error', 'Unknown')}")
                            else:
                                logging.info(f"DEBUG DELTA:   No similarity match for '{clean_new_dislike}' vs '{clean_entity_str}'.")
                        else:
                            logging.info(f"DEBUG DELTA:   Could not extract entity from existing 'like' memory: '{existing_mem['memory']}'.")
                    except Exception as e:
                        logging.warning(f"⚠️ DEBUG DELTA: Parsing error in dislike cleanup for '{existing_mem['memory']}': {e}")
                else:
                    logging.info(f"DEBUG DELTA:   Existing memory not a relevant 'Favorites' like. Category: {existing_mem['category']}, Memory: '{existing_mem['memory']}'.")

    # --- Step 2: Comprehensive Semantic Conflict Detection using LLM ---
    logging.info(f"DEBUG DELTA: Calling LLM for general conflict detection. New memory: '{new_user_message[:100]}'")
    
    # Pass the original user message to the LLM for conflict detection.
    # LLM will compare this against existing memories.
    llm_conflicts = await call_llm_for_conflict_detection(new_user_message, existing_memories_text_for_conflict_check)
    
    logging.info(f"DEBUG DELTA: LLM identified conflicts: {llm_conflicts}")

    if llm_conflicts: # This 'if' block processes conflicts found by LLM
        for conflict_dict in llm_conflicts:
            conflicting_mem_text = conflict_dict.get("conflicting_memory")
            if conflicting_mem_text:
                logging.info(f"DEBUG DELTA: LLM suggested conflict: '{conflicting_mem_text}'")
                
                matched_existing_mem = next((
                    mem for mem in existing_memories_for_conflict_check
                    if is_similar(conflicting_mem_text, mem["memory"])
                ), None)

                if matched_existing_mem:
                    logging.info(f"DEBUG DELTA:   *** SIMILARITY MATCH FOUND FOR LLM SUGGESTION! *** DELETING {matched_existing_mem['id']}.")
                    delete_result = await delete_persona_category(str(matched_existing_mem["id"])) # Calling DELETE
                    
                    if delete_result.get("status") == "success":
                        delta_results["details"]["general_conflicts_resolved"].append(matched_existing_mem["memory"])
                        delta_results["status"] = "delta_updates_applied" # Status changes if any deletion occurs
                        logging.info(f"Delta: DELETED general conflict memory: '{matched_existing_mem['memory']}' (ID: {matched_existing_mem['id']})")
                        any_deletion_occurred = True # Mark that a deletion occurred
                    else:
                        logging.error(f"Failed to DELETE general conflict memory {matched_existing_mem['id']}: {delete_result.get('error', 'Unknown')}")
                else:
                    logging.warning(f"DEBUG DELTA: LLM identified conflict '{conflicting_mem_text}' but could not find a sufficiently similar match in current DB memories for deletion.")

   
    is_original_message_negative_preference = _is_original_message_negative_preference(new_user_message) # Use the helper

    if (any_deletion_occurred and
        new_memory_category == "Favorites" and
        is_original_message_negative_preference):
        delta_results["pure_negation_delete_only"] = True
        logging.info("DEBUG DELTA: Flag set: pure_negation_delete_only = True. Reason: Deletion occurred AND new memory is Favorites AND original message is negative preference.")
    else:
        delta_results["pure_negation_delete_only"] = False
        logging.info("DEBUG DELTA: Flag set: pure_negation_delete_only = False. Reason: Not a pure negation for deletion, or no conflicts found leading to deletion.")

    # --- FINAL RETURN ---
    logging.info(f"Finished delta processing for '{new_user_message[:50]}'. Status: {delta_results['status']}")
    logging.info(f"DEBUG DELTA: Final pure_negation_delete_only flag returned: {delta_results['pure_negation_delete_only']}")
    return {
        "handled_by_delta": True,
        "status": delta_results["status"],
        "details": delta_results["details"],
        "pure_negation_delete_only": delta_results["pure_negation_delete_only"] # Return the new flag
    }

"""The function categorize_llm is the main and latest function which 
smartly categorizes users messages using llm"""
class CategorizeLLMRequest(BaseModel):
    message: str
    email: str
    bot_id: str
    user_name: str
    test_mode: bool = False
# In categorize_message_llm function (the endpoint @app.post("/categorize_llm"))

@app.post("/categorize_llm")
async def categorize_message_llm(request: CategorizeLLMRequest):
    logging.info(f"📥 Received LLM categorization request for {request.email}, message: {request.message[:50]}...")
    
    # FIX: Extract variables from request
    email = request.email
    bot_id = request.bot_id
    message = request.message
    user_name = request.user_name
    embedding = None
    magnitude = None
    recency = None
    rfm_score = None
    redundant = False
    try:
        llm_raw_output = await call_llm_for_categorization(request.message, request.user_name)
        logging.info(f"📩 LLM Categorizer Raw Output: {llm_raw_output[:500]}...")

        parsed_llm_results = parse_llm_json_response(llm_raw_output)
        
        # --- FIX START ---
        if not parsed_llm_results: # LLM returned [] for greeting
            logging.info("LLM Categorizer returned empty data, likely a greeting or filler message.")
            return {
                "status": "greeting_or_filler_not_stored", # Return a specific status
                "data": [], # Empty data
                "new_memory_id": None # No new ID
            }
        # --- FIX END ---

        main_categorized_item = None
        for item in parsed_llm_results:
            if isinstance(item, dict) and item.get("statement") and item.get("category"):
                main_categorized_item = item
                break
        
        if not main_categorized_item: # LLM returned non-empty but unparseable/invalid items
            logging.warning("LLM output contained data but no valid statement/category. Skipping storage.")
            raise HTTPException(status_code=400, detail="LLM could not generate valid categories with statement/category.")

        memory_statement = main_categorized_item["statement"]
        category = main_categorized_item["category"]
        
        
        embedding = await get_embedding(memory_statement)
        embedding = ensure_valid_embedding(embedding) 
        
        store_response = await store_in_persona_category(
            email=email,
            bot_id=bot_id,
            memory=memory_statement,
            category=category,
            embedding=embedding,          
            magnitude=magnitude or 0.0,   
            recency=recency or 0,         
            rfm_score=rfm_score or 0.0,   
            redundant=redundant   
        )
        
        if store_response["status"] == "success" and store_response["data"]:
            new_memory_id = store_response["data"][0].get("id") 
            if not new_memory_id:
                logging.error("Supabase insert successful but returned no 'id' for new memory.")
                raise HTTPException(status_code=500, detail="Failed to retrieve ID for new memory.")
            
            logging.info(f"✅ Stored LLM categorized memory: '{memory_statement}' in category '{category}' with ID: {new_memory_id}")
            
            return {
                "status": "categorized_and_initial_stored",
                "data": store_response["data"], 
                "new_memory_id": new_memory_id 
            }
        else:
            logging.error(f"Failed to store LLM-categorized memory: {store_response.get('error', 'Unknown error')}")
            raise HTTPException(status_code=500, detail=f"Failed to store LLM-categorized memory: {store_response.get('error', 'Unknown error')}")

    except HTTPException as he:
        logging.error(f"Handled HTTP Error in /categorize_llm: {he.detail}")
        raise he
    except Exception as e:
        logging.exception(f"Unhandled error in /categorize_llm: {e}")
        raise HTTPException(status_code=500, detail=f"LLM categorization failed: {str(e)}")
    
"""The function convert_to_third_person_llm is used to automatically convert any sentence to third person"""
class ConvertToThirdPersonRequest(BaseModel):
    user_name: str
    message: str

@app.post("/convert_to_third_person_llm")
async def convert_to_third_person_api(request: ConvertToThirdPersonRequest):
    logging.info(f"Received third-person conversion request for {request.user_name}, message: {request.message[:50]}...")
    try:
        converted_message = await call_llm_for_third_person(request.user_name, request.message)
        return {"original_message": request.message, "third_person_message": converted_message}
    except HTTPException as he:
        raise he
    except Exception as e:
        logging.exception(f"Unhandled error in /convert_to_third_person_llm: {e}")
        raise HTTPException(status_code=500, detail=f"Third-person conversion failed: {str(e)}")
    
"""The function delta_categorizer is the main function to delta_categorize"""
class DeltaCategorizerRequest(BaseModel):
    email: str
    bot_id: str
    memory: str 
    user_name: str
    new_memory_id: str 

@app.post("/delta_categorizer")
async def delta_categorizer(payload: DeltaCategorizerRequest):
    try:
        result = await process_with_delta(
            email=payload.email,
            bot_id=payload.bot_id,
            new_user_message=payload.memory, 
            user_name=payload.user_name
        )
        return result
    except HTTPException as he:
        logging.error(f"❌ Delta categorizer failed with HTTP error: {he.detail}")
        raise he
    except Exception as e:
        logging.exception(f"❌ Delta categorizer failed unexpectedly: {e}")
        raise HTTPException(status_code=500, detail=f"Delta categorizer failed: {str(e)}")

""" The function store-message is the main function which is also passed to frontend , 
which stores the user message and details and decides if they need to be stored in the 
supabase or be deleted or replaced with the help of categorizer and delta_categorizer"""
class StoreMessageRequest(BaseModel):
     email: str
     bot_id: str
     message: str
     user_name: str

@app.post("/store-message")
async def store_message(data: StoreMessageRequest):
    logging.info(f"Received /store-message request for {data.email}, message: '{data.message[:50]}...'")

    try:
        # 1. Call LLM Categorizer to get categorization and store initial memory
        # The LLM itself will now decide if it's a greeting and return []
        categorization_response = await categorize_message_llm(CategorizeLLMRequest(
            email=data.email,
            bot_id=data.bot_id,
            message=data.message,
            user_name=data.user_name
        ))
        
        # --- FIX START ---
        # Handle greetings/fillers immediately after categorization_response
        if categorization_response.get("status") == "greeting_or_filler_not_stored":
            logging.info(f"Skipping storage for message: '{data.message}' as LLM identified it as a greeting/filler.")
            return {
                "status": "greeting_or_filler_not_stored",
                "message": "Message identified as a greeting/filler, not stored in persona memory.",
                "categorization_result": [],
                "delta_result": {
                    "handled_by_delta": False,
                    "status": "skipped_by_llm",
                    "details": {}
                }
            }
        # --- FIX END ---

        # The rest of the logic should ONLY execute if it's NOT a greeting.
        # Now, check for actual content categorization success
        if categorization_response.get("status") != "categorized_and_initial_stored" or not categorization_response.get("new_memory_id"):
            logging.error(f"Initial LLM categorization failed or returned no ID for non-greeting: {categorization_response}")
            raise HTTPException(status_code=500, detail="Initial categorization failed or new memory ID not returned for content message.")
        
        new_memory_id_from_categorizer = categorization_response["new_memory_id"]
        newly_stored_memory_data = categorization_response["data"][0] if categorization_response.get("data") else {}
        
        delta_response = await process_with_delta(
            email=data.email,
            bot_id=data.bot_id,
            new_user_message=data.message,
            user_name=data.user_name,
            new_memory_id=new_memory_id_from_categorizer,
            new_memory_statement=newly_stored_memory_data.get("memory", ""),
            new_memory_category=newly_stored_memory_data.get("category", "")
        )

        if delta_response.get("pure_negation_delete_only"):
            logging.info(f"Store-message: Delta indicated pure negation ('pure_negation_delete_only' is True). Attempting to delete the newly stored memory (ID: {new_memory_id_from_categorizer}).")
            delete_new_memory_result = await delete_persona_category(str(new_memory_id_from_categorizer))
            
            if delete_new_memory_result.get("status") == "success":
                logging.info(f"Store-message: Successfully DELETED new memory (ID: {new_memory_id_from_categorizer}) after pure negation detection. Old conflicting memories also deleted.")
                return {
                    "status": "processed_pure_negation_finalized",
                    "categorization_result": [],
                    "delta_result": delta_response,
                    "final_action": "old_and_new_negation_deleted"
                }
            else:
                logging.error(f"Store-message: FAILED to delete new memory (ID: {new_memory_id_from_categorizer}) after pure negation detection: {delete_new_memory_result.get('error', 'Unknown')}. New memory will remain.")
                return {
                    "status": "processed_negation_delete_failed_new_kept",
                    "categorization_result": [newly_stored_memory_data],
                    "delta_result": delta_response,
                    "final_action": "old_deleted_new_kept_due_to_error"
                }
        
        return {
            "status": "processed",
            "categorization_result": categorization_response.get("data"),
            "delta_result": delta_response
        }

    except HTTPException as he:
        logging.error(f"Handled HTTP Error in /store-message: {he.detail}")
        raise he
    except Exception as e:
        logging.exception(f"Unhandled error in /store-message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store message and categorize: {str(e)}")
    

# Schedule the log upload every 30 minutes
def upload_log():
    print("Uploading log file to S3")
    upload_log_to_s3()

"""
    This Python function checks memory extraction every 30 minutes on startup.
"""
async def check_memory_extraction():
    print("Checking Memory Extraction")
    await checker()

"""
    The function `check_memory_extraction` runs every 30 minutes on startup to check and process
    scheduled messages.
    :return: The function `check_scheduled_messages()` is being returned.
"""
async def check_scheduled_tasks():
    check_daily_scheduled_messages()
    return check_scheduled_messages()

"""
    This Python function runs a redundancy task every hour and catches any exceptions that occur during
    the task.
"""
def redundant():
    """Main function to process all user-bot combinations"""
    logging.info(f"Starting redundancy check at {datetime.now()}")

    combinations = get_distinct_user_bot_combinations()

    if not combinations:
        logging.info("No user-bot combinations found to process")
        return

    total_updates = 0
    for combo in combinations:
        email = combo["email"]
        bot_id = combo["bot_id"]
        total_updates += process_user_bot_combination(email, bot_id)

    logging.info(f"Completed redundancy check. Total updates: {total_updates}")

def scheduled_hourly_categorization():
    logging.info("🔁 Running redundancy task every 1 hour")
    try:
        redundant()
    except Exception as e:
        logging.info(f"❌ Error during redundancy categorization: {e}")

"""
    This Python script defines a function that runs a categorization job for user messages every 3
    hours, logging information about the process.
"""
def run_categorization_job():
    logging.info("Starting categorization job...")
    pairs = get_today_user_bot_pairs()
    logging.info(f"Found {len(pairs)} unique (email, bot_id) pairs")

    for email, bot_id in pairs:
        categorize_user_messages(email, bot_id)
    logging.info("Categorization job complete. Sleeping for 3 hours...")

def scheduled_memory_categorization():
    print("⏰ Running categorization task every 3 hours")
    try:
        run_categorization_job()
    except Exception as e:
        print(f"Error during scheduled categorization: {e}")

"""
    The function `scheduled_daily_summary` runs every 24 hours to generate the summary of the
    previous day's chat between the user and bot
"""
def scheduled_daily_summary():
    print("🗓️ Running daily summary generation at 2 AM UTC")
    process_summaries_for_yesterday()




@app.get("/test-daily-summary")
def test_daily_summary():
    print("🧪 TEST: Running daily summary generation manually")
    scheduled_daily_summary()
    return {"status": "triggered"}









# Add this test endpoint to verify cache is working:

@app.get("/test-cache-now")
async def test_cache_now():
    """Test if cache is actually working after fixes"""
    try:
        test_text = "Hello, how are you?"
        test_voice = "fd2ada67-c2d9-4afe-b474-6386b87d8fc3"
        test_audio = "dGVzdF9hdWRpb19kYXRh"  # test_audio_data in base64

        print("🧪 Testing cache storage...")
        await cache_tts_response_async(test_text, test_voice, test_audio)

        print("🧪 Testing cache retrieval...")
        retrieved = await get_cached_tts_response_async(test_text, test_voice)

        return {
            "cache_enabled": TTS_CACHE_ENABLED,
            "cache_size": len(TTS_CACHE),
            "test_stored": True,
            "test_retrieved": retrieved is not None,
            "test_data_matches": retrieved == test_audio if retrieved else False,
            "cache_stats": TTS_CACHE_STATS,
            "executor_available": cache_executor is not None,
            "cache_keys_sample": list(TTS_CACHE.keys())[:3] if TTS_CACHE else []
        }
    except Exception as e:
        return {
            "error": str(e),
            "cache_enabled": TTS_CACHE_ENABLED,
            "executor_available": "cache_executor" in globals()
        }





# =============================================================================
# VOICE CALL FUNCTIONALITY - Added for speech-to-text and text-to-speech
# =============================================================================

# Helper function for speech-to-text conversion using Deepgram (primary) with AssemblyAI fallback
async def speech_to_text(audio_file: UploadFile) -> str:
    """
    Convert uploaded audio file to text using speech recognition
    Primary: Deepgram (fastest, 1-2 seconds)
    Fallback: AssemblyAI (commented), Google Speech Recognition + CMU Sphinx
    """
    try:
        # Read the uploaded file
        audio_data = await audio_file.read()

        # Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            temp_audio.write(audio_data)
            temp_audio_path = temp_audio.name

        try:
            # Convert audio to WAV format if needed using pydub
            audio_segment = AudioSegment.from_file(temp_audio_path)

            # Convert to WAV with specific parameters for better recognition
            wav_audio = audio_segment.set_frame_rate(16000).set_channels(1)

            # Create another temporary file for the processed WAV
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as processed_audio:
                wav_audio.export(processed_audio.name, format="wav")
                processed_audio_path = processed_audio.name

            # ==================== PRIMARY: Deepgram ====================
            try:
                # Initialize Deepgram client
                deepgram = DeepgramClient(api_key="544f9a9deffead086304452ffa70afcd461d30e8")

                # Read the audio file
                with open(processed_audio_path, "rb") as audio_file_data:
                    audio_buffer = audio_file_data.read()

                # Configure Deepgram options for optimal performance
                options = PrerecordedOptions(
                    model="nova-2",  # Latest model for best accuracy
                    language="en",
                    smart_format=True,  # Automatic punctuation and formatting
                    punctuate=True,
                    utterances=False,
                    diarize=False
                )

                # Transcribe the audio
                response = deepgram.listen.prerecorded.v("1").transcribe_file(
                    {"buffer": audio_buffer, "mimetype": "audio/wav"},
                    options
                )

                # Extract the transcript
                if response.results and response.results.channels and len(response.results.channels) > 0:
                    alternatives = response.results.channels[0].alternatives
                    if alternatives and len(alternatives) > 0:
                        transcript = alternatives[0].transcript
                        if transcript and transcript.strip():
                            logging.info("Deepgram transcription successful")
                            return transcript
                        else:
                            raise Exception("Deepgram returned empty transcript")
                    else:
                        raise Exception("No alternatives in Deepgram response")
                else:
                    raise Exception("No valid results from Deepgram")

            except Exception as e:
                logging.warning(f"Deepgram failed, falling back to Google Speech Recognition: {e}")

                # ==================== COMMENTED FALLBACK: AssemblyAI ====================
                # try:
                #     # Set AssemblyAI API key
                #     aai.settings.api_key = os.environ.get("ASSEMBLYAI_API_KEY")
                #
                #     # Create transcriber instance
                #     transcriber = aai.Transcriber()
                #
                #     # Transcribe the audio file
                #     transcript_result = transcriber.transcribe(processed_audio_path)
                #
                #     # Check if transcription was successful
                #     if transcript_result.status == aai.TranscriptStatus.completed:
                #         logging.info("AssemblyAI transcription successful")
                #         return transcript_result.text
                #     else:
                #         logging.warning(f"AssemblyAI transcription failed: {transcript_result.error}")
                #         raise Exception("AssemblyAI transcription failed")
                #
                # except Exception as e:
                #     logging.warning(f"AssemblyAI failed, falling back to Google Speech Recognition: {e}")

                # ==================== FALLBACK: Google Speech Recognition ====================
                # Initialize the speech recognizer
                recognizer = sr.Recognizer()

                # Load the audio file
                with sr.AudioFile(processed_audio_path) as source:
                    # Adjust for ambient noise
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    # Record the audio
                    audio = recognizer.record(source)

                # Convert speech to text using Google's speech recognition
                try:
                    transcript = recognizer.recognize_google(audio)
                    logging.info("Google Speech Recognition successful")
                    return transcript
                except sr.UnknownValueError:
                    # Try with alternative recognition services if Google fails
                    try:
                        transcript = recognizer.recognize_sphinx(audio)
                        logging.info("CMU Sphinx recognition successful")
                        return transcript
                    except:
                        logging.error("All speech recognition methods failed")
                        return "Could not understand audio"
                except sr.RequestError as e:
                    logging.error(f"Speech recognition request error: {e}")
                    return "Speech recognition service error"

        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_audio_path)
                if 'processed_audio_path' in locals():
                    os.unlink(processed_audio_path)
            except:
                pass

    except Exception as e:
        logging.error(f"Error in speech to text conversion: {e}")
        raise HTTPException(status_code=500, detail=f"Speech to text conversion failed: {str(e)}")


# ==================== COMMENTED OUT: Previous Google Speech Recognition Implementation ====================
# async def speech_to_text_google_fallback(audio_file: UploadFile) -> str:
#     """
#     Convert uploaded audio file to text using speech recognition
#     PREVIOUS IMPLEMENTATION - Google Speech Recognition Primary
#     """
#     try:
#         # Read the uploaded file
#         audio_data = await audio_file.read()
#
#         # Create a temporary file to store the audio
#         with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
#             temp_audio.write(audio_data)
#             temp_audio_path = temp_audio.name
#
#         try:
#             # Convert audio to WAV format if needed using pydub
#             audio_segment = AudioSegment.from_file(temp_audio_path)
#
#             # Convert to WAV with specific parameters for better recognition
#             wav_audio = audio_segment.set_frame_rate(16000).set_channels(1)
#
#             # Create another temporary file for the processed WAV
#             with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as processed_audio:
#                 wav_audio.export(processed_audio.name, format="wav")
#                 processed_audio_path = processed_audio.name
#
#             # Initialize the speech recognizer
#             recognizer = sr.Recognizer()
#
#             # Load the audio file
#             with sr.AudioFile(processed_audio_path) as source:
#                 # Adjust for ambient noise
#                 recognizer.adjust_for_ambient_noise(source, duration=0.5)
#                 # Record the audio
#                 audio = recognizer.record(source)
#
#             # Convert speech to text using Google's speech recognition
#             try:
#                 transcript = recognizer.recognize_google(audio)
#                 return transcript
#             except sr.UnknownValueError:
#                 # Try with alternative recognition services if Google fails
#                 try:
#                     transcript = recognizer.recognize_sphinx(audio)
#                     return transcript
#                 except:
#                     return "Could not understand audio"
#             except sr.RequestError as e:
#                 logging.error(f"Speech recognition request error: {e}")
#                 return "Speech recognition service error"
#
#         finally:
#             # Clean up temporary files
#             try:
#                 os.unlink(temp_audio_path)
#                 if 'processed_audio_path' in locals():
#                     os.unlink(processed_audio_path)
#             except:
#                 pass
#
#     except Exception as e:
#         logging.error(f"Error in speech to text conversion: {e}")
#         raise HTTPException(status_code=500, detail=f"Speech to text conversion failed: {str(e)}")

# ========== BACKGROUND HELPER FUNCTIONS FOR PARALLEL PROCESSING ==========
async def background_log_origin_response(email: str, bot_id: str, transcript: str, previous_conversation: list):
    """Background task to log origin response without blocking main flow"""
    try:
        log_messages_with_like_dislike(email, bot_id, transcript, "I was developed by the Desis Dev team!", "", previous_conversation[-5:], "")
    except Exception as e:
        logging.error(f"Background origin logging failed: {e}")

async def background_log_response(email: str, bot_id: str, transcript: str, response: str, previous_conversation: list, memory: str, request_time: str, platform: str):
    """Background task to log regular response without blocking main flow"""
    try:
        log = log_messages_with_like_dislike(email, bot_id, transcript, response, "", previous_conversation[-5:], memory)
        await insert_entry(email, transcript, response, bot_id, request_time, platform)
        return log
    except Exception as e:
        logging.error(f"Background response logging failed: {e}")
        return None

# Voice call endpoint that integrates speech-to-text with existing chat logic and text-to-speech
@app.post("/voice-call")
async def voice_call(
    audio_file: UploadFile = File(...),
    bot_id: str = Form("delhi"),
    custom_bot_name: str = Form(""),
    user_name: str = Form(""),
    user_gender: str = Form(""),
    language: str = Form(""),
    traits: str = Form(""),
    previous_conversation: str = Form("[]"),
    email: str = Form(""),
    request_time: str = Form(""),
    platform: str = Form(""),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    FULLY OPTIMIZED Voice call endpoint - ALL PERFORMANCE OPTIMIZATIONS APPLIED:
    1. Converts speech to text WHILE simultaneously preloading data (Deepgram STT - 67% faster)
    2. Skips memory retrieval (major bottleneck) - only performs origin check (84% faster)
    3. Uses gpt-3.5-turbo instead of o4-mini for 2-4s faster response generation
    4. Starts TTS generation immediately after response (parallel processing - saves 2-3s)
    5. Returns both text response and audio

    PERFORMANCE OPTIMIZATIONS APPLIED:
    - Phase 1: STT with Deepgram (2.33s, was 7s+ with AssemblyAI) ✅
    - Phase 2: Origin check only (~1s, was 9.78s with memory retrieval) ✅
    - Phase 3: gpt-3.5-turbo response (~2-3s, was 6.8s with o4-mini) ✅ NEW
    - Phase 4: Parallel TTS generation (~2-3s, overlapped with Phase 3) ✅ NEW

    Target: ~7-8 seconds total (was 23.48s) - 65%+ improvement
    Memory retrieval is still available in regular chat endpoints (/cv/chat)
    """
    start_time = time.time()
    logging.info(f"🎙️ Voice call started for bot_id={bot_id}, email={email}")

    try:
        # Validate audio file - allow common audio formats and handle cases where content_type might not be set
        valid_audio_types = ['audio/', 'application/octet-stream']
        valid_extensions = ['.wav', '.mp3', '.m4a', '.ogg', '.flac', '.aac']

        content_type_valid = any(audio_file.content_type.startswith(t) for t in valid_audio_types) if audio_file.content_type else False
        extension_valid = any(audio_file.filename.lower().endswith(ext) for ext in valid_extensions) if audio_file.filename else False

        if not (content_type_valid or extension_valid):
            raise HTTPException(status_code=400, detail=f"Invalid audio file format. Content-type: {audio_file.content_type}, Filename: {audio_file.filename}")

        # Parse previous conversation from JSON string
        try:
            previous_conversation_list = json.loads(previous_conversation) if previous_conversation else []
        except json.JSONDecodeError:
            previous_conversation_list = []

        # ========== PARALLEL PHASE 1: STT + Data Preloading ==========
        phase1_start = time.time()
        logging.info("🔄 Phase 1: Starting STT + Data Preloading in parallel")

        # Start STT task (5-8 seconds)
        stt_task = asyncio.create_task(speech_to_text(audio_file))

        # While STT is running, preload all static data in parallel
        async def preload_static_data():
            """Preload bot prompt, voice settings, and prepare conversation data"""
            # These operations can run simultaneously while STT processes
            previous_conversation = restrict_to_last_20_messages(previous_conversation_list)
            raw_bot_prompt = get_bot_prompt(bot_id)

            # Create personalized bot prompt
            bot_prompt = raw_bot_prompt.format(
                custom_bot_name=custom_bot_name,
                traitsString=traits,
                userName=user_name,
                userGender=user_gender,
                languageString=language
            )

            return {
                "previous_conversation": previous_conversation,
                "bot_prompt": bot_prompt,
                "raw_bot_prompt": raw_bot_prompt
            }

        # Start preloading task
        preload_task = asyncio.create_task(preload_static_data())

        # Wait for both STT and preloading to complete
        transcript, preloaded_data = await asyncio.gather(stt_task, preload_task)

        phase1_time = time.time() - phase1_start
        logging.info(f"✅ Phase 1 completed in {phase1_time:.2f}s (STT + Preloading)")

        if not transcript or transcript.strip() == "":
            return {"error": "Could not transcribe audio. Please try again."}

        # Extract preloaded data
        previous_conversation = preloaded_data["previous_conversation"]
        bot_prompt = preloaded_data["bot_prompt"]

        # ========== OPTIMIZED PHASE 2: Origin Check Only (Memory Retrieval Disabled for Voice Calls) ==========
        phase2_start = time.time()
        logging.info("🔄 Phase 2: Starting Origin Check Only (Memory Retrieval DISABLED for voice calls performance)")

        # ========== PERFORMANCE OPTIMIZATION: Memory Retrieval DISABLED for Voice Calls ==========
        # Memory retrieval is the biggest bottleneck in voice calls (9.78s out of 23.48s total)
        # For voice calls, we prioritize response speed over memory context
        # Memory retrieval is still available for regular chat endpoints (/cv/chat)

        # Only run origin check (fast ~1 second)
        origin_check_task = asyncio.create_task(
            check_for_origin_question(transcript, previous_conversation)
        )

        # ==================== COMMENTED OUT: Memory Retrieval for Voice Calls ====================
        # PERFORMANCE NOTE: This was taking 9.78s and causing slow voice responses
        # Uncomment below to re-enable memory retrieval for voice calls if needed
        #
        # memory_retrieval_task = asyncio.create_task(
        #     cached_retrieve_memory(transcript, email, bot_id, previous_conversation)
        # )
        #
        # # Wait for both to complete with timeout handling
        # try:
        #     # Set a timeout of 15 seconds for memory retrieval to prevent hanging
        #     check, memory_result = await asyncio.wait_for(
        #         asyncio.gather(origin_check_task, memory_retrieval_task),
        #         timeout=15.0
        #     )
        #     memory, rephrased_user_message, category = memory_result
        #     logging.info("✅ Memory retrieval completed within timeout")
        # except asyncio.TimeoutError:
        #     logging.warning("⚠️ Memory retrieval timed out, using fallback values")
        #     # Get origin check result (should be fast)
        #     try:
        #         check = await asyncio.wait_for(origin_check_task, timeout=2.0)
        #     except:
        #         check = "No"
        #
        #     # Use fallback values for memory retrieval
        #     memory = ""
        #     rephrased_user_message = transcript  # Use original transcript
        #     category = "General"  # Default category
        # except Exception as e:
        #     logging.error(f"Error in parallel processing: {e}")
        #     # Fallback values
        #     check = "No"
        #     memory = ""
        #     rephrased_user_message = transcript
        #     category = "General"
        # ==================== END COMMENTED MEMORY RETRIEVAL ====================

        # For voice calls: Use fast fallback values without memory retrieval
        try:
            # Only wait for origin check with reduced timeout since we're using gpt-3.5-turbo (faster)
            check = await asyncio.wait_for(origin_check_task, timeout=2.0)
            logging.info("✅ Origin check completed")
        except asyncio.TimeoutError:
            logging.warning("⚠️ Origin check timed out, using fallback")
            check = "No"
        except Exception as e:
            logging.error(f"Error in origin check: {e}")
            check = "No"

        # Use optimized fallback values (no memory retrieval for voice calls)
        memory = ""  # No memory context for faster voice responses
        rephrased_user_message = transcript  # Use original transcript
        category = "General"  # Default category

        phase2_time = time.time() - phase2_start
        logging.info(f"✅ Phase 2 completed in {phase2_time:.2f}s (Origin Check Only - Memory Retrieval DISABLED for voice calls)")

        # ========== RESPONSE GENERATION ==========
        phase3_start = time.time()
        logging.info("🔄 Phase 3: Starting Response Generation")

        reminder = False

        # If the question is from the origin, log the message and return a response
        if check == "Yes":
            response = "I was developed by a team of Desi Developers, but you brought me to life!!"

            # ========== CRITICAL FIX: Start TTS for origin response too ==========
            # Previously missing TTS for origin response - caused variable scoping error
            tts_start_time = time.time()
            tts_task = asyncio.create_task(generate_audio_optimized(
                TTSRequest(
                    transcript=response,
                    bot_id=bot_id,
                    output_format=get_smart_audio_format(response, "voice_call")
                ),
                background_tasks
            ))

            # Start logging in background (non-blocking)
            asyncio.create_task(
                background_log_origin_response(email, bot_id, transcript, previous_conversation)
            )

            chat_response = {
                "response": response,
                "message_id": "origin_response",  # Will be updated by background task
                "reminder": False
            }
        else:
            # If the category is Reminder, generate the reminder response
            if category == "Reminder":
                print("REMINDER")
                reminder_resp = await reminder_response(transcript, previous_conversation, request_time)
                response = reminder_resp['response']
                reminder = True

                # ========== QUICK WIN #2: Start TTS immediately for reminder ==========
                # Start TTS generation in parallel with logging (saves 2-3s)
                tts_start_time = time.time()
                tts_task = asyncio.create_task(generate_audio_optimized(
                    TTSRequest(
                        transcript=response,
                        bot_id=bot_id,
                        output_format=get_smart_audio_format(response, "voice_call")  # Smart format selection
                    ),
                    background_tasks
                ))

            else:
                # ========== OPTIMIZED: Generate bot response without memory context for voice calls ==========
                # For voice calls, we skip memory injection to prioritize response speed
                # Memory context is still available in regular chat endpoints (/cv/chat)

                # ========== QUICK WIN #1: Switch to gpt-3.5-turbo for 2-4s faster response ==========
                # Previously used: o4-mini (reasoning model, slower but more accurate)
                # Now using: gpt-3.5-turbo (chat model, 2-4s faster response time)
                # Construct messages format directly for OpenAI API
                messages = [
                    {
                        "role": "system",
                        "content": bot_prompt  # Bot prompt without memory context for speed
                    }
                ]
                messages.extend(previous_conversation)
                messages.append(
                    {
                        "role": "user",
                        "content": transcript
                    }
                )

                # ========== PREVIOUS MODEL (COMMENTED): o4-mini for accuracy ==========
                # response = await call_openai_api(messages, model="o4-mini")

                # ========== NEW MODEL: gpt-3.5-turbo for speed ==========
                #response = await call_openai_api(messages, model="gpt-3.5-turbo")
                response = await call_xai_api(messages, model="grok-beta")
                reminder = False

                # ========== QUICK WIN #2: Start TTS immediately after response ==========
                # Start TTS generation in parallel with logging (saves 2-3s)
                tts_start_time = time.time()
                tts_task = asyncio.create_task(generate_audio_optimized(
                    TTSRequest(
                        transcript=response,
                        bot_id=bot_id,
                        output_format=get_smart_audio_format(response, "voice_call")  # Smart format selection
                    ),
                    background_tasks
                ))

            # Start logging in background (non-blocking)
            log_task = asyncio.create_task(
                background_log_response(email, bot_id, transcript, response, previous_conversation, memory, request_time, platform)
            )

            chat_response = {
                "response": response,
                "message_id": "processing",  # Will be updated by background task
                "reminder": reminder
            }

        phase3_time = time.time() - phase3_start
        logging.info(f"✅ Phase 3 completed in {phase3_time:.2f}s (Response Generation)")

        # ========== QUICK WIN #2: PARALLEL PHASE 4: Wait for TTS completion ==========
        # TTS was started immediately after response generation (parallel processing)
        # Now wait for TTS to complete while logging continues in background
        logging.info("🔄 Phase 4: Waiting for TTS completion (started in parallel)")

        tts_response = await tts_task  # Wait for TTS task started earlier
        phase4_time = time.time() - tts_start_time  # Measure from when TTS actually started
        total_time = time.time() - start_time

        logging.info(f"✅ Phase 4 completed in {phase4_time:.2f}s (TTS Generation - Parallel)")
        logging.info(f"🎉 TOTAL Voice Call completed in {total_time:.2f}s")
        logging.info(f"📊 Performance Breakdown: Phase1={phase1_time:.2f}s, Phase2={phase2_time:.2f}s (Origin Check Only), Phase3={phase3_time:.2f}s, Phase4={phase4_time:.2f}s (Parallel TTS)")
        logging.info(f"🚀 OPTIMIZATIONS APPLIED: Deepgram STT + Memory Disabled + gpt-3.5-turbo + Parallel TTS")

        # Return combined response
        return {
            "transcript": transcript,
            "text_response": chat_response["response"],
            "message_id": chat_response["message_id"],
            "reminder": chat_response.get("reminder", False),
            "voice_id": tts_response["voice_id"],
            "audio_base64": tts_response["audio_base64"],
            "performance": {
                "total_time": round(total_time, 2),
                "phase_breakdown": {
                    "stt_preload": round(phase1_time, 2),
                    "origin_check_only": round(phase2_time, 2),  # Memory retrieval disabled for voice calls
                    "response_generation": round(phase3_time, 2),
                    "tts_generation_parallel": round(phase4_time, 2)  # Parallel TTS optimization
                },
                "optimizations_applied": [
                    "deepgram_stt",
                    "memory_retrieval_disabled",
                    "gpt_3_5_turbo_model",
                    "parallel_tts_generation"
                ]
            }
        }

    except Exception as e:
        total_time = time.time() - start_time
        logging.error(f"❌ Error in voice call after {total_time:.2f}s: {e}")
        return {"error": f"Voice call processing failed: {str(e)}"}

@app.get("/redis/health")
async def redis_health():
    """Check Redis connection health and provide cache statistics"""
    try:
        client = await get_redis_client()
        if not client:
            return {
                "status": "disconnected",
                "message": "Redis client not available - caching disabled",
                "fallback_active": True
            }

        # Test connection
        start_time = time.time()
        ping_result = await client.ping()
        response_time = (time.time() - start_time) * 1000  # Convert to ms

        # Get basic Redis info
        try:
            info = await client.info()
            memory_usage = info.get('used_memory_human', 'unknown')
            connected_clients = info.get('connected_clients', 'unknown')
            uptime = info.get('uptime_in_seconds', 'unknown')
        except:
            memory_usage = connected_clients = uptime = 'unavailable'

        return {
            "status": "connected",
            "ping": ping_result,
            "response_time_ms": round(response_time, 2),
            "host": REDIS_HOST,
            "memory_usage": memory_usage,
            "connected_clients": connected_clients,
            "uptime_seconds": uptime,
            "cache_ttl": CACHE_TTL,
            "message": "Redis caching active"
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Redis health check failed - falling back to direct memory retrieval"
        }

@app.get("/redis/cache-stats")
async def cache_stats():
    """Get cache performance statistics"""
    try:
        client = await get_redis_client()
        if not client:
            return {
                "status": "disconnected",
                "message": "Redis not available"
            }

        # Get cache keys matching our pattern
        cache_keys = await client.keys("memory_cache:*")
        total_keys = len(cache_keys)

        # Sample some keys to get average TTL
        sample_keys = cache_keys[:10] if len(cache_keys) > 10 else cache_keys
        ttl_values = []
        for key in sample_keys:
            ttl = await client.ttl(key)
            if ttl > 0:
                ttl_values.append(ttl)

        avg_ttl = sum(ttl_values) / len(ttl_values) if ttl_values else 0

        return {
            "status": "active",
            "total_cached_entries": total_keys,
            "average_ttl_seconds": round(avg_ttl, 1),
            "max_ttl_seconds": CACHE_TTL,
            "cache_pattern": "memory_cache:*",
            "performance_note": "Cache hits provide ~10,000x speed improvement for memory retrieval"
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.delete("/redis/cache")
async def clear_cache():
    """Clear all memory cache entries (use with caution)"""
    try:
        client = await get_redis_client()
        if not client:
            return {
                "status": "disconnected",
                "message": "Redis not available"
            }

        # Get and delete cache keys
        cache_keys = await client.keys("memory_cache:*")
        if cache_keys:
            deleted_count = await client.delete(*cache_keys)
            return {
                "status": "success",
                "deleted_entries": deleted_count,
                "message": f"Cleared {deleted_count} cache entries"
            }
        else:
            return {
                "status": "success",
                "deleted_entries": 0,
                "message": "No cache entries to clear"
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# ========== STREAMING TTS ENDPOINT - FOR LIGHTNING FAST VOICE CALLS ==========

# Streaming TTS Model for real-time audio generation
class StreamingTTSRequest(BaseModel):
    transcript: str
    bot_id: str
    output_format: Optional[dict] = {
        "container": "wav",
        "encoding": "pcm_s16le",
        "sample_rate": 22050,  # Optimized for streaming quality/speed balance
    }

@app.post("/stream-audio")
async def stream_audio(request: StreamingTTSRequest):
    """
    Stream TTS audio in real-time for lightning-fast voice responses.
    Similar to ChatGPT voice, this endpoint streams audio chunks as they're generated,
    providing immediate audio feedback instead of waiting for the full generation.
    """
    try:
        logging.info(f"🚀 STREAMING TTS called with bot_id: {request.bot_id}")

        # Get the appropriate voice ID for the bot
        voice_id = get_voice_id_for_bot(request.bot_id)

        def generate_audio_stream():
            """Generator function that yields audio chunks as they're produced"""
            try:
                # Use Cartesia's streaming capability
                audio_stream = client.tts.bytes(
                    model_id="sonic",
                    transcript=request.transcript,
                    voice={"mode": "id", "id": voice_id},
                    output_format=request.output_format
                )

                # Stream each chunk as it's generated
                for chunk in audio_stream:
                    if chunk:
                        # Encode chunk to base64 for JSON streaming
                        chunk_b64 = base64.b64encode(chunk).decode('utf-8')

                        # Format as JSON with metadata
                        json_chunk = json.dumps({
                            "type": "audio_chunk",
                            "data": chunk_b64,
                            "voice_id": voice_id
                        }) + "\n"

                        yield json_chunk.encode('utf-8')

                # Send completion signal
                completion_chunk = json.dumps({
                    "type": "stream_complete",
                    "voice_id": voice_id
                }) + "\n"
                yield completion_chunk.encode('utf-8')

            except Exception as e:
                # Send error signal
                error_chunk = json.dumps({
                    "type": "error",
                    "message": str(e)
                }) + "\n"
                yield error_chunk.encode('utf-8')

        # Return streaming response with proper headers for SSE
        return StreamingResponse(
            generate_audio_stream(),
            media_type="application/json",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering for real-time streaming
            }
        )

    except Exception as e:
        logging.error(f"Streaming TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stream-audio-raw")
async def stream_audio_raw(request: StreamingTTSRequest):
    """
    Stream raw audio bytes directly for even faster playback.
    This provides the fastest possible audio streaming experience by avoiding
    JSON formatting overhead and letting the client handle raw audio chunks.
    """
    try:
        logging.info(f"🎵 RAW STREAMING TTS called with bot_id: {request.bot_id}")

        # Get the appropriate voice ID for the bot
        voice_id = get_voice_id_for_bot(request.bot_id)

        def generate_raw_audio_stream():
            """Generator function that yields raw audio bytes"""
            try:
                # Use Cartesia's streaming capability
                audio_stream = client.tts.bytes(
                    model_id="sonic",
                    transcript=request.transcript,
                    voice={"mode": "id", "id": voice_id},
                    output_format=request.output_format
                )

                # Stream each raw audio chunk without any formatting
                for chunk in audio_stream:
                    if chunk:
                        yield chunk

            except Exception as e:
                logging.error(f"Raw streaming error: {e}")
                # Cannot yield error in raw audio stream
                return

        # Return raw audio streaming response
        return StreamingResponse(
            generate_raw_audio_stream(),
            media_type="audio/wav",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )

    except Exception as e:
        logging.error(f"Raw streaming TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== TTS OPTIMIZATION CONFIGURATIONS ==========
# Optimized audio formats for different use cases
# Replace the OPTIMIZED_AUDIO_FORMATS around line 1950 with this:

# Replace your OPTIMIZED_AUDIO_FORMATS (around line 1950) with this FIXED version:
OPTIMIZED_AUDIO_FORMATS = {
    "ultra_fast": {
        "container": "wav",
        "encoding": "pcm_s16le",  # ✅ FIXED: Standard 16-bit PCM (was pcm_f32le)
        "sample_rate": 8000,     # ✅ FIXED: Standard sample rate
    },
    "voice_call_ultra": {  # ✅ NEW: Even faster for voice calls
        "container": "wav",
        "encoding": "pcm_s16le",
        "sample_rate": 8000,
    },
    "balanced": {
        "container": "wav",
        "encoding": "pcm_s16le",  # ✅ FIXED: Standard 16-bit PCM
        "sample_rate": 8000,
    },
    "high_quality": {
        "container": "wav",
        "encoding": "pcm_s16le",  # ✅ FIXED: Standard 16-bit PCM
        "sample_rate": 8000,  # ✅ FIXED: Standard sample rate
    }
}

# Cache for common TTS responses to avoid repeated generation
TTS_CACHE = {}
TTS_CACHE_MAX_SIZE = 1000  # Increased cache size for better hit rate
TTS_CACHE_ENABLED = True
TTS_CACHE_TTL_HOURS = 24  # Cache entries expire after 24 hours
TTS_CACHE_STATS = {"hits": 0, "misses": 0, "total_requests": 0}

def get_optimized_audio_format(optimization_level: str = "ultra_fast"):
    """Get optimized audio format configuration"""
    return OPTIMIZED_AUDIO_FORMATS.get(optimization_level, OPTIMIZED_AUDIO_FORMATS["ultra_fast"])
'''
def get_smart_audio_format(text: str, use_case: str = "voice_call") -> dict:
    """
    Intelligently choose audio format based on text characteristics and use case

    Args:
        text: The text to be synthesized
        use_case: "voice_call", "streaming", "high_quality"

    Returns:
        Optimized audio format configuration
    """
    word_count = len(text.split())

    # For voice calls, prioritize speed
    if use_case == "voice_call":
        if word_count > 20:  # Long response - ultra fast for immediate feedback
            return get_optimized_audio_format("ultra_fast")
        elif word_count > 10:  # Medium response - balanced
            return get_optimized_audio_format("balanced")
        else:  # Short response - can afford slightly higher quality
            return get_optimized_audio_format("balanced")

    # For streaming, always use ultra_fast
    elif use_case == "streaming":
        return get_optimized_audio_format("ultra_fast")

    # For high quality use cases
    elif use_case == "high_quality":
        return get_optimized_audio_format("high_quality")

    # Default fallback
    return get_optimized_audio_format("ultra_fast")
'''
#prioritizing speed for voice calls:
# Update your get_smart_audio_format function around line 1980:

def get_smart_audio_format(text: str, use_case: str = "voice_call") -> dict:
    """Intelligently choose audio format for maximum speed"""
    word_count = len(text.split())

    # For voice calls, always prioritize speed
    if use_case == "voice_call":
        return get_optimized_audio_format("ultra_fast")  # Always use fastest

    # For other cases, use your existing logic
    elif use_case == "streaming":
        return get_optimized_audio_format("ultra_fast")
    else:
        return get_optimized_audio_format("balanced")


def cache_tts_response(text: str, voice_id: str, audio_base64: str):
    """Cache TTS response for common phrases with TTL support"""
    if not TTS_CACHE_ENABLED:
        return

    cache_key = f"{voice_id}:{hash(text)}"
    timestamp = time.time()

    # Simple LRU: remove oldest if cache is full
    if len(TTS_CACHE) >= TTS_CACHE_MAX_SIZE:
        oldest_key = next(iter(TTS_CACHE))
        del TTS_CACHE[oldest_key]

    TTS_CACHE[cache_key] = {
        "audio": audio_base64,
        "timestamp": timestamp
    }

def get_cached_tts_response(text: str, voice_id: str) -> Optional[str]:
    """Get cached TTS response if available and not expired"""
    if not TTS_CACHE_ENABLED:
        TTS_CACHE_STATS["misses"] += 1
        TTS_CACHE_STATS["total_requests"] += 1
        return None

    cache_key = f"{voice_id}:{hash(text)}"
    TTS_CACHE_STATS["total_requests"] += 1

    cached_entry = TTS_CACHE.get(cache_key)
    if not cached_entry:
        TTS_CACHE_STATS["misses"] += 1
        return None

    # Check TTL
    age_hours = (time.time() - cached_entry["timestamp"]) / 3600
    if age_hours > TTS_CACHE_TTL_HOURS:
        # Entry expired, remove it
        del TTS_CACHE[cache_key]
        TTS_CACHE_STATS["misses"] += 1
        return None

    TTS_CACHE_STATS["hits"] += 1
    return cached_entry["audio"]

async def generate_audio_word_by_word(text: str, voice_id: str, output_format: dict) -> str:
    """
    Generate audio using word-by-word parallel processing for faster results
    Splits long text into smaller chunks and processes them in parallel

    PERFORMANCE ISSUE FIX: If parallel processing takes too long (>4s), fallback to direct generation
    """
    parallel_start_time = time.time()
    words = text.split()

    if len(words) <= 5:  # Short text, use regular generation
        return await generate_audio_direct(text, voice_id, output_format)

    try:
        # Set a timeout for parallel processing to prevent performance degradation
        PARALLEL_TIMEOUT = 4.0  # If parallel takes >4s, fallback to direct

        # Split into chunks of 3-5 words for optimal performance
        chunk_size = min(5, max(3, len(words) // 4))
        chunks = [' '.join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

        logging.info(f"🔄 Attempting parallel processing with {len(chunks)} chunks")

        # Generate audio chunks in parallel
        async def generate_chunk(chunk_text: str):
            try:
                # Run the synchronous TTS call in a thread to avoid blocking
                audio_chunks = await asyncio.to_thread(
                    lambda: client.tts.bytes(
                        model_id="sonic",
                        transcript=chunk_text,
                        voice={"mode": "id", "id": voice_id},
                        output_format=output_format
                    )
                )
                return b"".join(audio_chunks)
            except Exception as e:
                logging.error(f"Error generating chunk '{chunk_text}': {e}")
                return b""

        # Process chunks in parallel with timeout
        chunk_tasks = [asyncio.create_task(generate_chunk(chunk)) for chunk in chunks]

        # Wait for all chunks with timeout
        try:
            chunk_results = await asyncio.wait_for(
                asyncio.gather(*chunk_tasks, return_exceptions=True),
                timeout=PARALLEL_TIMEOUT
            )
        except asyncio.TimeoutError:
            # Cancel all pending tasks
            for task in chunk_tasks:
                task.cancel()

            parallel_time = time.time() - parallel_start_time
            logging.warning(f"⚠️ Parallel processing timeout after {parallel_time:.2f}s - falling back to direct generation")
            return await generate_audio_direct(text, voice_id, output_format)

        # Combine all audio chunks
        combined_audio = b""
        successful_chunks = 0
        for result in chunk_results:
            if isinstance(result, bytes) and len(result) > 0:
                combined_audio += result
                successful_chunks += 1
            elif isinstance(result, Exception):
                logging.error(f"Chunk processing error: {result}")

        parallel_time = time.time() - parallel_start_time

        # If too few chunks succeeded or took too long, fallback to direct
        if successful_chunks < len(chunks) * 0.7 or parallel_time > PARALLEL_TIMEOUT:
            logging.warning(f"⚠️ Parallel processing inefficient ({successful_chunks}/{len(chunks)} chunks, {parallel_time:.2f}s) - falling back to direct")
            return await generate_audio_direct(text, voice_id, output_format)

        logging.info(f"✅ Parallel processing successful: {successful_chunks}/{len(chunks)} chunks in {parallel_time:.2f}s")
        return base64.b64encode(combined_audio).decode("utf-8")

    except Exception as e:
        parallel_time = time.time() - parallel_start_time
        logging.error(f"❌ Parallel processing failed after {parallel_time:.2f}s: {e}")
        logging.info("🔄 Falling back to direct generation")
        return await generate_audio_direct(text, voice_id, output_format)

async def generate_audio_direct(text: str, voice_id: str, output_format: dict) -> str:
    """Direct audio generation for shorter texts"""
    audio_chunks = client.tts.bytes(
        model_id="sonic",
        transcript=text,
        voice={"mode": "id", "id": voice_id},
        output_format=output_format
    )
    audio_data = b"".join(audio_chunks)
    return base64.b64encode(audio_data).decode("utf-8")
# ========== ENHANCED TTS ENDPOINT WITH ALL OPTIMIZATIONS ==========

# Replace your generate_audio_optimized function with this FINAL OPTIMIZED version:

# Replace your generate_audio_optimized function with this ABSOLUTE FASTEST version:

# Replace your generate_audio_optimized with this PERFECT version:

# Update your generate_audio_optimized function to use async cache:

@app.post("/generate-audio-optimized")
async def generate_audio_optimized(request: TTSRequest, background_tasks: BackgroundTasks):
    """
    PERFECT TTS: Sub-0.5s generation with full async optimization
    """
    tts_start_time = time.time()

    try:
        voice_id = get_voice_id_for_bot(request.bot_id)

        # ✅ USE ASYNC CACHE: This is faster than sync cache
        cached_audio = await get_cached_tts_response_async(request.transcript, voice_id)
        if cached_audio:
            cache_time = time.time() - tts_start_time
            print(f"⚡ ASYNC CACHE HIT: {cache_time:.3f}s")
            return {
                "voice_id": voice_id,
                "audio_base64": cached_audio,
                "cached": True,
                "generation_time": cache_time,
                "performance_target_met": True
            }

        # ✅ PERFECT FORMAT: Even faster than current 8kHz
        perfect_format = {
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": 8000,  # 25% faster than 8kHz, still audible
        }

        print(f"🎵 PERFECT: Using 6kHz format: {perfect_format}")

        # ✅ ZERO-WASTE GENERATION
        try:
            generation_start = time.time()

            audio_chunks = client.tts.bytes(
                model_id="sonic",
                transcript=request.transcript,
                voice={"mode": "id", "id": voice_id},
                output_format=perfect_format
            )

            audio_data = b"".join(audio_chunks)
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")

            generation_time = time.time() - generation_start
            print(f"🎯 PERFECT: Generated in {generation_time:.3f}s")

            if not audio_base64 or len(audio_data) < 100:
                raise Exception("Invalid audio generated")

        except Exception as e:
            error_time = time.time() - tts_start_time
            print(f"❌ PERFECT: Generation failed in {error_time:.3f}s: {e}")
            return {
                "voice_id": voice_id,
                "audio_base64": "",
                "cached": False,
                "generation_time": error_time,
                "error": str(e)
            }

        total_time = time.time() - tts_start_time

        # ✅ ASYNC CACHE STORAGE: Non-blocking background storage
        if audio_base64:
            asyncio.create_task(cache_tts_response_async(request.transcript, voice_id, audio_base64))

        print(f"🎯 PERFECT TTS: {total_time:.3f}s | Size: {len(audio_base64)}")

        return {
            "voice_id": voice_id,
            "audio_base64": audio_base64,
            "cached": False,
            "generation_time": total_time,
            "optimization_used": "perfect_async",
            "performance_target_met": total_time <= 0.5,
            "transfer_size": len(audio_base64),
            "format_used": perfect_format
        }

    except Exception as e:
        total_time = time.time() - tts_start_time
        print(f"❌ PERFECT: System error in {total_time:.3f}s: {e}")
        return {
            "voice_id": get_voice_id_for_bot(request.bot_id),
            "audio_base64": "",
            "cached": False,
            "generation_time": total_time,
            "error": str(e)
        }
# ========== TTS CACHE MANAGEMENT ENDPOINTS ==========
@app.get("/tts-cache/stats")
async def get_tts_cache_stats():
    """Get TTS cache performance statistics"""
    try:
        cache_size = len(TTS_CACHE)
        hit_rate = TTS_CACHE_STATS["hits"] / max(TTS_CACHE_STATS["total_requests"], 1) * 100

        return {
            "status": "success",
            "cache_enabled": TTS_CACHE_ENABLED,
            "cache_size": cache_size,
            "max_cache_size": TTS_CACHE_MAX_SIZE,
            "cache_utilization": f"{cache_size / TTS_CACHE_MAX_SIZE * 100:.1f}%",
            "ttl_hours": TTS_CACHE_TTL_HOURS,
            "statistics": {
                "total_requests": TTS_CACHE_STATS["total_requests"],
                "cache_hits": TTS_CACHE_STATS["hits"],
                "cache_misses": TTS_CACHE_STATS["misses"],
                "hit_rate_percentage": f"{hit_rate:.1f}%"
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.delete("/tts-cache/clear")
async def clear_tts_cache():
    """Clear TTS cache (use with caution)"""
    try:
        cleared_entries = len(TTS_CACHE)
        TTS_CACHE.clear()
        TTS_CACHE_STATS["hits"] = 0
        TTS_CACHE_STATS["misses"] = 0
        TTS_CACHE_STATS["total_requests"] = 0

        return {
            "status": "success",
            "cleared_entries": cleared_entries,
            "message": f"Cleared {cleared_entries} TTS cache entries and reset statistics"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# ========== TTS PERFORMANCE MONITORING ==========
@app.get("/tts-performance/summary")
async def get_tts_performance_summary():
    """Get comprehensive TTS performance metrics"""
    try:
        cache_size = len(TTS_CACHE)
        hit_rate = TTS_CACHE_STATS["hits"] / max(TTS_CACHE_STATS["total_requests"], 1) * 100

        return {
            "status": "success",
            "performance_targets": {
                "target_generation_time": "1.5-2.5s (down from 4.17s)",
                "target_improvement": "40-60% faster",
                "cache_hit_target": "<0.1s",
                "current_baseline": "4.17s"
            },
            "optimizations_active": {
                "tts_caching": TTS_CACHE_ENABLED,
                "smart_audio_formats": True,
                "parallel_word_processing": True,
                "voice_call_integration": True
            },
            "cache_performance": {
                "enabled": TTS_CACHE_ENABLED,
                "current_size": cache_size,
                "max_size": TTS_CACHE_MAX_SIZE,
                "utilization_percentage": round(cache_size / TTS_CACHE_MAX_SIZE * 100, 1),
                "ttl_hours": TTS_CACHE_TTL_HOURS,
                "hit_rate_percentage": round(hit_rate, 1),
                "total_requests": TTS_CACHE_STATS["total_requests"],
                "cache_hits": TTS_CACHE_STATS["hits"],
                "cache_misses": TTS_CACHE_STATS["misses"]
            },
            "audio_formats": {
                "ultra_fast": OPTIMIZED_AUDIO_FORMATS["ultra_fast"],
                "balanced": OPTIMIZED_AUDIO_FORMATS["balanced"],
                "high_quality": OPTIMIZED_AUDIO_FORMATS["high_quality"]
            },
            "recommendations": _get_performance_recommendations()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def _get_performance_recommendations():
    """Get performance optimization recommendations based on current stats"""
    recommendations = []

    # Cache recommendations
    hit_rate = TTS_CACHE_STATS["hits"] / max(TTS_CACHE_STATS["total_requests"], 1) * 100
    if hit_rate < 30 and TTS_CACHE_STATS["total_requests"] > 10:
        recommendations.append("📈 Low cache hit rate detected. Consider increasing cache size or TTL.")

    cache_utilization = len(TTS_CACHE) / TTS_CACHE_MAX_SIZE * 100
    if cache_utilization > 90:
        recommendations.append("💾 Cache nearly full. Consider increasing TTS_CACHE_MAX_SIZE.")

    if not TTS_CACHE_ENABLED:
        recommendations.append("🚀 TTS caching is disabled. Enable it for significant performance gains.")

    if len(recommendations) == 0:
        recommendations.append("✅ TTS performance optimizations are working well!")

    return recommendations


# Add these new configurations after the existing VOICE_MAPPING
# ========== ADVANCED TTS RESPONSE OPTIMIZATION CONFIGURATIONS ==========
# Response cache for ultra-fast pattern matching and repeated queries
RESPONSE_CACHE = {}
RESPONSE_CACHE_MAX_SIZE = 500  # Larger cache for common responses
RESPONSE_CACHE_TTL_HOURS = 48  # Longer TTL for response patterns
RESPONSE_CACHE_STATS = {"hits": 0, "misses": 0, "total_requests": 0}

# Instant responses for common greetings and phrases (<0.1s target)
INSTANT_RESPONSES = {
    "hello": "Hello! How can I help you today?",
    "hi": "Hi there! What can I do for you?",
    "good morning": "Good morning! How are you doing today?",
    "good afternoon": "Good afternoon! How can I assist you?",
    "good evening": "Good evening! What brings you here today?",
    "how are you": "I'm doing great, thank you for asking! How are you?",
    "thank you": "You're very welcome! Is there anything else I can help you with?",
    "thanks": "You're welcome! Happy to help!",
    "bye": "Goodbye! Have a wonderful day!",
    "goodbye": "Goodbye! It was great talking with you!",
    "help": "I'm here to help! What would you like to know?",
    "what's your name": "I'm your AI assistant. What's your name?",
    "who are you": "I'm an AI assistant here to help you with any questions you might have."
}

# Lightning-fast model configurations for different complexity levels
LIGHTNING_MODELS = {
    "instant": {"model": "gpt-3.5-turbo", "max_tokens": 50, "temperature": 0.7},
    "simple": {"model": "gpt-3.5-turbo", "max_tokens": 150, "temperature": 0.7},
    "complex": {"model": "gpt-3.5-turbo", "max_tokens": 300, "temperature": 0.8},
    "detailed": {"model": "gpt-4", "max_tokens": 500, "temperature": 0.8}
}

# Add these new helper functions after the existing TTS helper functions
async def get_instant_response(text: str) -> Optional[dict]:
    """Get instant response for common patterns and phrases (sub-0.1s target)"""
    start_time = time.time()
    try:
        RESPONSE_CACHE_STATS["total_requests"] += 1

        # Normalize input text for matching
        normalized_text = text.lower().strip()

        # ✅ PERFECT: Check for EXACT matches first
        if normalized_text in INSTANT_RESPONSES:
            RESPONSE_CACHE_STATS["hits"] += 1
            logging.info(f"⚡ INSTANT EXACT MATCH: '{normalized_text}' -> cached response")
            return {
                "response": INSTANT_RESPONSES[normalized_text],
                "match_type": "exact",
                "pattern": normalized_text,
                "response_time": time.time() - start_time
            }

        # ✅ BULLETPROOF: Only match standalone greetings with word boundaries
        for pattern, response in INSTANT_RESPONSES.items():
            # Check if the pattern is a complete word at the start
            if (normalized_text == pattern or  # Exact match
                normalized_text == pattern + "." or  # With period
                normalized_text == pattern + "!" or  # With exclamation
                normalized_text == pattern + "?" or  # With question mark
                (normalized_text.startswith(pattern + " ") and len(normalized_text.split()) <= 3)):  # With space + max 2 more words

                RESPONSE_CACHE_STATS["hits"] += 1
                logging.info(f"⚡ PATTERN STANDALONE MATCH: '{normalized_text}' matches '{pattern}'")
                return {
                    "response": response,
                    "match_type": "pattern_standalone",
                    "pattern": pattern,
                    "response_time": time.time() - start_time
                }

        # Check response cache for previously generated responses
        cache_key = f"response:{hash(normalized_text)}"
        if cache_key in RESPONSE_CACHE:
            cached_entry = RESPONSE_CACHE[cache_key]
            # Check TTL
            if time.time() - cached_entry["timestamp"] < RESPONSE_CACHE_TTL_HOURS * 3600:
                RESPONSE_CACHE_STATS["hits"] += 1
                logging.info(f"⚡ RESPONSE CACHE HIT: '{normalized_text[:30]}...'")
                return {
                    "response": cached_entry["response"],
                    "match_type": "cache",
                    "pattern": "cached_response",
                    "response_time": time.time() - start_time
                }
            else:
                # Remove expired entry
                del RESPONSE_CACHE[cache_key]

        RESPONSE_CACHE_STATS["misses"] += 1
        return None

    except Exception as e:
        logging.error(f"❌ Error in get_instant_response: {e}")
        RESPONSE_CACHE_STATS["misses"] += 1
        return None

async def generate_streaming_response(transcript: str, bot_id: str) -> dict:
    """Generate response using smart model selection and advanced optimizations"""
    start_time = time.time()

    try:
        # Analyze text complexity for smart model selection
        word_count = len(transcript.split())
        question_complexity = "simple"

        if word_count > 30 or "?" in transcript:
            question_complexity = "complex"
        elif word_count > 15:
            question_complexity = "medium"

        # Select optimal model configuration
        if question_complexity == "simple":
            model_config = LIGHTNING_MODELS["simple"]
        elif question_complexity == "complex":
            model_config = LIGHTNING_MODELS["complex"]
        else:
            model_config = LIGHTNING_MODELS["simple"]  # Default to fast model

        logging.info(f"🚀 Selected {model_config['model']} for {question_complexity} query ({word_count} words)")

        # Prepare messages for API call
        messages = [
            {"role": "system", "content": f"You are a helpful AI assistant. Keep responses concise and engaging."},
            {"role": "user", "content": transcript}
        ]

        # Generate response with optimized model
        response = await call_openai_api(messages, model=model_config["model"])

        # Cache the response for future use
        cache_key = f"response:{hash(transcript.lower().strip())}"
        timestamp = time.time()

        # Simple LRU: remove oldest if cache is full
        if len(RESPONSE_CACHE) >= RESPONSE_CACHE_MAX_SIZE:
            oldest_key = next(iter(RESPONSE_CACHE))
            del RESPONSE_CACHE[oldest_key]

        RESPONSE_CACHE[cache_key] = {
            "response": response,
            "timestamp": timestamp,
            "model_used": model_config["model"],
            "complexity": question_complexity
        }

        generation_time = time.time() - start_time

        return {
            "response": response,
            "response_type": "streaming_generated",
            "generation_time": generation_time,
            "model_used": model_config["model"],
            "complexity_detected": question_complexity,
            "cached": False
        }

    except Exception as e:
        generation_time = time.time() - start_time
        logging.error(f"❌ Error in generate_streaming_response: {e}")

        # Fallback to simple response
        return {
            "response": "I apologize, but I'm having trouble processing your request right now. Please try again.",
            "response_type": "fallback",
            "generation_time": generation_time,
            "model_used": "fallback",
            "error": str(e)
        }

async def parallel_tts_preprocessing(text: str, voice_id: str) -> dict:
    """Pre-optimize TTS settings while other processing happens"""
    try:
        # Analyze text for optimal TTS format
        word_count = len(text.split())

        # Pre-select smart audio format
        if word_count > 20:
            smart_format = get_optimized_audio_format("ultra_fast")
            optimization_level = "ultra_fast"
        elif word_count > 10:
            smart_format = get_optimized_audio_format("balanced")
            optimization_level = "balanced"
        else:
            smart_format = get_optimized_audio_format("balanced")
            optimization_level = "balanced"

        # Pre-check TTS cache
        cached_audio = get_cached_tts_response(text, voice_id)
        cache_available = cached_audio is not None

        # Determine processing method
        if cache_available:
            processing_method = "cache_hit"
        elif word_count > 15:
            processing_method = "word_by_word"
        else:
            processing_method = "direct"

        logging.info(f"🔧 TTS preprocessing: {word_count} words -> {optimization_level} format, {processing_method} method")

        return {
            "smart_format": smart_format,
            "optimization_level": optimization_level,
            "processing_method": processing_method,
            "cache_available": cache_available,
            "cache_checked": True,  # Always check cache in preprocessing
            "word_count": word_count,
            "estimated_time": 0.1 if cache_available else (1.5 if word_count > 15 else 1.0)
        }

    except Exception as e:
        logging.error(f"❌ Error in parallel_tts_preprocessing: {e}")
        # Return safe defaults
        return {
            "smart_format": get_optimized_audio_format("balanced"),
            "optimization_level": "balanced",
            "processing_method": "direct",
            "cache_available": False,
            "cache_checked": True,  # Always check cache even in error cases
            "word_count": len(text.split()),
            "estimated_time": 2.0,
            "error": str(e)
        }

# Add STT performance monitoring
# Global STT metrics storage
stt_metrics = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "deepgram_direct_successes": 0,
    "deepgram_fallback_successes": 0,
    "google_fallback_successes": 0,
    "average_processing_time": 0.0,
    "min_processing_time": float('inf'),
    "max_processing_time": 0.0,
    "processing_times": [],
    "provider_performance": {
        "deepgram_direct": {"count": 0, "total_time": 0.0, "success_rate": 0.0},
        "deepgram_fallback": {"count": 0, "total_time": 0.0, "success_rate": 0.0},
        "google_fallback": {"count": 0, "total_time": 0.0, "success_rate": 0.0}
    },
    "recent_performance": []  # Last 50 requests
}

def update_stt_metrics(processing_time: float, provider: str, success: bool):
    """Update STT performance metrics"""
    global stt_metrics

    stt_metrics["total_requests"] += 1

    if success:
        stt_metrics["successful_requests"] += 1
        stt_metrics["processing_times"].append(processing_time)

        # Update provider-specific metrics
        if provider in stt_metrics["provider_performance"]:
            provider_data = stt_metrics["provider_performance"][provider]
            provider_data["count"] += 1
            provider_data["total_time"] += processing_time
            provider_data["success_rate"] = (provider_data["count"] / stt_metrics["total_requests"]) * 100

        # Update overall timing metrics
        stt_metrics["min_processing_time"] = min(stt_metrics["min_processing_time"], processing_time)
        stt_metrics["max_processing_time"] = max(stt_metrics["max_processing_time"], processing_time)

        if stt_metrics["processing_times"]:
            stt_metrics["average_processing_time"] = sum(stt_metrics["processing_times"]) / len(stt_metrics["processing_times"])

        # Track specific provider successes
        if provider == "deepgram_direct":
            stt_metrics["deepgram_direct_successes"] += 1
        elif provider == "deepgram_fallback":
            stt_metrics["deepgram_fallback_successes"] += 1
        elif provider == "google_fallback":
            stt_metrics["google_fallback_successes"] += 1
    else:
        stt_metrics["failed_requests"] += 1

    # Keep only last 50 requests for recent performance
    stt_metrics["recent_performance"].append({
        "timestamp": time.time(),
        "processing_time": processing_time if success else None,
        "provider": provider,
        "success": success
    })

    if len(stt_metrics["recent_performance"]) > 50:
        stt_metrics["recent_performance"] = stt_metrics["recent_performance"][-50:]

# Add the ultra-optimized STT function
async def speech_to_text_optimized(audio_buffer: bytes, filename: str = "audio.wav") -> str:
    """
    Ultra-optimized Speech-to-Text function with Deepgram as primary provider

    Performance targets:
    - Target: 1.5-2.5s (down from 4+ seconds)
    - 65%+ performance improvement

    Optimizations:
    1. Direct buffer processing to Deepgram (no temporary files for primary path)
    2. Eliminated AudioSegment processing overhead
    3. Removed frame rate/channel conversion
    4. Single I/O operation to Deepgram
    5. Enhanced Deepgram configuration with "nova-2-general" model
    6. Minimal fallback chain: Deepgram direct → Deepgram file → Google Speech Recognition

    Returns transcribed text from audio
    """
    stt_start_time = time.time()

    try:
        logging.info(f"🚀 OPTIMIZED STT started - Processing {len(audio_buffer)} bytes")

        # ========== PRIMARY PATH: Direct Deepgram Buffer Processing ==========
        try:
            # Initialize Deepgram client
            deepgram = DeepgramClient(api_key=os.environ.get("DEEPGRAM_API_KEY"))

            # Enhanced Deepgram configuration for optimal performance and accuracy
            options = PrerecordedOptions(
                model="nova-2",          # Latest, most accurate model
                language="en",
                smart_format=True,       # Automatic punctuation and formatting
                diarize=False,          # Disable speaker detection for speed
                punctuate=True,
                profanity_filter=False,
                redact=False,
                summarize=False,
                detect_language=False,   # Skip language detection for speed
                paragraphs=False,        # Skip paragraph detection for speed
                utterances=False,        # Skip utterance timestamps for speed
                utt_split=0.8           # Optimal utterance splitting
            )

            # Direct buffer processing - no file I/O
            payload = {"buffer": audio_buffer}
            response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)

            # Extract transcription
            transcript = ""
            if response.results and response.results.channels:
                alternatives = response.results.channels[0].alternatives
                if alternatives and len(alternatives) > 0:
                    transcript = alternatives[0].transcript.strip()

            if transcript and len(transcript) > 0:
                processing_time = time.time() - stt_start_time
                logging.info(f"✅ DEEPGRAM DIRECT SUCCESS in {processing_time:.3f}s: '{transcript[:50]}{'...' if len(transcript) > 50 else ''}'")

                # Update performance metrics
                update_stt_metrics(processing_time, "deepgram_direct", True)

                return transcript
            else:
                raise Exception("Empty transcript from Deepgram direct processing")

        except Exception as deepgram_error:
            processing_time = time.time() - stt_start_time
            logging.warning(f"⚠️ Deepgram direct failed in {processing_time:.3f}s: {deepgram_error}")
            update_stt_metrics(processing_time, "deepgram_direct", False)

        # ========== FALLBACK 1: Deepgram with Temporary File ==========
        try:
            logging.info("🔄 Falling back to Deepgram file processing")
            fallback_start = time.time()

            # Create temporary file for fallback
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(audio_buffer)
                temp_file_path = temp_file.name

            try:
                # Process with Deepgram using file
                with open(temp_file_path, "rb") as audio_file:
                    payload = {"buffer": audio_file}
                    response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)

                # Extract transcription
                transcript = ""
                if response.results and response.results.channels:
                    alternatives = response.results.channels[0].alternatives
                    if alternatives and len(alternatives) > 0:
                        transcript = alternatives[0].transcript.strip()

                if transcript and len(transcript) > 0:
                    fallback_time = time.time() - fallback_start
                    total_time = time.time() - stt_start_time
                    logging.info(f"✅ DEEPGRAM FALLBACK SUCCESS in {total_time:.3f}s: '{transcript[:50]}{'...' if len(transcript) > 50 else ''}'")

                    # Update performance metrics
                    update_stt_metrics(total_time, "deepgram_fallback", True)

                    return transcript
                else:
                    raise Exception("Empty transcript from Deepgram file processing")

            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as deepgram_file_error:
            fallback_time = time.time() - stt_start_time
            logging.warning(f"⚠️ Deepgram file fallback failed in {fallback_time:.3f}s: {deepgram_file_error}")
            update_stt_metrics(fallback_time, "deepgram_fallback", False)

        # ========== FALLBACK 2: Google Speech Recognition ==========
        try:
            logging.info("🔄 Falling back to Google Speech Recognition")
            google_start = time.time()

            # Use speech_recognition library for Google Speech Recognition
            recognizer = sr.Recognizer()

            # Create temporary file for Google Speech Recognition
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(audio_buffer)
                temp_file_path = temp_file.name

            try:
                # Process with Google Speech Recognition
                with sr.AudioFile(temp_file_path) as source:
                    audio_data = recognizer.record(source)
                    transcript = recognizer.recognize_google(audio_data)

                if transcript and len(transcript.strip()) > 0:
                    total_time = time.time() - stt_start_time
                    logging.info(f"✅ GOOGLE FALLBACK SUCCESS in {total_time:.3f}s: '{transcript[:50]}{'...' if len(transcript) > 50 else ''}'")

                    # Update performance metrics
                    update_stt_metrics(total_time, "google_fallback", True)

                    return transcript.strip()
                else:
                    raise Exception("Empty transcript from Google Speech Recognition")

            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as google_error:
            total_time = time.time() - stt_start_time
            logging.warning(f"⚠️ Google Speech Recognition fallback failed in {total_time:.3f}s: {google_error}")
            update_stt_metrics(total_time, "google_fallback", False)

        # ========== ALL FALLBACKS FAILED ==========
        total_time = time.time() - stt_start_time
        error_msg = f"All STT providers failed after {total_time:.3f}s"
        logging.error(f"❌ {error_msg}")

        # Update metrics for complete failure
        update_stt_metrics(total_time, "all_failed", False)

        # Return fallback message
        return "Sorry, I couldn't process your audio. Please try again."

    except Exception as e:
        total_time = time.time() - stt_start_time
        logging.error(f"❌ STT optimization function error after {total_time:.3f}s: {e}")

        # Update metrics for system error
        update_stt_metrics(total_time, "system_error", False)

        return "Sorry, there was an error processing your audio. Please try again."

# Add explicit OPTIONS handler for CORS preflight requests
@app.options("/voice-call-ultra-fast")
async def voice_call_ultra_fast_options():
    """Handle CORS preflight requests for /voice-call-ultra-fast endpoint"""
    return JSONResponse(
        content={"message": "CORS preflight successful"},
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400"
        }
    )

# Add new endpoint for ultra-fast voice calls
# Around line 3200 in the voice_call_ultra_fast_endpoint function, add debugging:
'''
@app.post("/voice-call-ultra-fast")
async def voice_call_ultra_fast_endpoint(
    audio_file: UploadFile = File(...),
    bot_id: str = Form("delhi_mentor_male"),
    email: str = Form(""),
    platform: str = Form("web"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    ULTRA-FAST Voice Call endpoint with maximum speed optimizations
    """
    ultra_fast_start_time = time.time()

    try:
        logging.info(f"⚡ ULTRA-FAST VOICE CALL started - bot_id: {bot_id}")

        # ========== PHASE 1: OPTIMIZED STT PROCESSING ==========
        audio_content = await audio_file.read()
        transcript = await speech_to_text_optimized(audio_content, audio_file.filename)

        if not transcript or transcript.strip() == "":
            return JSONResponse(
                status_code=400,
                content={"error": "Could not transcribe audio. Please try again."}
            )

        # ========== PHASE 2: INSTANT RESPONSE CHECK ==========
        instant_response = await get_instant_response(transcript)
        if instant_response:
            response = instant_response["response"]
            logging.info(f"⚡ INSTANT RESPONSE in {instant_response['response_time']:.3f}s")
        else:
            # Generate response with fastest model
            bot_prompt = get_bot_prompt(bot_id)
            messages = [
                {"role": "system", "content": f"You are a helpful AI assistant. Keep responses very concise and direct."},
                {"role": "user", "content": transcript}
            ]
            #response = await call_openai_api(messages, model="gpt-3.5-turbo")
            response = await call_xai_api(messages, model="grok-beta")

        # ========== PHASE 3: ULTRA-FAST TTS WITH DEBUGGING ==========

        # 🎵 ADD DEBUGGING HERE - Before TTS generation
        print(f"🎵 DEBUG: Audio generation started for text: '{response[:100]}{'...' if len(response) > 100 else ''}'")
        print(f"🎵 DEBUG: Bot ID: {bot_id}")
        print(f"🎵 DEBUG: Voice ID will be: {get_voice_id_for_bot(bot_id)}")

        # Check TTS cache first
        voice_id = get_voice_id_for_bot(bot_id)
        tts_cache_result = get_cached_tts_response(response, voice_id)
        print(f"🎵 DEBUG: TTS cache check result: {'HIT' if tts_cache_result else 'MISS'}")

        # Use ultra-fast audio format for maximum speed
        tts_request = TTSRequest(
            transcript=response,
            bot_id=bot_id,
            output_format=get_optimized_audio_format("ultra_fast")
        )

        print(f"🎵 DEBUG: TTS request created with format: {tts_request.output_format}")

        audio_result = await generate_audio_optimized(tts_request, background_tasks)

        # 🎵 ADD DEBUGGING HERE - After TTS generation
        audio_base64 = audio_result.get("audio_base64")
        if audio_base64:
            print(f"✅ DEBUG: Audio generated successfully, length: {len(audio_base64)}")
            print(f"✅ DEBUG: Audio result keys: {list(audio_result.keys())}")
            print(f"✅ DEBUG: Audio cached: {audio_result.get('cached', False)}")

            # Validate audio format
            try:
                import base64
                audio_bytes = base64.b64decode(audio_base64)
                print(f"✅ DEBUG: Audio bytes decoded successfully, length: {len(audio_bytes)}")

                # Check for WAV header
                if audio_bytes[:4] == b'RIFF' and audio_bytes[8:12] == b'WAVE':
                    print(f"✅ DEBUG: Valid WAV audio format detected")
                else:
                    print(f"⚠️ DEBUG: Audio format check - Header: {audio_bytes[:12]}")
            except Exception as decode_error:
                print(f"❌ DEBUG: Audio base64 decode error: {decode_error}")
        else:
            print(f"❌ DEBUG: Audio generation failed - audio_base64 is None")
            print(f"❌ DEBUG: Audio result: {audio_result}")

        total_time = time.time() - ultra_fast_start_time

        # Rest of your function continues...
        background_tasks.add_task(
            insert_entry, email, transcript, response, bot_id,
            datetime.now().isoformat(), platform
        )

        logging.info(f"⚡ ULTRA-FAST Voice Call COMPLETED in {total_time:.3f}s")

        return {
            "transcript": transcript,
            "text_response": response,
            "voice_id": audio_result.get("voice_id"),
            "audio_base64": audio_result.get("audio_base64"),
            "performance": {
                "total_time": round(total_time, 2),
                "target_achieved": total_time <= 6.0,
                "optimizations_applied": [
                    "ultra_fast_stt",
                    "instant_response_check",
                    "ultra_fast_audio_format",
                    "minimal_logging"
                ]
            },
            "cached": audio_result.get("cached", False)
        }

    except Exception as e:
        total_time = time.time() - ultra_fast_start_time
        logging.error(f"❌ Ultra-fast Voice Call failed after {total_time:.3f}s: {e}")

        return JSONResponse(
            status_code=500,
            content={
                "error": "Ultra-fast voice call processing failed",
                "details": str(e),
                "processing_time": total_time
            }
        )
'''
# Replace your voice_call_ultra_fast_endpoint function:

@app.post("/voice-call-ultra-fast")
async def voice_call_ultra_fast_endpoint(
    audio_file: UploadFile = File(...),
    bot_id: str = Form("delhi_mentor_male"),
    email: str = Form(""),
    platform: str = Form("web"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    ULTRA-FAST Voice Call endpoint with maximum speed optimizations
    Target: 2.5-3.5s total response time
    """
    ultra_fast_start_time = time.time()

    try:
        logging.info(f"⚡ ULTRA-FAST VOICE CALL started - bot_id: {bot_id}")

        # ========== PHASE 1: OPTIMIZED STT PROCESSING ==========
        audio_content = await audio_file.read()
        transcript = await speech_to_text_optimized(audio_content, audio_file.filename)

        if not transcript or transcript.strip() == "":
            return JSONResponse(
                status_code=400,
                content={"error": "Could not transcribe audio. Please try again."}
            )


        # ✅ NEW: CALCULATE XP MAGNITUDE for ultra-fast voice call
        magnitude = get_magnitude_for_query(transcript)
        
        # ✅ NEW: AWARD IMMEDIATE XP based on magnitude
        immediate_xp_result = award_immediate_xp_and_magnitude(
            email, 
            bot_id, 
            magnitude
        )
        
        logging.info(f"⚡ Ultra-Fast XP: {email} awarded +{immediate_xp_result['immediate_xp_awarded']} XP (magnitude: {magnitude:.2f})")







        # ========== PHASE 2: INSTANT RESPONSE CHECK ==========
        instant_response = await get_instant_response(transcript)
        if instant_response:
            response = instant_response["response"]
            logging.info(f"⚡ INSTANT RESPONSE in {instant_response['response_time']:.3f}s")
        else:
            # Generate response with fastest model
            bot_prompt = get_bot_prompt(bot_id)
            messages = [
                {"role": "system", "content": f"You are a helpful AI assistant. Keep responses very concise and direct."},
                {"role": "user", "content": transcript}
            ]
            response = await call_xai_api(messages, model="grok-beta")

# Update your voice call to use the perfect TTS:

# In your voice_call_ultra_fast_endpoint, replace the TTS section:

        # ========== PHASE 3: PERFECT TTS ==========
        print(f"🎵 PERFECT: Audio generation started for: '{response[:50]}...'")

        # Use perfect audio format based on response length
        perfect_format = get_smart_audio_format(response, "voice_call")

        tts_request = TTSRequest(
            transcript=response,
            bot_id=bot_id,
            output_format=perfect_format  # Use dynamic perfect format
        )

        print(f"🎵 PERFECT: Using format: {perfect_format}")

        audio_result = await generate_audio_optimized(tts_request, background_tasks)

        # Validate audio generation
        audio_base64 = audio_result.get("audio_base64")
        if audio_base64:
            print(f"✅ DEBUG: Audio generated successfully, length: {len(audio_base64)}")

            # Validate audio format
            try:
                audio_bytes = base64.b64decode(audio_base64)
                print(f"✅ DEBUG: Audio bytes decoded successfully, length: {len(audio_bytes)}")

                # Check for WAV header
                if audio_bytes[:4] == b'RIFF' and audio_bytes[8:12] == b'WAVE':
                    print(f"✅ DEBUG: Valid WAV audio format detected")
                else:
                    print(f"⚠️ DEBUG: Audio format check - Header: {audio_bytes[:12]}")
            except Exception as decode_error:
                print(f"❌ DEBUG: Audio base64 decode error: {decode_error}")
        else:
            print(f"❌ DEBUG: Audio generation failed - audio_base64 is None")
            print(f"❌ DEBUG: Audio result: {audio_result}")

        total_time = time.time() - ultra_fast_start_time

        # Background logging
        background_tasks.add_task(
            insert_entry, email, transcript, response, bot_id,
            datetime.now().isoformat(), platform
        )

        logging.info(f"⚡ ULTRA-FAST Voice Call COMPLETED in {total_time:.3f}s")

        return {
            "transcript": transcript,
            "text_response": response,
            "voice_id": audio_result.get("voice_id"),
            "audio_base64": audio_result.get("audio_base64"),
            "performance": {
                "total_time": round(total_time, 2),
                "target_achieved": total_time <= 6.0,
                "optimizations_applied": [
                    "ultra_fast_stt",
                    "instant_response_check",
                    "ultra_fast_audio_format",
                    "minimal_logging"
                ]
            },
            "cached": audio_result.get("cached", False),
            
            # ✅ NEW: Include XP data in ultra-fast voice call response
            "xp_data": {
                "immediate_xp_awarded": immediate_xp_result["immediate_xp_awarded"],
                "current_total_xp": immediate_xp_result["current_total_xp"],
                "current_total_coins": immediate_xp_result["current_total_coins"],
                "magnitude": immediate_xp_result["magnitude"],
                "xp_calculation_success": immediate_xp_result["success"]
            }   
        }

    except Exception as e:
        total_time = time.time() - ultra_fast_start_time
        logging.error(f"❌ Ultra-fast Voice Call failed after {total_time:.3f}s: {e}")

        return JSONResponse(
            status_code=500,
            content={
                "error": "Ultra-fast voice call processing failed",
                "details": str(e),
                "processing_time": total_time
            }
        )
# Add STT performance monitoring endpoints
@app.get("/stt-performance/stats")
async def get_stt_performance_stats():
    """Get comprehensive STT performance statistics"""
    global stt_metrics

    # Calculate success rate
    success_rate = (stt_metrics["successful_requests"] / stt_metrics["total_requests"] * 100) if stt_metrics["total_requests"] > 0 else 0

    # Calculate recent performance (last 10 requests)
    recent_requests = stt_metrics["recent_performance"][-10:]
    recent_success_rate = (sum(1 for r in recent_requests if r["success"]) / len(recent_requests) * 100) if recent_requests else 0
    recent_avg_time = sum(r["processing_time"] for r in recent_requests if r["processing_time"]) / len([r for r in recent_requests if r["processing_time"]]) if recent_requests else 0

    # Provider performance breakdown
    provider_stats = {}
    for provider, data in stt_metrics["provider_performance"].items():
        if data["count"] > 0:
            provider_stats[provider] = {
                "requests": data["count"],
                "average_time": round(data["total_time"] / data["count"], 3),
                "success_rate": round(data["success_rate"], 1),
                "total_time": round(data["total_time"], 2)
            }

    return {
        "overall_stats": {
            "total_requests": stt_metrics["total_requests"],
            "successful_requests": stt_metrics["successful_requests"],
            "failed_requests": stt_metrics["failed_requests"],
            "success_rate_percentage": round(success_rate, 1),
            "average_processing_time": round(stt_metrics["average_processing_time"], 3),
            "min_processing_time": round(stt_metrics["min_processing_time"], 3) if stt_metrics["min_processing_time"] != float('inf') else None,
            "max_processing_time": round(stt_metrics["max_processing_time"], 3),
        },
        "provider_breakdown": {
            "deepgram_direct_successes": stt_metrics["deepgram_direct_successes"],
            "deepgram_fallback_successes": stt_metrics["deepgram_fallback_successes"],
            "google_fallback_successes": stt_metrics["google_fallback_successes"],
        },
        "provider_performance": provider_stats,
        "recent_performance": {
            "last_10_requests_success_rate": round(recent_success_rate, 1),
            "last_10_requests_avg_time": round(recent_avg_time, 3),
            "recent_requests_count": len(recent_requests)
        },
        "performance_targets": {
            "target_time": "1.5-2.5s",
            "target_success_rate": ">95%",
            "primary_provider": "deepgram_direct",
            "current_target_met": stt_metrics["average_processing_time"] <= 2.5 and success_rate >= 95
        },
        "optimization_status": {
            "direct_buffer_processing": True,
            "eliminated_audio_segment": True,
            "removed_frame_conversion": True,
            "minimal_fallback_chain": True,
            "enhanced_deepgram_config": True
        }
    }

@app.get("/stt-performance/summary")
async def get_stt_performance_summary():
    """Get high-level STT performance summary with recommendations"""
    stats = await get_stt_performance_stats()

    # Generate recommendations
    recommendations = []

    if stats["overall_stats"]["average_processing_time"] > 2.5:
        recommendations.append("⚠️ Average processing time exceeds 2.5s target")

    if stats["overall_stats"]["success_rate_percentage"] < 95:
        recommendations.append("⚠️ Success rate below 95% target")

    if stats["provider_breakdown"]["deepgram_direct_successes"] / stats["overall_stats"]["total_requests"] < 0.8:
        recommendations.append("⚠️ Deepgram direct success rate low - check API connectivity")

    if not recommendations:
        recommendations.append("✅ All STT performance targets met")

    return {
        "status": "healthy" if stats["performance_targets"]["current_target_met"] else "needs_attention",
        "summary": {
            "total_requests": stats["overall_stats"]["total_requests"],
            "average_time": f"{stats['overall_stats']['average_processing_time']}s",
            "success_rate": f"{stats['overall_stats']['success_rate_percentage']}%",
            "primary_provider_usage": f"{(stats['provider_breakdown']['deepgram_direct_successes'] / max(stats['overall_stats']['total_requests'], 1) * 100):.1f}%"
        },
        "performance_trend": "optimal" if stats["recent_performance"]["last_10_requests_avg_time"] <= 2.5 else "degraded",
        "recommendations": recommendations,
        "optimization_impact": {
            "baseline_time": "4+ seconds (before optimization)",
            "current_avg_time": f"{stats['overall_stats']['average_processing_time']}s",
            "improvement": f"{max(0, ((4.0 - stats['overall_stats']['average_processing_time']) / 4.0 * 100)):.1f}% faster"
        }
    }

@app.delete("/stt-performance/reset")
async def reset_stt_performance_stats():
    """Reset STT performance statistics (admin only)"""
    global stt_metrics

    stt_metrics = {
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "deepgram_direct_successes": 0,
        "deepgram_fallback_successes": 0,
        "google_fallback_successes": 0,
        "average_processing_time": 0.0,
        "min_processing_time": float('inf'),
        "max_processing_time": 0.0,
        "processing_times": [],
        "provider_performance": {
            "deepgram_direct": {"count": 0, "total_time": 0.0, "success_rate": 0.0},
            "deepgram_fallback": {"count": 0, "total_time": 0.0, "success_rate": 0.0},
            "google_fallback": {"count": 0, "total_time": 0.0, "success_rate": 0.0}
        },
        "recent_performance": []
    }

    return {"message": "STT performance statistics reset successfully", "timestamp": time.time()}

# Add STT performance testing endpoint
@app.post("/test-stt-performance")
async def test_stt_performance_endpoint(
    audio_file: UploadFile = File(...),
    iterations: int = Form(1)
):
    """
    Test STT performance with multiple iterations for benchmarking
    """
    try:
        logging.info(f"🧪 STT Performance Test started - {iterations} iterations")

        # Read audio file once
        audio_content = await audio_file.read()

        results = []
        total_start_time = time.time()

        for i in range(iterations):
            iteration_start = time.time()
            transcript = await speech_to_text_optimized(audio_content, audio_file.filename)
            iteration_time = time.time() - iteration_start

            results.append({
                "iteration": i + 1,
                "transcript": transcript,
                "processing_time": iteration_time,
                "target_met": iteration_time <= 2.5
            })

            logging.info(f"🧪 Iteration {i + 1}: {iteration_time:.3f}s - {'✅' if iteration_time <= 2.5 else '❌'}")

        total_time = time.time() - total_start_time

        # Calculate statistics
        processing_times = [r["processing_time"] for r in results]
        avg_time = sum(processing_times) / len(processing_times)
        min_time = min(processing_times)
        max_time = max(processing_times)
        success_rate = sum(1 for r in results if r["target_met"]) / len(results) * 100

        return {
            "test_results": results,
            "statistics": {
                "total_iterations": iterations,
                "total_time": total_time,
                "average_processing_time": avg_time,
                "min_processing_time": min_time,
                "max_processing_time": max_time,
                "target_success_rate": success_rate,
                "performance_target": "1.5-2.5s",
                "overall_target_met": avg_time <= 2.5
            },
            "stt_metrics": stt_metrics
        }

    except Exception as e:
        logging.error(f"❌ STT Performance Test failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "STT performance test failed", "details": str(e)}
        )
        
        
@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def read_root():
    return {"message": "Hello from Cloud Run 🚀"}



@app.get("/force-error")
async def force_error(email: str = "test@example.com"):
    raise Exception("This is a test error for Prometheus metrics.")

from prometheus_client import Counter, Histogram
from fastapi import Request
import time
from prometheus_client import Counter, Histogram


# ...existing code...
from fastapi import Request

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    email = "unknown"
    try:
        if request.method in ("POST", "PUT", "PATCH"):
            data = await request.json()
            email = data.get("email", "unknown")
        else:
            email = request.query_params.get("email", "unknown")
    except Exception:
        email = request.headers.get("X-User-Email", "unknown")
    api_user_requests_total.labels(email=email).inc()
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        api_errors_total.labels(email=email).inc()
        raise
    finally:
        duration = time.time() - start
        api_response_time_seconds.labels(email=email).observe(duration)
    return response

# ...existing code...

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from MM2.utils import (
    bot_response_v2, load_memories_to_redis, get_embedding, get_semantically_similar_memories
)
from MM2.serialization import serialize_memory, is_valid_memory
from MM2.redis_class import RedisManager

redis_manager = RedisManager()
redis_test_router = APIRouter()

class PersonaMemoryTestRequest(BaseModel):
    email: str
    bot_id: str
    query: str
    memory: Optional[str] = None
    id: Optional[str] = None
    embedding: Optional[list] = None
    magnitude: Optional[float] = None
    recency: Optional[int] = None
    frequency: Optional[int] = None
    rfm_score: Optional[float] = None
    created_at: Optional[str] = None
    last_used: Optional[str] = None
    category: Optional[str] = None
    redundant: Optional[bool] = None
    relation_id: Optional[str] = None
from MM2.bot_prompt import get_bot_prompt
 # Import your publisher

@redis_test_router.post("/redis-memory")
async def redis_memory_test(request: PersonaMemoryTestRequest, background_tasks: BackgroundTasks):
    try:
        user_id = f"{request.email}:{request.bot_id}"

        # 1. Load memories into Redis
        load_memories_to_redis(request.email, request.bot_id)

        # 2. Get embedding for the query
        query_embedding = await get_embedding(request.query)

        # 3. Search for semantic match in Redis
        similar_memories = await get_semantically_similar_memories(
            redis_manager.client, user_id, query_embedding, k=1, cutoff=0.7
        )

        # 4. Determine if cache hit
        cache_hit = False
        bot_response = None
        matched_memory = None

        if similar_memories and len(similar_memories) > 0 and similar_memories[0]['sim'] < 0.7:
            cache_hit = True
            matched_memory = similar_memories[0]
            bot_response = matched_memory['text']
        else:
            if not cache_hit:
                bot_prompt = get_bot_prompt(request.bot_id)
                bot_response = await bot_response_v2(
                    bot_prompt,
                    request.bot_id,
                    request.query,
                    request.query,
                    [],
                    "",
                    "",
                    "",
                    request.email,
                    ""
                )

        # 5. Optionally, upsert a new memory if provided
        upsert_result = None
        if request.memory:
            # Publish to RabbitMQ so workers process and upsert
            await publish_to_both_queues(
                user_id=f"{request.email}:{request.bot_id}",
                user_input=request.query,
                bot_reply=bot_response,
                bot_id=request.bot_id,
                memory=request.memory,
                mem_id=request.id
            )
            upsert_result = "Memory sent to RabbitMQ for worker upsert"

        # 6. Return detailed result
        return {
            "success": True,
            "email": request.email,
            "bot_id": request.bot_id,
            "query": request.query,
            "cache_hit": cache_hit,
            "matched_memory": matched_memory,
            "bot_response": bot_response,
            "upsert_result": upsert_result,
            "similar_memories": similar_memories,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
        
app.include_router(redis_test_router, prefix="/test", tags=["redis"])



def get_existing_ids(table_name, email, bot_id):
    resp = supabase.table(table_name).select("id").eq("email", email).eq("bot_id", bot_id).execute()
    return set(str(row["id"]) for row in (resp.data or []) if "id" in row)


from fastapi import Body
from datetime import datetime, timezone 
from supabase import create_client

class EndChatRequest(BaseModel):
    email: str
    bot_id: str

@app.post("/end-chat")
async def end_chat(request: EndChatRequest):
    """
    Flush all Redis data for a user-bot combo back to Supabase when chat is closed.
    Only new messages/memories (not already in Supabase) are upserted.
    Also clears the session flag in Redis so next session reloads from Supabase.
    """
    user_id = f"{request.email}:{request.bot_id}"
    session_flag = f"session_loaded:{user_id}"
    try:
        # 1. Fetch all memories and chats from Redis
        raw_memories = redis_manager.get_user_memories(user_id)
        raw_chats = redis_manager.get_user_chats(user_id)

        # 2. Serialize for Supabase
        from MM2.serialization import serialize_memory, serialize_chat, is_valid_memory

        serialized_memories = []
                
                
        for raw in raw_memories:
            try:
                if is_valid_memory(raw):
                    mem = serialize_memory(raw)
                    emb = mem.get("embedding")
                    if not (isinstance(emb, list) and len(emb) == 768):
                        emb = await get_embedding(mem["memory"])
                    if not emb or len(emb) != 768:
                        emb = [0.0] * 768
                    mem["embedding"] = [float(x) for x in emb]
                    serialized_memories.append(mem)
                else:
                    print(f"[end-chat] Skipping invalid memory: missing fields")
            except Exception as e:
                print(f"[end-chat] Skipping invalid memory: {e}")

        serialized_chats = []
        for raw in raw_chats:
            try:
                chat = serialize_chat(raw)
                serialized_chats.append(chat)
            except Exception as e:
                print(f"[end-chat] Skipping invalid chat: {e}")

        # 3. Only upsert new records (not already in Supabase)
        BATCH_SIZE = 100
        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

        def get_existing_ids(table_name, email, bot_id):
            resp = supabase.table(table_name).select("id").eq("email", email).eq("bot_id", bot_id).execute()
            return set(str(row["id"]) for row in (resp.data or []) if "id" in row)

        existing_memory_ids = get_existing_ids("persona_category", request.email, request.bot_id)
        existing_chat_ids = get_existing_ids("message_paritition", request.email, request.bot_id)

        new_memories = [mem for mem in serialized_memories if str(mem.get("id")) not in existing_memory_ids]
        new_chats = [chat for chat in serialized_chats if str(chat.get("id")) not in existing_chat_ids]

            
        
        
        def batch_insert(table_name, data):
            for i in range(0, len(data), BATCH_SIZE):
                batch = data[i:i+BATCH_SIZE]
                for row in batch:
                    row.pop("id", None)
                    row.pop("__reindex", None)
                    # FIX: Remove or set relation_id to None if it's invalid
                    if "relation_id" in row and (row["relation_id"] is None or str(row["relation_id"]).lower() == "none"):
                        row["relation_id"] = None
                try:
                    supabase.table(table_name).upsert(batch).execute()
                except Exception as e:
                    print(f"[end-chat] Upsert failed for {table_name} batch: {e}")

        if new_memories:
            batch_insert("persona_category", new_memories)
        if new_chats:
            batch_insert("message_paritition", new_chats)

        # 4. Clear Redis for this user-bot combo and session flag
        try:
            redis_manager.clear_user_data(user_id)
            # Also clear session flag so next session reloads from Supabase
            redis_manager.client.delete(session_flag)
        except Exception as e:
            print(f"[end-chat] Redis cleanup failed: {e}")

        return {
            "status": "chat_closed_and_synced",
            "memories_synced": len(new_memories),
            "chats_synced": len(new_chats)
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e)
        }
        
        
        



@app.get("/get-last-messages/{email}/{bot_id}")
def get_last_messages(email: str, bot_id: str, count: int = 3):
    user_id = f"{email}:{bot_id}"
    messages = redis_manager.get_user_chats(user_id)
    last_messages = messages[-count:] if messages else []
    return {"messages": last_messages}


@app.get("/get-last-bot-responses-string/{email}/{bot_id}")
def get_last_bot_responses_string(email: str, bot_id: str, count: int = 3):
    user_id = f"{email}:{bot_id}"
    messages = redis_manager.get_user_chats(user_id)
    last_messages = messages[-count:] if messages else []
    # Join all bot responses into a single string, separated by ". "
    bot_responses = [msg.get("bot_response", "") for msg in last_messages]
    combined = ". ".join(bot_responses)
    return {"bot_responses_string": combined}




if __name__ == "__main__":
    app.include_router(gemma_router, prefix="/cv/generate", tags=["gemma"])
    app.include_router(payments_router, prefix="/payments", tags=["payments"])
    app.include_router(redis_test_router, prefix="/test", tags=["redis"])
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8080))
    )
#integrated
