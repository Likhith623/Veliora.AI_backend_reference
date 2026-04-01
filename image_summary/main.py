import os
import google.generativeai as genai
from PIL import Image
import io
import base64
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import dotenv
from bot_persona import get_bot_prompt, BOT_PROMPTS
from supabase import create_client, Client

# Load environment variables from .ENV file
dotenv.load_dotenv()

# --- Setup API ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")  # Add Supabase URL from env
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Add Supabase key from env

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not found in environment variables.")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_KEY not found in environment variables.")

genai.configure(api_key=GOOGLE_API_KEY)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FastAPI App ---
app = FastAPI(title="Dynamic Image Personality Bot API", version="1.0.0")

# Add CORS middleware for frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class PersonalityRequest(BaseModel):
    image_base64: str
    bot_id: str = "mentor_male"  # Default bot

class BotResponse(BaseModel):
    image_description: str
    image_summary: str
    final_response: str
    bot_used: str
    image_base64_preview: str
    db_id: int = None  # Added to return the database ID

# --- Supabase Storage Function ---
def store_to_supabase(bot_id: str, image_base64: str, image_description: str, image_summary: str, final_response: str):
    """Store the analysis data to Supabase image_interpreter table"""
    try:
        data = {
            "bot_id": bot_id,
            "image_base64": image_base64,
            "image_description": image_description,
            "image_summary": image_summary,
            "final_response": final_response
        }
        
        response = supabase.table("image_interpreter").insert(data).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error storing to Supabase: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# --- Agent Functions ---
def describe_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    vision_model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    response = vision_model.generate_content([
        "You are an expert image analyst. If the image contains a famous or globally recognized person, identify them and provide a brief description about who they are and their significance. "
        "You are an expert image analyst. Describe what you see in this image in a meaningful, detailed way. "
        "If you can reasonably guess the person's cultural or national background "
        "based on appearance, clothing, or background elements, include that. If it's unclear, say so.",
        image
    ])
    return response.text.strip()

def image_analyzer_agent(image_description):
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content([
        "You are an AI vision assistant. Summarize this image description into something meaningful.",
        image_description
    ])
    return response.text.strip()

def dynamic_personality_responder_agent(image_summary, bot_id):
    """
    Dynamic bot responder that uses the bot persona from bot_persona.py
    """
    # Get the bot prompt from your bot_persona.py file
    bot_prompt = get_bot_prompt(bot_id)
    
    if bot_prompt == "Bot prompt not found.":
        # Fallback to default mentor_male if bot not found
        bot_prompt = get_bot_prompt("mentor_male")
        bot_id = "mentor_male"
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content([
        bot_prompt,  # This contains the full personality from your bot_persona.py
        f"\nImage analysis: {image_summary}",
        "\nBased on the image content, respond in character. Keep it conversational and engaging (2-3 sentences)."
    ])
    return response.text.strip()

@app.get("/")
async def root():
    return {
        "message": "Dynamic Image Personality Bot API is running!",
        "description": "Upload an image and choose a bot personality to get a personalized response",
        "available_bots": list(BOT_PROMPTS.keys()) if BOT_PROMPTS else ["Check bot_persona.py for available bots"]
    }
    
@app.get("/bots")
async def get_available_bots():
    """Get list of all available bot personalities from bot_persona.py"""
    if not BOT_PROMPTS:
        return {"error": "No bots found in bot_persona.py", "bots": []}
    
    return {
        "available_bots": list(BOT_PROMPTS.keys()),
        "total_count": len(BOT_PROMPTS),
        "usage": "Pass bot_id parameter when calling the analyze endpoints"
    }
    
@app.post("/analyze_image_with_file", response_model=BotResponse)
async def analyze_image_with_file(
    image: UploadFile = File(...),
    bot_id: str = Form("mentor_male")  # Default to mentor_male
):
    """
    Upload an image file to get response from selected bot persona
    """
    try:
        # Validate inputs
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Validate bot_id exists
        if bot_id not in BOT_PROMPTS:
            raise HTTPException(
                status_code=400, 
                detail=f"Bot '{bot_id}' not found. Available bots: {list(BOT_PROMPTS.keys())}"
            )
        
        # Read image bytes
        image_bytes = await image.read()
        
        # Convert to base64 for storage
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Store selfie in text format (keeping existing functionality)
        with open("selfie_base64.txt", "w") as f:
            f.write(image_base64)
        
        # Process through agents
        image_description = describe_image(image_bytes)
        image_summary = image_analyzer_agent(image_description)
        final_response = dynamic_personality_responder_agent(image_summary, bot_id)
        
        # Store data to Supabase and get the record
        db_record = store_to_supabase(bot_id, image_base64, image_description, image_summary, final_response)
        db_id = db_record["id"] if db_record else None
        
        return BotResponse(
            image_description=image_description,
            image_summary=image_summary,
            final_response=final_response,
            bot_used=bot_id,
            image_base64_preview=image_base64[:300] + "...",
            db_id=db_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")
    
    
@app.post("/analyze_image_with_base64", response_model=BotResponse)
async def analyze_image_with_base64(request: PersonalityRequest):
    """
    Send base64 encoded image to get response from selected bot persona
    """
    try:
        # Validate inputs
        if not request.image_base64:
            raise HTTPException(status_code=400, detail="Image base64 data is required")
        
        # Validate bot_id exists
        if request.bot_id not in BOT_PROMPTS:
            raise HTTPException(
                status_code=400, 
                detail=f"Bot '{request.bot_id}' not found. Available bots: {list(BOT_PROMPTS.keys())}"
            )
        
        # Decode base64 image
        try:
            image_bytes = base64.b64decode(request.image_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 image data")
        
        # Store selfie in text format
        with open("selfie_base64.txt", "w") as f:
            f.write(request.image_base64)
        
        # Process through agents
        image_description = describe_image(image_bytes)
        image_summary = image_analyzer_agent(image_description)
        final_response = dynamic_personality_responder_agent(image_summary, request.bot_id)
        
        # Store data to Supabase and get the record
        db_record = store_to_supabase(request.bot_id, request.image_base64, image_description, image_summary, final_response)
        db_id = db_record["id"] if db_record else None
        
        return BotResponse(
            image_description=image_description,
            image_summary=image_summary,
            final_response=final_response,
            bot_used=request.bot_id,
            image_base64_preview=request.image_base64[:300] + "...",
            db_id=db_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is running", "bots_loaded": len(BOT_PROMPTS)}

@app.get("/history")
async def get_analysis_history(limit: int = 10, bot_id: str = None):
    """Get past image analysis records"""
    try:
        query = supabase.table("image_interpreter").select(
            "id,bot_id,image_summary,final_response,created_at"
        ).order("created_at", desc=True).limit(limit)
        
        # Filter by bot_id if provided
        if bot_id:
            query = query.eq("bot_id", bot_id)
            
        response = query.execute()
        return {"records": response.data, "count": len(response.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching history: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)