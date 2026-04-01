# Extract the Information from the user message
import json
import uuid_utils as uuid # type: ignore
import time
from datetime import datetime,timezone

from MM2.utils import connect_pinecone,call_novita_ai_api,convert_to_clean_number,log_retrieve_memory_data,extract_json_from_text,call_gemini_api_v2

from MM2.prompt import MEMORY_EXTRACTOR_SYSTEM_PROMPT

pc,index = connect_pinecone()

# This function extracts memories from the user message
"""
    Input parameters:
    previous_conversation: The previous_conversation is a list of previous conversations.
    email: The email is a string that represents the user's email address.
    bot_id: The bot_id is a string that represents the unique identifier of the bot.
    
    Output:
    The function returns a boolean value indicating whether the memory extraction was successful or not.
"""

# extract_memory function to be replaced with api call made for category identification
# api: https://amaze18--category-generate-category.modal.run
async def extract_memory(previous_conversation,email,bot_id):

    # Convert the previous conversation to a string
    previous_conversation = format_conversation(previous_conversation)

    # Create a list of messages and insert the system prompt
    messages = [{
        "role": "system",
        "content": MEMORY_EXTRACTOR_SYSTEM_PROMPT
    }]

    # Add the previous conversation
    messages.append({
        "role": "user",
        "content": f""" 
            Conversation:
            {previous_conversation}
            """
    })

    # Call the OpenAI API
    response = await call_gemini_api_v2(messages)
    
    # Extract the JSON from the response and drop the other additional information from LLM
    json_str =  extract_json_from_text(response)

    # Parse the JSON
    json_response = json.loads(json_str)

    # Check if the extracted memories are empty
    if(json_response['extracted_memories'] == []):
        await log_retrieve_memory_data(previous_conversation,json_response['extracted_memories'],email,bot_id)
        return False

    # Extract the extracted memories
    extracted_memories_response = json_response['extracted_memories']

    # Create a list to store the formatted data
    formatted_data = []

    # Get the current time in a formatted string
    current_time = datetime.now(timezone.utc)

    # Format the current time as a string
    formatted_time = current_time.strftime("%a %b %d %Y %H:%M:%S GMT%z")

    # Convert the formatted time to a clean number
    created_at = convert_to_clean_number(formatted_time)
    
    # Process the extracted memories
    def process_section(section_data):
        for memory_item in section_data:
            formatted_item = {
                "id": f"mem_{uuid.uuid7()}",
                "text": memory_item["memory"],
                "metadata": {
                    "categories": memory_item["category"],
                    "created_at": created_at
                }
            }
            formatted_data.append(formatted_item)
    process_section(extracted_memories_response)

    # Convert the messages embeddings and store them in pinecone
    # Convert the text into numerical vectors that Pinecone can index
    embeddings = pc.inference.embed(
        model="multilingual-e5-large",
        inputs=[d['text'] for d in formatted_data],
        parameters={"input_type": "passage", "truncate": "END"}
    )
    records = []

    # Create a list of records to store the embeddings
    # this is the acceptable format for pinecone
    for d, e in zip(formatted_data, embeddings):
        records.append({
            "id": d["id"],
            "values": e["values"],
            "metadata": {
                "text": d["text"],
                "categories": d["metadata"]["categories"],
                "created_at": d["metadata"]["created_at"]
            }
        })

    # Upsert the records into the index
    index.upsert(
        vectors=records,
        namespace=f"{email}-{bot_id}-conversation" # User ID - email - delhi
    )

    # Log the data to the database
    await log_retrieve_memory_data(previous_conversation,extracted_memories_response,email,bot_id)

    return True

# This function formats the conversation for the user
def format_conversation(conversation):
    formatted_text = ""
    
    for message in conversation:
        # Handle user message
        formatted_text += f"User: {message['user_message']}\n"
        
        # Handle bot response
        formatted_text += f"Assistant: {message['bot_response']}\n\n"
    
    return formatted_text.strip()
