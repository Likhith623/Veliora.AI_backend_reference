from google import genai
import os
import time
import asyncio
from MM2.memory_functions import fetch_last_m_messages, get_semantically_similar_memories, get_highest_rfm_memories, get_embedding, time_ago_human
from supabase import create_client
from MM2.redis_class import RedisManager
redis_manager = RedisManager()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

from datetime import datetime, timezone
from MM2.serialization import is_valid_memory

def load_memories_to_redis(email: str, bot_id: str):
    from supabase import create_client
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    memories = supabase.table("persona_category").select("*").eq("email", email).eq("bot_id", bot_id).execute().data
    valid_memories = []
    for m in memories:
        if is_valid_memory(m):
            m = dict(m)
            if "memory" in m:
                m["memory_text"] = m.pop("memory")
            if "email" in m:
                m["user_id"] = m.pop("email")
            valid_memories.append(m)
    # Always call load_user_data, even if valid_memories is empty
    redis_manager.load_user_data(f"{email}:{bot_id}", valid_memories, [])
    # No error should be raised if valid_memories is empty

async def get_bot_response_from_memory(redis_manager, email: str, bot_id: str, user_input: str) -> dict:
    # Ensure memories are loaded for this user-bot combo
    load_memories_to_redis(redis_manager, email, bot_id)
    user_id = f"{email}:{bot_id}"

    embedding_time = time.perf_counter()
    input_embedding = await get_embedding(user_input)
    embedding_elapsed = time.perf_counter() - embedding_time
    fetch_start = time.perf_counter()
    # 1. Fetch recent chat history
    recent_task = fetch_last_m_messages(redis_manager.client, user_id, m=10)
    # 2. Retrieve top-5 semantically similar memories
    semantic_task = get_semantically_similar_memories(redis_manager.client, user_id, input_embedding, cutoff=0)
    recent, semantic = await asyncio.gather(recent_task, semantic_task)
    fetch_elapsed = time.perf_counter() - fetch_start

    semantic_block = "\n\n".join(
        f"{mem['text']}| Similarity score:{mem['sim']} | Temporal relevance: added {time_ago_human(mem['created_at'])}, last retrieved {time_ago_human(mem['last_used'])}"
        for mem in semantic
    ) if semantic else "No relevant memories found."

    history_block = "\n\n".join(
        [f"Timestamp: {r['timestamp']}\nUser: {r['user_message']}\nBot: {r['bot_response']}" for r in recent]
    ) if recent else "No recent chat history found."

    prompt = f"""
You are an engaging, friendly, and attentive conversational assistant. Your goal is to provide helpful, specific, and context-aware responses that feel natural and human.

**Your personality:** Curious, empathetic, and adaptive. Match the user's tone and energy. Use humor or encouragement when appropriate.

**Your tools:**
- Semantically relevant memories: Use these to recall user preferences, experiences, or facts.
- Recent chat history: Maintain conversational flow and continuity.

**Instructions:**
- Reference relevant memories if helpful to personalize your response.
- Build on the ongoing conversation, referencing previous messages like you are in a conversation.
- If you’re unsure, ask a clarifying question or offer a thoughtful suggestion.
- Avoid generic or repetitive answers from recent chat, only build on it; be as specific and vivid as possible.
- Respond in a warm, conversational tone. Do not mention that you are an AI.

**Context:**
Recent Chat:
{history_block}

Semantically Relevant Memories:
{semantic_block}

Current User Input:
{user_input}

Respond to the user now.
"""
    response_start = time.perf_counter()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    response_elapsed = time.perf_counter() - response_start

    # If no memory found, fallback to a normal response (no semantic_block)
    if not semantic:
        prompt = f"""
You are an engaging, friendly, and attentive conversational assistant. Your goal is to provide helpful, specific, and context-aware responses that feel natural and human.

Recent Chat:
{history_block}

Current User Input:
{user_input}

Respond to the user now.
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

    return {
        'response': response.text.strip(),
        'fetch_time': fetch_elapsed,
        'response_time': response_elapsed,
        'embeddings_time': embedding_elapsed,
        'memories_retrieved': {'semantic': semantic_block}
    }

async def get_bot_response_rfm(redis_manager, email: str, bot_id: str, user_input: str) -> dict:
    # Ensure memories are loaded for this user-bot combo
    load_memories_to_redis(redis_manager, email, bot_id)
    user_id = f"{email}:{bot_id}"

    fetch_start = time.perf_counter()
    # 1. Fetch recent chat history
    recent_task = fetch_last_m_messages(redis_manager.client, user_id, m=10)

    # 2. Fetch top 3 highest RFM score memories
    rfm_task = get_highest_rfm_memories(redis_manager.client, user_id)
    
    recent, rfm_memories = await asyncio.gather(recent_task, rfm_task)
    fetch_elapsed = time.perf_counter() - fetch_start

    rfm_block = (
        "\n\n".join(f"{mem['text']} | RFM score:{mem['rfm_score']} "
    for mem in rfm_memories)
        if rfm_memories else "No high-RFM memories available."
    )

    history_block = "\n\n".join(
        [f"Timestamp: {r['timestamp']}\nUser: {r['user_message']}\nBot: {r['bot_response']}" for r in recent]
    ) if recent else "No recent chat history found."

    # Create RFM-aware prompt
    prompt = f"""
