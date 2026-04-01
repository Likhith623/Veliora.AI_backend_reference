import numpy as np
import re
from datetime import datetime, timezone 
from MM2.bot_prompt import get_bot_prompt
REQUIRED_MEMORY_FIELDS = [
    "id", "email", "bot_id", "memory", "embedding", "magnitude",
    "recency", "frequency", "rfm_score", "created_at"
]

EMB_DIM = 768
def serialize_memory(mem):
    # Converts a memory dict for safe Supabase upsert
    serialized = {}
    field_map = {
        "user_id": "email",
        "memory_text": "memory"
    }
    for k, v in mem.items():
        k = field_map.get(k, k)
        if k == "embedding":
            if isinstance(v, np.ndarray):
                serialized[k] = v.tolist()
            else:
                serialized[k] = v
        elif k != "__redis_key__":
            serialized[k] = v
    return serialized

def serialize_chat(chat):
    # Extract email and bot_id from user_id BEFORE removing it
    if "email" not in chat or "bot_id" not in chat:
        if "user_id" in chat:
            parts = chat["user_id"].split(":", 1)
            chat["email"] = parts[0]
            chat["bot_id"] = parts[1] if len(parts) > 1 else ""
    # Remove __redis_key__ and user_id
    chat = {k: v for k, v in chat.items() if k not in ["__redis_key__", "user_id"]}
    # Ensure all required fields are present
    now_iso = datetime.now(timezone.utc).isoformat()
    if "created_at" not in chat or not chat["created_at"]:
        chat["created_at"] = now_iso
    if "timestamp" not in chat or not chat["timestamp"]:
        chat["timestamp"] = chat["created_at"]
    for field in ["requested_time", "platform", "activity_name"]:
        if field not in chat:
            chat[field] = ""
    for field in ["user_message", "bot_response"]:
        if field not in chat:
            chat[field] = ""
    # id: if missing, let Supabase auto-generate
    if "id" not in chat and "chat_id" in chat:
        chat["id"] = chat["chat_id"]
    # If id is still missing, do NOT set it (let Supabase generate)
    return chat

import numpy as np
 
def is_valid_memory(mem):
    """Enhanced memory validation with better error handling and flexible field checking"""
    required_fields = [
        ("id",),  # Must have id
        ("email", "user_id"),  # Must have either email or user_id
        ("bot_id",),  # Must have bot_id
        ("memory", "memory_text"),  # Must have either memory or memory_text
        ("embedding",),  # Must have embedding
        ("magnitude",),  # Must have magnitude
        ("recency",),  # Must have recency
        ("frequency",),  # Must have frequency
        ("rfm_score",),  # Must have rfm_score
        ("created_at",)  # Must have created_at
    ]
    
    print(f"🔍 VALIDATION: Checking memory with fields: {list(mem.keys())}")
    
    for i, field_group in enumerate(required_fields):
        found = False
        for f in field_group:
            if f in mem:
                v = mem[f]
                # Check if the field has a valid value
                if isinstance(v, np.ndarray):
                    if v.size > 0:
                        found = True
                        break
                elif isinstance(v, list):
                    if len(v) > 0:
                        found = True
                        break
                elif v not in [None, "", "null", "NULL"]:
                    found = True
                    break
        
        if not found:
            print(f"❌ VALIDATION: Missing required field group {field_group}")
            return False
        else:
            print(f"✅ VALIDATION: Found valid field from group {field_group}")
    
    # 🔧 CRITICAL FIX: Enhanced embedding validation
    emb = mem.get("embedding")
    print(f"🔍 VALIDATION: Embedding type: {type(emb)}, length: {len(emb) if isinstance(emb, (list, np.ndarray)) else 'N/A'}")
    
    if isinstance(emb, np.ndarray):
        if emb.size != EMB_DIM:
            print(f"❌ VALIDATION: Embedding array size {emb.size} != {EMB_DIM}")
            return False
    elif isinstance(emb, list):
        if len(emb) != EMB_DIM:
            print(f"❌ VALIDATION: Embedding list length {len(emb)} != {EMB_DIM}")
            return False
        # Check if all elements are numeric
        try:
            [float(x) for x in emb]
        except (TypeError, ValueError):
            print(f"❌ VALIDATION: Embedding contains non-numeric values")
            return False
    else:
        print(f"❌ VALIDATION: Embedding is not list or array: {type(emb)}")
        return False
    
    # 🔧 CRITICAL FIX: Validate numeric fields
    try:
        magnitude = mem.get("magnitude", 0)
        frequency = mem.get("frequency", 0)
        rfm_score = mem.get("rfm_score", 0)
        
        float(magnitude)
        int(frequency)
        float(rfm_score)
        
        print("✅ VALIDATION: All numeric fields validated successfully")
    except (TypeError, ValueError) as e:
        print(f"❌ VALIDATION: Numeric field validation failed: {e}")
        print(f"   magnitude: {mem.get('magnitude')} (type: {type(mem.get('magnitude'))})")
        print(f"   frequency: {mem.get('frequency')} (type: {type(mem.get('frequency'))})")
        print(f"   rfm_score: {mem.get('rfm_score')} (type: {type(mem.get('rfm_score'))})")
        return False
    
    print("✅ VALIDATION: Memory passed all validations")
    return True