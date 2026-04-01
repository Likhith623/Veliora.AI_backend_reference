import redis
import numpy as np
from datetime import datetime, timezone
import json
from dotenv import load_dotenv
import os
from MM2.memory_functions import normalize_memory_fields
from MM2.bot_prompt import get_bot_prompt
from MM2.memory_functions import normalize_memory_fields, clean_mem_id

load_dotenv()
#docker exec -it redis-stack redis-cli

class RedisManager:
    def __init__(self, host=None, port=None, db=0):
        host = host or os.environ.get('REDIS_HOST', 'localhost')
        port = port or int(os.environ.get('REDIS_PORT', 6379))
        db = db or int(os.environ.get('REDIS_DB', 0))
        self.client = redis.Redis(host=host, port=port, db=db)




    def store_memory(self, user_id, mem_id, memory_dict):
        key = f"memories:{user_id}:{mem_id}"
        mapping = {}
        
        print(f"🔧 REDIS DEBUG: Storing memory with key: {key}")
        print(f"🔧 REDIS DEBUG: Memory dict keys: {list(memory_dict.keys())}")
        
        for k, v in memory_dict.items():
            if k == 'embedding':
                # 🔧 CRITICAL FIX: Enhanced embedding handling for all formats
                if isinstance(v, bytes):
                    # Already in bytes format
                    mapping[k] = v
                    print(f"✅ REDIS DEBUG: Embedding already in bytes format")
                elif isinstance(v, list):
                    try:
                        # Convert list to FLOAT32 bytes
                        float_array = [float(x) for x in v]
                        if len(float_array) == 768:
                            mapping[k] = np.array(float_array, dtype=np.float32).tobytes()
                            print(f"✅ REDIS DEBUG: Converted list embedding to FLOAT32 bytes")
                        else:
                            print(f"❌ REDIS DEBUG: Invalid embedding length: {len(float_array)}, expected 768")
                            # Use default embedding
                            mapping[k] = np.array([0.0] * 768, dtype=np.float32).tobytes()
                    except Exception as e:
                        print(f"❌ REDIS DEBUG: Embedding conversion error: {e}")
                        mapping[k] = np.array([0.0] * 768, dtype=np.float32).tobytes()
                elif isinstance(v, np.ndarray):
                    try:
                        # Handle numpy array
                        if v.shape[0] == 768:
                            mapping[k] = v.astype(np.float32).tobytes()
                            print(f"✅ REDIS DEBUG: Converted numpy array to FLOAT32 bytes")
                        else:
                            print(f"❌ REDIS DEBUG: Invalid numpy array size: {v.shape[0]}")
                            mapping[k] = np.array([0.0] * 768, dtype=np.float32).tobytes()
                    except Exception as e:
                        print(f"❌ REDIS DEBUG: Numpy array conversion error: {e}")
                        mapping[k] = np.array([0.0] * 768, dtype=np.float32).tobytes()
                else:
                    try:
                        # Handle other formats (string, etc.)
                        if isinstance(v, str) and v.startswith('['):
                            # JSON string format
                            import json
                            parsed = json.loads(v)
                            mapping[k] = np.array(parsed, dtype=np.float32).tobytes()
                            print(f"✅ REDIS DEBUG: Converted JSON string embedding to bytes")
                        else:
                            # Use default embedding
                            mapping[k] = np.array([0.0] * 768, dtype=np.float32).tobytes()
                            print(f"⚠️ REDIS DEBUG: Using default embedding for unknown format")
                    except Exception as e:
                        print(f"❌ REDIS DEBUG: String parsing error: {e}")
                        mapping[k] = np.array([0.0] * 768, dtype=np.float32).tobytes()
            else:
                # Convert all other fields to strings for Redis storage
                mapping[k] = str(v) if not isinstance(v, str) else v
        
        try:
            self.client.hset(key, mapping=mapping)
            print(f"✅ REDIS DEBUG: Memory stored successfully in Redis with key: {key}")
            
            # Verify storage
            stored_data = self.client.hgetall(key)
            print(f"🔍 REDIS DEBUG: Verified storage - stored fields: {list(stored_data.keys())}")
            
        except Exception as e:
            print(f"❌ REDIS DEBUG: Failed to store memory in Redis: {e}")
            import traceback
            traceback.print_exc()
            raise



    def store_chat(self, user_id, chat_id, chat_dict):
        key = f"chat:{user_id}:{chat_id}"
        print(f"[DEBUG] store_chat key={key} mapping={chat_dict}")
        self.client.hset(key, mapping=chat_dict)
    
    def load_user_data(self, user_id, memories, chats):
        now = str(datetime.now(timezone.utc).timestamp())
        for mem in memories:
            mem_id = clean_mem_id(mem['id'])  # <-- FIX: always clean mem_id
            self.store_memory(user_id, mem_id, normalize_memory_fields(mem))
            key = f"memories:{user_id}:{mem_id}"
            self.client.hset(key, "__reindex", now)
        for chat in chats:
            chat_id = chat['id']
            self.store_chat(user_id, chat_id, chat)
            key = f"chat:{user_id}:{chat_id}"
            # Always update __reindex with a unique value
            self.client.hset(key, "__reindex", now)
    
    def get_user_memories(self, user_id):
        pattern = f"memories:{user_id}:*"
        keys = self.client.keys(pattern)
        memories = []
        for key in keys:
            mem = self.client.hgetall(key)
            decoded_mem = {}
            for k, v in mem.items():
                k = k.decode() if isinstance(k, bytes) else k
                if k == "embedding":
                    decoded_mem[k] = np.frombuffer(v, dtype=np.float32)
                else:
                    decoded_mem[k] = v.decode() if isinstance(v, bytes) else v
            decoded_mem["__redis_key__"] = key.decode() if isinstance(key, bytes) else key
            memories.append(decoded_mem)
        return memories

    def get_user_chats(self, user_id):
        pattern = f"chat:{user_id}:*"
        keys = self.client.keys(pattern)
        chats = []
        for key in keys:
            chat = self.client.hgetall(key)
            decoded_chat = {}
            for k, v in chat.items():
                k = k.decode() if isinstance(k, bytes) else k
                decoded_chat[k] = v.decode() if isinstance(v, bytes) else v
            decoded_chat["__redis_key__"] = key.decode() if isinstance(key, bytes) else key
            chats.append(decoded_chat)
        return chats
    
    def clear_user_data(self, user_id):
        # Remove all memory and chat keys for this user
        mem_keys = self.client.keys(f"memories:{user_id}:*")
        chat_keys = self.client.keys(f"chat:{user_id}:*")
        total_keys = mem_keys + chat_keys 
        decoded_keys = [key.decode('utf-8') for key in total_keys]
        if decoded_keys:
          self.client.delete(*decoded_keys)
        return len(total_keys)
    
    def has_user_data(self, user_id: str) -> bool:
        # Check if any memories or chats exist for this user_id in Redis
        mem_keys = list(self.client.scan_iter(f"memories:{user_id}:*"))
        chat_keys = list(self.client.scan_iter(f"chat:{user_id}:*"))
        return bool(mem_keys or chat_keys)

    def load_user_data(self, user_id, memories, chats):
        now = str(datetime.now(timezone.utc).timestamp())
        for mem in memories:
            mem_id = clean_mem_id(mem['id'])  # <-- FIX: always clean mem_id
            self.store_memory(user_id, mem_id, normalize_memory_fields(mem))
            key = f"memories:{user_id}:{mem_id}"
            self.client.hset(key, "__reindex", now)
        for chat in chats:
            chat_id = chat['id']
            self.store_chat(user_id, chat_id, chat)
            key = f"chat:{user_id}:{chat_id}"
            # Always update __reindex with a unique value
            self.client.hset(key, "__reindex", now)