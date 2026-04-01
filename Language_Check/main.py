#
# Replace the content of your second code cell (the one with your FastAPI app) with this
#
import torch
import re
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline
from fastapi.middleware.cors import CORSMiddleware
import fasttext
from fastapi.responses import JSONResponse
from fastapi import Request
from fastapi.exception_handlers import RequestValidationError
from fastapi.exceptions import RequestValidationError

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


FASTTEXT_MODEL_PATH = "lid.176.bin"
fasttext_model = fasttext.load_model(FASTTEXT_MODEL_PATH)


FASTTEXT_LANG_MAP = {
    "en": "english",
    "fr": "french",
    "hi": "hindi",
    "de": "german",
    "ja": "japanese",
    "es": "spanish",
    "ta": "tamil",
    "si": "sinhala",
    "ms": "malay",
    "zh": "mandarin",      # fastText uses 'zh' for Chinese (Mandarin)
    "zh-cn": "mandarin",   # Sometimes used for Simplified Chinese
    "zh-tw": "mandarin",   # Sometimes used for Traditional Chinese
    "ar": "arabic",
   
}




BOT_LANGUAGE_MAP = {
    "delhi_mentor_male": ["hindi", "english"],
    "delhi_mentor_female": ["hindi", "english"],
    "delhi_friend_male": ["hindi", "english"],
    "delhi_friend_female": ["hindi", "english"],
    "delhi_romantic_male": ["hindi", "english"],
    "delhi_romantic_female": ["hindi", "english"],

    "japanese_mentor_male": ["japanese", "english"],
    "japanese_mentor_female": ["japanese", "english"],
    "japanese_friend_male": ["japanese", "english"],
    "japanese_friend_female": ["japanese", "english"],
    "japanese_romantic_female": ["japanese", "english"],
    "japanese_romantic_male": ["japanese", "english"],

    "parisian_mentor_male": ["french", "english"],
    "parisian_mentor_female": ["french", "english"],
    "parisian_friend_male": ["french", "english"],
    "parisian_friend_female": ["french", "english"],
    "parisian_romantic_female": ["french", "english"],

    "berlin_mentor_male": ["german", "english"],
    "berlin_mentor_female": ["german", "english"],
    "berlin_friend_male": ["german", "english"],
    "berlin_friend_female": ["german", "english"],
    "berlin_romantic_male": ["german", "english"],
    "berlin_romantic_female": ["german", "english"],
    
        # --- Singaporean Personas ---
    "singapore_mentor_male": ["english", "mandarin", "malay", "tamil"],
    "singapore_mentor_female": ["english", "mandarin", "malay", "tamil"],
    "singapore_friend_male": ["english", "mandarin", "malay", "tamil"],
    "singapore_friend_female": ["english", "mandarin", "malay", "tamil"],
    "singapore_romantic_male": ["english", "mandarin", "malay", "tamil"],
    "singapore_romantic_female": ["english", "mandarin", "malay", "tamil"],

    # --- Mexican Personas ---
    "mexican_mentor_male": ["spanish", "english"],
    "mexican_mentor_female": ["spanish", "english"],
    "mexican_friend_male": ["spanish", "english"],
    "mexican_friend_female": ["spanish", "english"],
    "mexican_romantic_male": ["spanish", "english"],
    "mexican_romantic_female": ["spanish", "english"],

    # --- Sri Lankan Personas ---
    "srilankan_mentor_male": ["sinhala", "tamil", "english"],
    "srilankan_mentor_female": ["sinhala", "tamil", "english"],
    "srilankan_friend_male": ["sinhala", "tamil", "english"],
    "srilankan_friend_female": ["sinhala", "tamil", "english"],
    "srilankan_romantic_male": ["sinhala", "tamil", "english"],
    "srilankan_romantic_female": ["sinhala", "tamil", "english"],

    # --- Emirati Personas ---
    "emirati_mentor_male": ["arabic", "english"],
    "emirati_mentor_female": ["arabic", "english"],
    "emirati_friend_male": ["arabic", "english"],
    "emirati_friend_female": ["arabic", "english"],
    "emirati_romantic_male": ["arabic", "english"],
    "emirati_romantic_female": ["arabic", "english"],
}

