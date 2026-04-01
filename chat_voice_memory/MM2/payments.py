import os
import logging
import uuid
from datetime import datetime, timedelta, date
from fastapi import APIRouter, HTTPException, Request, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import stripe
import re
import asyncio
from typing import Callable, Dict, Any
from datetime import datetime, timezone
# --- Initial Setup & Configuration ---

# 1. Load Environment Variables
load_dotenv()

# 2. Setup Production-Ready Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 3. Validate Required Environment Variables
required_env_vars = [
    "STRIPE_SECRET_KEY", 
    "STRIPE_WEBHOOK_SECRET",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "PAYMENT_SUCCESS_URL",
    "PAYMENT_CANCEL_URL",
    "CRON_SECRET_KEY"
]
for var in required_env_vars:
    if not os.getenv(var):
        error_msg = f"FATAL: Missing required environment variable: {var}"
        logger.error(error_msg)
        raise ValueError(error_msg)

# 4. Initialize Services
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# This is a placeholder for your actual Supabase client initialization.
# In a real application, this would be properly configured.
try:
    from MM2.utils import supabase
    # In a real app, you would also need a way to handle transactions.
    # This is a conceptual placeholder. You might need a library or a helper function for this.
    # from MM2.utils import db_transaction 
except ImportError:
    logger.error("Could not import Supabase client. Using mock objects for demonstration.")
    # Mock objects for demonstration purposes if Supabase is not installed.
    class MockSupabaseQuery:
        def select(self, *args, **kwargs): return self
        def update(self, *args, **kwargs): return self
        def insert(self, *args, **kwargs): return self
        def eq(self, *args, **kwargs): return self
        def lt(self, *args, **kwargs): return self
        def execute(self):
            class MockResponse:
                def __init__(self): self.data = []
            return MockResponse()
    class MockSupabaseClient:
        def table(self, name): return MockSupabaseQuery()
    supabase = MockSupabaseClient()
    # Mock transaction handler
    async def db_transaction(operations_func, *args, **kwargs):
        logger.info("Executing mock transaction.")
        return await operations_func(*args, **kwargs)
    
    
    
#REPLACE WITH THE REAL STRIPE ID'S
# 5. Define Your Product Plans
PRICE_TO_PLAN_DETAILS = {
    "price_1PG...monthly": {"duration_days": 30, "plan_name": "Monthly"},
    "price_1PG...annual": {"duration_days": 365, "plan_name": "Annual"},
}

# --- API Router and Security ---

router = APIRouter()
bearer_scheme = HTTPBearer()

# --- CHANGE: Placeholder for Real User Authentication ---
# In your real application, this function would validate a JWT or session token
# and return the user's details from your database.
async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)) -> Dict[str, Any]:
    """
    Real user authentication - FIXED to work with your database schema
    """
    token = credentials.credentials
    
    # For now, using your mock logic but with correct field mapping
    if token == "fake-super-secret-token":
        # Fetch user from database using email (you'll replace this with real JWT logic)
        try:
            user_query = lambda: supabase.table("user_details").select("*").eq("email", "test@example.com").execute()
            user_result = await db_operation_with_retry(user_query)
            
            if user_result.data:
                user_data = user_result.data[0]
                return {
                    "user_id": str(user_data["id"]),  # Use primary key 'id' as user_id
                    "email": user_data["email"],
                    "stripe_customer_id": user_data.get("stripe_customer_id"),
                    "name": user_data.get("name", ""),
                    "subscription_status": user_data.get("subscription_status", "Free trial")
                }
        except Exception as e:
            logger.error(f"Error fetching user: {e}")
            
    raise HTTPException(
        status_code=401,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

def get_cron_secret(credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)) -> None:
    """Dependency to secure an endpoint with a static bearer token."""
    if credentials.credentials != os.getenv("CRON_SECRET_KEY"):
        logger.warning("Unauthorized attempt to access a cron endpoint.")
        raise HTTPException(status_code=401, detail="Invalid cron secret token")

# --- Pydantic Models for Request Bodies ---

class CheckoutSessionRequest(BaseModel):
    price_id: str

# --- Helper Functions ---

def send_admin_alert(subject: str, details: str):
    """
    CRITICAL: Implement this function to send an email or Slack/Discord message
    to your admin team on critical failures.
    """
    logger.critical(f"--- ADMIN ALERT ---")
    logger.critical(f"Subject: {subject}")
    logger.critical(f"Details: {details}")
    logger.critical(f"-------------------")

