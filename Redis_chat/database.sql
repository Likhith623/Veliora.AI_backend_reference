-- chat_message_logs
create table public.chat_message_logs (
  id uuid primary key default gen_random_uuid (),
  user_id text not null,
  user_message text,
  bot_response text,
  timestamp timestamp with time zone default now()
);


-- persona_category
create table public.persona_category (
  id uuid primary key default gen_random_uuid (),
  user_id text not null,
  memory_text text,
  embedding public.vector,
  created_at timestamp with time zone default now(),
  last_used timestamp with time zone default now(),
  frequency integer default 1,
  magnitude real,
  rfm_score real
);


-- HNSW Index for vector search:
create index if not exists persona_category_embedding_hnsw_idx 
on public.persona_category using hnsw (embedding vector_cosine_ops)
with (m = '16', ef_construction = '64');



