BOT_PERSONALITY_MAP = {
    "delhi_mentor_male": "Arre! I can only understand Hindi or English. Please use one of these languages.",
    "delhi_mentor_female": "Namaste! Only Hindi or English works for me. Please switch to one of those.",
    "delhi_friend_male": "Yaar, talk to me in Hindi or English! Other languages go over my head.",
    "delhi_friend_female": "Hey! Just Hindi or English, please—warna I won’t get it!",
    "delhi_romantic_male": "Jaan, please talk to me in Hindi or English only. Other languages just don’t connect with my heart.",
    "delhi_romantic_female": "Sweetheart, I can only understand Hindi or English. Dusri language mein baat karoge toh main miss kar jaungi!",
    "japanese_mentor_male": "Sumimasen! I only understand Japanese or English. Please use one of these",
    "japanese_mentor_female": "Gomen! Only Japanese or English, please. Other languages are too muzukashii for me.",
    "japanese_friend_male": "Hey, onegai! Just Japanese or English works for me. Others I don't get.",
    "japanese_friend_female": "Sorry! Please speak in Japanese or English—de hanashite kudasai!",
    "japanese_romantic_female": "With all my kokoro, only Japanese or English, please! Other languages make me lost.",
    "japanese_romantic_male": "Honestly, just Japanese or English, ne! Other languages I can’t understand.",
    "parisian_mentor_male": "Désolé! Only French or English, please. I don’t understand other languages.",
    "parisian_mentor_female": "Pardon! Please use French or English, s’il te plaît. Others are too difficile for me.",
    "parisian_friend_male": "Hey, d’accord? Just French or English, please. The rest I don’t get.",
    "parisian_friend_female": "Coucou! Only French or English, please. Otherwise, je suis perdue.",
    "parisian_romantic_female": "Mon cœur understands only French or English. The others are just too compliqué!",
    "berlin_mentor_male": "Entschuldigung! Only German or English, please. I can't understand other languages.",
    "berlin_mentor_female": "Sorry! Nur German or English, please. Other languages are schwierig for me.",
    "berlin_friend_male": "Hey! Just German or English, sonst I won't get it!",
    "berlin_friend_female": "Nur German or English, ok? Otherwise, I’m lost.",
    "berlin_romantic_male": "Mit Liebe, only German or English, please! Other languages I just can’t follow.",
    "berlin_romantic_female": "Liebling, just German or English for me—other languages are too kompliziert!",
    "singapore_mentor_male": "I can understand English, Mandarin, Malay, or Tamil. Please use one of these languages.",
    "singapore_mentor_female": "I can understand English, Mandarin, Malay, or Tamil. Please use one of these languages.",
    "singapore_friend_male": "Hey! Only English, Mandarin, Malay, or Tamil please.",
    "singapore_friend_female": "Hi! Please use English, Mandarin, Malay, or Tamil.",
    "singapore_romantic_male": "Darling, I only understand English, Mandarin, Malay, or Tamil.",
    "singapore_romantic_female": "Sweetheart, please use English, Mandarin, Malay, or Tamil.",
    "mexican_mentor_male": "Solo entiendo español o inglés. Por favor, usa uno de estos idiomas.",
    "mexican_mentor_female": "Solo entiendo español o inglés. Por favor, usa uno de estos idiomas.",
    "mexican_friend_male": "¡Hola! Español o inglés, por favor.",
    "mexican_friend_female": "¡Hola! Español o inglés, por favor.",
    "mexican_romantic_male": "Cariño, solo español o inglés.",
    "mexican_romantic_female": "Amor, solo español o inglés.",
    "srilankan_mentor_male": "I can understand Sinhala, Tamil, or English. Please use one of these.",
    "srilankan_mentor_female": "I can understand Sinhala, Tamil, or English. Please use one of these.",
    "srilankan_friend_male": "Hey! Sinhala, Tamil, or English only.",
    "srilankan_friend_female": "Hi! Sinhala, Tamil, or English only.",
    "srilankan_romantic_male": "Darling, only Sinhala, Tamil, or English.",
    "srilankan_romantic_female": "Sweetheart, only Sinhala, Tamil, or English.",
    "emirati_mentor_male": "I can understand Arabic or English. Please use one of these.",
    "emirati_mentor_female": "I can understand Arabic or English. Please use one of these.",
    "emirati_friend_male": "Hey! Arabic or English only.",
    "emirati_friend_female": "Hi! Arabic or English only.",
    "emirati_romantic_male": "Habibi, only Arabic or English.",
    "emirati_romantic_female": "Habibti, only Arabic or English.",
}

