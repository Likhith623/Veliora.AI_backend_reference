#helping functions related to read, write and publish model metrics
#utils
import requests # type: ignore
import os
import httpx
from dotenv import load_dotenv # type: ignore
load_dotenv()
from openai import AsyncOpenAI # type: ignore
from openai import OpenAI
import logging
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from newspaper import Article
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import json
from datetime import datetime
from llama_index.llms.google_genai import GoogleGenAI

from MM2.bot_prompt import get_bot_prompt
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

import re
import time
import json
import random
import pytz # type: ignore
import requests, modal
import traceback
from datetime import datetime, timedelta, timezone , time
# import datetime

import string
import uuid







from MM2.memory_functions import get_semantically_similar_memories, get_highest_rfm_memories, get_embedding
from MM2.redis_class import RedisManager
redis_manager = RedisManager()




from pinecone import Pinecone, ServerlessSpec


# from supabase import create_client, Client #type: ignore
from supabase import Client, create_client #type: ignore
from MM2.prompt import ORIGIN_IDENTIFICATION_SYSTEM_PROMPT,REMINDER_BLEND_RESPONSE_SYSTEM_PROMPT

#importing ML libraries for the pretrained BERT for NSFW-classification
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
from transformers import TrainingArguments, Trainer
import torch

#logging into huggingface cause the model is currently private and requires login for use
from huggingface_hub import login
import os
import logging
hf_token = os.getenv("HF_TOKEN")
if hf_token and hf_token.startswith("hf_"):
    login(token=hf_token)
else:
    logging.warning(f"HF_TOKEN is not set or invalid: {hf_token}")

#loading the Classifier for use
def load_classifier():
    tokenizer = AutoTokenizer.from_pretrained("CultureVo/fine-tuned_BERT_for_NSFW_classifier")
    model = AutoModelForSequenceClassification.from_pretrained("CultureVo/fine-tuned_BERT_for_NSFW_classifier")
    classifier = pipeline("text-classification", model = model, tokenizer = tokenizer)
    return classifier

# Use it like this:
classifier = load_classifier()

def prRed(skk): print("\033[91m{}\033[00m" .format(skk))
def prGreen(skk): print("\033[92m{}\033[00m" .format(skk))
def prYellow(skk): print("\033[93m{}\033[00m" .format(skk))
def prLightPurple(skk): print("\033[94m{}\033[00m" .format(skk))
def prPurple(skk): print("\033[95m{}\033[00m" .format(skk))
def prCyan(skk): print("\033[96m{}\033[00m" .format(skk))
def prLightGray(skk): print("\033[97m{}\033[00m" .format(skk))
def prBlack(skk): print("\033[98m{}\033[00m" .format(skk))

# Initialize a Pinecone client with your API key
api_key = os.getenv("PINECONE_API_KEY")  # Change from PINECONE_API to PINECONE_API_KEY
if not api_key:
    raise ValueError("PINECONE_API_KEY environment variable is not set")

pc = Pinecone(api_key=api_key)  # Use the validated api_key variable

# Create a serverless index
index_name = "noviai-mm2"

# Check if index exists using list_indexes() instead of has_index()
existing_indexes = [index.name for index in pc.list_indexes()]
if index_name not in existing_indexes:  # Replace the has_index check
    pc.create_index(
        name=index_name,
        dimension=1024,
        metric="cosine",
        spec=ServerlessSpec(
            cloud='aws',
            region='us-east-1'
        )
    )

# Wait for the index to be ready
while not pc.describe_index(index_name).status['ready']:
    time.sleep(1)

index = pc.Index(index_name) #Index name will be constant

# Supabase connection details
SUPABASE_URL = os.getenv("SUPABASE_URL")  # Supabase project URL from environment variable
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Supabase API key from environment variable
API_KEY = os.getenv("SUMMARY_API_KEY")
MODEL_NAME = "sonar-reasoning"

# Create a Supabase client using project URL and API key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def log_to_supabase(message,email,bot_id,bot_response,relative_data,extracted_data):
    data = {
        "message" : message,
        "email" : email,
        "bot_id" : bot_id,
        "bot_response" : bot_response,
        "vector_retrieved_data" : relative_data,
        "extracted_data" : extracted_data,
    }

    response = supabase.table("new_message_logs").insert(data).execute()

    return response
# Add this function to utils.py

# Update your call_xai_api function around line 89:














def call_gemini_ai(prompt, max_tokens=300):
    """
    Calls Gemini AI (Google Generative AI) to summarize content.
    You must have the `google-generativeai` package installed and your API key set as GEMINI_API_KEY.
    """
    import google.generativeai as genai
    import os

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY environment variable is not set")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=0.7,
        )
    )
    return response.text.strip()

















def detect_urls_in_query(query):
    """Detect if the query contains website URLs with enhanced YouTube detection"""
    print(f"🔍 Checking for URLs in query: {query}")

    # Fixed URL patterns with proper ordering (specific first, general last)
    url_patterns = [
        r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+(?:&[\w=&-]*)?',  # Full YouTube URLs
        r'https?://youtu\.be/[\w-]+(?:\?[\w=&-]*)?',                       # Short YouTube URLs
        r'https?://[^\s]+\.[a-zA-Z]{2,}(?:/[^\s]*)?',                     # Complete HTTPS URLs
        r'http://[^\s]+\.[a-zA-Z]{2,}(?:/[^\s]*)?',                       # Complete HTTP URLs
        r'www\.[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?',                 # www. URLs
    ]

    found_urls = []

    # Process patterns in order, skip general patterns if specific ones match
    for i, pattern in enumerate(url_patterns):
        matches = re.findall(pattern, query, re.IGNORECASE)
        for match in matches:
            # Clean the URL
            clean_url = match.strip().rstrip('.,;:!?')

            # Ensure proper protocol
            if not clean_url.startswith(('http://', 'https://')):
                if 'youtube.com' in clean_url or 'youtu.be' in clean_url:
                    clean_url = 'https://' + clean_url
                else:
                    clean_url = 'https://' + clean_url

            # Validate URL structure and avoid duplicates
            try:
                parsed = urlparse(clean_url)
                if parsed.netloc and parsed.scheme in ['http', 'https']:
                    # Check if this URL is already found (avoid duplicates)
                    if not any(clean_url.startswith(existing) or existing.startswith(clean_url) for existing in found_urls):
                        found_urls.append(clean_url)
                        print(f"✅ Found valid URL: {clean_url}")
            except:
                continue

        # If we found YouTube URLs, skip general patterns to avoid duplicates
        if i < 2 and found_urls:  # YouTube patterns are first two
            break

    return found_urls


def fetch_website_content(url):
    print(f"🌐 Fetching content from: {url}")

    # Try newspaper3k first
    try:
        article = Article(url)
        article.download()
        article.parse()
        text = article.text
        title = article.title or ""
        if text and len(text.split()) > 50:
            print("✅ Extracted content with newspaper3k")
            return {
                'title': title,
                'content': text,
                'url': url,
                'type': 'website',
                'extracted_at': datetime.now().isoformat()
            }
        else:
            print("⚠️ newspaper3k returned too little content, falling back to Selenium...")
    except Exception as e:
        print(f"❌ Error extracting with newspaper3k: {e}")
        print("⚠️ Falling back to Selenium + BeautifulSoup...")
        # === ADD DEBUG HERE ===
    import time
    print("DEBUG: time =", time)
    print("DEBUG: time.sleep =", getattr(time, 'sleep', '❌ NOT FOUND'))
    # ======================

    # Fallback: Selenium + BeautifulSoup (your existing code)
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)

        print("🚗 ChromeDriver started, loading URL...")
        driver.get(url)
        time.sleep(3)
        print("✅ Page loaded, extracting HTML...")
        html = driver.page_source
        driver.quit()
        print("✅ HTML extracted, parsing with BeautifulSoup...")
        soup = BeautifulSoup(html, 'html.parser')

        # Check for YouTube
        is_youtube = 'youtube.com/watch' in url or 'youtu.be/' in url
        if is_youtube:
            data = extract_youtube_content(soup, url)
            print("DEBUG: YouTube extraction result:", data)
            return data

        # For non-YouTube websites, use general extraction
        return extract_general_website_content(soup, url)

    except Exception as e:
        print(f"❌ Error fetching {url} with Selenium: {e}")
        return None

