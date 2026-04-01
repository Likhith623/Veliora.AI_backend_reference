-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.blog_posts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  title text NOT NULL,
  slug text NOT NULL UNIQUE,
  content text NOT NULL,
  excerpt text,
  tags ARRAY DEFAULT '{}'::text[],
  publish_date date NOT NULL DEFAULT CURRENT_DATE,
  status text NOT NULL DEFAULT 'draft'::text CHECK (status = ANY (ARRAY['draft'::text, 'published'::text, 'archived'::text])),
  author_email text NOT NULL,
  featured_image_url text,
  additional_images ARRAY DEFAULT '{}'::text[],
  view_count integer DEFAULT 0,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT blog_posts_pkey PRIMARY KEY (id)
);
CREATE TABLE public.bot_personality_details (
  bot_id text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_name text,
  bot_city text,
  bot_country text,
  bot_gender text,
  bot_user_relation text,
  CONSTRAINT bot_personality_details_pkey PRIMARY KEY (bot_id)
);
CREATE TABLE public.categorization_progress (
  email text NOT NULL,
  bot_id text NOT NULL,
  last_processed_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT categorization_progress_pkey PRIMARY KEY (email, bot_id)
);
CREATE TABLE public.chat_message_logs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id text NOT NULL,
  user_message text,
  bot_response text,
  timestamp timestamp with time zone DEFAULT now(),
  CONSTRAINT chat_message_logs_pkey PRIMARY KEY (id)
);
CREATE TABLE public.conversations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  bot_id character varying NOT NULL,
  user_email character varying NOT NULL,
  username character varying DEFAULT 'User'::character varying,
  user_message text NOT NULL,
  previous_conversation text,
  image_url text,
  image_base64 text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT conversations_pkey PRIMARY KEY (id)
);
CREATE TABLE public.delta_category (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  email text NOT NULL,
  bot_id text NOT NULL,
  message1 text NOT NULL,
  message2 text NOT NULL,
  relation text NOT NULL,
  category text NOT NULL,
  output text,
  timestamp timestamp with time zone NOT NULL DEFAULT now(),
  message1_id uuid,
  message2_id uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT delta_category_pkey PRIMARY KEY (id)
);
CREATE TABLE public.emotion_contexts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  conversation_id uuid,
  emotion character varying,
  location character varying,
  action character varying,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT emotion_contexts_pkey PRIMARY KEY (id),
  CONSTRAINT emotion_contexts_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id)
);
CREATE TABLE public.frontend_error_logs (
  message text NOT NULL,
  source character varying NOT NULL,
  line_number integer,
  column_number integer,
  stack_trace text,
  browser character varying,
  url character varying,
  additional_context text,
  timestamp timestamp with time zone
);
CREATE TABLE public.image_interpreter (
  id integer NOT NULL DEFAULT nextval('image_interpreter_id_seq'::regclass),
  bot_id character varying NOT NULL,
  image_base64 text NOT NULL,
  image_description text,
  image_summary text,
  final_response text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT image_interpreter_pkey PRIMARY KEY (id)
);
CREATE TABLE public.last_cat_message (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  email text,
  message_id text,
  bot_id text,
  morning_message text DEFAULT ''::text,
  CONSTRAINT last_cat_message_pkey PRIMARY KEY (id)
);
CREATE TABLE public.log_messages_with_like_dislike (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  user_email text DEFAULT ''::text,
  bot_id text DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  feedback text DEFAULT ''::text,
  last_5_messages text DEFAULT ''::text,
  memory_retrieved text DEFAULT ''::text,
  memory_extracted text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT log_messages_with_like_dislike_pkey PRIMARY KEY (id)
);
CREATE TABLE public.message_paritition (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  email text NOT NULL DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_id text DEFAULT ''::text,
  requested_time text DEFAULT ''::text,
  platform text DEFAULT ''::text,
  activity_name text DEFAULT ''::text,
  timestamp timestamp with time zone DEFAULT now(),
  CONSTRAINT message_paritition_pkey PRIMARY KEY (id, email)
);
CREATE TABLE public.message_paritition_0 (
  id bigint NOT NULL,
  email text NOT NULL DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_id text DEFAULT ''::text,
  requested_time text DEFAULT ''::text,
  platform text DEFAULT ''::text,
  activity_name text DEFAULT ''::text,
  timestamp timestamp with time zone DEFAULT now(),
  CONSTRAINT message_paritition_0_pkey PRIMARY KEY (id, email)
);
CREATE TABLE public.message_paritition_1 (
  id bigint NOT NULL,
  email text NOT NULL DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_id text DEFAULT ''::text,
  requested_time text DEFAULT ''::text,
  platform text DEFAULT ''::text,
  activity_name text DEFAULT ''::text,
  timestamp timestamp with time zone DEFAULT now(),
  CONSTRAINT message_paritition_1_pkey PRIMARY KEY (id, email)
);
CREATE TABLE public.message_paritition_2 (
  id bigint NOT NULL,
  email text NOT NULL DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_id text DEFAULT ''::text,
  requested_time text DEFAULT ''::text,
  platform text DEFAULT ''::text,
  activity_name text DEFAULT ''::text,
  timestamp timestamp with time zone DEFAULT now(),
  CONSTRAINT message_paritition_2_pkey PRIMARY KEY (id, email)
);
CREATE TABLE public.message_paritition_3 (
  id bigint NOT NULL,
  email text NOT NULL DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_id text DEFAULT ''::text,
  requested_time text DEFAULT ''::text,
  platform text DEFAULT ''::text,
  activity_name text DEFAULT ''::text,
  timestamp timestamp with time zone DEFAULT now(),
  CONSTRAINT message_paritition_3_pkey PRIMARY KEY (id, email)
);
CREATE TABLE public.message_paritition_4 (
  id bigint NOT NULL,
  email text NOT NULL DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_id text DEFAULT ''::text,
  requested_time text DEFAULT ''::text,
  platform text DEFAULT ''::text,
  activity_name text DEFAULT ''::text,
  timestamp timestamp with time zone DEFAULT now(),
  CONSTRAINT message_paritition_4_pkey PRIMARY KEY (id, email)
);
CREATE TABLE public.message_paritition_5 (
  id bigint NOT NULL,
  email text NOT NULL DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_id text DEFAULT ''::text,
  requested_time text DEFAULT ''::text,
  platform text DEFAULT ''::text,
  activity_name text DEFAULT ''::text,
  timestamp timestamp with time zone DEFAULT now(),
  CONSTRAINT message_paritition_5_pkey PRIMARY KEY (id, email)
);
CREATE TABLE public.message_paritition_6 (
  id bigint NOT NULL,
  email text NOT NULL DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_id text DEFAULT ''::text,
  requested_time text DEFAULT ''::text,
  platform text DEFAULT ''::text,
  activity_name text DEFAULT ''::text,
  timestamp timestamp with time zone DEFAULT now(),
  CONSTRAINT message_paritition_6_pkey PRIMARY KEY (id, email)
);
CREATE TABLE public.message_paritition_7 (
  id bigint NOT NULL,
  email text NOT NULL DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_id text DEFAULT ''::text,
  requested_time text DEFAULT ''::text,
  platform text DEFAULT ''::text,
  activity_name text DEFAULT ''::text,
  timestamp timestamp with time zone DEFAULT now(),
  CONSTRAINT message_paritition_7_pkey PRIMARY KEY (id, email)
);
CREATE TABLE public.message_paritition_8 (
  id bigint NOT NULL,
  email text NOT NULL DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_id text DEFAULT ''::text,
  requested_time text DEFAULT ''::text,
  platform text DEFAULT ''::text,
  activity_name text DEFAULT ''::text,
  timestamp timestamp with time zone DEFAULT now(),
  CONSTRAINT message_paritition_8_pkey PRIMARY KEY (id, email)
);
CREATE TABLE public.message_paritition_9 (
  id bigint NOT NULL,
  email text NOT NULL DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_id text DEFAULT ''::text,
  requested_time text DEFAULT ''::text,
  platform text DEFAULT ''::text,
  activity_name text DEFAULT ''::text,
  timestamp timestamp with time zone DEFAULT now(),
  CONSTRAINT message_paritition_9_pkey PRIMARY KEY (id, email)
);
CREATE TABLE public.messages (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  email text DEFAULT ''::text,
  user_message text DEFAULT ''::text,
  bot_response text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  bot_id text DEFAULT ''::text,
  requested_time text DEFAULT ''::text,
  platform text,
  CONSTRAINT messages_pkey PRIMARY KEY (id)
);
CREATE TABLE public.notes (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  notes text DEFAULT ''::text,
  email text,
  bot_id text,
  extracted_data text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT notes_pkey PRIMARY KEY (id)
);
CREATE TABLE public.payment_transactions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  stripe_session_id text NOT NULL UNIQUE,
  user_id uuid NOT NULL,
  stripe_customer_id text NOT NULL,
  price_id text NOT NULL,
  payment_amount numeric,
  processed_at timestamp with time zone DEFAULT now(),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT payment_transactions_pkey PRIMARY KEY (id),
  CONSTRAINT payment_transactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.user_details(id)
);
CREATE TABLE public.persona_category (
  email text NOT NULL,
  bot_id text NOT NULL,
  category text,
  memory text,
  created_at timestamp with time zone DEFAULT now(),
  redundant boolean DEFAULT false,
  id integer NOT NULL DEFAULT nextval('persona_category_id_seq'::regclass),
  relation_id uuid,
  embedding USER-DEFINED,
  magnitude real,
  recency smallint,
  frequency integer NOT NULL DEFAULT 1,
  rfm_score real,
  CONSTRAINT persona_category_pkey PRIMARY KEY (id)
);
CREATE TABLE public.persona_category_2 (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id text NOT NULL,
  memory_text text,
  embedding USER-DEFINED,
  created_at timestamp with time zone DEFAULT now(),
  last_used timestamp with time zone DEFAULT now(),
  frequency integer DEFAULT 1,
  magnitude real,
  rfm_score real,
  CONSTRAINT persona_category_2_pkey PRIMARY KEY (id)
);
CREATE TABLE public.proactive_messages (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  message text DEFAULT ''::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT proactive_messages_pkey PRIMARY KEY (id)
);
CREATE TABLE public.retrieve_memory_data (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  previous_conversations text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  extracted_data text,
  email text,
  bot_id text,
  CONSTRAINT retrieve_memory_data_pkey PRIMARY KEY (id)
);
CREATE TABLE public.scheduler (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  email text,
  bot_id text,
  message text,
  scheduled_time timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  user_timezone_offset text DEFAULT ''::text
);
CREATE TABLE public.summary (
  email character varying NOT NULL,
  bot_id text NOT NULL,
  generated_summary text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  summary_date date
);
CREATE TABLE public.todos (
  id integer NOT NULL DEFAULT nextval('todos_id_seq'::regclass),
  name text NOT NULL,
  CONSTRAINT todos_pkey PRIMARY KEY (id)
);
CREATE TABLE public.user_details (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  email text UNIQUE,
  user_id uuid,
  name text NOT NULL,
  gender text CHECK (gender = ANY (ARRAY['Male'::text, 'Female'::text, 'Other'::text])),
  city text,
  created_at timestamp without time zone DEFAULT now(),
  auth_provider text,
  subscription_status text NOT NULL DEFAULT 'Free trial'::text,
  subscription_duration text,
  payment_date date,
  payment_amount numeric,
  subscription_expires_at date,
  stripe_customer_id text UNIQUE,
  current_plan text,
  role text DEFAULT 'user'::text CHECK (role = ANY (ARRAY['user'::text, 'admin'::text])),
  timezone text DEFAULT 'UTC'::text,
  CONSTRAINT user_details_pkey PRIMARY KEY (id),
  CONSTRAINT user_details_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.user_xp (
  id bigint NOT NULL DEFAULT nextval('user_xp_id_seq'::regclass),
  email text NOT NULL,
  bot_id text,
  xp_score integer DEFAULT 0,
  coins integer DEFAULT 0,
  magnitude double precision DEFAULT 0,
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT user_xp_pkey PRIMARY KEY (id)
);