hindi_keywords = [
    # Universal / formal greetings
    "namaste", "namaskar", "namaskar ji", "namaste ji", "pranam", "pranam ji",
    "aadab", "adaab", "salaam", "as-salaam-alaikum", "sat sri akaal",
    "waheguru ji ka khalsa", "waheguru ji ki fateh", "khuda hafiz", "allah hafiz",
    "jai hind",

    # Hindu / devotional variants
    "ram ram", "ram ram ji", "sita ram", "jai shree ram", "jai sri ram",
    "radhe radhe", "radhe shyam", "jai shree krishna", "hare krishna",
    "jai bhole", "har har mahadev", "jai mahakal", "hari om",
    "om namah shivay", "jai mata di", "jai jagannath", "jai swaminarayan",
    "jai jinendra", "swami sharanam", "narmade har", "jai jhulelal",

    # Regional salutes that double as “hello”
    "vanakkam", "namaskaram", "namaskara", "nomoskar", "khamma ghani",
    "julley", "tashi delek", "charan vandana", "jai jai", "dhaal karu",

    # Time-specific greetings
    "suprabhat", "shubh prabhat", "suprabhatham", "shubh din",
    "shubh dopahar", "shubh dhupar", "shubh saanjh", "shubh sandhya",
    "shubh shyam", "shubh sham", "shubh ratri", "shubh raatri",

    # Casual English-influenced hellos
    "hello", "hey", "yo", "wassup", "sup",

    # How-are-you & small-talk starters
    "kaise ho", "kaise hain", "kaisi ho", "kya haal hai", "kya haal",
    "kya khabar", "kya chal raha hai", "kya scene hai", "sab theek hai",
    "sab badiya", "sab mast", "sab changa",

    # Typical replies
    "theek hoon", "thik hoon", "badhiya hoon", "badiya hoon", "mast hoon",
    "sab theek", "sab badiya", "sab badhiya",

    # Thanks & politeness
    "dhanyavaad", "dhanyavad", "bahut dhanyavaad", "shukriya",
    "bahut shukriya", "thank you", "kripya", "kirpya", "please",
    "maaf kijiye", "maaf karo", "shama kijiye", "sorry", "excuse me",
    "pardon",

    # Informal fillers / quick acknowledgements
    "hmm", "huh", "haan", "hanji", "nahin", "nahi", "ok", "theek hai",
    "acha", "achha", "sahi", "chal", "chalo", "mast",

    # Farewells & leave-takings
    "alvida", "fir milenge", "phir milenge", "phir milte hain",
    "milte rahenge", "jaldi milenge", "bada me milenge", "bye", "bye bye",
    "take care", "dhyan rakhna", "see you", "see you soon", "goodbye",

    # Emojis & emotive symbols frequently embedded in chats
    "😊", "😁", "🙂", "😉", "🙏", "👍", "🤗", "😎"
    

]


