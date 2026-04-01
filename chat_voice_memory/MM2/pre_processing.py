# Categorize the user message and rephrase it 
# Dynamic category retrieval
import json
import logging

from fastapi import FastAPI,File,UploadFile,Form,BackgroundTasks # type: ignore
from MM2.utils import call_novita_ai_api,format_client_conversation,extract_json_from_text,call_gemini_api_v2

from MM2.prompt import CATEGORY_IDENTIFIER_SYSTEM_PROMPT,REMINDER_SYSTEM_PROMPT
import requests
import datetime
import traceback
import os
import re
from MM2.utils import connect_pinecone , get_username , get_botname , supabase
pc,index = connect_pinecone()

# def categorizer(query : str , email : str , bot_id : str ):
#     modelname = "sonar-reasoning"
#     api_key = os.getenv("CATEGORIZER_API_KEY")

#     url = os.getenv("CATEGORIZER_GCP_URL")
    
#     username = get_username(email)
#     bot_name = get_botname(bot_id)

#     payload = {
#                 "query": query,
#                 "type_analysis": "character analysis",
#                 "api_key": api_key,
#                 "modelname": modelname,
#                 "user1": username,
#                 "user2": bot_name,
#             }
#     try:
#         response = requests.post(url, json=payload)
#         print("Status Code:", response.status_code)

#         raw_text = response.text.strip()

#         # If server error, log and exit early
#         if "503" in raw_text or "Error" in raw_text:
#             logging.error(f"Categorizer server error: {raw_text}")
#             return None

#         if raw_text.startswith('"') and raw_text.endswith('"'):
#             try:
#                 raw_text = json.loads(raw_text)
#             except json.JSONDecodeError as e:
#                 logging.error(f"Failed to decode wrapped string for {email}, {bot_id}: {e}")
#                 return None

#         match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.DOTALL)
#         if match:
#             json_block = match.group(1).strip()
#         else:
#             json_block = raw_text.strip()

#         if json_block.startswith('{') and json_block.endswith('}'):
#             json_block = '[' + json_block + ']'

#         result = json.loads(json_block)
#         print("Parsed JSON:", result)
#         return result

#     except Exception as e:
#         traceback.print_exc()
#         print("Non-JSON response:", response.text)
#         return None


"""
    This function retrieves the memory from the pinecone index

    Input parameters:
    query: The query is a string that represents the user's message or question.
    email: The email is a string that represents the user's email address.
    bot_id: The bot_id is a string that represents the unique identifier of the bot.
    previous_conversation: The previous_conversation is a list of previous conversations.
    
    Output:
    The function returns a tuple containing the following elements:
    matches_string: A string that represents the matches found in the pinecone index.
    rephrased : A string that represents the rephrased user message.
    category : A string that represents the category of the user message.
"""
# async def retrieve_memory(query,email,bot_id,previous_conversation):

    # Initialize the messages list with the system prompt
    # messages = [
    #     {
    #         "role": "system",
    #         "content": CATEGORY_IDENTIFIER_SYSTEM_PROMPT
    #     }
    # ]

    # # Format the previous conversation in to String
    # previous_conversation = format_client_conversation(previous_conversation)

    # # Append the previous conversation and user message to the messages
    # messages.append({
    #     "role": "user",
    #     "content": f"""    
    #     Previous Conversations: [{previous_conversation}]  
    #     User Message: {query}  
    #     """
    # })

    # # res = call_novita_ai_api(messages,model="deepseek/deepseek_v3")

    # # Call OpenAI API
    # res = await call_openai_api(messages , model="o3-mini")

    # # Extract the JSON from the response
    # json_str = extract_json_from_text(res)

    # # Parse the JSON
    # extracted = json.loads(json_str)
    
    # # Extract the relevant information from the JSON

    # # Extract the rephrased user message
    # rephrased = str(extracted['rephrased_user_message'])

    # # Experimental Area more research required
    # category = str(extracted['category'])

    # # return value is true or false, memory_required id false for Hii and Hello messages
    # memory_required = extracted['memory_required']


    # if memory_required == False:
    #     return "",rephrased,category

    # Convert the query into a numerical vector that Pinecone can search with
    # query_embedding = pc.inference.embed(
    #     model="multilingual-e5-large",
    #     inputs=[rephrased], 
    #     parameters={
    #         "input_type": "query"
    #     }
    # )

    # # Query Pinecone for the closest matches to the query embedding
    # results = index.query(
    #     namespace=f"{email}-{bot_id}-conversation",
    #     vector=query_embedding[0].values,
    #     top_k=5,
    #     # filter = {
    #     #     "categories": {"$eq": category}, 
    #     # },
    #     include_values=False,
    #     include_metadata=True
    # )
    # # logging.info(f"result['matches']: {results['matches']}") # for testing purpose
    # # Sort matches by created_at timestamp (newest first)
    # # Extracting the timestamp from the metadata
    # sorted_matches = sorted(
    #     results['matches'],
    #     # Creating the datetime object from the timestamp number
    #     key=lambda x: datetime.datetime.strptime(
    #         f"{x['metadata']['created_at'][:4]}-{x['metadata']['created_at'][4:6]}-{x['metadata']['created_at'][6:8]} "
    #         f"{x['metadata']['created_at'][8:10]}:{x['metadata']['created_at'][10:12]}:{x['metadata']['created_at'][12:]}",
    #         "%Y-%m-%d %H:%M:%S"
    #     ),
    #     reverse=True  # newest first
    # )

    # # Update results with sorted matches
    # results['matches'] = sorted_matches
    # # print(sorted_matches)

    # # Convert created_at timestamp to datetime object
    # for match in sorted_matches:
    #     match['metadata']['created_at'] = datetime.datetime.strptime(
    #         # Insert formatting characters into the clean number string
    #         f"{match['metadata']['created_at'][:4]}-{match['metadata']['created_at'][4:6]}-{match['metadata']['created_at'][6:8]} "
    #         f"{match['metadata']['created_at'][8:10]}:{match['metadata']['created_at'][10:12]}:{match['metadata']['created_at'][12:]}",
    #         "%Y-%m-%d %H:%M:%S"
    #     )

    # # Extract the matches as a string
    # matches_string = ""

    # # Converting the matches to a string
    # for e in sorted_matches:
    #     matches_string += f"""{e["metadata"]["text"]}\nCreated at: {e["metadata"]["created_at"]}\n--------------------\n"""
        
    # # User external logging service to log
    # print(matches_string)
    # return matches_string,rephrased,category

    # return "","",""

