
from supabase import create_client, Client
from datetime import datetime, timezone
import logging
from typing import Dict, Optional
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables from the correct path
dotenv_path = Path('../.env')
load_dotenv(dotenv_path=dotenv_path)

# Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Add validation to ensure environment variables are loaded
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def upsert_user_xp(email: str, bot_id: str, xp_score: int = 0, coins: int = 0, magnitude: float = 0.0):
    """
    Upsert (insert or update) the user's XP, coins, and magnitude for a given bot.
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "email": email,
            "bot_id": bot_id,
            "xp_score": xp_score,
            "coins": coins,
            "magnitude": magnitude,
            "updated_at": now
        }
        
        # ✅ FIXED: Use the exact constraint name from your table
        res = supabase.table("user_xp").upsert(
            data, 
            on_conflict="email, bot_id"  # This matches your unique constraint
        ).execute()
        
        logging.info(f"✅ Updated XP for {email} - {bot_id}: XP={xp_score}, Coins={coins}, Magnitude={magnitude}")
        return res
    except Exception as e:
        logging.error(f"❌ Error upserting user XP: {e}")
        return None
    
    
def get_user_xp(email: str, bot_id: str):
    """
    Fetch the user's XP/coins/magnitude for a given bot.
    """
    try:
        res = supabase.table("user_xp").select("*").eq("email", email).eq("bot_id", bot_id).limit(1).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        logging.error(f"❌ Error fetching user XP: {e}")
        return None

def add_xp_to_user(email: str, bot_id: str, xp_increment: int):
    """
    Add XP points to a user's existing total
    """
    try:
        current_data = get_user_xp(email, bot_id)
        if current_data:
            new_xp = current_data["xp_score"] + xp_increment
            return upsert_user_xp(email, bot_id, xp_score=new_xp, 
                                coins=current_data["coins"], 
                                magnitude=current_data["magnitude"])
        else:
            # Create new entry
            return upsert_user_xp(email, bot_id, xp_score=xp_increment)
    except Exception as e:
        logging.error(f"❌ Error adding XP: {e}")
        return None

def add_coins_to_user(email: str, bot_id: str, coin_increment: int):
    """
    Add coins to a user's existing total
    """
    try:
        current_data = get_user_xp(email, bot_id)
        if current_data:
            new_coins = current_data["coins"] + coin_increment
            return upsert_user_xp(email, bot_id, xp_score=current_data["xp_score"], 
                                coins=new_coins, 
                                magnitude=current_data["magnitude"])
        else:
            # Create new entry
            return upsert_user_xp(email, bot_id, coins=coin_increment)
    except Exception as e:
        logging.error(f"❌ Error adding coins: {e}")
        return None

def update_magnitude_for_user(email: str, bot_id: str, magnitude: float):
    """
    Update the magnitude score for a user
    """
    try:
        current_data = get_user_xp(email, bot_id)
        if current_data:
            return upsert_user_xp(email, bot_id, 
                                xp_score=current_data["xp_score"], 
                                coins=current_data["coins"], 
                                magnitude=magnitude)
        else:
            # Create new entry
            return upsert_user_xp(email, bot_id, magnitude=magnitude)
    except Exception as e:
        logging.error(f"❌ Error updating magnitude: {e}")
        return None

def calculate_immediate_xp_from_magnitude(magnitude: float) -> int:
    """
    Convert magnitude (1.0-5.0) to immediate XP points (1-10)
    This provides instant XP feedback based on emotional intensity
    """
    # Scale magnitude to XP: 1.0 -> 1 XP, 5.0 -> 10 XP
    xp_points = int(round((magnitude - 1.0) * 2.25 + 1))
    return max(1, min(10, xp_points))  # Ensure 1-10 range

def award_immediate_xp_and_magnitude(email: str, bot_id: str, magnitude: float):
    """
    Award immediate XP based on magnitude and update user's total XP and coins
    Returns the calculation results for frontend display
    """
    try:
        import logging
        
        # Calculate immediate XP based on magnitude (1-10 XP based on 0-5 magnitude scale)
        immediate_xp = max(1, min(10, int(magnitude * 2)))
        
        # Get current user data
        current_user_data = get_user_xp(email, bot_id)
        
        if current_user_data:
            current_total_xp = current_user_data.get("xp_score", 0)
            current_total_coins = current_user_data.get("coins", 0)
        else:
            current_total_xp = 0
            current_total_coins = 0
        
        # Calculate new totals
        new_total_xp = current_total_xp + immediate_xp
        new_total_coins = current_total_coins + immediate_xp  # 1:1 ratio for simplicity
        
        # Update the database
        result = upsert_user_xp(email, bot_id, new_total_xp, new_total_coins, magnitude)
        
        if result:
            logging.info(f"🎯 Immediate XP awarded: {email} got +{immediate_xp} XP (magnitude: {magnitude:.2f}) | Total: {new_total_xp}")
            
            return {
                "success": True,
                "immediate_xp_awarded": immediate_xp,
                "current_total_xp": new_total_xp,
                "current_total_coins": new_total_coins,
                "magnitude": magnitude
            }
        else:
            return {
                "success": False,
                "immediate_xp_awarded": 0,
                "current_total_xp": current_total_xp,
                "current_total_coins": current_total_coins,
                "magnitude": magnitude,
                "error": "Database update failed"
            }
            
    except Exception as e:
        logging.error(f"❌ Error in award_immediate_xp_and_magnitude: {e}")
        return {
            "success": False,
            "immediate_xp_awarded": 0,
            "current_total_xp": 0,
            "current_total_coins": 0,
            "magnitude": magnitude,
            "error": str(e)
        }