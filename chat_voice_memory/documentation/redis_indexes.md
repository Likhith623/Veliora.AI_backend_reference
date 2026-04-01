Issue Documentation – Redis Index Flushing in VM
Background

In our chatbot application, Redis is used as the in-memory database and vector search backend. We created two indexes in Redis:

chats_idx – Stores and indexes chat history for fast retrieval.

memories_idx – Stores and indexes user memories, including embeddings for semantic search.

These indexes are created using RediSearch (FT.CREATE) commands.

Problem

When running the application on the VM, Redis indexes were being automatically removed after some time.
This issue was noticed because:

Search queries started failing with "index not found" errors.

Manual inspection with FT._LIST showed that previously created indexes no longer existed.

Cause

Redis is in-memory by default, meaning:

If Redis is restarted, data and indexes are lost unless persistence is explicitly enabled (RDB or AOF).

In cloud/VM environments, Redis instances can restart or flush data due to:

Memory eviction policies (volatile-lru, allkeys-lru, etc.)

Manual or automatic restarts by the VM.

No persistence configuration (appendonly / save disabled).

Since RediSearch indexes are stored in Redis memory, they are lost during such events.

Impact

If indexes are missing, all search functionality in the chatbot breaks.

Memory retrieval and chat history queries fail.

Application response times increase due to fallback operations or error handling.

Solution Implemented

We created a indexes.py script that:

Connects to Redis.

Checks if required indexes (chats_idx and memories_idx) exist.

Creates them only if they do not exist.

We then set up a cron job to run this script every 10 minutes.
This ensures that:

If Redis indexes are flushed or lost for any reason, they are automatically recreated.

If indexes already exist, no changes are made (avoiding duplication errors).

Technical Implementation
1. Script: indexes.py

Key features:

Uses redis-py to connect to Redis.

Loads environment variables from .env for connection details.

Checks existing indexes using:

existing_indexes = client.execute_command('FT._LIST')


Creates missing indexes with FT.CREATE and appropriate schema definitions:

chats_idx schema:

user_message – TEXT

bot_response – TEXT

user_id – TAG

timestamp – TEXT

memories_idx schema:

user_id – TAG

memory_text – TEXT

embedding – VECTOR (HNSW, 768 dims, cosine similarity)

Numeric and date fields for metadata.

Prints clear logs for:

Connection status

Index creation success/failure

Final list of indexes after execution

2. Cron Job Setup

To automate index recreation:

*/10 * * * * /usr/bin/python3 /path/to/indexes.py >> /var/log/redis_index_creation.log 2>&1


Runs every 10 minutes (*/10 * * * *).

Appends logs to /var/log/redis_index_creation.log for monitoring.

Works silently if indexes already exist.

Why This Fix Works

Idempotent: Safe to run repeatedly without duplication.

Self-Healing: Automatically repairs missing indexes without manual intervention.

Low Overhead: Checking index existence is lightweight.

Logs for Debugging: Every run is logged, so if indexes are repeatedly disappearing, we can investigate Redis persistence and memory settings.

Future Recommendations

Enable Redis persistence (appendonly yes or save options) to prevent index loss after restart.

Monitor Redis memory usage to avoid eviction.

Consider deploying Redis with a managed service (like Redis Cloud or AWS ElastiCache) for better reliability.

Add alerting if indexes are recreated too often (indicating an underlying stability issue).

✅ Final Outcome:
With this setup, even if Redis flushes indexes, they are recreated within 10 minutes automatically, ensuring the chatbot remains functional without manual recovery steps.