def extract_youtube_content(soup, url):
    """Extract detailed content from YouTube video pages with enhanced accuracy"""
    print("🎥 Extracting YouTube video content...")

    try:
        # Extract video ID for potential transcript access
        video_id = ""
        if 'watch?v=' in url:
            video_id = url.split('watch?v=')[1].split('&')[0]
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0]

        # Extract video title with multiple fallbacks
        title = ""
        title_selectors = [
            'meta[property="og:title"]',
            'meta[name="title"]',
            'title',
            'h1.ytd-video-primary-info-renderer',
            '[data-e2e="video-title"]',
            'h1.ytd-watch-metadata',
            '.ytd-video-primary-info-renderer h1'
        ]

        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    title = element.get('content', '').strip()
                else:
                    title = element.get_text().strip()
                if title and len(title) > 5:
                    break

        # Clean YouTube title
        if title:
            title = title.replace(' - YouTube', '').strip()
            title = re.sub(r'\s+', ' ', title)

        # Extract video description with better selectors
        description = ""
        desc_selectors = [
            'meta[property="og:description"]',
            'meta[name="description"]',
            '[data-e2e="video-desc"]',
            '#description',
            '.description',
            '.ytd-video-secondary-info-renderer #description',
            '.ytd-expandable-video-description-body-renderer',
            'ytd-expandable-video-description-body-renderer'
        ]

        for selector in desc_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    description = element.get('content', '').strip()
                else:
                    description = element.get_text().strip()
                if description and len(description) > 30:
                    break

        # Extract channel name with better accuracy
        channel = ""
        channel_selectors = [
            'meta[property="og:video:creator"]',
            '.ytd-video-owner-renderer a',
            '.ytd-channel-name a',
            '#owner-name a',
            '.yt-user-info a',
            'link[itemprop="url"]'
        ]

        for selector in channel_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    channel = element.get('content', '').strip()
                elif element.name == 'link':
                    href = element.get('href', '')
                    if '/channel/' in href or '/@' in href:
                        channel = href.split('/')[-1].replace('@', '').strip()
                else:
                    channel = element.get_text().strip()
                if channel and len(channel) > 2:
                    break

        # Extract video metadata from page content and JSON-LD
        page_text = soup.get_text()

        # Try to extract structured data (JSON-LD)
        json_scripts = soup.find_all('script', type='application/ld+json')
        video_metadata = {}

        for script in json_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0] if data else {}

                if data.get('@type') == 'VideoObject':
                    video_metadata = data
                    break
            except:
                continue

        # Extract comprehensive video information
        views = ""
        view_patterns = [
            r'([\d,\.]+)\s*views',
            r'([\d,\.]+)\s*Views',
            r'watched\s*([\d,\.]+)',
            r'"viewCount":"(\d+)"',
            r'"interactionCount":"(\d+)"'
        ]

        for pattern in view_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                views = match.group(1)
                break

        # Get view count from structured data
        if not views and video_metadata.get('interactionStatistic'):
            interaction = video_metadata['interactionStatistic']
            if isinstance(interaction, list):
                for stat in interaction:
                    if stat.get('interactionType', {}).get('@type') == 'WatchAction':
                        views = stat.get('userInteractionCount', '')
                        break
            elif isinstance(interaction, dict):
                views = interaction.get('userInteractionCount', '')

        # Extract duration with better patterns
        duration = ""
        duration_patterns = [
            r'Duration:\s*(\d+:\d+(?::\d+)?)',
            r'(\d+:\d+:\d+)',
            r'(\d+:\d+)',
            r'"lengthSeconds":"(\d+)"',
            r'"duration":"PT(\d+)M(\d+)S"',
            r'"duration":"PT(\d+)H(\d+)M(\d+)S"'
        ]

        for pattern in duration_patterns:
            match = re.search(pattern, page_text)
            if match:
                if 'lengthSeconds' in pattern:
                    seconds = int(match.group(1))
                    minutes = seconds // 60
                    remaining_seconds = seconds % 60
                    if minutes >= 60:
                        hours = minutes // 60
                        minutes = minutes % 60
                        duration = f"{hours}:{minutes:02d}:{remaining_seconds:02d}"
                    else:
                        duration = f"{minutes}:{remaining_seconds:02d}"
                elif 'PT' in pattern and 'H' in pattern:
                    hours, minutes, seconds = match.groups()
                    duration = f"{hours}:{minutes.zfill(2)}:{seconds.zfill(2)}"
                elif 'PT' in pattern:
                    minutes, seconds = match.groups()
                    duration = f"{minutes}:{seconds.zfill(2)}"
                else:
                    duration = match.group(1)
                break

        # Get duration from structured data
        if not duration and video_metadata.get('duration'):
            duration_iso = video_metadata['duration']
            # Parse ISO 8601 duration (PT1H30M45S format)
            duration_match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_iso)
            if duration_match:
                hours, minutes, seconds = duration_match.groups()
                hours = int(hours) if hours else 0
                minutes = int(minutes) if minutes else 0
                seconds = int(seconds) if seconds else 0

                if hours > 0:
                    duration = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    duration = f"{minutes}:{seconds:02d}"

        # Extract keywords/tags with better coverage
        keywords = ""
        keywords_sources = [
            soup.find('meta', {'name': 'keywords'}),
            video_metadata.get('keywords', [])
        ]

        all_keywords = []
        for source in keywords_sources:
            if isinstance(source, str):
                all_keywords.extend([k.strip() for k in source.split(',') if k.strip()])
            elif hasattr(source, 'get'):
                content = source.get('content', '')
                all_keywords.extend([k.strip() for k in content.split(',') if k.strip()])
            elif isinstance(source, list):
                all_keywords.extend(source)

        if all_keywords:
            keywords = ', '.join(all_keywords[:10])  # Limit to 10 keywords

        # Extract upload date
        upload_date = ""
        if video_metadata.get('uploadDate'):
            upload_date = video_metadata['uploadDate']
        else:
            date_patterns = [
                r'"publishDate":"([^"]+)"',
                r'"datePublished":"([^"]+)"'
            ]
            for pattern in date_patterns:
                match = re.search(pattern, page_text)
                if match:
                    upload_date = match.group(1)
                    break

        # Try to extract video captions/transcript content from page
        transcript_content = ""

        # Look for transcript in page scripts
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string and 'captions' in script.string.lower():
                # Try to extract caption data
                caption_matches = re.findall(r'"text":"([^"]+)"', script.string)
                if caption_matches:
                    # Clean and join captions
                    clean_captions = []
                    for caption in caption_matches[:50]:  # Limit to first 50 captions
                        caption = caption.replace('\\n', ' ').replace('\\', '').strip()
                        if len(caption) > 5 and not caption.startswith(('[', '{')):
                            clean_captions.append(caption)

                    if clean_captions:
                        transcript_content = ' '.join(clean_captions)
                        break

        # Analyze comments for additional context (limited)
        comments_content = ""
        comment_elements = soup.find_all(class_=re.compile(r'comment.*content'))
        if comment_elements:
            comment_texts = []
            for elem in comment_elements[:5]:  # First 5 comments only
                comment_text = elem.get_text().strip()
                if len(comment_text) > 20 and len(comment_text) < 200:
                    comment_texts.append(comment_text)

            if comment_texts:
                comments_content = ' | '.join(comment_texts)

        # Build comprehensive content structure
        content_parts = []

        if title:
            content_parts.append(f"Title: {title}")

        if channel:
            content_parts.append(f"Channel: {channel}")
          # Video statistics
        stats = []
        if duration:
            stats.append(f"Duration: {duration}")
        if views:
            stats.append(f"Views: {views}")
        if upload_date:
            try:
                date_obj = datetime.fromisoformat(upload_date.replace('Z', '+00:00'))
                formatted_date = date_obj.strftime('%Y-%m-%d')
                stats.append(f"Published: {formatted_date}")
            except:
                stats.append(f"Published: {upload_date}")

        if stats:
            content_parts.append(f"Video Details: {' | '.join(stats)}")

        if keywords:
            content_parts.append(f"Topics/Tags: {keywords}")

        # Enhanced description processing
        if description:
            # Extract meaningful content from description
            desc_lines = description.split('\n')
            content_lines = []
            links = []

            for line in desc_lines:
                line = line.strip()
                if not line:
                    continue

                # Extract links
                if line.startswith('http') or 'http' in line:
                    url_matches = re.findall(r'https?://[^\s]+', line)
                    links.extend(url_matches)
                    # Remove URLs from description text
                    line = re.sub(r'https?://[^\s]+', '', line).strip()

                # Keep meaningful content
                if (len(line) > 15 and
                    not line.lower().startswith(('subscribe', 'follow', 'like', 'comment', 'share', 'download', 'visit', 'check out')) and
                    not re.match(r'^[#@]', line) and
                    not line.startswith('►')):
                    content_lines.append(line)

            # Build enhanced description
            enhanced_desc_parts = []

            if content_lines:
                main_desc = ' '.join(content_lines[:8])  # First 8 meaningful lines
                if len(main_desc) > 800:
                    main_desc = main_desc[:800] + "..."
                enhanced_desc_parts.append(f"Description: {main_desc}")

            if links:
                enhanced_desc_parts.append(f"Referenced Links: {len(links)} links mentioned")

            if enhanced_desc_parts:
                content_parts.extend(enhanced_desc_parts)

        # Add transcript if available
        if transcript_content:
            if len(transcript_content) > 1000:
                transcript_content = transcript_content[:1000] + "..."
            content_parts.append(f"Video Content Sample: {transcript_content}")
          # Add comment insights if available
        if comments_content:
            content_parts.append(f"Viewer Comments Sample: {comments_content}")

        final_content = '. '.join(content_parts)

        print(f"✅ YouTube content extracted: {len(final_content)} characters")
        print(f"📋 Title: {title[:50]}..." if title else "📋 Title: Not found")
        print(f"📋 Channel: {channel}" if channel else "📋 Channel: Not found")
        print(f"📋 Description length: {len(description) if description else 0}")
        print(f"📋 Transcript found: {len(transcript_content) > 0}")
        print(f"📋 Video ID: {video_id}" if video_id else "📋 Video ID: Not extracted")

        return {
            'title': title or 'YouTube Video',
            'content': final_content,
            'url': url,
            'type': 'youtube_video',
            'channel': channel,
            'description': description[:800] if description else '',
            'video_id': video_id,
            'duration': duration,
            'views': views,
            'upload_date': upload_date,
            'keywords': keywords,
            'transcript_sample': transcript_content[:500] if transcript_content else '',
            'extracted_at': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"❌ Error extracting YouTube content: {e}")
        import traceback
        traceback.print_exc()
        return None
    