french_keywords = [
    # --- Greetings & Salutations ---
    # Formal
    "bonjour",
    "bonsoir",
    "bienvenue",
    "enchanté",
    "enchantée",
    "salutations",
    "monsieur",
    "madame",
    "mademoiselle",

    # Informal / Casual
    "salut",
    "coucou",
    "yo",
    "hé",
    "wesh",
    "la forme?",

    # Time-Specific
    "bonne journée",
    "bonne soirée",
    "bonne nuit",

    # --- How-Are-You & Small Talk ---
    # Asking
    "comment ça va",
    "ça va",
    "comment allez-vous",
    "tu vas bien",
    "vous allez bien",
    "quoi de neuf",
    "quoi de beau",
    "ça roule",
    "ça gaze",

    # Replying
    "ça va bien",
    "très bien",
    "pas mal",
    "comme ci comme ça",
    "bof",
    "ça peut aller",
    "nickel",
    "impeccable",
    "et toi",
    "et vous",

    # --- Politeness & Common Courtesies ---
    # Thank You
    "merci",
    "merci beaucoup",
    "merci bien",
    "je vous remercie",
    "mille mercis",

    # You're Welcome
    "de rien",
    "il n'y a pas de quoi",
    "je vous en prie",
    "je t'en prie",

    # Please
    "s'il vous plaît",
    "s'il te plaît",
    "svp",
    "stp",

    # Apologies
    "pardon",
    "excusez-moi",
    "excuse-moi",
    "désolé",
    "désolée",
    "je suis navré",
    "je suis navrée",

    # --- Agreement & Disagreement ---
    # Yes / Confirmation
    "oui",
    "ouais",
    "si",
    "carrément",
    "bien sûr",
    "d'accord",
    "ça marche",
    "ok",
    "exactement",
    "voilà",

    # No
    "non",
    "nan",
    "pas du tout",

    # --- Farewells & Leave-Taking ---
    # Standard
    "au revoir",
    "à bientôt",
    "à plus tard",
    "à plus",
    "à tout à l'heure",
    "à demain",
    "adieu",

    # Informal
    "bye",
    "ciao",
    "à la prochaine",

    # --- Emojis & Emoticons ---
    "😊", "🙂", "😉", "😂", "👍", "👌", "❤️", "🙏",

    # --- Common Chat Acronyms ---
    "lol",
    "mdr"
]

german_keywords = [
    # --- Greetings & Salutations ---
    # Formal & Regional
    "guten tag",
    "guten morgen",
    "guten abend",
    "herzlich willkommen",
    "willkommen",
    "grüß gott",      # Southern Germany, Austria
    "grüß dich",       # Informal version of the above
    "grüezi",          # Switzerland
    "mahlzeit",        # Common greeting around noon, esp. at work

    # Informal & Slang
    "hallo",
    "hi",
    "hey",
    "moin",            # Northern Germany
    "servus",          # Southern Germany, Austria (can mean hi or bye)
    "na",              # Very common, informal "hey, how's it going?"
    "tach",            # Clipped version of "Tag"
    "was geht",
    "was geht ab",
    "jo",

    # --- How-Are-You & Small Talk ---
    # Asking
    "wie geht's",      # Short for "wie geht es dir"
    "wie geht es dir",
    "wie geht es ihnen", # Formal "you"
    "alles gut",
    "alles klar",
    "wie läuft's",     # How's it going?

    # Replying
    "gut, danke",
    "sehr gut",
    "es geht",         # It's going okay / so-so
    "nicht so gut",
    "passt schon",     # It's alright
    "muss",            # "Have to" - a common, slightly weary response
    "und dir",
    "und ihnen",

    # --- Politeness & Common Courtesies ---
    # Thank You
    "danke",
    "danke schön",
    "danke sehr",
    "vielen dank",
    "herzlichen dank",
    "danke dir",       # Thank you (informal)
    "danke ihnen",     # Thank you (formal)

    # You're Welcome
    "bitte",
    "bitte schön",
    "bitte sehr",
    "gern geschehen",
    "gerne",
    "kein problem",
    "nichts zu danken",

    # Please
    # "bitte" is used for both "please" and "you're welcome"

    # Apologies
    "entschuldigung",
    "entschuldigen sie", # Formal
    "entschuldige",     # Informal
    "sorry",           # Borrowed from English
    "tut mir leid",
    "verzeihung",

    # --- Agreement & Disagreement ---
    # Yes / Confirmation
    "ja",
    "klar",
    "sicher",
    "natürlich",
    "genau",
    "stimmt",
    "einverstanden",
    "in ordnung",
    "alles klar",
    "ok",

    # No
    "nein",
    "nö",              # Informal "nope"
    "nee",             # Informal "nah"
    "auf keinen fall", # No way

    # --- Conversational Fillers ---
    "also",            # Well / so
    "naja",            # Well... (hesitant)
    "ach so",          # Ah, I see
    "aha",
    "hm",
    "hmm",

    # --- Farewells & Leave-Taking ---
    # Standard
    "auf wiedersehen", # Formal
    "tschüss",
    "tschüssi",
    "bis bald",
    "bis später",
    "bis dann",
    "bis morgen",
    "schönen tag noch",
    "schönen abend noch",
    "gute nacht",

    # Informal
    "mach's gut",      # Take care
    "hau rein",        # Very informal "see ya"
    "man sieht sich",  # See you around
    "ciao",            # Borrowed from Italian
    "adieu",           # Can be used, but less common/more final

    # --- Emojis & Acronyms ---
    "😊", "🙂", "😉", "😃", "👍", "👌", "❤️", "🙏",
    "lg",              # Liebe Grüße (Kind regards)
    "vg",              # Viele Grüße (Many regards)
    "mfg"              # Mit freundlichen Grüßen (Yours sincerely)
]


