from test_utils import *
import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notes_processing import extract_notes_memory

# Test Configuration
TEST_EMAIL = "singewartanmay@gmail.com"
TEST_BOT_ID = "delhi_mentor_male"

async def test_no_notes():
    prLightGray("\nTest 0: No Notes Provided")
    notes = ""

    extracted_info = await extract_notes_memory(
        notes,
        TEST_EMAIL,
        TEST_BOT_ID
    )

    prBlack(f"Message: {notes}")
    # prBlack(f"Extractor Info: {extracted_info}")
    # asset to check as Json
    assert_bool_type(extracted_info, "Extracted Memory")
    assert extracted_info == False, "Memory should be False"
    # assert_list_type(extracted_memory, "Extracted Memory")

async def test_short_note():
    prLightGray("\nTest 1: Short Note")
    notes = "I enjoy reading mystery novels before bed."

    extracted_info = await extract_notes_memory(
        notes,
        TEST_EMAIL,
        TEST_BOT_ID
    )

    prBlack(f"Message: {notes}")
    # prBlack(f"Extractor Info: {extracted_info}")
    # asset to check as Json
    assert_list_type(extracted_info, "Extracted Memory")

async def test_middle_note():
    prLightGray("\nTest 2: Medium-Length Note")
    notes = "I recently started learning French because I want to travel to Paris. I’ve been using Duolingo every day for 15 minutes. My goal is to be able to hold a basic conversation by the end of this year."

    extracted_info = await extract_notes_memory(
        notes,
        TEST_EMAIL,
        TEST_BOT_ID
    )

    prBlack(f"Message: {notes}")
    # prBlack(f"Extractor Info: {extracted_info}")
    # asset to check as Json
    assert_list_type(extracted_info, "Extracted Memory")

async def test_long_note():
    prLightGray("\nTest 3: Long Note")
    notes = "I’ve always loved hiking in the mountains, but this year, I’ve decided to take it more seriously. I’m training for a multi-day trek in the Rockies, and I’ve been increasing my stamina with long weekend hikes. I also joined a hiking group for safety and to meet people who share the same interest. I plan to summit Mount Elbert in the summer as my first big goal. Aside from that, I’m working on improving my photography skills, specifically landscape photography. I recently bought a new DSLR camera and enrolled in an online course to learn more about shooting in manual mode."

    extracted_info = await extract_notes_memory(
        notes,
        TEST_EMAIL,
        TEST_BOT_ID
    )

    prBlack(f"Message: {notes}")
    # prBlack(f"Extractor Info: {extracted_info}")
    # asset to check as Json
    assert_list_type(extracted_info, "Extracted Memory")


async def run_all_tests():
    """Run all test cases"""
    prCyan("Running Memory Retrieval Tests")
    
    test_functions = [
        test_no_notes,
        test_short_note,
        test_middle_note,
        test_long_note,
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