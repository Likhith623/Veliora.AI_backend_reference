# Extract the Information from the user message
import json
import uuid_utils as uuid # type: ignore
import time
from datetime import datetime,timezone

from MM2.utils import connect_pinecone,convert_to_clean_number,extract_json_from_text,call_gemini_api_v2  

from MM2.prompt import NOTES_MEMORY_EXTRACTION_SYSTEM_PROMPT

pc,index = connect_pinecone()

# extract_memory(messages.data,email,bot_id)
async def extract_notes_memory(notes,email,bot_id):

    messages = [{
        "role": "system",
        "content": NOTES_MEMORY_EXTRACTION_SYSTEM_PROMPT
    }]

    messages.append({
        "role": "user",
        "content": f""" 
            Notes:
            {notes}
            """
    })

    res = await call_gemini_api_v2(messages)
    
    json_str =  extract_json_from_text(res)
    res = json.loads(json_str)

    if(res['extracted_data'] == []):
        return False

    res = res['extracted_data']

    formatted_data = []

    current_time = datetime.now(timezone.utc)
    formatted_time = current_time.strftime("%a %b %d %Y %H:%M:%S GMT%z")

    created_at = convert_to_clean_number(formatted_time)
    
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
    process_section(res)

    # Convert the messages embeddings and store them in pinecone
    # Convert the text into numerical vectors that Pinecone can index
    embeddings = pc.inference.embed(
        model="multilingual-e5-large",
        inputs=[d['text'] for d in formatted_data],
        parameters={"input_type": "passage", "truncate": "END"}
    )
    records = []

    # Prepare the records for Pinecone
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

    return formatted_data

def format_conversation(conversation):
    formatted_text = ""
    
    for message in conversation:
        # Handle user message
        formatted_text += f"User: {message['user_message']}\n"
        
        # Handle bot response
        formatted_text += f"Assistant: {message['bot_response']}\n\n"
    
    return formatted_text.strip()