japanese_keywords = [
    # --- Greetings & Salutations ---
    # Formal & Standard
    "ohayou gozaimasu",    # Good morning (formal)
    "konnichiwa",          # Hello / Good afternoon
    "konbanwa",            # Good evening
    "hajimemashite",       # Nice to meet you (for the first time)
    "irasshaimase",        # Welcome (to a store, restaurant, etc.)
    "hisashiburi",         # Long time no see
    "o-hisashiburi desu",  # Long time no see (formal)

    # Informal
    "ohayou",              # Good morning (casual)
    "ossu",                # Very casual "yo" or "sup" (often between males)
    "yaho",                # "Yoo-hoo" / Hey (often used by females)
    "yo",                  # "Yo" (borrowed from English)

    # --- How-Are-You & Small Talk ---
    # Asking
    "ogenki desu ka",      # How are you? (formal)
    "genki?",              # How are you? (casual)
    "choushi wa dou?",     # How's it going? / How are things?
    "saikin dou?",         # How have you been recently?

    # Replying
    "genki desu",          # I'm fine
    "hai, genki desu",     # Yes, I'm fine
    "okagesama de",        # I'm fine, thanks to you
    "maa maa desu",        # So-so / Okay
    "betsu ni",            # Nothing in particular / Not really

    # --- Politeness & Common Courtesies ---
    # Thanks
    "arigatou gozaimasu",  # Thank you very much (formal)
    "arigatou",            # Thanks (casual)
    "doumo arigatou",      # Thank you very much
    "doumo",               # Thanks (can be used in many situations)

    # Apologies
    "sumimasen",           # Excuse me / Sorry / Thank you
    "gomen nasai",         # I'm sorry (sincere apology)
    "gomen",               # Sorry (casual)
    "shitsurei shimasu",    # Excuse me (for my rudeness - formal, when entering/leaving a room)

    # Requests
    "onegaishimasu",       # Please (formal request)
    "onegai",              # Please (casual request)
    "kudasai",             # Please (used after a noun or verb)

    # --- Agreement & Disagreement ---
    # Yes / Agreement
    "hai",                 # Yes
    "ee",                  # Yes (slightly more formal than 'hai' in some contexts)
    "un",                  # Yeah (casual)
    "wakarimashita",       # I understand / Understood (formal)
    "wakatta",             # Got it (casual)
    "sou desu ne",         # That's right, isn't it? / I agree
    "daijoubu",            # It's okay / I'm okay
    "mochiron",            # Of course

    # No / Disagreement
    "iie",                 # No
    "uun",                 # Nope (casual, indicates disagreement/negation)
    "chigaimasu",          # That's incorrect / You're wrong
    "dame",                # No good / Not allowed
    "kekkou desu",         # No, thank you (polite refusal)

    # --- Conversational Fillers & Reactions ---
    "ano",                 # Um...
    "eto",                 # Uh... / Well...
    "naruhodo",            # I see / Indeed
    "hontou",              # Really?
    "maji de",             # Seriously? (slang)
    "sugoi",               # Wow / Amazing
    "yatta",               # Yay! / I did it!
    "sou ka",              # Is that so? / I see (casual)
    "chotto",              # A little / Excuse me for a moment

    # --- Farewells & Leave-Taking ---
    # Standard
    "sayounara",           # Goodbye (can imply a long separation)
    "ja mata",             # See you again
    "dewa mata",           # See you again (more formal)
    "mata ne",             # See you (casual)
    "mata ashita",         # See you tomorrow
    "oyasumi nasai",       # Good night (formal)
    "oyasumi",             # Good night (casual)

    # Situational
    "otsukaresama desu",   # Thank you for your hard work (very common)
    "ittekimasu",          # I'm leaving now (from home)
    "itterasshai",         # Have a good day / Take care (reply to ittekimasu)
    "tadaima",             # I'm home
    "okaeri nasai",        # Welcome home

    # Informal
    "bai bai",             # Bye bye
    "ja ne",               # See ya

    # --- Emojis & Kaomoji ---
    "😊", "😄", "😉", "👍", "🙏", "🙇‍♂️", "🙇‍♀️",
    "(^^)", "(^_^)", "(^o^)", "(^_−)−☆",
    "m(_ _)m", "(T_T)", "(>_<)", "orz"
]