async def db_operation_with_retry(operation: Callable, max_retries: int = 3, initial_wait: float = 0.5):
    """Executes a database operation with exponential backoff."""
    for attempt in range(max_retries):
        try:
            # Remove 'await' here
            return operation()
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Database operation failed after {max_retries} attempts.")
                raise e
            wait_time = initial_wait * (2 ** attempt)
            logger.warning(f"DB operation failed (attempt {attempt + 1}), retrying in {wait_time:.2f}s... Error: {e}")
            await asyncio.sleep(wait_time)

# --- Core Business Logic ---

async def fulfill_premium_upgrade_transaction(
    user_id: str, 
    stripe_customer_id: str, 
    price_id: str, 
    session_id: str
):
    """
    FIXED to work with your exact database schema
    """
    plan_details = PRICE_TO_PLAN_DETAILS.get(price_id)
    if not plan_details:
        raise ValueError(f"Invalid price_id '{price_id}' during fulfillment.")

    # Retrieve session to get exact amount paid
    stripe_session = stripe.checkout.Session.retrieve(session_id)
    payment_amount = stripe_session.amount_total / 100 if stripe_session.amount_total else 0
    
    # 1. Update user subscription - FIXED field mapping
    expires_at = date.today() + timedelta(days=plan_details["duration_days"])
    
    user_update_data = {
        "subscription_status": "Premium",
        "subscription_expires_at": expires_at.isoformat(),
        "payment_date": date.today().isoformat(),
        "payment_amount": payment_amount,
        "subscription_duration": f"{plan_details['duration_days']} days",
        "current_plan": plan_details["plan_name"]
    }
    
    # Use 'id' field (primary key) instead of 'user_id'
    await supabase.table("user_details").update(user_update_data).eq("id", user_id).execute()

    # 2. Record transaction - FIXED to use correct user_id reference
    transaction_data = {
        "stripe_session_id": session_id,
        "user_id": user_id,  # This references the id field from user_details table
        "stripe_customer_id": stripe_customer_id,
        "price_id": price_id,
        "payment_amount": payment_amount,
        "processed_at": datetime.utcnow().isoformat()
    }
    await supabase.table("payment_transactions").insert(transaction_data).execute()

    logger.info(f"Transaction complete for user {user_id} from session {session_id}. Amount: ${payment_amount}")


# --- API Endpoints ---

