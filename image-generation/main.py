# main.py (Improved version with better cancellation handling)

import os
import re
import json
import logging
import asyncio
import uuid
import base64
import time
import random
from typing import Optional, Dict
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from gradio_client import Client, file, handle_file
from supabase import create_client, Client as SupabaseClient
import litellm
from dotenv import load_dotenv
import httpx
import signal
import weakref
from fastapi.staticfiles import StaticFiles

# Mount static file directory for serving images


# --- Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from bot_prompts import BOT_PROMPTS as VALID_BOT_IDS
except ImportError:
    logger.error("FATAL: bot_prompts.py not found.")
    exit()

# Configuration
GRADIO_TIMEOUT = int(os.environ.get("GRADIO_TIMEOUT", "120"))  # Increased from 60
HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "90"))      # Increased from 45
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))         # Increased from 2
CONNECTION_TIMEOUT = int(os.environ.get("CONNECTION_TIMEOUT", "45")) # Increased from 30

# Global shutdown flag
shutdown_event = asyncio.Event()

# Alternative Gradio spaces for fallback
FALLBACK_SPACES = [
    "multimodalart/Ip-Adapter-FaceID",
    # Add more spaces as fallbacks if needed
    # "InstantX/InstantID",
    # "SG161222/RealVisXL_V4.0",
]

# --- Models ---
class ImageGenerationRequest(BaseModel):
    bot_id: str
    message: str
    email: str
    previous_conversation: Optional[str] = ""
    username: Optional[str] = "User"

class ImageGenerationResponse(BaseModel):
    bot_id: str
    image_url: str
    image_base64: str
    status: str
    emotion_context: Dict[str, str]

class ErrorDetail(BaseModel):
    status: str = "error"
    message: str

# --- Request tracking ---
active_requests = weakref.WeakSet()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# --- FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup...")
    try:
        await chatbot_service.initialize_gradio_client()
        yield
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        yield
    finally:
        logger.info("Application shutdown.")
        shutdown_event.set()
        # Cancel all active requests
        for request_task in list(active_requests):
            if not request_task.done():
                request_task.cancel()

app = FastAPI(
    title="AI Image Generation API",
    version="3.5.0",
    lifespan=lifespan,
    responses={
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
        500: {"model": ErrorDetail},
        503: {"model": ErrorDetail},
    }
)

os.makedirs("static/images", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

allowed_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Chatbot Service ---
class ChatbotService:
    def __init__(self):
        self.gradio_client = None
        self.current_space = None
        self.client_lock = asyncio.Lock()
        self.last_error_time = 0
        self.error_count = 0
        self.max_errors = 5
        self.error_reset_interval = 300  # 5 minutes
        
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set.")
        os.environ["GEMINI_API_KEY"] = self.gemini_api_key

        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")
        if supabase_url and supabase_key:
            self.supabase_client: SupabaseClient = create_client(supabase_url, supabase_key)
            logger.info("Supabase client initialized.")
        else:
            self.supabase_client = None
            logger.warning("Supabase not initialized.")

    def _check_error_threshold(self):
        """Check if we've exceeded error threshold"""
        current_time = time.time()
        if current_time - self.last_error_time > self.error_reset_interval:
            self.error_count = 0
        return self.error_count < self.max_errors

    def _record_error(self):
        """Record an error occurrence"""
        self.error_count += 1
        self.last_error_time = time.time()

    async def initialize_gradio_client(self):
        """Initialize Gradio client with better error handling"""
        async with self.client_lock:
            if not self._check_error_threshold():
                logger.error("Too many errors, skipping client initialization")
                return False

            for space in FALLBACK_SPACES:
                if shutdown_event.is_set():
                    logger.info("Shutdown requested, aborting client initialization")
                    return False

                try:
                    logger.info(f"Attempting to connect to {space}")
                    
                    # Create client with shorter timeout
                    client_task = asyncio.create_task(
                        asyncio.to_thread(Client, space)
                    )
                    
                    # Wait for initialization with shutdown check
                    try:
                        self.gradio_client = await asyncio.wait_for(
                            client_task,
                            timeout=CONNECTION_TIMEOUT
                        )
                    except asyncio.TimeoutError:
                        client_task.cancel()
                        logger.warning(f"Connection to {space} timed out")
                        continue

                    self.current_space = space
                    logger.info(f"Successfully connected to {space}")
                    
                    # Quick verification
                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(self.gradio_client.view_api),
                            timeout=10.0
                        )
                        logger.info(f"Gradio client connection to {space} verified.")
                        return True
                    except Exception as e:
                        logger.warning(f"Could not verify connection to {space}: {e}")
                        self.gradio_client = None
                        continue
                        
                except Exception as e:
                    logger.warning(f"Failed to connect to {space}: {e}")
                    continue
            
            logger.error("Failed to connect to any Gradio space")
            self.gradio_client = None
            self.current_space = None
            self._record_error()
            return False

    async def reinitialize_gradio_client(self):
        """Reinitialize the Gradio client"""
        logger.info("Reinitializing Gradio client...")
        self.gradio_client = None
        self.current_space = None
        return await self.initialize_gradio_client()

    def get_bot_response_for_context(self, request_data: ImageGenerationRequest, bot_name: str) -> str:
        """Get bot response with timeout and error handling"""
        messages = [
            {"role": "system", "content": f"You are {bot_name}. React briefly showing emotion."},
            {"role": "user", "content": request_data.message}
        ]
        try:
            response = litellm.completion(
                model="gemini/gemini-1.5-flash", 
                messages=messages, 
                stream=False, 
                max_tokens=50,
                timeout=20  # Reduced timeout
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Gemini API failed: {e}")
            return f"{bot_name} is thinking: '{request_data.message}'"

    def extract_context(self, text: str) -> Dict[str, str]:
        """Extract context with improved error handling"""
        prompt = f"""
        Analyze the following text and extract emotional context information.
        Return ONLY a valid JSON object with exactly these three keys: emotion, location, action.
        
        Text: "{text}"
        
        Example response:
        {{"emotion": "happy", "location": "a room", "action": "smiling"}}
        """
        try:
            response = litellm.completion(
                model="gemini/gemini-1.5-flash",
                messages=[{"role": "user", "content": prompt}],
                timeout=20  # Reduced timeout
            )
            content = response.choices[0].message.content
            # Clean up the response to extract JSON
            cleaned = re.sub(r'```json\s*|\s*```', '', content).strip()
            cleaned = re.sub(r'^[^{]*(\{.*\})[^}]*$', r'\1', cleaned, flags=re.DOTALL)
            
            result = json.loads(cleaned)
            
            # Ensure all required keys exist and have non-None values
            context = {
                "emotion": result.get("emotion") or "neutral",
                "location": result.get("location") or "a room", 
                "action": result.get("action") or "looking at camera"
            }
            
            logger.info(f"Extracted context: {context}")
            return context
            
        except Exception as e:
            logger.warning(f"Context extraction failed: {e}")
            return {"emotion": "neutral", "location": "a room", "action": "looking at camera"}

    # main.py (Changes to existing function)

    async def generate_and_save_selfie(self, bot_name: str, base_image_path: str, context: Dict) -> tuple[str, str]:
        """Generate and save selfie with improved cancellation handling"""
        if not self.gradio_client:
            raise HTTPException(status_code=503, detail="Image service unavailable.")

        prompt_text = (
            f"Close-up portrait of a person like reference image, {context.get('emotion', 'neutral')}, "
            f"{context.get('action', 'looking at camera')}, at {context.get('location', 'a room')}. "
            f"The person's name is {bot_name}. Ultra-detailed, cinematic."
        )
        
        # Define a new list of fallback spaces to be more resilient
        # The original file has this, ensure this list is still there
        FALLBACK_SPACES = [
            "multimodalart/Ip-Adapter-FaceID",
            # Add a few more as backups if needed
            # "InstantX/InstantID",
        ]

        last_error = None

        for attempt in range(MAX_RETRIES):
            if shutdown_event.is_set():
                raise HTTPException(status_code=503, detail="Service is shutting down")

            gradio_task = None
            try:
                logger.info(f"Generating image (attempt {attempt + 1}/{MAX_RETRIES}) with prompt: {prompt_text}")

                request_cancelled = asyncio.Event()

                gradio_task = asyncio.create_task(
                    self._safe_gradio_predict(base_image_path, prompt_text, request_cancelled)
                )

                done, pending = await asyncio.wait(
                    [gradio_task, asyncio.create_task(shutdown_event.wait())],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=GRADIO_TIMEOUT
                )

                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                if shutdown_event.is_set():
                    request_cancelled.set()
                    raise HTTPException(status_code=503, detail="Service is shutting down")

                if gradio_task in done:
                    result = await gradio_task
                    return await self._process_gradio_result(result)
                else:
                    request_cancelled.set()
                    raise asyncio.TimeoutError("Image generation timed out")

            except asyncio.CancelledError:
                logger.warning(f"Attempt {attempt + 1} was cancelled. Retrying...")
                last_error = "Request was cancelled"
                if gradio_task and not gradio_task.done():
                    gradio_task.cancel()
                continue
                
            except asyncio.TimeoutError:
                logger.warning(f"Attempt {attempt + 1} timed out after {GRADIO_TIMEOUT} seconds")
                last_error = f"Timeout after {GRADIO_TIMEOUT}s"
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed with error: {e}")
                last_error = str(e)
            
            # This code block is a crucial part of the retry logic.
            if attempt < MAX_RETRIES - 1:
                # Check for a specific pattern of failure that might be solved by switching spaces
                if ("cancelled" in last_error.lower() or "timeout" in last_error.lower()) and self.current_space == FALLBACK_SPACES[0]:
                    logger.info("Persistent failure detected. Attempting to reinitialize Gradio client with a fallback space.")
                    await self.reinitialize_gradio_client()

                if not shutdown_event.is_set():
                    delay = min((2 ** attempt) + random.uniform(0, 1), 10)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    try:
                        await asyncio.wait_for(asyncio.sleep(delay), timeout=delay + 1)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        logger.info("Retry delay was interrupted")
                        raise HTTPException(status_code=503, detail="Request was cancelled")

        # This code block will be reached only if all attempts fail.
        # It explicitly raises an exception, preventing the TypeError.
        logger.error(f"All {MAX_RETRIES} attempts failed for image generation. Last error: {last_error}")
        self._record_error()
        raise HTTPException(
            status_code=503,
            detail=f"Image generation failed after {MAX_RETRIES} attempts. Last error: {last_error}"
        )
       
               
    async def _safe_gradio_predict(self, base_image_path: str, prompt_text: str, cancellation_event: asyncio.Event):
        """Safely run gradio prediction with cancellation support"""
        def run_prediction():
            return self.gradio_client.predict(
                images=[handle_file(base_image_path)],
                prompt=prompt_text,
                negative_prompt="nsfw, low quality, deformed, ugly, blurry",
                api_name="/generate_image"
            )
        
        # Run the prediction in a thread
        prediction_task = asyncio.create_task(asyncio.to_thread(run_prediction))
        
        # Wait for either completion or cancellation
        done, pending = await asyncio.wait(
            [prediction_task, asyncio.create_task(cancellation_event.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        if prediction_task in done:
            return await prediction_task
        else:
            raise asyncio.CancelledError("Prediction was cancelled")

    async def _process_gradio_result(self, result) -> tuple[str, str]:
        """Process gradio result and save image"""
        if not result or not isinstance(result, list) or len(result) == 0:
            logger.error(f"Invalid or empty image response from Gradio: {result}")
            raise ValueError("Invalid or empty image response.")
        
        # Handle different response formats
        try:
            if isinstance(result[0], dict) and "image" in result[0]:
                temp_path = result[0]["image"]
            elif isinstance(result[0], str):
                temp_path = result[0]
            else:
                temp_path = result[0]
        except (IndexError, TypeError, KeyError) as e:
            logger.error(f"Unexpected Gradio result format: {result} | Error: {e}")
            raise ValueError("Unexpected image data format from API.")
            
        # Verify the file exists and is readable
        if not os.path.exists(temp_path):
            raise ValueError(f"Generated image file not found: {temp_path}")

        with open(temp_path, "rb") as f:
            image_bytes = f.read()
        
        if len(image_bytes) == 0:
            raise ValueError("Generated image file is empty")
            
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        unique_filename = f"{uuid.uuid4()}.png"
        output_path = f"static/images/{unique_filename}"
        with open(output_path, "wb") as f:
            f.write(image_bytes)

        logger.info(f"Image successfully generated and saved: {output_path}")
        return f"/static/images/{unique_filename}", image_base64
    
    async def log_conversation_to_supabase(self, request_data: ImageGenerationRequest, response_data: ImageGenerationResponse):
        """Log conversation with timeout handling"""
        if not self.supabase_client:
            return

        def db_ops():
            try:
                conv_payload = {
                    "bot_id": request_data.bot_id,
                    "user_email": request_data.email,
                    "username": request_data.username,
                    "user_message": request_data.message,
                    "previous_conversation": request_data.previous_conversation,
                    "image_url": response_data.image_url,
                    "image_base64": response_data.image_base64,
                }
                conv_resp = self.supabase_client.table("conversations").insert(conv_payload).execute()
                conv_id = conv_resp.data[0]["id"]
                emotion_payload = {
                    "conversation_id": conv_id,
                    "emotion": response_data.emotion_context.get("emotion"),
                    "location": response_data.emotion_context.get("location"),
                    "action": response_data.emotion_context.get("action")
                }
                self.supabase_client.table("emotion_contexts").insert(emotion_payload).execute()
                logger.info(f"Successfully logged conversation {conv_id} to Supabase")
            except Exception as e:
                logger.error(f"Supabase logging failed: {e}")

        try:
            await asyncio.wait_for(asyncio.to_thread(db_ops), timeout=15.0)
        except asyncio.TimeoutError:
            logger.error("Supabase logging timed out")
        except Exception as e:
            logger.error(f"Error in Supabase logging: {e}")

# --- Global Service ---
chatbot_service = ChatbotService()

# --- Routes ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"status": "error", "message": exc.detail})

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500, 
        content={"status": "error", "message": "Internal server error"}
    )

@app.get("/", include_in_schema=False)
def root():
    return {"status": "healthy", "message": "AI Image Generation API is running."}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "status": "healthy" if not shutdown_event.is_set() else "shutting_down",
        "gradio_client": "connected" if chatbot_service.gradio_client else "disconnected",
        "current_space": chatbot_service.current_space,
        "supabase": "connected" if chatbot_service.supabase_client else "not configured",
        "error_count": chatbot_service.error_count,
        "active_requests": len(active_requests)
    }
    
    status_code = 200 if (chatbot_service.gradio_client and not shutdown_event.is_set()) else 503
    return JSONResponse(status_code=status_code, content=health_status)

@app.get("/debug/gradio")
async def debug_gradio():
    """Debug endpoint to check Gradio client status"""
    if not chatbot_service.gradio_client:
        return {"status": "no_client", "space": None}
    
    try:
        # Try a simple heartbeat to the Gradio space
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            if chatbot_service.current_space:
                space_url = f"https://{chatbot_service.current_space.replace('/', '-')}.hf.space"
                response = await client.get(space_url)
                return {
                    "status": "connected",
                    "space": chatbot_service.current_space,
                    "space_reachable": response.status_code == 200,
                    "error_count": chatbot_service.error_count
                }
    except Exception as e:
        return {
            "status": "error",
            "space": chatbot_service.current_space,
            "error": str(e),
            "error_count": chatbot_service.error_count
        }

@app.post("/v1/generate_image", response_model=ImageGenerationResponse)
async def generate_image(request: ImageGenerationRequest, http_request: Request, background_tasks: BackgroundTasks):
    """Generate image endpoint with improved cancellation handling"""
    if shutdown_event.is_set():
        logger.warning("Shutdown event is set, rejecting new request.")
        raise HTTPException(status_code=503, detail="Service is shutting down")

    start_time = time.time()
    request_task = asyncio.current_task()
    active_requests.add(request_task)

    try:
        # Validate bot_id
        if request.bot_id not in VALID_BOT_IDS:
            raise HTTPException(status_code=404, detail=f"Bot '{request.bot_id}' is not valid.")

        # Check for base image
        photos_dir = "photos"
        base_image_path = None
        for ext in [".jpeg", ".jpg", ".png", ".webp"]:
            potential_path = os.path.join(photos_dir, f"{request.bot_id}{ext}")
            if os.path.exists(potential_path):
                base_image_path = potential_path
                break
        
        if not base_image_path:
            raise HTTPException(status_code=404, detail=f"Base image for bot '{request.bot_id}' not found.")

        # Check if Gradio client is available
        if not chatbot_service.gradio_client:
            logger.warning("Gradio client not available, attempting to reinitialize...")
            success = await chatbot_service.initialize_gradio_client()
            if not success:
                raise HTTPException(status_code=503, detail="Image generation service is currently unavailable.")

        # Generate bot response and extract context
        bot_name = request.bot_id.replace("_", " ").title()
        
        try:
            bot_response = chatbot_service.get_bot_response_for_context(request, bot_name)
            context = chatbot_service.extract_context(bot_response)
        except Exception as e:
            logger.warning(f"Context generation failed, using defaults: {e}")
            context = {"emotion": "neutral", "location": "a room", "action": "looking at camera"}

        # Generate image
        # Generate image
        image_path, image_base64 = await chatbot_service.generate_and_save_selfie(
            bot_name, base_image_path, context
        )

        # ✅ Ensure proper localhost URL
        IMAGE_SERVER_BASE = os.environ.get("IMAGE_SERVER_BASE", "https://fastapi-imagegen-2l5aaarlka-uc.a.run.app")
        full_url = f"{IMAGE_SERVER_BASE}{image_path}"

        # Create response
        final_response = ImageGenerationResponse(
            bot_id=request.bot_id,
            image_url=full_url,
            image_base64=image_base64,
            status="success",
            emotion_context=context
        )

        # Log to Supabase in background
        background_tasks.add_task(
            chatbot_service.log_conversation_to_supabase, 
            request, 
            final_response
        )

        processing_time = time.time() - start_time
        logger.info(f"Image generation completed in {processing_time:.2f} seconds -> {full_url}")
        
        return final_response

    except asyncio.CancelledError:
        if shutdown_event.is_set():
            logger.info("Request cancelled due to server shutdown.")
            raise HTTPException(status_code=503, detail="Service is shutting down")
        else:
            logger.warning("Request cancelled by client.")
            raise HTTPException(status_code=499, detail="Client closed connection")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in generate_image: {e}", exc_info=True)
        processing_time = time.time() - start_time
        logger.error(f"Failed after {processing_time:.2f} seconds")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        active_requests.discard(request_task)


# --- Run ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        timeout_keep_alive=30,
        timeout_notify=30,
        limit_concurrency=5,  # Reduced concurrency
        graceful_timeout=30
    )