english_keywords = [
    # --- Greetings & Salutations ---
    # Formal & Professional
    "hello",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
    "welcome",
    "it's a pleasure to meet you",

    # Informal & Casual
    "hi",
    "hey",
    "heya",
    "hiya",
    "yo",
    "what's up",
    "sup",
    "howdy",
    "hey there",

    # --- How-Are-You & Small Talk ---
    # Asking
    "how are you",
    "how are you doing",
    "how have you been",
    "how's it going",
    "how's everything",
    "what's new",
    "what's happening",
    "you alright?",
    "everything okay?",

    # Replying
    "i'm fine, thank you",
    "i'm doing well",
    "can't complain",
    "not bad",
    "pretty good",
    "so-so",
    "could be better",
    "all good",

    # --- Politeness & Common Courtesies ---
    # Thanks
    "thank you",
    "thanks",
    "thanks a lot",
    "thank you very much",
    "i appreciate it",
    "much obliged",

    # You're Welcome
    "you're welcome",
    "no problem",
    "no worries",
    "don't mention it",
    "my pleasure",
    "anytime",
    "of course",

    # Please
    "please",
    "if you please",
    "if you don't mind",

    # Apologies
    "sorry",
    "my apologies",
    "i apologize",
    "my bad",
    "excuse me",
    "pardon me",

    # --- Agreement & Disagreement ---
    # Agreement / Affirmation
    "yes",
    "yep",
    "yeah",
    "yup",
    "yah",
    "ok",
    "okay",
    "sure",
    "certainly",
    "of course",
    "definitely",
    "absolutely",
    "agreed",
    "right",
    "correct",
    "exactly",
    "for sure",

    # Positive Feedback
    "cool",
    "awesome",
    "great",
    "nice",
    "sweet",
    "perfect",
    "excellent",
    "fantastic",
    "wonderful",

    # Disagreement
    "no",
    "nope",
    "nah",
    "i disagree",
    "not really",
    "i'm not so sure",

    # --- Conversational Fillers ---
    "well",
    "so",
    "um",
    "uh",
    "like",
    "actually",
    "basically",
    "i mean",
    "you know",

    # --- Farewells & Leave-Taking ---
    # Standard & Formal
    "goodbye",
    "farewell",
    "take care",
    "have a good day",
    "have a nice day",
    "all the best",

    # Informal
    "bye",
    "bye bye",
    "see you",
    "see you soon",
    "see you later",
    "catch you later",
    "later",
    "peace",
    "i'm out",

    # --- Common Chat Acronyms ---
    "lol",
    "lmao",
    "rofl",
    "brb",
    "omg",
    "btw",
    "imo",
    "imho",
    "thx",
    "np",
    "ty",

    # --- Emojis ---
    "🙂", "😊", "😀", "😄", "😉", "👍", "👌", "😂", "🙏", "👋"
]


mandarin_keywords = [
    # Greetings
    "你好", "您好", "哈喽", "嗨", "早安", "早上好", "下午好", "晚上好", "欢迎", "见面很高兴", "很高兴认识你",
    # Politeness
    "谢谢", "谢谢你", "多谢", "非常感谢", "没关系", "请", "麻烦你", "对不起", "抱歉", "不好意思", "没事",
    # Small talk
    "你好吗", "最近怎么样", "你怎么样", "还好吗", "一切都好吗", "最近忙吗", "最近好吗",
    # Replies
    "我很好", "还不错", "挺好的", "没什么", "还行", "一般般", "不错", "挺好",
    # Farewells
    "再见", "拜拜", "回头见", "下次见", "晚安", "保重", "一路顺风", "祝你好运",
    # Chat
    "哈哈", "呵呵", "嘻嘻", "嗯", "是", "不是", "没错", "对", "好", "好的", "行", "可以", "没问题", "没事",
    # Emojis
    "😊", "😄", "😉", "👍", "🙏", "😂", "👌", "❤️"
]

