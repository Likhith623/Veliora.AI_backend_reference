
# Memories Workflow

This project manages and categorizes chat interactions between users and bots.  
It extracts meaningful information, categorizes it, identifies changes (deltas), and checks for redundancies — ensuring efficient memory management in Supabase.


## Workflow Overview

1. **Collect** chat logs from users and bots.
2. **Categorize** messages into structured memories.
3. **Identify** changes (deltas) in categories.
4. **Detect** redundant memories to avoid duplication.


## Components

### 1. Chat Message Logs
- **Source:** Supabase `messages` table
- **Fields:** 
  - `email`
  - `bot_id`
  - `user_message`
  - `bot_response`
  - `created_at`
  - `requested_at`
- **Purpose:** Store raw chat logs from conversations.


### 2. Categorizer API
- **Input:** Chat messages from the `message` table.
- **Process:** Categorizes the message content into memory structures.
- **Output:** 
  - `email`
  - `bot_id`
  - `memory`
  - `category`
  - `created_at`
- **Destination:** Stored in the `persona_category` table.


### 3. Persona_Category Table
- **Database:** Supabase
- **Purpose:** Centralized storage for categorized memories.
- **Fields:**
  - `email`
  - `bot_id`
  - `memory`
  - `category`
  - `created_at`


### 4. Delta Category API
- **Input:** Data from `persona_category`.
- **Process:** Detects new or modified categories (deltas) and maps relations.
- **Output:** 
  - Delta category with relation
  - Relation ID
- **Destination:** Updates `persona_category` table.


### 5. Redundancy API
- **Input:** Data from `persona_category`.
- **Process:** Checks for memory redundancy.
- **Output:** 
  - Redundancy flag: `True` or `False`
- **Destination:** Updates `persona_category` table.

## Flow Diagram
<p align="center">
  <img src="./images/memories-workflow.png" alt="Memories Workflow" width="600"/>
</p>

## API LINKS

Category API: https://amaze18--category-generate-category.modal.run
Summary API: https://amaze18--summary-generate-summary.modal.run
Delta Category API: https://amaze18--delta-category-delta-category.modal.run
PPX API: https://amaze18--get-ppx-env-f.modal.run
Redundancy handle API: https://amaze18--redundancy-handle-redundancy-handle.modal.run

