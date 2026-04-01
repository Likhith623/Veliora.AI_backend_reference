import pytz # type: ignore
import requests, modal
import traceback
from datetime import datetime, timedelta, timezone , time
import logging
from MM2.bot_prompt import get_bot_prompt
import os
from supabase import Client, create_client
from pathlib import Path
from dotenv import load_dotenv
# This ensures it always looks for .env in the parent directory of MM2
PROJECT_ROOT = Path(__file__).parent.parent
DOTENV_FILE_PATH = PROJECT_ROOT / ".env"

# Load environment variables from the .env file
load_dotenv(dotenv_path=DOTENV_FILE_PATH)

# Add Supabase connection here
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_bot_personality(bot_id: str):
    # Fetch the bot personality data
    response = supabase.table("bot_personality_details") \
                       .select("bot_name, bot_city") \
                       .eq("bot_id", bot_id) \
                       .execute()

    if response.data:
        bot_data = response.data[0]
        bot_name = bot_data.get("bot_name", "Unknown")
        bot_city = bot_data.get("bot_city", "Unknown")
        return {"bot_name": bot_name, "bot_city": bot_city}
    else:
        return {"error": "Bot not found."}
# Map bot cities to their primary timezones
CITY_TIMEZONES = {
    "New Delhi": "Asia/Kolkata",
    "Tokyo": "Asia/Tokyo",
    "Paris": "Europe/Paris",
    "Berlin": "Europe/Berlin",
    "Punggol": "Asia/Singapore",
    "Sengkang": "Asia/Singapore",
    "Ang Mo Kio": "Asia/Singapore",
    "Bishan": "Asia/Singapore",
    "Tiong Bahru": "Asia/Singapore",
    "Tanjong Pagar": "Asia/Singapore",
    "Matara": "Asia/Colombo",
    "Negombo": "Asia/Colombo",
    "Galle": "Asia/Colombo",
    "Jaffna": "Asia/Colombo",
    "Colombo": "Asia/Colombo",
    "Kandy": "Asia/Colombo",
    "Guadalajara": "America/Mexico_City",
    "Oaxaca": "America/Mexico_City",
    "Mexico City": "America/Mexico_City",
    "San Miguel de Allende": "America/Mexico_City",
    "Merida": "America/Mexico_City",
    "Nad Al Sheba": "Asia/Dubai",
    "Al Warqa": "Asia/Dubai",
    "Al Ain": "Asia/Dubai",
    "Al Fahidi": "Asia/Dubai",
    "Jumeirah": "Asia/Dubai",
    "Al Barsha": "Asia/Dubai",
    # Add other cities as needed
}

logging.basicConfig(
    filename='addendum.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

def bot_current_time(bot_id):
    """Current Time Information based on Bot's Persona City"""
    bot_details = get_bot_personality(bot_id)
    bot_city = bot_details.get("bot_city")
    bot_timezone_str = CITY_TIMEZONES.get(bot_city, "UTC")  # Default to UTC
    
    try:
        bot_timezone = pytz.timezone(bot_timezone_str)
        utc_now = datetime.now(timezone.utc).replace(tzinfo=pytz.utc)
        current_time_in_bot_tz = utc_now.astimezone(bot_timezone)

        tz_abbr = current_time_in_bot_tz.strftime('%Z')
        tz_offset = current_time_in_bot_tz.strftime('%z')
        bot_timezone_info = f"{tz_abbr} ({tz_offset})" if tz_abbr and tz_abbr != tz_offset else f"UTC{tz_offset}"

        current_time_info = (
            f"Current Time (Bot's Local Time in {bot_city}): "
            f"{current_time_in_bot_tz.strftime('%Y-%m-%d %H:%M:%S')} {bot_timezone_info}"
        )
        logging.info(
            f'BOT TIMEZONE: {bot_timezone_str} | BOT ID: {bot_id} | BOT CITY: {bot_city} | CURRENT TIME: {current_time_info}'
        )
    except pytz.UnknownTimeZoneError:
        logging.warning(f"Unknown timezone: {bot_timezone_str} for bot_id: {bot_id}. Falling back to UTC.")
        current_utc_time = datetime.now(timezone.utc).replace(tzinfo=pytz.utc).isoformat()
        bot_timezone_info = "UTC"
        current_time_info = f"Current Time (Bot's Local Time): {current_utc_time} ({bot_timezone_info})"
        logging.error(f'EXCEPTION BLOCK: {current_time_info}')

    return current_time_info
