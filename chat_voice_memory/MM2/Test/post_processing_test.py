from test_utils import *
import sys
import os
import asyncio
import json
from datetime import datetime,timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from post_processing import extract_memory,format_conversation,convert_to_clean_number

def test_format_conversation():
    prCyan("Running Format Conversation Tests")
    conversation = [
        {
            "email":"test@example.com",
            "user_message": "Hello, how are you doing today?",
            "bot_response": "I'm doing great, thank you for asking!",
            "bot_id": "test_bot"
        },
        {
            "email":"test@example.com",
            "user_message": "How are you doing today?",
            "bot_response": "I'm doing great, thank you for asking!",
            "bot_id": "test_bot"
        }
    ]

    formatted_conversation = format_conversation(conversation)

    print("Formatted Conversation:",formatted_conversation)

    if formatted_conversation == "":
        prRed("FAIL: Formatted conversation should not be empty")
    elif formatted_conversation.strip() != """User: Hello, how are you doing today?
Assistant: I'm doing great, thank you for asking!

User: How are you doing today?
Assistant: I'm doing great, thank you for asking!""":
        prRed(f"FAIL: Formatted conversation should be 'User: Hello, how are you doing today? \n Assistant: I'm doing great, thank you for asking!'. Actual conversation: {formatted_conversation.strip()}")
    else:
        prGreen("PASS: Formatted conversation is as expected")

    return True

def test_convert_to_clean_number():
    prCyan("Running Convert to Clean Number Tests")
    current_time = datetime.now(timezone.utc)
    formatted_time = current_time.strftime("%a %b %d %Y %H:%M:%S GMT%z")

    clean_number = convert_to_clean_number(formatted_time)

    if clean_number == "":
        prRed("FAIL: Clean number should not be empty")
    elif len(clean_number.strip()) != len("20250121013137"):
        prRed(f"FAIL: Clean number is not the expected length. Actual length: {len(clean_number.strip())}")
    else:
        prGreen("PASS: Clean number is as expected")

    return True

def test_extract_memory():
    prCyan("Running Extract Memory Tests")
    message = "You remember what we discussed yesterday on this topic!"

    previous_conversation = [
        {
            "role": "user",
            "content": "You know what? I love that game."
        },
        {
            "role": "assistant",
            "content": "Yeah, I do. It's a really fantastic game!"
        }
    ]

def main():
    # asyncio.run(test_retrieve_memory())
    # test_format_conversation()
    test_convert_to_clean_number()

if __name__ == "__main__":
    main()