def extract_general_website_content(soup, url):
    """Extract content from general websites with robust fallbacks and better paragraph structure"""
    print("🌐 Extracting general website content...")

    try:
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement']):
            element.decompose()

        # Try to extract main content from common containers
        main_content = None
        content_selectors = [
            'article', 'main', '[role="main"]', '.content', '.main-content',
            '.post-content', '.entry-content', '.article-content', '.story-body',
            '#content', '#main-content', '.container', '#mw-content-text'
        ]

        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                main_content = elements[0]
                break

        # If no specific content container found, use body
        if not main_content:
            main_content = soup.find('body')

        if not main_content:
            return None

        # Get title
        title = ""
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()

        # Try to extract all <p> tags as paragraphs (best for most sites)
        paragraphs = [p.get_text(" ", strip=True) for p in main_content.find_all('p') if len(p.get_text(strip=True)) > 30]
        clean_text = '\n\n'.join(paragraphs)

        # Fallback: If still too short, try <div> and <span> tags
        if len(clean_text) < 100:
            divs = [d.get_text(" ", strip=True) for d in main_content.find_all('div') if len(d.get_text(strip=True)) > 40]
            spans = [s.get_text(" ", strip=True) for s in main_content.find_all('span') if len(s.get_text(strip=True)) > 40]
            all_blocks = paragraphs + divs + spans
            clean_text = '\n\n'.join(all_blocks)

        # Fallback: If still too short, get all visible text from <body>
        if len(clean_text) < 100:
            body = soup.find('body')
            if body:
                text = body.get_text(separator='\n\n', strip=True)
                if len(text) > len(clean_text):
                    clean_text = text

        # Final fallback: get all text from soup
        if len(clean_text) < 100:
            text = soup.get_text(separator='\n\n', strip=True)
            if len(text) > len(clean_text):
                clean_text = text

        # Limit content length for summarization
        if len(clean_text) > 3000:
            clean_text = clean_text[:3000] + "..."

        print(f"✅ Successfully extracted content: {len(clean_text)} characters")

        return {
            'title': title,
            'content': clean_text,
            'url': url,
            'type': 'website',
            'extracted_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"❌ Error extracting general website content: {e}")
        return None



def create_website_summary_response(query, website_data, bot_id=None):
    """Create a concise, persona-based summary of website content using AI"""
    print(f"📝 Creating AI-powered website summary response...")

    if not website_data:
        return f"I was unable to fetch content from the website you provided. Please check the URL and try again."

    title = website_data.get('title', 'Untitled')
    content = website_data.get('content', '')
    url = website_data.get('url', '')
    content_type = website_data.get('type', 'website')

    print(f"[DEBUG] Extracted content length: {len(content)}")
    print(f"[DEBUG] Extracted content preview: {content[:200]}")

    if not content or len(content) < 50:
        return f"I was able to access the website '{title}' but couldn't extract enough readable content to provide a summary."

    # --- Fetch bot prompt and traits ---
    bot_prompt = ""
    traits = ""
    if bot_id:
        try:
            bot_prompt = get_bot_prompt(bot_id)
            # You can fetch traits if you have them
        except Exception as e:
            print(f"Error fetching bot prompt: {e}")

    # --- NEW PROMPT: 2-3 line summary, persona-based ---
    ai_prompt = (
        f"You are a helpful assistant. {bot_prompt} "
        f"Summarize the following website content in 2-3 clear, complete sentences, using your unique style and personality. "
        f"Do not cut off sentences in the middle. Focus on the main topics and key details. "
        f"Here is the content:\n\n{content[:1500]}"
    )

    summary_text = call_gemini_ai(ai_prompt, max_tokens=120)
    # Ensure summary is not cut in the middle of a sentence
    if summary_text and isinstance(summary_text, str):
        # Optionally, trim to the last full sentence if needed
        if not summary_text.strip().endswith(('.', '!', '?')):
            last_period = summary_text.strip().rfind('.')
            if last_period != -1:
                summary_text = summary_text.strip()[:last_period+1]
    else:
        summary_text = f"I was able to access the website '{title}' but couldn't extract enough readable content to provide a summary."

    return summary_text.strip().replace(",,", ",").replace(" ,", ",").replace(" .", ".")

def create_structured_website_fallback(query, website_data, bot_id=None):
    import re
    from datetime import datetime
    from bot_prompt import get_bot_prompt

    title = website_data.get('title', 'Untitled')
    content = website_data.get('content', '')
    url = website_data.get('url', '')
    content_type = website_data.get('type', 'website')

    # --- Fetch bot prompt and traits ---
    bot_prompt = ""
    traits = ""
    if bot_id:
        try:
            bot_prompt = get_bot_prompt(bot_id)
            from utils import get_botname
            traits = get_botname(bot_id) or ""
        except Exception as e:
            bot_prompt = ""
            traits = ""

    response_parts = []

    if content_type == 'youtube_video':
        response_parts.append("# 🎥 Comprehensive YouTube Video Analysis")
        response_parts.append(f"*Comprehensive analysis completed on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*")
        return "\n".join(response_parts)

    # For general websites
    if content:
        ai_prompt = (
            f"You are a helpful assistant. {bot_prompt} "
            f"Your personality traits: {traits}. "
            f"Summarize the following website content in 2-3 clear, well-structured paragraphs, "
            f"using your unique style and personality. Focus on the main topics and key details. "
            f"Separate each paragraph with a blank line.\n\n{content[:1500]}"
        )
        summary_text = call_gemini_ai(ai_prompt, max_tokens=100)
        if summary_text and isinstance(summary_text, str) and len(summary_text.strip().split()) > 20:
            paragraphs = re.split(r'\n{2,}', summary_text.strip())
            if len(paragraphs) < 2:
                sentences = re.split(r'(?<=[.!?])\s+', summary_text.strip())
                midpoint = len(sentences) // 2
                summary_text = " ".join(sentences[:midpoint]) + "\n\n" + " ".join(sentences[midpoint:])
            response_parts = [summary_text]
        else:
            sentences = re.split(r'(?<=[.!?])\s+', content)
            filtered = [s.strip() for s in sentences if len(s.strip()) > 40 and not s.strip().endswith(':')]
            fallback_summary = " ".join(filtered[:6])
            if not fallback_summary or len(fallback_summary.split()) < 30:
                fallback_summary = (
                    f"This website appears to provide information related to '{title or query}'. "
                    "It covers key topics and recent developments relevant to this subject. "
                    "For more details, please visit the website directly."
                )
            response_parts = [fallback_summary]
    else:
        response_parts = [
            f"I was able to access the website '{title}' but couldn't extract enough readable content to provide a summary."
        ]

    response_parts.append(f"*Summary generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*")
    return "\n\n".join(response_parts)



























async def call_xai_api(messages, model="grok-beta"):
    """XAI Grok API with model fallback and OpenAI backup"""
    print(f"Calling XAI Grok API for voice call with model: {model}")
    
    # Try different models in order
    models_to_try = ["grok-beta", "grok-2-1212", "grok-2-latest", "grok-vision-beta"]
    
    for model_name in models_to_try:
        try:
            headers = {
                "Authorization": f"Bearer {os.getenv('XAI_API_KEY')}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messages": messages,
                "model": model_name,
                "stream": False,
                "temperature": 0.7,
                "max_tokens": 150
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                response_content = result["choices"][0]["message"]["content"]
                
            logging.info(f"✅ XAI SUCCESS with model: {model_name}")
            return clean_to_single_line(response_content)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logging.warning(f"⚠️ XAI model {model_name} forbidden (403), trying next...")
                continue
            else:
                logging.error(f"⚠️ XAI model {model_name} failed with {e.response.status_code}")
                continue
        except Exception as e:
            logging.warning(f"⚠️ XAI model {model_name} failed: {e}")
            continue
    
    # All XAI models failed - fallback to OpenAI
    logging.warning("🔄 All XAI models failed, falling back to Gemini")
    try:
        return await call_gemini_api_v2(messages, model="gemini-2.0-flash")
    except Exception as e:
        logging.error(f"❌ Gemini fallback also failed: {e}")
        raise Exception("Both XAI and Gemini failed")
    
async def log_retrieve_memory_data(previous_conversations,extracted_data,email,bot_id):
    data = {
        "previous_conversations" : previous_conversations,
        "extracted_data" : extracted_data,
        "email" : email,
        "bot_id" : bot_id,
    }

    response = supabase.table("retrieve_memory_data").insert(data).execute()

    return response



# Defining the nsfw function
def call_nsfw(query, personality, previous_conversation, gender, username, botname, user_relation):
    user1 = username
    user2 = botname
    url_response = "https://api.novita.ai/v3/openai/chat/completions"  #  append `/chat/completions`
    api_key = "sk_rNKb5W0X-Y8Nv69g3nid7KHzfiDvklvr7qwmrZ1Mhbk"  #  replace with your Novita API key

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    instruction = "Strict instruction: Respond according to your personality given and keep the response between 3-4 lines"

    bot_prompt = (
        "Your name is " + botname +
        ", and you talk/respond by applying your reasoning. " + personality + 
        " Given you are the user's " + user_relation +
        " for the user question: " + query +
        "Keep the response strictly within 3-4 lines " + instruction
    )

    response = requests.post(
        url_response,
        headers=headers,
        json={
            "model": "Sao10K/L3-8B-Stheno-v3.2",  # model ID
            "messages": [
                {"role": "system", "content": bot_prompt},
                {"role": "user", "content": f"Previous conversation so far: {previous_conversation}, current user query: {query}"}
            ],
            "allow_nsfw": True,  #This is what enables NSFW generation
            "temperature": 1.0,               # Adjusts randomness; 1.0 is good for creativity
            "top_p": 0.9,                     # Controls diversity via nucleus sampling
            "frequency_penalty": 0.4,        # Reduces repetition of similar lines
            "presence_penalty": 0.0
        }
    )
    # model = "Stheno-v3.2"
    try:
        print("Response JSON: CALLED STHENO")
        x = response.json()
        final = x["choices"][0]["message"]["content"]
    except Exception as e:
        print("Non-JSON response:", e)
        final = response.text()

    for k in ["User1", "user1", "[user1]", "[User1]"]:
        final = final.replace(k, user1)
    

    return final

from MM2.serialization import is_valid_memory
import ast
from datetime import datetime, timedelta, timezone
# DELETE the second definition (around line 1250) and keep only this comprehensive version:

def load_memories_to_redis(email: str, bot_id: str):
    user_id = f"{email}:{bot_id}"
    session_flag = f"session_loaded:{user_id}"
    
    # Check if session is already loaded
    if redis_manager.client.get(session_flag):
        print(f"🎯 DEBUG: Session already loaded for {user_id}")
        return {"status": "already_loaded"}

    # Clear existing data and load from Supabase
    redis_manager.clear_user_data(user_id)
    print(f"🔧 DEBUG: Cleared existing data for {user_id}")
    
    from supabase import create_client
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    
    five_days_ago = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

    try:
        memories = supabase.table("persona_category").select("*").eq("email", email).eq("bot_id", bot_id).execute().data or [] 
        chats = supabase.table("message_paritition").select("*").eq("email", email).eq("bot_id", bot_id).gte("created_at", five_days_ago).execute().data or []
        
        print(f"🐛 DEBUG: Fetched {len(memories)} memories and {len(chats)} chats from Supabase")
    except Exception as e:
        print(f"❌ DEBUG: Error fetching from Supabase: {e}")
        return {"status": "error", "message": str(e)}

    valid_memories = []
    processing_errors = []
    
    for m in memories:
        try:
            m = dict(m)
            original_id = m.get('id')
            
            # 🔧 CRITICAL FIX 1: Field name mapping
            if "memory" in m and "memory_text" not in m:
                m["memory_text"] = m["memory"]
                print(f"✅ DEBUG: Added memory_text field for memory {original_id}")
            
            # 🔧 CRITICAL FIX 2: User ID creation
            m["user_id"] = f"{email}:{bot_id}"
            
            # 🔧 CRITICAL FIX 3: Enhanced embedding handling
            emb = m.get("embedding", None)
            if emb is None or emb == "":
                print(f"⚠️ DEBUG: No embedding found for memory {original_id}, using default")
                emb = [0.0] * 768
            elif isinstance(emb, str):
                try:
                    import ast
                    emb = ast.literal_eval(emb)
                    print(f"✅ DEBUG: Parsed string embedding for memory {original_id}")
                except Exception as e:
                    print(f"❌ DEBUG: Failed to parse string embedding for memory {original_id}: {e}")
                    emb = [0.0] * 768
            elif hasattr(emb, '__iter__') and not isinstance(emb, str):
                try:
                    emb = list(emb)
                    print(f"✅ DEBUG: Converted iterable embedding for memory {original_id}")
                except Exception as e:
                    print(f"❌ DEBUG: Failed to convert embedding for memory {original_id}: {e}")
                    emb = [0.0] * 768
            
            if not isinstance(emb, list):
                print(f"❌ DEBUG: Embedding is not a list for memory {original_id}, using default")
                emb = [0.0] * 768
                
            # Ensure proper dimensions and types
            try:
                emb = [float(x) for x in emb if isinstance(x, (int, float)) or (isinstance(x, str) and str(x).replace('.', '', 1).replace('-', '', 1).isdigit())]
                if len(emb) != 768:
                    if len(emb) < 768:
                        emb = emb + [0.0] * (768 - len(emb))
                        print(f"✅ DEBUG: Padded embedding to 768 dimensions for memory {original_id}")
                    else:
                        emb = emb[:768]
                        print(f"✅ DEBUG: Truncated embedding to 768 dimensions for memory {original_id}")
                print(f"✅ DEBUG: Embedding processed successfully for memory {original_id} - {len(emb)} dimensions")
            except Exception as e:
                print(f"❌ DEBUG: Embedding processing failed for memory {original_id}: {e}")
                emb = [0.0] * 768
                
            m["embedding"] = emb
            
            # 🔧 CRITICAL FIX 4: Ensure all required numeric fields
            m["magnitude"] = float(m.get("magnitude", 1.0)) if m.get("magnitude") is not None else 1.0
            m["frequency"] = int(m.get("frequency", 1)) if m.get("frequency") is not None else 1
            m["recency"] = int(m.get("recency", 5)) if m.get("recency") is not None else 5
            m["rfm_score"] = float(m.get("rfm_score", 1.0)) if m.get("rfm_score") is not None else 1.0
            
            # 🔧 CRITICAL FIX 5: Ensure required timestamp fields
            if not m.get("created_at"):
                m["created_at"] = datetime.now(timezone.utc).isoformat()
                print(f"✅ DEBUG: Set default created_at for memory {original_id}")
            
            if not m.get("last_used"):
                m["last_used"] = datetime.now(timezone.utc).isoformat()
                print(f"✅ DEBUG: Set default last_used for memory {original_id}")
            
            print(f"🔧 DEBUG: Processing memory ID {original_id} - All fields: {list(m.keys())}")
            
            # Validate before adding
            if is_valid_memory(m):
                valid_memories.append(m)
                print(f"✅ DEBUG: Memory {original_id} validated and added")
            else:
                error_msg = f"Memory {original_id} failed validation"
                processing_errors.append(error_msg)
                print(f"❌ DEBUG: {error_msg}")
                print(f"   - Has memory_text: {'memory_text' in m and m['memory_text']}")
                print(f"   - Embedding valid: {isinstance(m.get('embedding'), list) and len(m.get('embedding', [])) == 768}")
                print(f"   - Required fields: {all(field in m for field in ['id', 'user_id', 'magnitude', 'frequency'])}")
                
        except Exception as e:
            error_msg = f"Error processing memory {m.get('id', 'unknown')}: {e}"
            processing_errors.append(error_msg)
            print(f"❌ DEBUG: {error_msg}")
            import traceback
            traceback.print_exc()
    
    print(f"🎯 DEBUG: {len(valid_memories)} out of {len(memories)} memories passed validation")
    
    # Load data into Redis
    try:
        redis_manager.load_user_data(user_id, valid_memories, chats)
        redis_manager.client.set(session_flag, 1)
        
        # 🔧 CRITICAL FIX 6: Verify Redis storage
        stored_memory_keys = redis_manager.client.keys(f"memories:{user_id}:*")
        stored_chat_keys = redis_manager.client.keys(f"chat:{user_id}:*")
        
        print(f"🚀 DEBUG: Loaded {len(stored_memory_keys)} memories and {len(stored_chat_keys)} chats into Redis for {user_id}")
        
        return {
            "memories_fetched": len(memories),
            "memories_validated": len(valid_memories),
            "memories_stored": len(stored_memory_keys),
            "chats_loaded": len(stored_chat_keys),
            "processing_errors": processing_errors[:5] if processing_errors else [],
            "success_rate": f"{(len(valid_memories)/len(memories)*100):.1f}%" if memories else "N/A"
        }
        
    except Exception as e:
        print(f"❌ DEBUG: Error loading data into Redis: {e}")
        return {
            "status": "error", 
            "message": f"Failed to load data into Redis: {e}",
            "memories_processed": len(valid_memories),
            "processing_errors": processing_errors
        }
    
from MM2.addendum import bot_current_time 
from MM2.memory_functions import fetch_last_m_messages, get_semantically_similar_memories, get_highest_rfm_memories, get_embedding, time_ago_human
from MM2.redis_class import RedisManager
from MM2.bot_prompt import get_bot_prompt
import os
from google import genai

redis_manager = RedisManager()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


async def bot_response_v2(bot_prompt_f, bot_id, user_message, username, add_prompt=""):
    user_id = f"{username}:{bot_id}"

    # Get embedding for the user query
    input_embedding = await get_embedding(user_message)

    # Fetch recent chat history, RFM memories, semantic memories from Redis
    recent_task = fetch_last_m_messages(redis_manager.client, user_id, m=10)
    rfm_task = get_highest_rfm_memories(redis_manager.client, user_id)
    semantic_task = get_semantically_similar_memories(redis_manager.client, user_id, input_embedding, cutoff=1.0)
    recent, rfm, semantic = await asyncio.gather(recent_task, rfm_task, semantic_task)


    # 🔧 ADD THESE DEBUG LINES:
    print(f"🐛 DEBUG - User ID: {user_id}")
    print(f"🐛 DEBUG - Recent messages count: {len(recent)}")
    print(f"🐛 DEBUG - Recent messages: {recent[:2] if recent else 'EMPTY'}")
    
    # Check Redis directly for debugging
    pattern = f"chat:{user_id}:*"
    keys = redis_manager.client.keys(pattern)
    print(f"🐛 DEBUG - Redis chat keys found: {len(keys)}")
    if keys:
        sample_key = keys[0]
        sample_data = redis_manager.client.hgetall(sample_key)
        print(f"🐛 DEBUG - Sample chat data: {sample_data}")
        
        
        
    rfm_block = (
        "\n\n".join(f"{mem.get('memory_text', mem.get('text', ''))} | RFM score:{mem['rfm_score']}" for mem in rfm)
        if rfm else "No high-RFM memories available."
    )
    semantic_block = "\n\n".join(
        f"{mem.get('memory_text', mem.get('text', ''))} | Similarity score: {mem['sim']} | Added: {time_ago_human(mem['created_at'])}, Last used: {time_ago_human(mem['last_used'])}"
        for mem in semantic
    ) if semantic else "No semantically similar memories found."
    history_block = "\n\n".join(
        [f"Timestamp: {r['timestamp']}\nUser: {r['user_message']}\nBot: {r['bot_response']}" for r in recent]
    ) if recent else "No recent chat history found."
    
    current_time_info = bot_current_time(bot_id)

    additional_prompt_section = ""
    if add_prompt and add_prompt.strip():
        additional_prompt_section = f"\n{add_prompt.strip()}\n"
    
    
    # Improved prompt
    prompt = f"""{bot_prompt_f}

==== CONTEXT ====
{current_time_info}

Recent Chat History:
{history_block}

Semantically Relevant Memories:
{semantic_block}

Important Memories (Ranked by RFM):
{rfm_block}

==== USER INPUT ====
{user_message}

**Your tools:**
- Recent chat history: Maintain conversational flow and continuity.
- Semantically relevant memories: Use these to recall user preferences, experiences, or facts.
- High-RFM memories: Use these to understand what matters most to the user.

{additional_prompt_section}
==== INSTRUCTIONS ====
1. First review the recent conversation history to understand the ongoing discussion context.
2. Reference specific points from the recent conversation when relevant to maintain continuity.
3. Also examine both types of memories (Semantic and RFM) for relevant information.
4. When a memory is relevant, incorporate it naturally using phrases like "As you mentioned before..."
5. If multiple information sources are relevant, blend conversation history with memories seamlessly.
6. Be concise and don't invent information not present in either the conversation history or memories.
7. Prioritize recent conversation context for immediate relevance, and memories for longer-term context.
8. Conversations need to look natural and reference past conversations, as if two persons are talking to each other
9. Do not repeatedely ask user the same set of things, if user says not to repeat obey it and be creative in your replies
10. **Strictly follow and use the current time information provided above ({current_time_info}) in your response.**

Now, respond to the user.
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )


    # Fallback if no memories found
    if not recent and not rfm and not semantic:
        fallback_additional_prompt = ""
        if add_prompt and add_prompt.strip():
            fallback_additional_prompt = f"\n{add_prompt.strip()}\n"
            
        prompt = f"""{bot_prompt_f}

{current_time_info}
{fallback_additional_prompt}

Current User Input:
{user_message}

Respond to the user now.
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

    return response.text.strip()
def call_gemini_api(query,text,previous_conversation, gender ,username, botname, bot_id):
    #print(f"Calling Gemini API with model: {model}")

    #query: Optional[str] = None
    #api_key: Optional[str] = None
    #modelname: Optional[str] = None
    #user1: Optional[str] = None
    #user2: Optional[str] = None
    #gender: Optional[str] = None
    #prompt : Optional[str] = None
    #previous_conversation : Optional[str] = None

    # Selecting the default model
    # model = "meta-llama/llama-3.1-70b-instruct"

    # Chat completion API call
    user1 = username
    user2 = botname
    GEMINI_API_KEY= os.getenv("GEMINI_API_KEY")
    model = "gemini-2.0-flash" 
    # Initialize the Gemini LLM
    llm = GoogleGenAI(
        model=model,
        api_key=GEMINI_API_KEY
    )
    # Construct the complete system prompt using inputs
    full_prompt = (
        f"User: {username} (Gender: {gender})\n"
        f"Bot: {botname}\n"
        f"Personality: {text}\n"
        f"Previous Conversation: {previous_conversation}\n"
        f"Bot Prompt: {get_bot_prompt(bot_id)}\n"
        f"User Message: {query}\n"
        "Important: Do NOT prefix your answer with 'Bot:', 'User:', 'Gender:',and don't give \n in the response, or any role label. Do NOT repeat any part of the prompt. Just answer directly, in character, as the bot. DO NOT GIVE ANYTHING EXCEPT THE RESPONSE"
    )
    # Send the prompt to the LLM
    try:
        response = llm.complete(full_prompt)
        response_raw = response.text
    except Exception as e:
        print(f"❌ Error in call_gemini_api: {e}")
        logging.error(f"Error in call_gemini_api: {e}")
        return f"Sorry, there was an error with Gemini API. Error: {str(e)}"
    
    try:
         # Log/print the raw response for debugging if needed
        processed_response = response_raw.replace("User1", user1)
        processed_response = processed_response.replace("user1", user1)
        processed_response = processed_response.replace("[user1]", user2)
        processed_response = processed_response.replace("[User1]", user2)
        return processed_response.strip()
    except json.JSONDecodeError:
        return f"JSON Decode Error: Unable to parse API response. Raw response: {response.text} :::: gem novi response ::::"
    except KeyError as e:
        return f"KeyError: {str(e)}. API response structure is different than expected. Raw response: {getattr(response, 'json', lambda: {})()}"

async def log_retrieve_memory_data(previous_conversations,extracted_data,email,bot_id):
    data = {
        "previous_conversations" : previous_conversations,
        "extracted_data" : extracted_data,
        "email" : email,
        "bot_id" : bot_id,
    }

    response = supabase.table("retrieve_memory_data").insert(data).execute()

    return response

def log_messages_with_like_dislike(user_email,bot_id,user_message,bot_response,feedback,last_5_messages,memory_extracted):
    data = {
        "user_email": user_email,
        "bot_id": bot_id,
        "user_message": user_message,
        "bot_response": bot_response,
        "feedback": feedback,
        "last_5_messages": last_5_messages,
        "memory_retrieved": memory_extracted,
        "memory_extracted": ""
    }

    res = supabase.table("log_messages_with_like_dislike").insert(data).execute()
    return res

def log_notes_memory(notes,extracted_data,email,bot_id):
    data = {
        "notes": notes,
        "extracted_data": extracted_data,
        "email": email,
        "bot_id": bot_id
    }

    res = supabase.table("notes").insert(data).execute()
    return res

def like_dislike(message_id,like_or_dislike):
    return supabase.table("log_messages_with_like_dislike").update({"feedback" : like_or_dislike}).eq("id", message_id).execute()

def restrict_to_last_20_messages(messages):
    return messages[-20:]

def clean_to_single_line(text):
    """Removes all \\n characters and extra spaces for a single-line output."""
    return ' '.join(text.replace("\\n", " ").split())

async def call_gemini_api_v2(messages, model="gemini-2.0-flash"):
    """
    Calls the Gemini API (or compatible endpoint) with the provided messages and model.
    Returns a single-line cleaned response.
    """
    print(f"Calling Gemini API with model: {model}")
    # Prepare the prompt from the messages list
    prompt_lines = []
    for msg in messages:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        prompt_lines.append(f"{role}: {content}")
    full_prompt = "\n".join(prompt_lines)

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    # Initialize the Gemini LLM
    llm = GoogleGenAI(
        model=model,
        api_key=GEMINI_API_KEY
    )
    # Send the prompt to the LLM
    try:
        response = llm.complete(full_prompt)
        result = response.text
    except Exception as e:
        logging.error(f"Error in Gemini LLM call: {e}")
        logging.error(f"Full error details: {str(e)}")
        print(f"❌ Detailed Gemini API Error: {e}")
        print(f"❌ Error type: {type(e)}")
        result = f"Sorry, there was an error processing your request. Error: {str(e)}"
    logging.info("response:%s %s", model, result)
    return clean_to_single_line(result)

async def call_openai_api(messages,model="o4-mini"):
    print(f"Calling to OpenAI API with model: {model}")
    client = AsyncOpenAI(
        # base_url="https://api.novita.ai/v3/openai",
        # Get the Novita AI API Key by referring to: https://novita.ai/docs/get-started/quickstart.html#_2-manage-api-key.
        api_key= os.getenv("OPENAI_API_KEY"),
    )
    # Selecting the default model
    # model = "meta-llama/llama-3.1-70b-instruct"

    # Chat completion API call
    try:
        if model == "o4-mini":
            # chat_completion_res = await client.chat.completions.create(
            chat_completion_res = await client.responses.create(
                model=model,
                reasoning={"effort": "medium"},
                # input=[{"role": "system", "content": "Always think step-by-step, reason thoroughly, and double-check before responding."},*messages,],
                input=messages,
                max_output_tokens=1500,
                # temperature=0.2, # Lower temperature = more focused, logical responses
                # top_p=0.9, # Keep top_p high enough for slight creativity but limit randomness
            )
        elif model == "o3-mini":
            chat_completion_res = await client.chat.completions.create(
                model=model,
                messages=messages,
            )
        else:
            chat_completion_res = await client.chat.completions.create(
                model=model,
                messages=messages,
        )
    except Exception as e:
        traceback.print_exc()
        print("Error in OpenAI API call:", e)

    # Return the response
    if model == "o4-mini":
        o4_mini_respose = chat_completion_res.output_text
    else:
        o4_mini_respose = chat_completion_res.choices[0].message.content
        
    logging.info("response:%s %s", model, o4_mini_respose)
    return clean_to_single_line(o4_mini_respose)

async def call_grok_api(messages , model="grok-2-1212"):
    print("calling grok")
    client = AsyncOpenAI(
        base_url="https://api.x.ai/v1",
        api_key= os.getenv("XAI_API_KEY"),
    )

    # Chat completion API call
    chat_completion_res = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1
    )

    # Return the response
    return chat_completion_res.choices[0].message.content

async def call_novita_ai_api(messages,model = "meta-llama/llama-3.3-70b-instruct"):
    print("Callin novita ai api")
    client = AsyncOpenAI(
        base_url="https://api.novita.ai/v3/openai",
        api_key= os.getenv("NOVITA_API_KEY"),
    )

    # Chat completion API call
    chat_completion_res = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.1
    )

    # Return the response
    return chat_completion_res.choices[0].message.content


def connect_pinecone():
    return pc,index


def clean_bot_string(raw_string):
    if not isinstance(raw_string, str):
        return "Bhagwan has an overload of queries from millions of devotees. Please wait for Bhagwan, because Bhagwan ke ghar mein der hai but andher nahin."

    # Step 1: Basic cleaning
    cleaned = raw_string.strip().strip('"').replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
    
    # Step 2: Remove extra spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Step 3: Remove references like [1], [4], [123]
    cleaned = re.sub(r'\[\d+\]', '', cleaned)

    # Step 4: Remove common operators and formatting that are not usually part of natural text
    cleaned = re.sub(r'[*=_`#]+', '', cleaned).strip() # Remove *, =, _, `, #
    cleaned = re.sub(r'\s*[*=_`#]+\s*', ' ', cleaned).strip() # Remove with surrounding spaces
    cleaned = re.sub(r'[*=_`#]+\s*$', '', cleaned).strip() # Remove at the end with leading spaces
    cleaned = re.sub(r'^\s*[*=_`#]+', '', cleaned).strip() # Remove at the beginning with trailing spaces
    
    return cleaned

#bhagwan response function added to get response from lord krishna modal api
async def bhagwan_response(user_name, user_gender, bot_id, message):
    api_key = os.getenv("PPX_API_KEY")
    modelname = 'sonar-reasoning'

    try:
        response = requests.post(
            "https://amaze18--krishna-krishna-uvach.modal.run",
            json={
                "query": message,
                "api_key": api_key,
                "modelname": modelname,
                "user1": bot_id,
                "user2": user_name,
                "gender": user_gender
            }, 
        )

        logging.info(f"Status: {response.status_code}")
        logging.info(f"bhagwan_api_response: {response.text}")

        if response.status_code != 200 or "model is overloaded" in response.text.lower():
            logging.error(f"Overload or error from API for bot_id={bot_id}, user={user_name}: {response.text}")
            return "Service is currently overloaded. Please try again later."

        cleaned = clean_bot_string(response.text)
        if not cleaned or "NoneType" in cleaned or "Error" in cleaned:
            logging.error(f"Invalid response after cleaning for bot_id={bot_id}, user={user_name}: {cleaned}")
            return "Bhagwan has an overload of queries from millions of devotees. Please wait for Bhagwan, because Bhagwan ke ghar mein der hai but andher nahin."

        return cleaned

    except httpx.RequestError as e:
        logging.error(f"Request error during bhagwan_response API call for bot_id={bot_id}, user={user_name}: {e}")
        return "Could not reach the response service. Please try again later."
    
# call_openai_api(request.bot_prompt,request.message,request.previous_conversation,memory)
async def bot_response(frontend_bot_prompt,bot_id,user_message,rephrased_user_message,previous_conversation,memory,request_time):

    if previous_conversation and previous_conversation[-1].get('feedback', ""):
        bot_prompt = f"""
        {frontend_bot_prompt}

        ## Current time:
        {request_time}

        ## Related memory:
        {memory}

        ## Previous conversation:
        {{previous_conversation[-1]['content']}}

        ## Important notes for memory reference:
        - Only reference information from the Related Memory if it is relevant to the user's query. 
        - If the information is not relevant, do not reference it.
        - Make use of the current time to provide in Related memory and Current time to respond to the user query

        ## User Feedback on the last message:
        - User has given feedback on the last message. Try to incorporate it into the conversation.
        - The user {previous_conversation[-1]['feedback']} your response: "{previous_conversation[-1]['content']}".

        ## Instruction:
        Please refer to previous conversations and apply your reasoning while framing response to user. Dont bring suggestions which are contradicting or 
        conflicting to user's needs or requirements in your response, given these previous conversations/related memories. 
        Most focus shall be on related memory/previous conversations. Refrain from repeating same response to user or asking same questions again.

        """

    # Additional information:
    # You have the ability to remember things that the user asks or to do something. 
    # Provide a positive response and be proactive. Ask more details about something if needed.
    else:
        bot_prompt = f"""
        {frontend_bot_prompt}

        ## Current time:
        {request_time}

        ## Related memory:
        {memory}

        ## Previous conversation:
        {{previous_conversation[-1]['content']}}

        ## Important notes for memory reference:
        - Only reference information from the Related Memory if it is relevant to the user's query. 
        - If the information is not relevant, do not reference it.
        - Make use of the current time to provide in Related memory and Current time to respond to the user query

        ## Instruction:
        Please refer to previous conversations and apply your reasoning while framing response to user. Dont bring suggestions which are contradicting or 
        conflicting to user's needs or requirements in your response, given these previous conversations/related memories. 
        Most focus shall be on related memory/previous conversations. Refrain from repeating same response to user or asking same questions again.
        
        """

    ## Additional information:
    #  You have the ability to remember things that the user asks or to do something. Provide a positive response and be proactive. 
    ## Ask more details about something if needed.
       
    messages = [
        {
            "role": "system", 
            "content": bot_prompt
        }
    ]
    messages.extend(previous_conversation)

    messages.append(
        {
            "role": "user",
            "content": user_message
        }
    )
   # All bots now use Gemini API only (removed XAI/Grok routing)
    try:
        # Use Gemini for all bots (romantic, mentor, friend, etc.)
        print(f"🤖 Using Gemini API for bot: {bot_id}")
        response = await call_gemini_api_v2(messages)
        print(f"✅ Gemini success for bot: {bot_id}")
    except Exception as e:
        print(f"❌ Error calling Gemini API: {e}")
        # Fallback to Gemini if there's any error
        response = await call_gemini_api_v2(messages)
        print(f"🆘 Using Gemini fallback")    
        
    # Change this function make it call different LLM eg. Grok or OpenAI
    # response = await call_openai_api(messages)
    # response = await call_grok_api(messages)

    return response

async def reminder_response_to_user(message, previous_conversation,request_time,remind_time):
    messages = [
        {
            "role" : "system",
            "content" : REMINDER_BLEND_RESPONSE_SYSTEM_PROMPT
        }
    ]

    messages.extend(previous_conversation)

    messages.append({
        "role": "user",
        "content": f""" 
        Reminder: {message} 
        Current Time: {request_time}
        Reminder Time: {remind_time}

        ## Using both the reminder details and the conversation history, craft a response that effectively blends the two. Be sure to check the current time against the reminder time:
        - If they align, proceed as if consent has been given.
        - If there's a discrepancy or if the user appears to have forgotten, address that accordingly in your response.
        """
    })
    # return await call_openai_api(message,model="o3-mini")
    # lets update it to o4-mini # refer: https://platform.openai.com/docs/pricing
    #  lets update it to o4-mini # refer: https://platform.openai.com/docs/pricing
    return await call_gemini_api_v2(messages,model="gemini-2.0-flash")

async def check_for_origin_question(user_message,previous_conversation):
   prompt = ORIGIN_IDENTIFICATION_SYSTEM_PROMPT

   messages = [
        {
            "role": "system", 
            "content": prompt
        }
    ]
   
   messages.extend(previous_conversation[-5:])
   
   messages.append(
        {
            "role": "user",
            "content": user_message
        }
    )

#    res = await call_novita_ai_api(messages,model="mistralai/mistral-nemo")
#    res = await call_novita_ai_api(messages,model="meta-llama/llama-3.3-70b-instruct")
    # 🚀 CRITICAL FIX: Switch to gpt-3.5-turbo for ultra-fast origin check (<1s instead of 5s+)
    # o4-mini is a reasoning model (slow) - gpt-3.5-turbo is perfect for simple yes/no decisions
   # Use Gemini for origin check (consistent with all other bot responses)
   res = await call_gemini_api_v2(messages, model="gemini-2.0-flash")

   if res.strip() == "Yes":
       return "Yes"
   
   return "No"

def format_client_conversation(conversation):
    formatted_text = ""
    
    for message in conversation:
        role = message['role']
        content = message['content']
        
        # Capitalize first letter of role
        formatted_role = role.capitalize()
        formatted_text += f"{formatted_role}: {content}\n\n"
    
    return formatted_text.strip()

def convert_to_clean_number(request_time):
    # First convert to datetime
    time_data = datetime.strptime(request_time.split(" (")[0], "%a %b %d %Y %H:%M:%S GMT%z")
    
    # Convert to string and remove timezone part
    time_str = str(time_data).split("+")[0]
    
    # Remove all spaces, hyphens, and colons
    clean_number = time_str.replace(" ", "").replace("-", "").replace(":", "")
    
    return clean_number

def get_before_after_dates(date_number, days_before=1, days_after=1):
    # Convert the number string back to datetime
    # Format: YYYYMMDDHHMMSS
    date_str = f"{date_number[:4]}-{date_number[4:6]}-{date_number[6:8]} {date_number[8:10]}:{date_number[10:12]}:{date_number[12:]}"
    current_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    
    # Calculate before and after dates
    before_date = current_date - timedelta(days=days_before)
    after_date = current_date + timedelta(days=days_after)
    
    # Convert back to clean number format
    before_number = before_date.strftime("%Y%m%d%H%M%S")
    after_number = after_date.strftime("%Y%m%d%H%M%S")
    
    return before_number, after_number

## Example usage:
# date_number = "20250121013137"
# before, after = get_before_after_dates(date_number)
# print(f"Day before: {before}")  # Output: 20250120013137
# print(f"Day after: {after}")    # Output: 20250122013137

# # You can also specify different number of days:
# before, after = get_before_after_dates(date_number, days_before=2, days_after=3)
# print(f"Two days before: {before}")  # Output: 20250119013137
# print(f"Three days after: {after}")  # Output: 20250124013137

def extract_json_from_text(text):
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != 0:
            return text[start:end]
        return text
    except:
        return text
    
#________________________________________________________________________________________________________________________________________________________________________________
    
async def check_entry_exists(email, bot_id):
    """
    This Python function checks if an entry exists in a Supabase table based on email and bot_id, and
    creates a new entry if it does not exist.
    
    @param email The `check_entry_exists` function you provided seems to be checking if an entry exists
    in a Supabase table named "last_cat_message" based on the provided `email` and `bot_id`. If no entry
    is found for the given `email` and `bot_id`, it creates a
    @param bot_id Bot_id is a unique identifier for a chatbot or a bot application. It helps in
    distinguishing different bots or instances of bots within a system.
    
    @return If the `response.data` is an empty list, the function will return "Created". Otherwise, it
    will return the `response` object.
    """
    response = supabase.table("last_cat_message").select("message_id").eq("email", email).eq("bot_id", bot_id).execute()
    if response.data == []:
        created = supabase.table("last_cat_message").insert({"email" : email,"bot_id" : bot_id,"message_id" : ""}).execute()
        return "Created"
    return response


async def get_messages(email, bot_id, message_id):
    # The above code is querying a table named "messages" from a Supabase database. It selects all columns
    # ("*") where the "email" column matches the provided email and the "bot_id" column matches the
    # provided bot_id.
    query = supabase.table("message_paritition").select("*").eq("email", email).eq("bot_id", bot_id)
    
    # Only add the gt filter if message_id is not empty
    if message_id:
        query = query.gt("id", message_id)
        
    response = query.limit(20).order("created_at").execute()
    return response

def sync_messages(email, bot_id, message_id):
    # Get latest messages last 40 messages
    # The code is querying a table named "messages" from a Supabase database. It filters the
    # messages based on the "email" and "bot_id" fields. If a "message_id" is provided, it further filters
    # the messages to only include those with an "id" greater than the provided "message_id", orders the
    # results by "created_at" in descending order, limits the results to 40 entries, and then executes the
    # query. If no "message_id" is provided, it simply limits the results to 40 entries, orders them by
    # "created_at" in
    messages = supabase.table("message_paritition").select("*").eq("email", email).eq("bot_id", bot_id)
    if message_id:
        messages = messages.gt("id", message_id).order("created_at", desc=True).limit(40).execute()
    else:
        messages = messages.limit(40).order("created_at", desc=True).execute()
    
    if messages.data == []:
        return []

    # Reverse the list to get the latest messages first
    messages = messages.data[::-1]
    
    formatted_messages = []
    # The code is iterating over a list of `messages`. For each `message`, it checks if
    # it contains a key `'user_message'` or `'bot_response'`. If the message contains a
    # `'user_message'`, it creates a new dictionary with keys `"text"`, `"sender"`, and `"timestamp"`
    # using the corresponding values from the message. If the message contains a `'bot_response'`, it
    # creates a new dictionary with keys `"text"`, `"sender"`, `"id"`, `"feedback"`, and `"timestamp"`
    # using the corresponding values from the message. The code
    
    for message in messages:
        if 'user_message' in message:
            formatted = {
                "text": message["user_message"],
                "sender": "user",
                "timestamp": message["created_at"],
                "platform": message.get("platform")
            }
            if "activity_name" in message:
                formatted["activity_name"] = message["activity_name"]
            formatted_messages.append(formatted)
        if 'bot_response' in message:
            formatted = {
                "text": message["bot_response"],
                "sender": "bot",
                "id": message["id"],
                "feedback": "",
                "timestamp": message["created_at"],
                "platform": message.get("platform")
            }
            if "activity_name" in message:
                formatted["activity_name"] = message["activity_name"]
            formatted_messages.append(formatted)
    
    return formatted_messages

from MM2 import post_processing

async def extractor(email, bot_id, message_id):
    try:
        # The code snippet is using Python to asynchronously retrieve messages using the
        # `get_messages` function with the provided `email`, `bot_id`, and `message_id` parameters. It
        # then checks if the `data` attribute of the `messages` object is an empty list. If it is
        # empty, the code will return from the function.
        messages = await get_messages(email, bot_id, message_id)
        if messages.data == []:
            return
            
        msg_count = len(messages.data)
        print("message Length:", msg_count)
        
        # The Python code snippet is checking if the `msg_count` variable is greater than or equal to 5.
        # If it is, the code then proceeds to extract memory from the `messages.data` using the
        # `post_processing.extract_memory` function with the parameters `messages.data`, `email`, and
        # `bot_id`.
        # Process if more than 5 messages
        if msg_count >= 5:
            await post_processing.extract_memory(messages.data, email, bot_id)
            supabase.table("last_cat_message").update({"message_id": messages.data[-1]['id']}).eq("email", email).eq("bot_id", bot_id).execute()
            print("Data Extraction after 5 messages")
            
        # Only check time-based condition for 1-4 messages
        elif msg_count > 0:
            try:
                last_message_time = datetime.fromisoformat(messages.data[0]['created_at'])
                time_diff = datetime.now(timezone.utc) - last_message_time
                
                # The code snippet is checking if the variable `time_diff` is greater
                # than 5 minutes using a timedelta comparison. If the condition is met, it prints
                # "Data Extraction after 5 minutes", then proceeds to extract memory from
                # `messages.data`, and updates a Supabase table named "last_cat_message" with the
                # latest message ID from `messages.data` for a specific email and bot ID.
                if time_diff > timedelta(minutes=5):
                    print("Data Extraction after 5 minutes")
                    await post_processing.extract_memory(messages.data, email, bot_id)
                    supabase.table("last_cat_message").update({"message_id": messages.data[-1]['id']}).eq("email", email).eq("bot_id", bot_id).execute()

            except (IndexError, AttributeError) as e:
                print(f"Error processing messages: {e}")
                
    except Exception as e:
        print(f"Error in extract_memory: {e}")

import asyncio
async def checker():
    # The code is using the Supabase client to query the "last_cat_message" table and
    # retrieve all columns for all rows. If the response data is empty (no rows returned), it will
    # print a message indicating that no data was found in the "last_cat_message" table.
    response = supabase.table("last_cat_message").select("*").execute() 
    if response.data == []:
        print("No data found in last_cat_message table")
        return
    else:
        print(f"Found {len(response.data)} records to process")
        # The code is iterating over the `response.data` and for each `data` item, it is
        # trying to call the `extractor` function with the parameters `data['email']`,
        # `data['bot_id']`, and `data['message_id']` using the `await` keyword (assuming it is inside
        # an asynchronous function). If an exception occurs during the execution of the `extractor`
        # function, it catches the exception and prints an error message with the details of the
        # exception.
        for data in response.data:
            try:
                await extractor(data['email'], data['bot_id'], data['message_id'])
            except Exception as e:
                print(f"Error in extractor: {e}")

async def insert_entry(email, user_message, bot_response, bot_id, requested_time, platform):
    # The code is inserting a new record into a table named "messages" using Supabase. It
    # includes fields such as email, user_message, bot_response, bot_id, and requested_time. After
    # inserting the record, it then calls a function `check_entry_exists` with the email and bot_id
    # parameters and finally returns the response from the insert operation.
    response = supabase.table("message_paritition").insert({
        "email": email,
        "user_message": user_message,
        "bot_response": bot_response,
        "bot_id": bot_id,
        "requested_time": requested_time,
        "platform": platform,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }).execute()
    await check_entry_exists(email, bot_id)
    return response

#--------------------------------------------Proactive Messages----------------------------------------------------

def create_morning_message(user_datetime_str: str, email: str, bot_id: str, message: str) -> dict:
    # Parse the timezone and offset more robustly
    try:
        # Handle different timezone formats
       # The code snippet is checking a given `user_datetime_str` string for the presence of
       # timezone information. It first checks if the string contains "GMT", then extracts the
       # timezone part. If not found, it checks for the presence of a `+` or `-` sign followed by the
       # timezone information. If none of these conditions are met, it raises a `ValueError`
       # indicating that no timezone information was found in the datetime string.
        if "GMT" in user_datetime_str:
            tz_part = user_datetime_str.split("GMT")[1].split(" ")[0]
        elif "+" in user_datetime_str:
            tz_part = "+" + user_datetime_str.split("+")[1].split(" ")[0]
        elif "-" in user_datetime_str:
            tz_part = "-" + user_datetime_str.split("-")[1].split(" ")[0]
        else:
            raise ValueError("No timezone found in datetime string")

        # Extract hours and minutes, handling both 4-digit and 2-digit formats
        tz_sign = tz_part[0]
        if len(tz_part) == 5:  # Format like +0530
            tz_hours = int(tz_part[1:3])
            tz_minutes = int(tz_part[3:5])
        else:  # Format like -08
            tz_hours = int(tz_part[1:])
            tz_minutes = 0

        tz_total_minutes = tz_hours * 60 + tz_minutes
        if tz_sign == '-':
            tz_total_minutes = -tz_total_minutes

        # Create timezone object
        user_tz = pytz.FixedOffset(tz_total_minutes)
        
        # Get current time in user's timezone
        current_time = datetime.now(user_tz)
        
        # Calculate next 7:15 AM in user's timezone
        next_morning = current_time.replace(hour=7, minute=15, second=0, microsecond=0)
        if next_morning <= current_time:
            next_morning += timedelta(days=1)
        
        # Convert to UTC for storage
        next_morning_utc = next_morning.astimezone(pytz.UTC)
        
        schedule = {
            'email': email,
            'bot_id': bot_id,
            'scheduled_time': next_morning_utc.isoformat(),
            'message': message,
            'user_timezone_offset': tz_part  # Store original timezone string
        }
        
        # Log for verification
        prPurple(f"User's timezone: GMT{tz_part}")
        prPurple(f"Current time in user's timezone: {current_time}")
        prPurple(f"Scheduled delivery time (user timezone): {next_morning}")
        prPurple(f"Scheduled delivery time (UTC): {next_morning_utc}")
        
        return schedule

    except Exception as e:
        prRed(f"Error creating morning message: {e}")
        return None

def schedule_message(email: str, bot_id: str,last_morning_message:str) -> dict | None:
    # Get user's last message to determine timezone
    result = supabase.table("message_paritition") \
        .select("requested_time") \
        .eq("email", email) \
        .eq("bot_id", bot_id) \
        .order("created_at", desc=True) \
        .limit(10) \
        .execute()
    
    if not result.data:
        prRed(f"No previous messages found for email: {email}")
    else:
        last_requested_time_str = ""
        try :
            # check in all 10 messages for the requested_time
            for message in result.data:
                if message['requested_time']:
                    last_requested_time_str = message['requested_time']
                    break
        except Exception as e:
            prRed(f"No Local Time found for email: {email}")
            return None
        
        if last_requested_time_str:
            # The above Python code is retrieving a new morning message from a database table named
            # "proactive_messages".
            get_new_morning_message_data = ""
            if last_morning_message == "":
                get_new_morning_message_data = supabase.table("proactive_messages").select("*").limit(1).execute()
                get_new_morning_message = get_new_morning_message_data.data[0]['message']  # Use dictionary access syntax
            else:
                get_new_morning_message_data = supabase.table("proactive_messages").select("*").gt("id", last_morning_message).limit(1).execute()
                get_new_morning_message = get_new_morning_message_data.data[0]['message']           

            prGreen(f"Morning message: {get_new_morning_message}")
           # The code snippet is calling a function `create_morning_message` with the provided
           # arguments `last_requested_time_str`, `email`, `bot_id`, and `get_new_morning_message`.
           # This function likely generates a morning message based on the input parameters and
           # schedules it to be sent at a specific time.
            schedule = create_morning_message(
                user_datetime_str=last_requested_time_str,
                email=email,
                bot_id=bot_id,
                message=get_new_morning_message
            )

            prGreen(f"\nSchedule: {schedule}")

            try:
                # The code is inserting a new record into a table named "scheduler" in a
                # Supabase database. It includes the fields "email", "bot_id", "scheduled_time",
                # "message", and "user_timezone_offset" with corresponding values.
                supabase.table("scheduler").insert({
                    "email": email,
                    "bot_id": bot_id,
                    "scheduled_time": schedule['scheduled_time'],
                    "message": schedule['message'],
                    "user_timezone_offset": schedule['user_timezone_offset']
                }).execute()
                supabase.table("last_cat_message").update({"morning_message": get_new_morning_message_data.data[0]['id']}).eq("email", email).eq("bot_id", bot_id).execute()
                return prPurple(f"\nFinal schedule: {schedule}")
            except Exception as e:
                print(f"Error in schedule_message: {e}")
                return None
        else:
            prRed(f"No Local Time found for email: {email}")
    

def check_daily_scheduled_messages():
    print("Checking daily scheduled messages...")
    # get email and bot_id from the last_cat_message table
    all_emails_and_bot_ids = supabase.table("last_cat_message").select("*").execute()
    # loop through the email and bot_id
    print(f"Found {len(all_emails_and_bot_ids.data)} email and bot_id pairs.")
    for email_and_bot_id in all_emails_and_bot_ids.data:
        email = email_and_bot_id['email']
        bot_id = email_and_bot_id['bot_id']
        last_morning_message = email_and_bot_id["morning_message"]
        # get all scheduled messages for the email and bot_id
        all_scheduled_messages = supabase.table("scheduler").select("*").eq("email", email).eq("bot_id", bot_id).execute()
        prCyan(f"Found {len(all_scheduled_messages.data)} scheduled messages for {email} and {bot_id}.")
        # Check if any message is schedule in between 7 AM and 8 AM on users timezone
        if len(all_scheduled_messages.data) > 0:
           prLightPurple("message is scheduled in between 7 AM and 8 AM")
           prBlack("----------------------- END OF SCHEDULING MESSAGES -----------------------")
        else:
            # Check if the last 3 messages at least one record should have a user message
            last_3_messages = supabase.table("message_paritition").select("*").eq("email", email).eq("bot_id", bot_id).order("id", desc=True).limit(3).execute()
            # prCyan(f"Found {len(last_3_messages.data)} messages for {email} and {bot_id}.")
            # loop through the last 3 messages and check if the message is a user message in any of the last 3 messages if yes then schedule the message else do nothing
            if last_3_messages.data[0]['user_message'] == '' and last_3_messages.data[1]['user_message'] == '' and last_3_messages.data[2]['user_message'] == '':
                prYellow("No user message in last 3 messages, so user is inactive")
                prBlack("----------------------- END OF SCHEDULING MESSAGES -----------------------")
                continue
            else:
                prPurple("Going for scheduling message")
                try:
                    schedule_message(email, bot_id,last_morning_message)
                except Exception as e:
                    prRed(f"Error in scheduling message: {e}")

                prBlack("----------------------- END OF SCHEDULING MESSAGES -----------------------")
                

def check_scheduled_messages():
    print("Checking scheduled messages...")
    # get email and bot_id from the last_cat_message table
    all_emails_and_bot_ids = supabase.table("last_cat_message").select("*").execute()
    # loop through the email and bot_id
    print(f"Found {len(all_emails_and_bot_ids.data)} email and bot_id pairs.")
    for email_and_bot_id in all_emails_and_bot_ids.data:
        email = email_and_bot_id['email']
        bot_id = email_and_bot_id['bot_id']
        # get all scheduled messages for the email and bot_id
        all_scheduled_messages = supabase.table("scheduler").select("*").eq("email", email).eq("bot_id", bot_id).execute()
        print(f"Found {len(all_scheduled_messages.data)} scheduled messages for {email} and {bot_id}.")
        # loop through the scheduled messages
        for scheduled_message in all_scheduled_messages.data:
            scheduled_time = datetime.fromisoformat(scheduled_message['scheduled_time'])
            current_time = datetime.now(timezone.utc)
            print(f"Scheduled time: {scheduled_time}")
            print(f"Current time: {current_time}")
            # check if the scheduled message is due
            if scheduled_time < current_time:
                # remove the scheduled message from the scheduler table
                supabase.table("scheduler").delete().eq("email", email).eq("bot_id", bot_id).eq("scheduled_time", scheduled_time).execute()
                # add the message to the messages table
                supabase.table("message_paritition").insert({
                    "email": email,
                    "bot_id": bot_id,
                    "user_message": "",
                    "bot_response": scheduled_message['message'],
                    "requested_time": "",
                }).execute()
                print(f"Scheduled message {scheduled_message['message']} has been sent.")


# ---------------------------------------------------------------------- Get Memories -------------------------------------------------------
def get_memories_from_DB(email,bot_id):
    query_response = index.query(
        namespace=f"{email}-{bot_id}-conversation",
        vector=[0] * 1024,
        top_k=10,
        include_values=False,
        include_metadata=True
    )
    return query_response


# Parse a string timestamp into a timezone-aware datetime object
def parse_requested_time(requested_time_str):
    if not requested_time_str or not isinstance(requested_time_str, str):
        return None
    try:
        # Fix: Normalize microseconds to 6 digits before parsing
        normalized_time = requested_time_str.replace('Z', '+00:00')
        if '.' in normalized_time and ('+' in normalized_time or '-' in normalized_time[-6:]):
            # Split by timezone
            if '+' in normalized_time:
                base_time, tz_part = normalized_time.rsplit('+', 1)
                tz_sign = '+'
            else:
                base_time, tz_part = normalized_time.rsplit('-', 1)
                tz_sign = '-'
            
            if '.' in base_time:
                time_part, microseconds = base_time.rsplit('.', 1)
                # Pad microseconds to 6 digits or truncate to 6 digits
                microseconds = microseconds.ljust(6, '0')[:6]
                normalized_time = f"{time_part}.{microseconds}{tz_sign}{tz_part}"
        
        return datetime.fromisoformat(normalized_time)
    except Exception as e:
        logging.warning(f"Failed to parse timestamp '{requested_time_str}': {e}")
        return None


# Fetch messages from Supabase sent in the last 2 days for a specific user and bot
def get_user_messages(email, bot_id):
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    logging.info(f"[get_user_messages] Fetching messages since {two_days_ago} for {email}, {bot_id}")

    response = supabase.table("message_paritition") \
        .select("*") \
        .eq("email", email) \
        .eq("bot_id", bot_id) \
        .gte("created_at", two_days_ago) \
        .execute()

    logging.info(f"[get_user_messages] Retrieved {len(response.data)} messages")
    return response.data


# Filter only messages where local date (from requested_time or created_at) is yesterday
def filter_yesterdays_messages(messages):
    yesterday = datetime.now().date() - timedelta(days=1)
    logging.info(f"[filter_yesterdays_messages] Filtering for local date = {yesterday}")

    filtered = []

    for msg in messages:
        requested_time_str = msg.get("requested_time")
        dt = parse_requested_time(requested_time_str)

        if not dt and msg.get("created_at"):
            try:
                dt = datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00"))
                logging.info(f"[filter_yesterdays_messages] ⏰ Fallback to created_at: {dt}")
            except Exception as e:
                logging.error(f"[filter_yesterdays_messages] ❌ Failed to parse created_at: {e}")
                continue

        if dt and dt.date() == yesterday:
            filtered.append(msg)
            logging.info(f"[filter_yesterdays_messages] ✅ Included message at {dt}")
        else:
            logging.info(f"[filter_yesterdays_messages] ❌ Excluded message at {dt if dt else 'N/A'}")

    logging.info(f"[filter_yesterdays_messages] Total messages for yesterday: {len(filtered)}")
    return filtered


# Retrieve user's display name using their email from the 'user_details' table
def get_user_details_by_email(email):
    response = supabase.table("user_details") \
        .select("name, gender") \
        .eq("email", email) \
        .limit(1) \
        .execute()

    if response.data and len(response.data) > 0:
        return {
            "name": response.data[0]["name"],
            "gender": response.data[0]["gender"]
        }
    else:
        return {
            "name": "User",
            "gender": ""
        }
    
# Get details of bots from the bot_personality_details table
def get_bot_details_by_id(bot_id):
    response = supabase.table("bot_personality_details") \
        .select("bot_name, bot_gender, bot_user_relation") \
        .eq("bot_id", bot_id) \
        .limit(1) \
        .execute()

    if response.data and len(response.data) > 0:
        return {
            "bot_name": response.data[0]["bot_name"],
            "bot_gender": response.data[0]["bot_gender"],
            "bot_user_relation": response.data[0]["bot_user_relation"]
        }
    else:
        return {
            "bot_name": "Bot",
            "bot_gender": "",
            "bot_user_relation": ""
        }
    
# Get all (email, bot_id) pairs with activity in last 2 days
def get_all_users_and_bots():
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    response = supabase.table("message_paritition") \
        .select("email, bot_id") \
        .gte("created_at", two_days_ago) \
        .execute()

    unique_pairs = set()
    for row in response.data:
        unique_pairs.add((row["email"], row["bot_id"]))
    return list(unique_pairs)