@router.post("/create-checkout-session")
async def create_checkout_session(
    req: CheckoutSessionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    FIXED to work with your database schema
    """
    price_id = req.price_id
    if price_id not in PRICE_TO_PLAN_DETAILS:
        raise HTTPException(status_code=400, detail="Invalid subscription plan selected.")

    user_id = current_user["user_id"]
    stripe_customer_id = current_user.get("stripe_customer_id")

    # Create Stripe customer if missing
    if not stripe_customer_id:
        logger.warning(f"User {user_id} is missing a Stripe Customer ID. Creating one now.")
        try:
            customer = stripe.Customer.create(
                email=current_user["email"], 
                name=current_user.get("name", ""),
                metadata={"user_id": user_id}
            )
            stripe_customer_id = customer.id
            
            # Save customer ID to database - FIXED to use 'id' field
            await db_operation_with_retry(
                lambda: supabase.table("user_details").update({
                    "stripe_customer_id": stripe_customer_id
                }).eq("id", user_id).execute()
            )
        except Exception as e:
            logger.error(f"Failed to create Stripe Customer for user {user_id}: {e}")
            raise HTTPException(status_code=503, detail="Could not initialize payment profile.")

    try:
        # Create Stripe Checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="payment",
            customer=stripe_customer_id,
            success_url=os.getenv("PAYMENT_SUCCESS_URL") + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=os.getenv("PAYMENT_CANCEL_URL"),
            metadata={
                "user_id": user_id,
                "price_id": price_id
            },
            expires_at=int((datetime.now() + timedelta(minutes=59)).timestamp())
        )
        
        logger.info(f"Checkout session {session.id} created for user {user_id}.")
        return {"checkout_url": session.url, "session_id": session.id}
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error for user {user_id}: {e}")
        raise HTTPException(status_code=502, detail="Payment provider error.")
    except Exception as e:
        logger.error(f"Unexpected error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handles incoming webhooks from Stripe, secured by signature verification."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET"))
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning(f"Invalid webhook signature. IP: {request.client.host}. Error: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session.get("id")
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        price_id = metadata.get("price_id")
        stripe_customer_id = session.get("customer")

        if not all([user_id, price_id, session_id, stripe_customer_id]):
            error_msg = f"Webhook {event['id']} missing critical data. Session: {session_id}, UserID: {user_id}"
            logger.error(error_msg)
            send_admin_alert("Webhook Error", error_msg)
            return {"status": "error", "reason": "Missing metadata"}

        # --- IDEMPOTENCY CHECK ---
        try:
            check_op = lambda: supabase.table("payment_transactions").select("id").eq("stripe_session_id", session_id).execute()
            processed_check = await db_operation_with_retry(check_op)
            if processed_check.data:
                logger.info(f"Webhook for session {session_id} already processed. Ignoring.")
                return {"status": "success", "detail": "already processed"}
        except Exception as e:
            logger.critical(f"DB FAILED during idempotency check for {session_id}: {e}")
            send_admin_alert("CRITICAL: DB Failure on Webhook", f"Could not check idempotency for {session_id}. Error: {e}")
            raise HTTPException(status_code=503, detail="Database unavailable. Webhook will be retried.")
        
        # --- CHANGE: ATOMIC FULFILLMENT ---
        try:
            # Wrap the core logic in a database transaction
            await db_transaction(
                fulfill_premium_upgrade_transaction,
                user_id=user_id,
                stripe_customer_id=stripe_customer_id,
                price_id=price_id,
                session_id=session_id
            )
            logger.info(f"Successfully fulfilled order via transaction for session {session_id}")
        except Exception as e:
            logger.error(f"CRITICAL: Transaction failed for session {session_id}: {e}")
            send_admin_alert(
                subject="CRITICAL: Payment Fulfillment Transaction Failed",
                details=f"User: {user_id}\nSession: {session_id}\nError: {e}"
            )
            # Return 500 so Stripe retries the webhook
            raise HTTPException(status_code=500, detail="Failed to fulfill order atomically.")

    return {"status": "success"}

@router.get("/session-status/{session_id}")
async def get_session_status(session_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Frontend endpoint to check a session's status. Secured to prevent enumeration."""
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        # Security check: Ensure the logged-in user is the one who owns this session
        if session.customer != current_user.get("stripe_customer_id"):
            logger.warning(f"User {current_user['user_id']} tried to access session {session_id} owned by another customer.")
            raise HTTPException(status_code=403, detail="Permission denied.")
            
        return {
            "status": session.status,
            "payment_status": session.payment_status,
        }
    except stripe.error.InvalidRequestError:
        raise HTTPException(status_code=404, detail="Session not found.")
    except Exception as e:
        logger.error(f"Error retrieving session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")

@router.post("/tasks/update-expired-subscriptions", dependencies=[Depends(get_cron_secret)])
async def update_expired_subscriptions_task():
    """
    SECURED cron job endpoint that efficiently reverts all expired subscriptions in a single query.
    """
    logger.info("Cron Task: Starting check for expired subscriptions.")
    today_iso = date.today().isoformat()
    
    try:
        # --- CHANGE: Scalable Bulk Update ---
        # This single query is vastly more efficient than looping through users.
        # It finds all premium users whose subscription expired *before* today and updates them.
        update_op = lambda: supabase.table("user_details").update({
            "subscription_status": "Free" # Or your desired default status
        }).eq("subscription_status", "Premium").lt("subscription_expires_at", today_iso).execute()

        result = await db_operation_with_retry(update_op)
        updated_count = len(result.data)
        
        logger.info(f"Cron Task: Successfully updated {updated_count} expired subscriptions.")
        return {"status": "success", "updated_count": updated_count}
        
    except Exception as e:
        error_msg = f"Cron Task FAILED: {e}"
        logger.critical(error_msg)
        send_admin_alert("CRITICAL: Daily Cron Job Failed", error_msg)
        raise HTTPException(status_code=500, detail="Internal error during scheduled task.")

# Add subscription status endpoint for frontend
@router.get("/subscription-status/{user_id}")
async def get_subscription_status(user_id: str):
    """
    Get subscription status - FIXED for your database schema
    """
    try:
        user_query = lambda: supabase.table("user_details").select(
            "subscription_status, subscription_expires_at, current_plan, payment_amount, payment_date"
        ).eq("id", user_id).execute()
        
        result = await db_operation_with_retry(user_query)
        
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = result.data[0]
        subscription_status = user_data.get("subscription_status", "Free trial")
        expires_at = user_data.get("subscription_expires_at")
        
        # Check if subscription is still active
        is_active = False
        days_remaining = 0
        
        if subscription_status == "Premium" and expires_at:
            try:
                expiry_date = date.fromisoformat(expires_at)
                today = date.today()
                is_active = expiry_date > today
                days_remaining = (expiry_date - today).days if is_active else 0
                
                # Auto-update expired subscriptions
                if not is_active:
                    update_op = lambda: supabase.table("user_details").update({
                        "subscription_status": "Free trial"
                    }).eq("id", user_id).execute()
                    await db_operation_with_retry(update_op)
                    subscription_status = "Free trial"
                    
            except ValueError:
                logger.warning(f"Invalid date format for user {user_id}: {expires_at}")
        
        return {
            "user_id": user_id,
            "subscription_status": subscription_status,
            "is_active": is_active,
            "expires_at": expires_at,
            "days_remaining": days_remaining,
            "current_plan": user_data.get("current_plan"),
            "payment_amount": user_data.get("payment_amount"),
            "payment_date": user_data.get("payment_date")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking subscription status for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")



@router.get("/subscription-status/by-email/{email}")
async def get_subscription_status_by_email(email: str):
    """
    Get subscription status using email instead of user_id (UUID)
    """
    try:
        # Find user by email
        user_query = lambda: supabase.table("user_details").select(
            "id, subscription_status, subscription_expires_at, current_plan, payment_amount, payment_date"
        ).eq("email", email).execute()
        result = await db_operation_with_retry(user_query)
        
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = result.data[0]
        subscription_status = user_data.get("subscription_status", "Free trial")
        expires_at = user_data.get("subscription_expires_at")
        user_id = str(user_data.get("id"))
        
        # Check if subscription is still active
        is_active = False
        days_remaining = 0
        
        if subscription_status == "Premium" and expires_at:
            try:
                expiry_date = date.fromisoformat(expires_at)
                today = date.today()
                is_active = expiry_date > today
                days_remaining = (expiry_date - today).days if is_active else 0
                
                # Auto-update expired subscriptions
                if not is_active:
                    update_op = lambda: supabase.table("user_details").update({
                        "subscription_status": "Free trial"
                    }).eq("email", email).execute()
                    await db_operation_with_retry(update_op)
                    subscription_status = "Free trial"
                    
            except ValueError:
                logger.warning(f"Invalid date format for user {user_id}: {expires_at}")
        
        return {
            "user_id": user_id,
            "email": email,
            "subscription_status": subscription_status,
            "is_active": is_active,
            "expires_at": expires_at,
            "days_remaining": days_remaining,
            "current_plan": user_data.get("current_plan"),
            "payment_amount": user_data.get("payment_amount"),
            "payment_date": user_data.get("payment_date")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking subscription status for email {email}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Add these imports at the top
import uuid
from datetime import datetime, timezone

# Add these testing endpoints at the end of your file

# --- TESTING ENDPOINTS FOR SWAGGER UI ---

class ManualUpgradeRequest(BaseModel):
    email: str
    plan_type: str  # "monthly" or "annual"
    test_mode: bool = True

@router.post("/test/manual-upgrade")
async def manual_upgrade_user(request: ManualUpgradeRequest):
    """
    TESTING: Manually upgrade a user to premium for testing purposes
    """
    try:
        logger.info(f"🧪 Manual upgrade test for {request.email} to {request.plan_type}")
        
        # Get user from database
        user_query = lambda: supabase.table("user_details").select("*").eq("email", request.email).execute()
        user_result = await db_operation_with_retry(user_query)
        
        if not user_result.data:
            # Create test user if not exists
            test_user_data = {
                "email": request.email,
                "name": f"Test User {request.email}",
                "subscription_status": "Free trial",
                "created_at": datetime.utcnow().isoformat()
            }
            
            create_user = lambda: supabase.table("user_details").insert(test_user_data).execute()
            user_result = await db_operation_with_retry(create_user)
            
            if not user_result.data:
                raise HTTPException(status_code=500, detail="Failed to create test user")
        
        user_data = user_result.data[0]
        user_id = str(user_data["id"])
        
        # Determine plan details
        if request.plan_type == "monthly":
            duration_days = 30
            plan_name = "Monthly Test"
        else:
            duration_days = 365
            plan_name = "Annual Test"
        
        # Calculate expiry date
        expires_at = date.today() + timedelta(days=duration_days)
        
        # Update user to premium
        user_update_data = {
            "subscription_status": "Premium",
            "subscription_expires_at": expires_at.isoformat(),
            "payment_date": date.today().isoformat(),
            "payment_amount": 29.99 if request.plan_type == "monthly" else 299.99,
            "subscription_duration": f"{duration_days} days",
            "current_plan": plan_name
        }
        
        update_op = lambda: supabase.table("user_details").update(user_update_data).eq("id", user_id).execute()
        result = await db_operation_with_retry(update_op)
        
        # Create test transaction record
        test_session_id = f"test_session_{uuid.uuid4().hex[:16]}"
        transaction_data = {
            "stripe_session_id": test_session_id,
            "user_id": user_id,
            "stripe_customer_id": f"test_customer_{user_id}",
            "price_id": f"test_price_{request.plan_type}",
            "payment_amount": user_update_data["payment_amount"],
            "processed_at": datetime.utcnow().isoformat()
        }
        
        transaction_op = lambda: supabase.table("payment_transactions").insert(transaction_data).execute()
        transaction_result = await db_operation_with_retry(transaction_op)
        
        return {
            "success": True,
            "message": f"✅ Successfully upgraded {request.email} to {plan_name}",
            "user_id": user_id,
            "expires_at": expires_at.isoformat(),
            "plan_details": {
                "plan_name": plan_name,
                "duration_days": duration_days,
                "payment_amount": user_update_data["payment_amount"]
            },
            "test_session_id": test_session_id
        }
        
    except Exception as e:
        logger.error(f"❌ Manual upgrade test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Manual upgrade failed: {str(e)}")

@router.get("/test/user-status/{email}")
async def get_test_user_status(email: str):
    """
    TESTING: Get user subscription status by email for testing
    """
    try:
        user_query = lambda: supabase.table("user_details").select("*").eq("email", email).execute()
        result = await db_operation_with_retry(user_query)
        
        if not result.data:
            return {
                "found": False,
                "message": f"No user found with email: {email}"
            }
        
        user_data = result.data[0]
        expires_at = user_data.get("subscription_expires_at")
        
        # Check if subscription is active
        is_active = False
        days_remaining = 0
        
        if user_data.get("subscription_status") == "Premium" and expires_at:
            try:
                expiry_date = date.fromisoformat(expires_at)
                today = date.today()
                is_active = expiry_date > today
                days_remaining = (expiry_date - today).days if is_active else 0
            except ValueError:
                pass
        
        return {
            "found": True,
            "user_id": str(user_data["id"]),
            "email": user_data["email"],
            "name": user_data.get("name"),
            "subscription_status": user_data.get("subscription_status"),
            "current_plan": user_data.get("current_plan"),
            "subscription_expires_at": expires_at,
            "is_active": is_active,
            "days_remaining": days_remaining,
            "payment_amount": user_data.get("payment_amount"),
            "payment_date": user_data.get("payment_date"),
            "subscription_duration": user_data.get("subscription_duration"),
            "stripe_customer_id": user_data.get("stripe_customer_id")
        }
        
    except Exception as e:
        logger.error(f"❌ Test user status failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user status: {str(e)}")

class CreateTestUserRequest(BaseModel):
    email: str
    name: str
    subscription_status: str = "Free trial"

@router.post("/test/create-user")
async def create_test_user(request: CreateTestUserRequest):
    """
    TESTING: Create a test user for payment testing
    """
    try:
        # Check if user already exists
        user_query = lambda: supabase.table("user_details").select("*").eq("email", request.email).execute()
        existing_result = await db_operation_with_retry(user_query)
        
        if existing_result.data:
            return {
                "success": False,
                "message": f"User with email {request.email} already exists",
                "existing_user": existing_result.data[0]
            }
        
        # Create new test user
        test_user_data = {
            "email": request.email,
            "name": request.name,
            "subscription_status": request.subscription_status,
            "created_at": datetime.utcnow().isoformat()
        }
        
        create_op = lambda: supabase.table("user_details").insert(test_user_data).execute()
        result = await db_operation_with_retry(create_op)
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create test user")
        
        return {
            "success": True,
            "message": f"✅ Test user created successfully",
            "user_data": result.data[0]
        }
        
    except Exception as e:
        logger.error(f"❌ Create test user failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create test user: {str(e)}")

@router.delete("/test/reset-user/{email}")
async def reset_test_user(email: str):
    """
    TESTING: Reset a user back to free trial status
    """
    try:
        # Reset user subscription
        reset_data = {
            "subscription_status": "Free trial",
            "subscription_expires_at": None,
            "payment_date": None,
            "payment_amount": None,
            "subscription_duration": None,
            "current_plan": None
        }
        
        reset_op = lambda: supabase.table("user_details").update(reset_data).eq("email", email).execute()
        result = await db_operation_with_retry(reset_op)
        
        return {
            "success": True,
            "message": f"✅ Reset {email} to free trial status",
            "updated_records": len(result.data) if result.data else 0
        }
        
    except Exception as e:
        logger.error(f"❌ Reset test user failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset user: {str(e)}")

@router.get("/test/transactions/{email}")
async def get_user_transactions(email: str):
    """
    TESTING: Get all payment transactions for a user
    """
    try:
        # Get user ID first
        user_query = lambda: supabase.table("user_details").select("id").eq("email", email).execute()
        user_result = await db_operation_with_retry(user_query)
        
        if not user_result.data:
            return {
                "found": False,
                "message": f"No user found with email: {email}",
                "transactions": []
            }
        
        user_id = str(user_result.data[0]["id"])
        
        # Get transactions
        transaction_query = lambda: supabase.table("payment_transactions").select("*").eq("user_id", user_id).execute()
        transactions = await db_operation_with_retry(transaction_query)
        
        return {
            "found": True,
            "user_id": user_id,
            "email": email,
            "transaction_count": len(transactions.data) if transactions.data else 0,
            "transactions": transactions.data if transactions.data else []
        }
        
    except Exception as e:
        logger.error(f"❌ Get user transactions failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get transactions: {str(e)}")

@router.get("/test/system-status")
async def get_system_status():
    """
    TESTING: Get overall system status for payment testing
    """
    try:
        # Test database connection
        test_query = lambda: supabase.table("user_details").select("id").limit(1).execute()
        db_test = await db_operation_with_retry(test_query)
        
        # Count users by status
        all_users = lambda: supabase.table("user_details").select("subscription_status").execute()
        users_result = await db_operation_with_retry(all_users)
        
        status_counts = {}
        if users_result.data:
            for user in users_result.data:
                status = user.get("subscription_status", "Unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count transactions
        all_transactions = lambda: supabase.table("payment_transactions").select("id").execute()
        transactions_result = await db_operation_with_retry(all_transactions)
        
        return {
            "system_status": "✅ Operational",
            "database_connected": True,
            "environment_variables": {
                "SUPABASE_URL": "✅ Set" if os.getenv("SUPABASE_URL") else "❌ Missing",
                "SUPABASE_KEY": "✅ Set" if os.getenv("SUPABASE_KEY") else "❌ Missing",
                "STRIPE_SECRET_KEY": "✅ Set" if os.getenv("STRIPE_SECRET_KEY") else "❌ Missing",
                "CRON_SECRET_KEY": "✅ Set" if os.getenv("CRON_SECRET_KEY") else "❌ Missing",
            },
            "user_statistics": {
                "total_users": len(users_result.data) if users_result.data else 0,
                "status_breakdown": status_counts
            },
            "transaction_statistics": {
                "total_transactions": len(transactions_result.data) if transactions_result.data else 0
            },
            "test_endpoints_available": [
                "POST /payments/test/create-user",
                "POST /payments/test/manual-upgrade", 
                "GET /payments/test/user-status/{email}",
                "GET /payments/test/transactions/{email}",
                "DELETE /payments/test/reset-user/{email}",
                "GET /payments/test/system-status"
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ System status check failed: {e}")
        return {
            "system_status": "❌ Error",
            "database_connected": False,
            "error": str(e)
        }

# Add health check for payment system
@router.get("/health")
async def payment_system_health():
    """
    Health check for payment system
    """
    try:
        # Test basic functionality
        test_query = lambda: supabase.table("user_details").select("id").limit(1).execute()
        await db_operation_with_retry(test_query)
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": "✅ Connected",
                "stripe": "✅ Configured" if stripe.api_key else "❌ Not configured",
                "environment": "✅ All variables set"
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }