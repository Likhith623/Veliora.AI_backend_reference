
# System Logic Overview

This section explains the core logic behind how XP and Coins are calculated in the chatbot system.

## XP Score Calculation

### Input:
- Last 8 messages (4 user + 4 assistant turns)
- Evaluated by a secondary LLM via a prompt that defines emotional/contextual XP score rubric.

### Evaluation Categories:
- XP Score is an integer between 0 and 8.
- The score reflects the emotional depth, continuity, roleplay progress, or memory usage.
- Specific mappings used are:

| XP Score | Meaning |
|----------|---------|
| 1 | Quick Hello |
| 2 | Mood Sync or Heartfelt Moment |
| 3 | Acted on Suggestion or Deep Dive Chat |
| 4 | Hey, I Remember! (Memory Callback) |
| 5 | Storytime Start or Big Emotion Shared |
| 6 | Opening Up (User or Bot Shares Deeply) |
| 8 | Scene Complete! (Roleplay Journey) |

### Aggregation:
- XP score is saved in `xp_scores_last_80` list.
- Total XP is incremented after every batch of 10 judge reports (80 messages).

## Coin System Logic

### Inputs:
- Total XP across batches
- XP score for current batch
- Last activity timestamps

### Activity-Based Rewards:

| Activity | Condition | Coins |
|----------|-----------|-------|
| Daily Check-In | Once per day | +2 |
| Meaningful Conversation | XP score ≥3 & not already done today | +3 |
| Weekly Streak | ≥5 days of XP > 0 in past 7 days | +10 |
| Emotional Milestone | On crossing 20, 60, 120, 220 XP | +8 |
| Response After Inactivity | First response after ≥48 hours | +5 |

### Code Logic:
- `check_daily_checkin()` checks date and last_checkin.
- `check_meaningful_convo(xp_score)` checks XP threshold and daily status.
- `check_weekly_streak()` scans 7-day XP history and resets XP for bonus days.
- `check_milestone(total_xp)` compares total XP with known milestone values.
- `check_response_after_inactivity()` compares timestamp delta with 48h threshold.

---


# Chatbot XP & Coin System Documentation

This document outlines the logic and structure behind the XP (experience points), coin reward system, and judge-based monitoring integrated into the chatbot. This ensures quality control, gamification, and user engagement in long-running conversations.

---

## System Overview

The chatbot has the following main components:

- **User-Bot Chat Loop**: Interaction between the user and Jayden Lim (chatbot persona).
- **Judge Monitoring System**: Evaluates conversation quality every 8 messages.
- **XP Scoring System**: Awards XP based on quality, emotional depth, and contextual behavior.
- **Coin Reward System**: Grants coins based on time, streaks, emotional events, and activity triggers.

---


## Judge Monitoring System (LLM-Based Quality Evaluator)

The **Judge Monitoring System** is a stand-alone module focused on monitoring conversation quality, consistency, and flow. It uses a separate LLM (Judge Model) to periodically review chunks of conversation.

### Purpose
The judge is **not part of the chatbot's response generation loop**. Its purpose is to **evaluate** conversation segments for emotional quality, coherence, tone, and engagement issues. It provides feedback data, not XP or coins directly.

### Trigger Frequency
- Triggered every **8 messages** (4 user-bot turns).
- Evaluates the **last 8 messages** as a complete conversation segment.

### Prompt Content to Judge LLM
The judge receives:
- A conversation snippet of the last 8 messages.
- A prompt that instructs it to evaluate the following:

  - **Coherence** (Score 1–10): Logical continuity of dialogue.
  - **Tone Consistency** (Score 1–10): Emotional and narrative tone stability.
  - **Repetition Detected** (Yes/No)
  - **User Confusion Detected** (Yes/No)
  - **Intervention Suggested** (Yes/No): If manual attention is needed.
  - **XP Score (0–8)**: Based on emotional depth, engagement, or narrative movement.

### Judge Output Format
- The judge model responds with a structured report.
- Data is parsed using regular expressions to extract each metric.
- **Only the XP Score** is forwarded to the XP system; the rest is logged for analytics and quality control.

---

## XP System

The **XP (Experience Points) System** is an independent gamification module that tracks the **depth, emotional engagement, and quality** of the user's interaction with the chatbot.

### Source of XP
XP is **extracted from the Judge LLM’s report**, specifically from the **XP Score** field. All other judge metrics are ignored by this module.

### How XP Is Calculated
- After every 8-message chunk, the XP Score (from the judge) is extracted.
- This score is an integer from 0 to 8 and is appended to a buffer `xp_scores_last_80`.

| XP Score | Description |
|----------|-------------|
| 1        | Quick Hello |
| 2        | Mood Sync or Heartfelt Moment |
| 3        | Acted on Suggestion or Deep Dive Chat |
| 4        | Hey, I Remember! (Memory Callback) |
| 5        | Storytime Start or Big Emotion Shared |
| 6        | Opening Up (User or Bot Shares Deeply) |
| 8        | Scene Complete! (Roleplay Journey) |

### XP Summary & Batch Evaluation
- Every **10 judge reports** (i.e., 80 messages), the system summarizes the batch:
  - Prints a summary of XP-related events (e.g., memory use, roleplay scenes, deep emotion).
  - Adds batch total to `total_xp_score`.

### Role of XP
- XP is used to **drive coin rewards**, trigger **milestones**, and track **emotional progress**.
- XP has **no effect on the chatbot’s personality or behavior**, maintaining full separation from generation logic.


### How XP Is Calculated

- **Input**: Every 8 messages (4 turns), judge evaluates and outputs an XP score (0–8).
- **Storage**: Each score is appended to `xp_scores_last_80`.
- **Batch Evaluation**: After 10 judge runs (80 messages), a summary is printed.