# Generate a summary by sending chat data to an external API
def generate_summary(chat_text, user_name, user_gender, bot_name, bot_gender, bot_user_relation):
    payload = {
        "text": chat_text,
        "api_key": API_KEY,
        "modelname": MODEL_NAME,
        "user1": user_name,
        "user2": bot_name,
        "user1_gender": user_gender,
        "user2_gender": bot_gender,
        "relation": bot_user_relation
    }

    print(json.dumps(payload, indent=4))

    try:
        response = requests.post("https://amaze18--summary-gemini-generate-summary.modal.run", json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"[generate_summary] API failed with status: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"[generate_summary] Failed to parse summary response: {e}")
        return None


# Store the generated summary in Supabase if it doesn't already exist
def store_summary(email, bot_id, summary_text, summary_date):
    now_utc = datetime.now(timezone.utc).isoformat()

    existing = supabase.table("summary") \
        .select("email") \
        .eq("email", email) \
        .eq("bot_id", bot_id) \
        .eq("summary_date", summary_date.isoformat()) \
        .limit(1) \
        .execute()

    if existing.data:
        logging.info(f"[store_summary] Summary already exists for {email}, {summary_date}")
        return

    try:
        supabase.table("summary").insert({
            "email": email,
            "bot_id": bot_id,
            "generated_summary": summary_text,
            "created_at": now_utc,
            "summary_date": summary_date.isoformat()
        }).execute()
        logging.info(f"[store_summary] ✅ Summary stored for {email}, {bot_id}")
    except Exception as e:
        logging.error(f"[store_summary] ❌ Error while inserting summary: {e}")


# Master function that runs once a day
def process_summaries_for_yesterday():
    logging.info("📦 [process_summaries_for_yesterday] Processing summaries for each user (based on local time)")

    user_bot_pairs = get_all_users_and_bots()

    for email, bot_id in user_bot_pairs:
        logging.info(f"\n--- Processing user: {email}, bot: {bot_id} ---")
        all_msgs = get_user_messages(email, bot_id)
        messages = filter_yesterdays_messages(all_msgs)

        if not messages:
            logging.info(f"[process_summaries_for_yesterday] No messages from yesterday for {email}")
            continue

        user_details = get_user_details_by_email(email)
        user_name = user_details["name"]
        user_gender = user_details["gender"]

        bot_details = get_bot_details_by_id(bot_id)
        bot_name = bot_details["bot_name"]
        bot_gender = bot_details["bot_gender"]
        bot_user_relation = bot_details["bot_user_relation"]

        chat_text = "\n".join(
            f"user1: {m['user_message']}\nuser2: {m['bot_response']}"
            for m in messages
        )
        logging.info("chat text")
        logging.info(chat_text)

        summary = generate_summary(chat_text, user_name, user_gender, bot_name, bot_gender, bot_user_relation)
        logging.info("summary")
        logging.info(summary)

        yesterday_date = datetime.now().date() - timedelta(days=1)
        if summary:
            store_summary(email, bot_id, summary, yesterday_date)
#------------------------------------------------------- helper functions for categorizer api -------------------------------------------------------
def get_today_user_bot_pairs():
    try:
        utc_now = datetime.now(timezone.utc)
        start = datetime.combine(utc_now.date(), time.min, tzinfo=timezone.utc).isoformat()
        end = datetime.combine(utc_now.date(), time.max, tzinfo=timezone.utc).isoformat()

        response = supabase.table("message_paritition") \
            .select("email, bot_id") \
            .gte("created_at", start) \
            .lte("created_at", end) \
            .execute()

        pairs = {(item["email"], item["bot_id"]) for item in response.data if item.get("email") and item.get("bot_id")}
        return list(pairs)

    except Exception as e:
        logging.error(f"Exception in get_today_user_bot_pairs: {e}")
        return []


def get_last_processed_time(email: str, bot_id: str):
    try:
        response = supabase.table("categorization_progress") \
            .select("last_processed_at") \
            .eq("email", email) \
            .eq("bot_id", bot_id) \
            .limit(1).execute()

        if response.data:
            return datetime.fromisoformat(response.data[0]["last_processed_at"])
    except Exception as e:
        logging.error(f"Error fetching last processed time for {email}, {bot_id}: {e}")
    return None

def get_username(email: str):
    try:
        response = supabase.table("user_details") \
            .select("name") \
            .eq("email", email) \
            .limit(1).execute()
        if response.data:
            return response.data[0]["name"]
    except Exception as e:
        logging.error(f"Error fetching username for {email}: {e}")
    return None

# 🤖 Fetch botname for the given bot_id
def get_botname(bot_id: str):
    try:
        response = supabase.table("bot_personality_details") \
            .select("bot_name") \
            .eq("bot_id", bot_id) \
            .limit(1).execute()
        if response.data:
            return response.data[0]["bot_name"]
    except Exception as e:
        logging.error(f"Error fetching botname for {bot_id}: {e}")
    return None

def update_last_processed_time(email: str, bot_id: str, timestamp: datetime):
    try:
        supabase.table("categorization_progress").upsert({
            "email": email,
            "bot_id": bot_id,
            "last_processed_at": timestamp.isoformat()
        }).execute()
    except Exception as e:
        logging.error(f"Error updating last processed time for {email}, {bot_id}: {e}")


def fetch_new_messages(email: str, bot_id: str):
    try:
        last_processed = get_last_processed_time(email, bot_id)
        utc_now = datetime.now(timezone.utc)

        query = supabase.table('message_paritition').select("*") \
            .eq('email', email) \
            .eq('bot_id', bot_id) \
            .order("created_at")

        if last_processed:
            query = query.gt('created_at', last_processed.isoformat())
        else:
            start = datetime.combine(utc_now.date(), time.min, tzinfo=timezone.utc)
            query = query.gte('created_at', start.isoformat())

        response = query.execute()
        return response.data if not getattr(response, "error", None) else []

    except Exception as e:
        logging.error(f"Error fetching new messages for {email}, {bot_id}: {e}")
        return []


def combine_messages(messages):
    try:
        chat_log = ""
        for msg in messages:
            user_msg = msg.get('user_message', '').strip()
            bot_msg = msg.get('bot_response', '').strip()
            if user_msg:
                chat_log += f"user1: {user_msg}\nuser2: {bot_msg}\n"
        return chat_log
    except Exception as e:
        logging.error(f"Error combining messages: {e}")
        return ""
from MM2.serialization import serialize_memory
def categorize_user_messages(email: str, bot_id: str):
    modelname = "sonar-reasoning"
    api_key = os.getenv("CATEGORIZER_API_KEY")
    url = os.getenv("CATEGORIZER_URL")
    
    # Fetch messages for processing
    messages = fetch_new_messages(email, bot_id)
    if not messages:
        logging.info(f"No new messages to process for {email}, {bot_id}")
        return
    
    username = get_username(email)
    botname = get_botname(bot_id)

    if not username or not botname:
        logging.error(f"Missing username or botname for {email}, {bot_id}. Skipping categorizer call.")
        return
    
    batch_size = 25
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        chat_log = combine_messages(batch)

        if not chat_log.strip():
            logging.info(f"Empty user messages in batch for {email}, {bot_id}. Skipping categorizer API call.")
            continue

        payload = {
            "query": chat_log,
            "type_analysis": "character analysis",
            "api_key": api_key,
            "modelname": modelname,
            "user1": username,
            "user2": botname,
        }

        try:
            # Send the request to categorizer API
            response = requests.post(url, json=payload)
            print("Status Code:", response.status_code)

            raw_text = response.text.strip()

            # If server error, log and exit early
            if "503" in raw_text or "Error" in raw_text:
                logging.error(f"Categorizer server error: {raw_text}")
                continue

            if raw_text.startswith('"') and raw_text.endswith('"'):
                try:
                    raw_text = json.loads(raw_text)
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to decode wrapped string for {email}, {bot_id}: {e}")
                    continue

            match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.DOTALL)
            if match:
                json_block = match.group(1).strip()
            else:
                json_block = raw_text.strip()

            if json_block.startswith('{') and json_block.endswith('}'):
                json_block = '[' + json_block + ']'

            result = json.loads(json_block)
            print("Parsed JSON:", result)

            rows_to_insert = []
            for item in result:
                memory = item.get("rephrased_user_message")
                category = item.get("category")
                if memory and category:
                    rows_to_insert.append({
                        "email": email,
                        "bot_id": bot_id,
                        "memory": memory,
                        "category": category
                    })

            if not rows_to_insert:
                logging.warning(f"No valid memory-category pairs found for {email}, {bot_id} in this batch")
                continue

            rows_to_insert = [serialize_memory(row) for row in rows_to_insert]
            supabase.table("persona_category").upsert(rows_to_insert).execute()
            update_last_processed_time(email, bot_id, datetime.fromisoformat(batch[-1]["created_at"]))
            logging.info(f"Inserted {len(rows_to_insert)} rows and updated last_processed_at for {email}, {bot_id}")

        except Exception as e:
            traceback.print_exc()
            logging.error(f"Error processing categorizer API call for {email}, {bot_id}: {e}")

# -------------------------------helper functions for summary-------------------------------

"""
    Fetches summaries from the summary table for a specific user and bot.
"""
def get_summaries_from_DB(email: str, bot_id: str):
    try:
        response = (
            supabase
            .table("summary")
            .select("generated_summary, summary_date")
            .eq("email", email)
            .eq("bot_id", bot_id)
            .order("summary_date", desc=False)
            .execute()
        )
        
        if response.data:
            return response.data
        else:
            return []
    except Exception as e:
        logging.error(f"Error fetching summaries from DB: {e}")
        return []
    
"""
    Deletes a specific summary from the summary table.
    Returns True if the summary was deleted, False otherwise.
"""    
def delete_summary_from_DB(email: str, bot_id: str, summary_date):
    try:
        response = (
            supabase
            .table("summary")
            .delete()
            .eq("email", email)
            .eq("bot_id", bot_id)
            .eq("summary_date", str(summary_date))  # Ensure it's a string in 'YYYY-MM-DD'
            .execute()
        )
        
        # Check if any rows were deleted
        return bool(response.data and len(response.data) > 0)
    
    except Exception as e:
        logging.error(f"Error deleting summary from DB: {e}")
        return False

#----------------------------------------------------- functions for redundancy ------------------------------------------------------------------

REDUNDANCY_API_URL=os.getenv("REDUNDANCY_API_URL") 
REDUNDANCY_API_KEY=os.getenv("REDUNDANCY_API_KEY")

def get_distinct_user_bot_combinations():
    """Fetch all unique email-bot_id combinations with non-redundant memories"""
    query = supabase.table("persona_category") \
        .select("email, bot_id") \
        .eq("redundant", False) \
        .not_.is_("memory", "NULL") \
        .not_.eq("memory", "")
    
    result = query.execute()
    
    # Extract distinct combinations in Python
    if not result.data:
        return []
    
    # Use a set to get unique combinations
    unique_combinations = set()
    for record in result.data:
        unique_combinations.add((record["email"], record["bot_id"]))
    
    # Convert back to list of dictionaries
    return [{"email": email, "bot_id": bot_id} for email, bot_id in unique_combinations]
    print(unique_combinations)

def fetch_memories(email, bot_id):
    """Fetch memories for a specific user and bot"""
    response = supabase.table("persona_category") \
        .select("id, memory, category") \
        .eq("email", email) \
        .eq("bot_id", bot_id) \
        .eq("redundant", False) \
        .execute()
    return response.data

def extract_clean_json(response):
    """Extract and clean JSON from API response"""
    raw_text = response.text.strip()
    logging.info(f"Raw API response (preview): {raw_text[:300]}...")

    # Step 1: If double-encoded string, decode once
    if raw_text.startswith('"') and raw_text.endswith('"'):
        try:
            raw_text = json.loads(raw_text)
        except Exception:
            logging.warning("Failed to decode double-encoded string")

    # Step 2: Extract from code block if present
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.DOTALL)
    if match:
        json_block = match.group(1).strip()
    else:
        json_block = raw_text

    # Step 3: Manually parse multiple top-level JSON objects
    json_objects = []
    for obj in re.finditer(r'{.*?}', json_block, re.DOTALL):
        try:
            parsed = json.loads(obj.group())
            json_objects.append(parsed)
        except json.JSONDecodeError as e:
            logging.warning(f"Skipping malformed JSON object: {e}")

    if not json_objects:
        raise ValueError("Invalid JSON block format or no valid objects found")

    return json_objects

def normalize(text):
    """Normalize text for comparison"""
    text = text.lower().strip()
    text = re.sub(f"[{re.escape(string.punctuation)}]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def call_redundancy_api(memories, categories):
    """Call the redundancy detection API"""
    payload = {
        "rephrased_memories": "\n".join(memories),
        "category": "\n".join(categories),
        "modelname": "sonar-reasoning",
        "api_key": REDUNDANCY_API_KEY
    }
    
    response = requests.post(REDUNDANCY_API_URL, json=payload)
    response.raise_for_status()
    return extract_clean_json(response)

def process_redundant_groups(response_data, records):
    """Process API response and identify redundant groups"""
    redundant_pairs = []
    if isinstance(response_data, list):
        logging.info(f"Processing {len(response_data)} groups")
        for item in response_data:
            if item.get("redundant") == "True":
                messages = [v for k, v in item.items() 
                          if k.startswith("rephrased_user_message") and v]
                if messages:
                    redundant_pairs.append(messages)
                    logging.info(f"Found redundant group: {messages}")
    return redundant_pairs

def update_redundant_memories(redundant_pairs, records):
    """Update Supabase with redundant memory information"""
    updates = 0
    already_updated_ids = set()
    message_to_relation = {}

    def find_or_create_relation_id(group):
        for mem in group:
            norm = normalize(mem)
            if norm in message_to_relation:
                return message_to_relation[norm]
        return str(uuid.uuid4())

    for group in redundant_pairs:
        relation_id = find_or_create_relation_id(group)

        for mem in group:
            norm = normalize(mem)
            matched = False
            for r in records:
                if (normalize(r["memory"]) == norm and 
                    r["id"] not in already_updated_ids):
                    logging.info(f"Updating memory ID {r['id']} with relation_id {relation_id}")
                    supabase.table("persona_category").update({
                        "redundant": True,
                        "relation_id": relation_id
                    }).eq("id", r["id"]).execute()
                    already_updated_ids.add(r["id"])
                    updates += 1
                    message_to_relation[norm] = relation_id
                    matched = True
                    break
            if not matched:
                logging.warning(f"Could not match: {mem}")
    
    return updates

def process_user_bot_combination(email, bot_id):
    """Process a single user-bot combination"""
    logging.info(f"Processing {email} - {bot_id}")
    
    records = fetch_memories(email, bot_id)
    if not records:
        logging.info(f"No memories found for {email} - {bot_id}")
        return 0
    
    memories = [r["memory"] for r in records]
    categories = [r["category"] for r in records]
    
    try:
        response_data = call_redundancy_api(memories, categories)
        redundant_pairs = process_redundant_groups(response_data, records)
        updates = update_redundant_memories(redundant_pairs, records)
        logging.info(f"Updated {updates} records for {email} - {bot_id}")
        return updates
    except Exception as e:
        logging.error(f"Error processing {email} - {bot_id}: {str(e)}")
        return 0


#integrated