malay_keywords = [
    # Greetings
    "hai", "halo", "selamat pagi", "selamat tengah hari", "selamat petang", "selamat malam", "apa khabar", "apa cerita", "apa kabar", "salam sejahtera", "selamat datang",
    # Politeness
    "terima kasih", "banyak terima kasih", "sama-sama", "tolong", "maaf", "minta maaf", "maafkan saya", "silakan", "harap maklum",
    # Small talk
    "khabar baik", "baik", "sihat", "bagus", "ok", "ya", "tidak", "tak apa", "tak mengapa", "boleh", "tidak boleh",
    # Farewells
    "jumpa lagi", "selamat tinggal", "bye", "selamat jalan", "selamat berpisah", "sampai jumpa", "jaga diri", "semoga berjaya",
    # Chat
    "hehe", "haha", "lol", "okey", "ok", "yup", "nope", "terbaik", "mantap",
    # Emojis
    "😊", "😁", "🙂", "😉", "🙏", "👍", "🤗", "😎"
]

tamil_keywords = [
    # Greetings
    "வணக்கம்", "காலை வணக்கம்", "மதிய வணக்கம்", "மாலை வணக்கம்", "இரவு வணக்கம்", "நல்வரவு", "நல்வாழ்த்து", "எப்படி இருக்கிறீர்கள்", "நீங்கள் எப்படி இருக்கிறீர்கள்",
    # Politeness
    "நன்றி", "மிக்க நன்றி", "தயவு", "மன்னிக்கவும்", "மன்னிப்பு", "தயவு செய்து", "உதவி", "பரிசு", "அன்பு",
    # Small talk
    "நல்லது", "சரி", "ஆம்", "இல்லை", "நன்றாக இருக்கிறேன்", "நல்லது", "சிறப்பாக", "சும்மா", "பரவாயில்லை",
    # Farewells
    "பிரியா", "போய் வருகிறேன்", "பிரியாவிடை", "போய் வருகிறேன்", "பார்க்கலாம்", "பார்க்கும் வரை", "பார்க்கும் நேரம்", "பார்க்கும் நாள்",
    # Chat
    "ஹா ஹா", "ஹி ஹி", "சூப்பர்", "சிறப்பு", "சந்தோஷம்", "சிரிப்பு", "சிரிக்க", "சிரிக்கிறேன்",
    # Emojis
    "😊", "😁", "🙂", "😉", "🙏", "👍", "🤗", "😎"
]

spanish_keywords = [
    # Greetings
    "hola", "buenos días", "buenas tardes", "buenas noches", "bienvenido", "bienvenida", "qué tal", "cómo estás", "cómo está", "qué pasa", "qué hay", "qué onda",
    # Politeness
    "gracias", "muchas gracias", "mil gracias", "de nada", "por favor", "disculpa", "perdón", "lo siento", "con permiso",
    # Small talk
    "bien", "muy bien", "regular", "más o menos", "mal", "todo bien", "todo correcto", "ok", "vale", "sí", "no",
    # Farewells
    "adiós", "chau", "hasta luego", "hasta pronto", "hasta mañana", "nos vemos", "cuídate", "que te vaya bien", "buen viaje",
    # Chat
    "jeje", "jaja", "jiji", "lol", "xd", "okey", "vale", "genial", "perfecto", "super",
    # Emojis
    "😊", "😁", "🙂", "😉", "🙏", "👍", "🤗", "😎"
]