# async def retrieve_memory(query,email,bot_id , previous_conversation):
#     res = categorizer(query, email, bot_id)
#     if not res:
#         logging.error("Categorizer returned no data.")
#         return "", "", ""

#     # Extract rephrased message and category
#     rephrased_user_message = res[0].get('rephrased_user_message', '')
#     category = res[0].get('category', '')
#     logging.info(f"rephrased_user_message: {rephrased_user_message}")
#     logging.info(f"category:{category}")
    
#     try:
#         # Step 1: Fetch all matching rows
#         response = supabase.table("persona_category")\
#             .select("memory, redundant, relation_id")\
#             .match({
#                 "email": email,
#                 "bot_id": bot_id,
#                 "category": category,
#             })\
#             .execute()

#         if not response.data:
#             logging.info("No matching memory found.")
#             return "", rephrased_user_message, category

#         # Step 2: Separate and filter
#         seen_relations = set()
#         memories = []

#         for item in response.data:
#             memory = item["memory"]
#             redundant = item["redundant"]
#             relation_id = item.get("relation_id")

#             if not redundant:
#                 # Always include non-redundant
#                 memories.append(memory)
#             else:
#                 # Only one per relation_id
#                 if relation_id not in seen_relations:
#                     seen_relations.add(relation_id)
#                     memories.append(memory)

#         # Final memory block
#         memory = "\n".join(memories)
#         logging.info(f"Filtered memory: {memory}")

#     except Exception as e:
#         logging.error(f"Failed to fetch or filter memory from Supabase: {e}")
#         memory = ""

#     return memory, rephrased_user_message, category


async def retrieve_memory(query, email, bot_id, previous_conversation):
    try:
        url = os.getenv("CATEGORIZER_GCP_URL")
        payload = {
            "query": query,
            "email": email,
            "bot_id": bot_id,
            "previous_conversation": previous_conversation,
        }

        response = requests.post(url, json=payload)

        if response.status_code != 200:
            logging.error(f"GCP Memory API error {response.status_code}: {response.text}")
            return "", "", ""

        data = response.json()
        memory = data.get("memory", "")
        rephrased_user_message = data.get("rephrased_user_message", "")
        category = data.get("category", "")

        logging.info(f"Memory: {memory}")
        logging.info(f"Rephrased: {rephrased_user_message}")
        logging.info(f"Category: {category}")

        return memory, rephrased_user_message, category

    except Exception as e:
        logging.error(f"Exception in retrieve_memory: {e}")
        return "", "", ""

"""
This function generates a reminder response based on the user message, previous conversation, and request time.

Input:
user_message: The user_message is a string that represents the user's message or question.
previous_conversation: The previous_conversation is a list of previous conversations.
request_time: The request_time is a string that represents the current time.

Output:
The function returns a string that represents the reminder response.
"""

async def reminder_response(user_message,previous_conversation,request_time):
    model = "o3-mini"
    messages = [
        {
            "role": "system",
            "content": REMINDER_SYSTEM_PROMPT
        }
    ]

    messages.extend(previous_conversation)

    messages.append({
        "role": "user",
        "content": f"""    
        User Message: {user_message} 
        Current Time: {request_time}
        """
    })

    res = await call_gemini_api_v2(messages,model)

    json_str = extract_json_from_text(res)
    extracted = json.loads(json_str)

    return extracted

async def get_stats():
    return( await index.describe_index_stats())
