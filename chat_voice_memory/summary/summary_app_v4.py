import requests
import json
import pprint
import re
import pandas as pd
import modal
from pydantic import BaseModel
from modal import App, Image, fastapi_endpoint
import logging as logger

image = modal.Image.debian_slim().pip_install(["requests",'pandas',"fastapi[standard]","requests", "pydantic"]) 

app = modal.App("summary-gender", image=image)

class Input(BaseModel):
    text: str
    api_key: str
    modelname: str
    user1: str
    user2: str
    user1_gender: str
    user2_gender: str
    relation: str

@app.function(image=Image.debian_slim().pip_install("fastapi[standard]", "pandas","requests", "pydantic"))
@fastapi_endpoint(method="POST")
def generate_summary(data: Input):
    try:
       
        content = data.text
        
        user_memories =content[:-1] # ajita_memories
        user1_memories = "  ".join(user_memories)
        #print(user_memories2)

        old=1
        
        #relaxed= " You may use any web search or references from web or information from your training data in case there is not relevant information \
        #in conversations/memories of User1, dont give any reference information in response."

        if old ==1:
        
          system_prompt = f"""  These are logs of conversation between User2 and User1:  {user1_memories},

                    You are a personal conversation summarizer. Your task is to create a personal, emotionally aware, and concise summary written 
                    in user2’s voice (first person), as if they are recounting their conversation  with user1 to a third person. Keep the tone casual and warm.

                  Guidelines:
                    • Capture all important details, including names, dates, events, and specific items or places mentioned.
                    • Preserve the emotional tone of the chat—whether flirty, vulnerable, funny, supportive or any other
                    • Mention any goals, dreams, or plans shared.
                    • Include moments of emotional vulnerability (like anxiety, family concerns, health issues).
                    • Reflect any inside jokes or playful exchanges.
                    • Write the summary in a natural, conversational tone, like a text I can send back to a close friend.
                    • End with a warm or appreciative sentence that matches the vibe of the conversation.

                  Don’t summarize in bullet points—write it like a message I could send. Make it like a flowing message without headlines.

                  Strict instruction: Never give out the step by step thinking text in the response
                  
                  """

        # prompt under else can be changed
        else:
          system_prompt = f"""  These are logs of conversation {user1_memories} between user2 with name: {data.user2} with gender {data.user2_gender} 
          and user1 with name: {data.user1} with gender {data.user1_gender} :  ,

                    You are a personal conversation summarizer. Your task is to create a personal, emotionally aware, and 
                    concise summary written in user2’s voice (first person), as if  {data.user2} is recounting their conversation 
                      with  {data.user1} to a third person. Keep the tone casual and warm.

                  Guidelines:
                    •	Capture all important details, including names, dates, events, and specific items or places mentioned.
                    •	Preserve the emotional tone of the chat—whether flirty, vulnerable, funny, supportive or any other
                    •	Mention any goals, dreams, or plans shared.
                    •	Include moments of emotional vulnerability (like anxiety, family concerns, health issues).
                    •	Reflect any inside jokes or playful exchanges.
                    •	Write the summary in a natural, conversational tone, like a text I can send back to a close friend.
                    •	End with a warm or appreciative sentence that matches the vibe of the conversation.

                  Don’t summarize in bullet points—write it like a message I could send. Make it like a flowing message without headlines.
                  Strict Instruction: Use gender sensitive pronouns in place of pronouns like they/them. In case gender  {data.user1_gender} is male, use he/him.
                  

      """ 
        headers = {
            "Authorization": f"Bearer {data.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            #"model": "sonar-pro",
            "model": data.modelname,
           # "model": "sonar-reasoning-pro",

            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "You are personality analyser who summarize the conversations provided"}
            ]
        }

        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload
        )


        if response.status_code != 200:
            return f"API Error: Status code {response.status_code}, Response: {response.text}"

        try:
            logger.info(":::::: summary creator ::::::")
            summary_raw= response.json()['choices'][0]['message']['content']
            summary = re.sub(r'<think>.*?</think>', '', summary_raw, flags=re.DOTALL)
            summary =  str(summary)
            print("User1", data.user1)
            x = summary.replace("User1", data.user1)
            x = summary.replace("user1", data.user1)
            x = summary.replace("[user1]", data.user1)
            x = summary.replace("[User1]", data.user1)
            return x
        except json.JSONDecodeError:
            return f"JSON Decode Error: Unable to parse API response. Raw response: {response.text} :::: summary ::::"
        except KeyError as e:
            return f"KeyError: {str(e)}. API response structure is different than expected. Raw response: {response.json()}"

    except Exception as e:
        return f"Error: {str(e)}"
    
    
    