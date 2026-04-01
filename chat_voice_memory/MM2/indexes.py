import redis
import os
from dotenv import load_dotenv

load_dotenv()

def create_redis_indexes():
    """Create required Redis indexes for the chatbot application"""
    
    redis_host = os.getenv('REDIS_HOST', '34.131.107.77')
    redis_port = int(os.getenv('REDIS_PORT', 6379))

    print(f"Connecting to Redis at {redis_host}:{redis_port}...")
    
    try:
        client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        client.ping()
        print("✅ Connected to Redis successfully")

        # Get list of existing indexes
        try:
            existing_indexes = client.execute_command('FT._LIST')
        except redis.ResponseError:
            existing_indexes = []
        
        # --- Create chats_idx ---
        if 'chats_idx' in existing_indexes:
            print("⚠️  chats_idx already exists")
        else:
            print("Creating chats_idx...")
            try:
                client.execute_command(
                    'FT.CREATE', 'chats_idx', 
                    'ON', 'HASH', 
                    'PREFIX', '1', 'chat:', 
                    'SCHEMA', 
                    'user_message', 'TEXT', 'WEIGHT', '1',
                    'bot_response', 'TEXT', 'WEIGHT', '1',
                    'user_id', 'TAG', 'SEPARATOR', ',',
                    'timestamp', 'TEXT', 'WEIGHT', '1'
                )
                print("✅ chats_idx created successfully")
            except redis.ResponseError as e:
                print(f"❌ Failed to create chats_idx: {e}")

        # --- Create memories_idx ---
        if 'memories_idx' in existing_indexes:
            print("⚠️  memories_idx already exists")
        else:
            print("Creating memories_idx...")
            try:
                client.execute_command(
                    'FT.CREATE', 'memories_idx',
                    'ON', 'HASH',
                    'PREFIX', '1', 'memories:',
                    'SCHEMA',
                    'user_id', 'TAG', 'SEPARATOR', ',',
                    'memory_text', 'TEXT', 'WEIGHT', '1',
                    'embedding', 'VECTOR', 'HNSW', '10', 'TYPE', 'FLOAT32', 'DIM', '768', 'DISTANCE_METRIC', 'COSINE', 'M', '16', 'EF_CONSTRUCTION', '200',
                    'rfm_score', 'NUMERIC',
                    'magnitude', 'NUMERIC',
                    'frequency', 'NUMERIC',
                    'created_at', 'TEXT', 'WEIGHT', '1',
                    'last_used', 'TEXT', 'WEIGHT', '1'
                )
                print("✅ memories_idx created successfully")
            except redis.ResponseError as e:
                print(f"❌ Failed to create memories_idx: {e}")

        # Final confirmation
        print("\nVerifying created indexes...")
        indexes = client.execute_command('FT._LIST')
        print(f"Available indexes: {indexes}")
        print("\n🎉 Redis index creation completed!")

    except redis.ConnectionError:
        print(f"❌ Failed to connect to Redis at {redis_host}:{redis_port}")
        print("Please check if Redis is running and the connection details are correct")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    create_redis_indexes()
