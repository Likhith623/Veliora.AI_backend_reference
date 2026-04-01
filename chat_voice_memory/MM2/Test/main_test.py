from test_utils import *
import sys
import os
import asyncio
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import restrict_to_last_20_messages,bot_response,extract_json_from_text,check_entry_exists

def test_restrict_to_last_20_messages():
    prCyan("Running Restrict to Last 20 Messages Tests")
    messages = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100]
    restricted_messages = restrict_to_last_20_messages(messages)

    if restricted_messages == []:
        prRed("FAIL: Restricted messages should not be empty")
    elif len(restricted_messages) != 20:
        prRed(f"FAIL: Restricted messages should have length 20. Actual length: {len(restricted_messages)}")
    elif restricted_messages[-1] != 100:
        prRed(f"FAIL: Restricted messages should end with 100. Last element: {restricted_messages[-1]}")
    else:
        print("Restricted messages",restricted_messages)
        prGreen("PASS: Restricted messages are as expected to be last 20 messages")

    return True

async def bot_response_test():
    prCyan("Running Bot Response Tests")
    bot_prompt = "You are a helpful assistant."
    user_message = "can you summarize the above conversation"
    rephrased_user_message = "User is asking for a summary of the conversation"
    previous_conversation = [
        {
            "role": "user",
            "content": "Hello, how are you doing today?"
        },
        {
            "role": "assistant",
            "content": "I'm doing great, thank you for asking!"
        }
    ]
    memory = ""

    response = await bot_response(bot_prompt,user_message,rephrased_user_message,previous_conversation,memory)

    prBlack(f"Response: {response}")
    assert_string_type(response, "Bot response")

    return True

def extract_json_from_text_test():
    prCyan("Running Extract JSON from Text Tests")

    text = """
    Some random text

    {
        "key1": "value1",
        "key2": "value2"
    }

    """

    json_str = extract_json_from_text(text)

    json_obj = json.loads(json_str)
    print("JSON Object:", json_str)

    assert_json_type(json_obj, "JSON Object")

async def check_entry_exists_test():
    prCyan("Running Check Entry Exists Tests")

    email = "test@example.com"
    bot_id = "test_bot"

    response = check_entry_exists(email, bot_id)

    print("Check Entry Exists Response:", response)

    assert_string_type(response, "Check Entry Exists Response")



def main():
    # test_restrict_to_last_20_messages()
    # asyncio.run(bot_response_test())
    # extract_json_from_text_test()
    check_entry_exists_test()
if __name__ == "__main__":
    main()
