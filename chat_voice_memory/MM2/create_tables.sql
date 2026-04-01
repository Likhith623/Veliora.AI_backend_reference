CREATE TABLE last_cat_message_ISB_Dlabs (
    id BIGINT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE,
    email TEXT,
    message_id TEXT,
    bot_id TEXT
);

CREATE TABLE notes_ISB_Dlabs (
    id BIGINT PRIMARY KEY,
    notes TEXT,
    email TEXT,
    bot_id TEXT,
    extracted_data TEXT,
    created_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE log_messages_with_like_dislike_ISB_Dlabs (
    id BIGINT PRIMARY KEY,
    user_email TEXT,
    bot_id TEXT,
    user_message TEXT,
    bot_response TEXT,
    feedback TEXT,
    last_5_messages TEXT,
    memory_retrieved TEXT,
    memory_extracted TEXT,
    created_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE retrieve_memory_data_ISB_Dlabs (
    id BIGINT PRIMARY KEY,
    previous_conversations TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    extracted_data TEXT,
    email TEXT,
    bot_id TEXT
);

CREATE TABLE new_message_logs_ISB_Dlabs (
    id BIGINT PRIMARY KEY,
    message TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    email TEXT,
    bot_id TEXT,
    bot_response TEXT,
    vector_retrieved_data TEXT,
    extracted_data TEXT
);