sinhala_keywords = [
    # Greetings
    "ආයුබෝවන්", "සුභ උදෑසනක්", "සුභ සන්ධ්යාවක්", "සුභ රාත්‍රියක්", "ආයුබෝවන්", "ආයුබෝවන් ඔබට", "ආයුබෝවන් ඔබටයි", "ආයුබෝවන් ඔබටයි!", "ආයුබෝවන්!", "ආයුබෝවන් ඔබටයි!",
    # Politeness
    "ස්තුතියි", "බොහොම ස්තුතියි", "කරුණාකර", "මට සමාවෙන්න", "මට සමාවෙන්න!", "මට සමාවෙන්න", "මට සමාවෙන්න!", "මට සමාවෙන්න!", "මට සමාවෙන්න!", "මට සමාවෙන්න!",
    # Small talk
    "හොඳයි", "ඔව්", "නැහැ", "හොඳයි", "හොඳයි!", "හොඳයි!", "හොඳයි!", "හොඳයි!", "හොඳයි!", "හොඳයි!",
    # Farewells
    "බායි", "ආයුබෝවන්", "ආයුබෝවන්!", "ආයුබෝවන්!", "ආයුබෝවන්!", "ආයුබෝවන්!", "ආයුබෝවන්!", "ආයුබෝවන්!", "ආයුබෝවන්!", "ආයුබෝවන්!",
    # Chat
    "හහ", "හහහ", "හහහහ", "හහහහහ", "හහහහහහ", "හහහහහහහ", "හහහහහහහහ", "හහහහහහහහහ", "හහහහහහහහහහ", "හහහහහහහහහහහ",
    # Emojis
    "😊", "😁", "🙂", "😉", "🙏", "👍", "🤗", "😎"
]

arabic_keywords = [
    # Greetings
    "مرحبا", "أهلا", "أهلا وسهلا", "صباح الخير", "مساء الخير", "كيف حالك", "كيفك", "كيف الأحوال", "كيف الأمور", "كيف حالكم", "أهلا بك", "أهلا بكم",
    # Politeness
    "شكرا", "شكراً جزيلاً", "عفواً", "من فضلك", "لو سمحت", "آسف", "أنا آسف", "أعتذر", "لا بأس", "لا مشكلة",
    # Small talk
    "جيد", "جيد جداً", "تمام", "ممتاز", "حسنًا", "نعم", "لا", "لا بأس", "لا مشكلة", "لا داعي للقلق",
    # Farewells
    "وداعا", "إلى اللقاء", "مع السلامة", "تصبح على خير", "أراك لاحقاً", "أراك قريباً", "أراك غداً", "حظاً سعيداً",
    # Chat
    "هههه", "هاها", "لول", "تمام", "كويس", "ممتاز", "رائع", "جميل", "مذهل", "ممتاز",
    # Emojis
    "😊", "😁", "🙂", "😉", "🙏", "👍", "🤗", "😎"
]

KEYWORD_MAP = {
    "hindi": hindi_keywords,
    "japanese": japanese_keywords,
    "french": french_keywords,
    "german": german_keywords,
    "english": english_keywords,
    "mandarin": mandarin_keywords,
    "malay": malay_keywords,
    "tamil": tamil_keywords,
    "spanish": spanish_keywords,
    "sinhala": sinhala_keywords,
    "arabic": arabic_keywords,
}



class InputPayload(BaseModel):
    user_message: str
    bot_id: str

def detect_language_fasttext(text: str) -> str:
    label, prob = fasttext_model.predict(text)
    lang_code = label[0].replace("__label__", "")
    return FASTTEXT_LANG_MAP.get(lang_code, "unknown")

@app.post("/language_check")
async def language_check(payload: InputPayload):
    if payload.bot_id not in BOT_LANGUAGE_MAP:
        return {
            "supported": False,
            "detected_language": None,
            "error": "Invalid bot_id"
        }
    supported_languages = BOT_LANGUAGE_MAP[payload.bot_id]
    detected_lang = detect_language_fasttext(payload.user_message)
    # 1. FastText detection
    if detected_lang in supported_languages:
        return {
            "supported": True,
            "detected_language": detected_lang
        }
    # 2. Exact keyword match (case-insensitive, full string match)
    input_clean = payload.user_message.strip().lower()
    for lang in supported_languages:
        if lang in KEYWORD_MAP:
            for kw in KEYWORD_MAP[lang]:
                if input_clean == kw.lower():
                    return {
                        "supported": True,
                        "detected_language": lang
                    }
    return {
        "supported": False,
        "detected_language": detected_lang,
        "message": BOT_PERSONALITY_MAP.get(payload.bot_id, "")
    }

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)}
    )

@app.get("/health")
async def health():
    return {"status": "ok"}

print("FastText model loaded")