from test_utils import *
import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pre_processing import retrieve_memory

# Test Configuration
TEST_EMAIL = "singewartanmay@gmail.com"
TEST_BOT_ID = "delhi_mentor_male"

async def test_basic_query():
    """Test basic query without previous conversation"""
    prLightGray("\nTest 1: Basic Query - No Previous Conversation")
    
    message = "I want to learn programming"
    previous_conversation = []

    matches_string, rephrased = await retrieve_memory(
        message, 
        TEST_EMAIL, 
        TEST_BOT_ID, 
        previous_conversation
    )

 
    prBlack(f"Message: {message}")
    prBlack(f"Matched String: {matches_string}")
    prBlack(f"Rephrased: {rephrased}")

    # Assertions
    assert matches_string == "", "Memory matches should be empty for basic query"
    assert rephrased != "", "Rephrased query should not be empty"
    assert_string_type(rephrased, "Rephrased query")

async def test_query_with_context():
    """Test query with previous conversation context"""
    prLightGray("\nTest 2: Query with Previous Conversation")
    
    message = "I want to learn programming"
    previous_conversation = [
        {
            "role": "user",
            "content": "I want to learn programming"
        },
        {
            "role": "assistant",
            "content": "I'm glad you're interested in learning programming! What languages interest you?"
        }
    ]

    matches_string, rephrased = await retrieve_memory(
        message, 
        TEST_EMAIL, 
        TEST_BOT_ID, 
        previous_conversation
    )

 
    prBlack(f"Message: {message}")
    prBlack(f"Matched String: {matches_string}")
    prBlack(f"Rephrased: {rephrased}")

    # Assertions
    assert matches_string == "", "Memory matches should be empty with context"
    assert rephrased != "", "Rephrased query should not be empty"
    assert_string_type(rephrased, "Rephrased query")

async def test_memory_required():
    """Test query requiring memory retrieval"""
    prLightGray("\nTest 3: Query Requiring Memory")
    
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

    matches_string, rephrased = await retrieve_memory(
        message, 
        TEST_EMAIL, 
        TEST_BOT_ID, 
        previous_conversation
    )

 
    prBlack(f"Message: {message}")
    prBlack(f"Matched String: {matches_string}")
    prBlack(f"Rephrased: {rephrased}")

    # Assertions
    assert matches_string != "", "Memory matches should not be empty when memory is required"
    assert rephrased != "", "Rephrased query should not be empty"
    assert_string_type(matches_string, "Memory matches")
    assert_string_type(rephrased, "Rephrased query")

async def test_empty_message():
    """Test behavior with empty message"""
    prLightGray("\nTest 4: Empty Message")
    
    message = ""
    previous_conversation = []

    matches_string, rephrased = await retrieve_memory(
        message, 
        TEST_EMAIL, 
        TEST_BOT_ID, 
        previous_conversation
    )

 
    prBlack(f"Message: {message}")
    prBlack(f"Matched String: {matches_string}")
    prBlack(f"Rephrased: {rephrased}")

    # Assertions
    assert matches_string == "", "Memory matches should be empty for empty message"
    assert rephrased == "", "Rephrased query should handle empty message"

async def test_long_conversation():
    """Test with a longer conversation history"""
    prLightGray("\nTest 5: Long Conversation History")
    
    message = "What did we discuss about Python earlier?"
    previous_conversation = [
        {"role": "user", "content": "I want to learn Python"},
        {"role": "assistant", "content": "Python is a great language to start with!"},
        {"role": "user", "content": "What about data science?"},
        {"role": "assistant", "content": "Python is excellent for data science."},
        {"role": "user", "content": "Tell me about libraries"},
        {"role": "assistant", "content": "Popular libraries include NumPy and Pandas."}
    ]

    matches_string, rephrased = await retrieve_memory(
        message, 
        TEST_EMAIL, 
        TEST_BOT_ID, 
        previous_conversation
    )

 
    prBlack(f"Message: {message}")
    prBlack(f"Matched String: {matches_string}")
    prBlack(f"Rephrased: {rephrased}")

    # Assertions
    assert matches_string != "", "Memory matches should contain previous Python discussion"
    assert rephrased != "", "Rephrased query should reference Python context"

async def run_all_tests():
    """Run all test cases"""
    prCyan("Running Memory Retrieval Tests")
    
    test_functions = [
        test_basic_query,
        test_query_with_context,
        test_memory_required,
        test_empty_message,
        test_long_conversation
    ]

    for test_func in test_functions:
        try:
            await test_func()
            prGreen(f"PASS: {test_func.__name__}")
        except AssertionError as e:
            prRed(f"FAIL: {test_func.__name__} - {str(e)}")
        except Exception as e:
            prRed(f"ERROR: {test_func.__name__} - {str(e)}")

def main():
    asyncio.run(run_all_tests())

if __name__ == "__main__":
    main()