### XP Activity Mapping

| XP Score | Activity Description |
|----------|----------------------|
| 1        | Quick Hello |
| 2        | Mood Sync or Heartfelt Moment |
| 3        | Acted on Suggestion or Deep Dive Chat |
| 4        | Hey, I Remember! (Memory Callback) |
| 5        | Storytime Start or Big Emotion Shared |
| 6        | Opening Up (User or Bot Shares Deeply) |
| 8        | Scene Complete! (Roleplay Journey) |

### Batch XP Printout
- Triggered every 80 messages.
- Aggregates XP, prints activity summary.
- XP added to `total_xp_score`.

---

## Coin Reward System

The **Coin Reward System** is a core gamification module designed to incentivize consistent, meaningful interactions between the user and the chatbot. It transforms engagement patterns into collectible rewards, encouraging deeper conversation, emotional expression, and regular check-ins.

Coins are **not directly influenced by XP score alone** — they are awarded based on specific tracked activities, milestones, and time-based events.

### How Coins Are Calculated

- Coins are evaluated **after every 10 judge reports** (i.e., every 80 messages).
- The **CoinTracker** class monitors XP patterns, activity timestamps, and user behavior to determine coin eligibility.
- If an activity’s condition is met, the corresponding coin bonus is granted **once per evaluation period** (to avoid duplicate rewards).
- After coin evaluation, a summary is printed, displaying:
  - Completed Activities
  - Coins Awarded

### Coin Award Conditions & Logic Breakdown

| Activity Type                 | Trigger Condition                                              | Coins | Logic |
|-------------------------------|----------------------------------------------------------------|-------|-------|
| **Daily Check-In**            | First conversation detected per calendar day                  | +2    | `check_daily_checkin()` validates by date against last check-in timestamp. |
| **Meaningful Conversation**   | At least one XP score ≥ 3 in a given day                      | +3    | `check_meaningful_convo()` checks XP threshold and ensures once per day. |
| **Weekly Streak Bonus**       | User active with XP > 0 on **5 out of last 7 days**           | +10   | `check_weekly_streak()` inspects `xp_by_day` for qualifying days. |
| **Emotional Milestone**       | On first-time XP crossing **20, 60, 120, 220 total XP**       | +8    | `check_milestone()` triggers only once per milestone. |
| **Response After Inactivity** | First message after **≥48 hours** since last user activity    | +5    | `check_response_after_inactivity()` checks against last activity timestamp. |

### Award Process

- The `CoinTracker` class handles all coin-related logic.
- The system maintains:
  - `xp_by_day` dictionary for tracking daily XP.
  - `awarded_milestones` set for tracking unlocked milestones.
  - `last_activity_timestamps` for checking inactivity and check-in logic.
- Coins are awarded in **batches**, ensuring clear tracking and user feedback.
- Coin summaries include a clear, professional activity name with reward details.

---

## XP & Coin API Integration

The XP & Coin system is fully integrated with the backend to ensure real-time reward processing, tracking, and gamified user experience. XP is awarded based on emotional magnitude, and Coins are calculated at **1 Coin = 10 XP**.


### API Endpoints Overview

| Endpoint | Purpose |
|----------|---------|
| **POST /cv/chat**, **/v2/cv/chat**, **/voice-call-ultra-fast** | Automatically awards XP & Coins after each user message |
| **GET /user-xp/{email}/{bot_id}** | Retrieves XP, Coins, Magnitude, and last updated time |
| **GET /user-xp-leaderboard/{bot_id}** | Returns leaderboard sorted by XP for a specific bot |
| **POST /award-xp** | Allows admins to manually award XP & Coins |
| **GET /xp-statistics** | Provides global XP, Coin, and usage statistics |
| **GET /user-xp-current/{email}/{bot_id}** | Retrieves real-time XP & Coin data for frontend display |


### API Usage Highlights

- **Automatic XP Awarding** after each user interaction via main chat and voice endpoints.
- **Real-time Coin & XP Tracking** reflected instantly in user dashboards.
- **Leaderboard Integration** encourages competitive engagement.
- **Manual Admin Awards** allow flexibility for promotions or corrections.
- **Global Statistics API** supports system monitoring and insights.
- **Frontend XP Display Sync** via optimized current XP retrieval endpoints.


### Sample API Response (XP Award Example):

json
{
  "immediate_xp_awarded": 20,
  "current_total_xp": 300,
  "current_total_coins": 30,
  "magnitude": 4.0,
  "xp_calculation_success": true
}

---

## Code Modules

### Main Variables

- `chat_history`: Stores all messages.
- `judge_trigger_every`: 8 (messages)
- `xp_scores_last_80`: Stores XP for batch.
- `report_count`: Counts how many judge runs completed.
- `total_xp_score`: Accumulated lifetime XP.
- `CoinTracker`: Handles coin logic, milestone tracking, streaks, and more.

### XP and Coin Awarding Flow

1. Every 8 messages → Run Judge
2. Parse Judge → Extract XP → Append to `xp_scores_last_80`
3. After 10 reports:
    - Analyze XP batch
    - Print summary of XP activities and total XP
    - Run CoinTracker to evaluate and award eligible coins

---

## Modifying the System

- To change XP frequency: update `judge_trigger_every`
- To analyze more or fewer reports: change `report_count % N`
- To add new coin logic: extend `CoinTracker` methods
- To add new XP types: update XP mapping in the activity print section

---

## Summary

This system offers scalable, periodic evaluation of chatbot performance and user engagement, rewarding sustained interaction with meaningful XP and coin feedback.

All logic is modular and can be easily expanded or edited.