You are an engaging, helpful assistant with a strong memory for what matters most to the user. Your responses should be context-aware, specific, and feel genuinely conversational.

**Your personality:** Friendly, supportive, and attentive to details the user cares about.

**Your tools:**
- High-RFM memories: Use these to understand what is most important and frequently discussed by the user.
- Recent chat history: Reference previous exchanges to maintain continuity.

**Instructions:**
- Use high-RFM memories to ground your response in the user's top interests, needs, or concerns.
- Reference recent chat to maintain flow and context.
- Be specific, avoid generic statements, and personalize your reply.
- If appropriate, ask a thoughtful follow-up question or offer a relevant suggestion.
- Maintain a warm, conversational tone. Do not mention that you are an AI.

**Context:**
Recent Chat:
{history_block}

Important Memories (ranked by RFM):
{rfm_block}

Current User Input:
{user_input}

Respond to the user now.
"""

    response_start = time.perf_counter()
    # 4. Generate the response
    response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)
    response_elapsed = time.perf_counter() - response_start

    # If no RFM memory found, fallback to a normal response (no rfm_block)
    if not rfm_memories:
        prompt = f"""
You are an engaging, helpful assistant. Provide a response based on the recent chat history.

Recent Chat:
{history_block}

Current User Input:
{user_input}

Respond to the user now.
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

    return {'response':response.text.strip(), 'fetch_time':fetch_elapsed, 'response_time': response_elapsed, 'memories_retrieved':{'rfm': rfm_block}}

async def get_bot_response_combined(redis_manager, email: str, bot_id: str, user_input: str) -> dict:
    # Ensure memories are loaded for this user-bot combo
    load_memories_to_redis(redis_manager, email, bot_id)
    user_id = f"{email}:{bot_id}"

    embedding_time = time.perf_counter()
    input_embedding = await get_embedding(user_input)
    embedding_elapsed = time.perf_counter() - embedding_time
    fetch_start = time.perf_counter()
    # 1. Fetch recent chat history
    recent_task = fetch_last_m_messages(redis_manager.client, user_id, m=10)
    # 2. Fetch top RFM memories
    rfm_task = get_highest_rfm_memories(redis_manager.client, user_id)

    # 3. Fetch top semantic memories based on current user input
    semantic_task = get_semantically_similar_memories(redis_manager.client, user_id, input_embedding, cutoff = 0.4)
    
    recent, rfm, semantic = await asyncio.gather(recent_task, rfm_task, semantic_task)

    fetch_elapsed = time.perf_counter() - fetch_start
    # === Format memory blocks ===
    rfm_block = (
        "\n\n".join(f"{mem['text']} | RFM score:{mem['rfm_score']} "
    for mem in rfm)
        if rfm else "No high-RFM memories available."
    )
    
    semantic_block = "\n\n".join(
    f"{mem['text']}| Similarity score:{mem['sim']} | Temporal relevance: added {time_ago_human(mem['created_at'])}, last retrieved {time_ago_human(mem['last_used'])}"
    for mem in semantic
) if semantic else "No semantically similar memories found."

    history_block = "\n\n".join(
        [f"Timestamp: {r['timestamp']}\nUser: {r['user_message']}\nBot: {r['bot_response']}" for r in recent]
    ) if recent else "No recent chat history found."

    # Create comprehensive prompt
    prompt = f"""You are an engaging, friendly, and attentive conversational assistant. Your goal is to provide helpful, specific, and context-aware responses that feel natural and human.

**Your personality:** Curious, empathetic, and adaptive. Match the user's tone and energy. Use humor or encouragement when appropriate.

**Your tools:**
- Semantically relevant memories: Use these to recall user preferences, experiences, or facts.
- High-RFM memories: Use these to understand what matters most to the user.
- Recent chat history: Maintain conversational flow and continuity.

**Instructions:**
- Reference relevant memories if helpful to personalize your response.
- Build on the ongoing conversation, referencing previous messages like you are in a conversation.
- If you’re unsure, ask a clarifying question or offer a thoughtful suggestion.
- Avoid generic or repetitive answers from recent chat, only build on it; be as specific and vivid as possible.
- Respond in a warm, conversational tone. Do not mention that you are an AI. Sound like youre speaking in a natural conversation.

**Context:**
Recent Chat:
{history_block}

Semantically Relevant Memories:
{semantic_block}

Important Memories (ranked by Recency, Frequency, Magnitude score):
{rfm_block}

Current User Input:
{user_input}

Respond to the user now.
 """

    response_start = time.perf_counter()
    # 4. Generate response using Gemini
    response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)
    response_elapsed = time.perf_counter() - response_start

    # If no memories found, fallback to a normal response
    if not recent and not rfm and not semantic:
        prompt = f"""
You are an engaging, friendly, and attentive conversational assistant. Your goal is to provide helpful, specific, and context-aware responses that feel natural and human.

Current User Input:
{user_input}

Respond to the user now.
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

    return {'response':response.text.strip(), 'fetch_time': fetch_elapsed,'embedding_time':embedding_elapsed, 'response_time':response_elapsed, 'memories_retrieved':{'semantic':semantic_block, 'rfm': rfm_block}}


