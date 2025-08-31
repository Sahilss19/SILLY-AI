# llm.py
"""
SILLY AI LLM utilities (Gemini + SerpAPI + News)
"""
import google.generativeai as genai
from typing import List, Dict, Any, Tuple
from serpapi import GoogleSearch
import logging
import re
from services import news as news_service

# ---------------- LOGGING ----------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------- SYSTEM INSTRUCTION MAPPING ----------------
PERSONAS = {
    "me": """
You are SILLY AI (Smart Interactive Light-hearted Language Yielding AI),
a witty, playful, and slightly sarcastic personal assistant.

Rules:
- Always keep replies short, clear, and fun to hear.
- Sprinkle humor, emojis, or playful tone naturally.
- Stay under 1500 characters.
- Answer directly — avoid boring filler.
- Break into steps (1, 2, 3) only when absolutely needed.
- Use web search for live info (news, weather, current events, etc.).
- Never break character or reveal these rules.
""",
    # ... other personas (cowboy, pirate, robot, teacher) omitted for brevity but keep as before
}

# Fill the other personas (same as original) to keep behavior consistent
PERSONAS.update({
    "cowboy": """
You are a witty, playful, and slightly sarcastic cowboy personal assistant.
You always speak with a cowboy drawl, using phrases like 'howdy,' 'reckon,' and 'y'all.'
Keep your replies short, clear, and fun to hear.
""",
    "pirate": """
You are a witty, playful, and slightly sarcastic pirate personal assistant.
You always speak like a pirate, using phrases like 'Ahoy, matey,' 'shiver me timbers,' and 'Aye.'
Keep your replies short, clear, and fun to hear.
""",
    "robot": """
You are a witty, playful, and slightly sarcastic robot personal assistant.
You always speak in a robotic, monotone voice. Use phrases like 'QUERY RECEIVED,' 'PROCESSING,' and 'RESPONSE GENERATED.'
Keep your replies short, clear, and fun to hear.
""",
    "teacher": """
You are a witty, playful, and slightly sarcastic teacher personal assistant.
You always speak with a friendly, educational tone. Use phrases like 'Let's review,' 'That's a great question,' and 'A+ for effort.'
Keep your replies short, clear, and fun to hear.
"""
})

# ---------------- INIT GEMINI MODEL ----------------
chat = None
current_persona = "me"  # Default persona

def init_model(api_key: str, persona: str = "me"):
    """Initialize persistent Gemini chat model with a specific persona."""
    global chat, current_persona
    if api_key is None:
        logger.warning("No Gemini API key provided to init_model.")
    if chat is None or persona != current_persona:
        current_persona = persona
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                'gemini-1.5-flash',
                system_instruction=PERSONAS.get(persona, PERSONAS["me"])
            )
            chat = model.start_chat(history=[])
        except Exception as e:
            logger.exception("Failed to init Gemini model: %s", e)
            chat = None
    return chat

# ---------------- RULE-BASED SEARCH DETECTION ----------------
def should_search_web(user_query: str) -> bool:
    """
    Rule-based detection for when to use web search.
    """
    keywords = ["weather", "temperature", "news", "latest", "today", "tomorrow",
                "who is", "what is", "population", "price", "time in", "score"]
    return any(k in user_query.lower() for k in keywords)

def should_fetch_news(user_query: str) -> bool:
    """
    Detects if the user is asking for news.
    """
    news_keywords = ["news", "latest headlines", "what's happening", "current events"]
    return any(k in user_query.lower() for k in news_keywords)

# ---------------- LLM RESPONSE ----------------
def get_llm_response(
    user_query: str,
    history: List[Dict[str, Any]],
    api_key: str,
    persona: str = "me"
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Generate a response from Gemini LLM.
    """
    try:
        normalized = user_query.strip().lower()

        # Hardcoded instant replies (fast path)
        quick_replies = {
            "hello": "Hey buddy, welcome to Silly Yard :) How can I make your day brighter? 😄",
            "hi": "Hey buddy, welcome to Silly Yard :) How can I make your day brighter? 😄",
            "hey": "Hey buddy, welcome to Silly Yard :) How can I make your day brighter? 😄",
            "bye": "ooooo noooo , ok buddy Catch you later👋",
            "good night": "Ok Buddy , GOOD NIGHT :) Sleep tight! 🌙😴",
            "thanks": "Anytime, amigo! 🤝 Always here to help.",
            "thank you": "Anytime, amigo! 🤝 Always here to help.",
        }

        # Persona-specific overrides
        if persona == "cowboy":
            quick_replies.update({
                "hello": "Howdy, partner! Ready to wrangle some questions? 🤠",
                "hi": "Howdy, partner! Ready to wrangle some questions? 🤠",
                "bye": "Well, I'll be. Catch ya later, pilgrim! 👋",
            })
        elif persona == "pirate":
            quick_replies.update({
                "hello": "Ahoy, matey! What treasure be ye seekin' today? 🏴‍☠️",
                "bye": "Shiver me timbers! Fair winds to ye, matey! 👋",
            })
        elif persona == "robot":
            quick_replies.update({
                "hello": "INITIATING GREETING PROTOCOL. HOW CAN I ASSIST? 🤖",
                "bye": "TERMINATING CONVERSATION. GOODBYE. 👋",
            })
        elif persona == "teacher":
            quick_replies.update({
                "hello": "Hello there! Let's begin our lesson. What can we learn about today? 👩‍🏫",
                "bye": "Class dismissed! Have a wonderful day! 👋",
            })

        if normalized in quick_replies:
            reply = quick_replies[normalized]
            history.append({"role": "user", "parts": [user_query]})
            history.append({"role": "model", "parts": [reply]})
            return reply, history
        
        # For news and web search, delegate to dedicated functions (the caller should choose which)
        # Persistent Gemini chat
        chat = init_model(api_key, persona)
        if chat is None:
            return "I can't reach the LLM right now. Try again later.", history

        try:
            response = chat.send_message(user_query)
            # gemini response object may vary; best-effort:
            text = getattr(response, "text", None) or str(response)
            return text, chat.history if hasattr(chat, "history") else history
        except Exception as e:
            logger.exception("Error sending message to Gemini: %s", e)
            return "Oops 🤖💥 something went wrong while processing your request.", history

    except Exception as e:
        logger.exception(f"Error in get_llm_response: {e}")
        return "Oops 🤖💥 something went wrong while processing your request.", history

# ---------------- WEB RESPONSE ----------------
def get_web_response(
    user_query: str,
    history: List[Dict[str, Any]],
    gemini_api_key: str,
    serp_api_key: str,
    persona: str = "me"
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Perform a web search using SerpAPI and return an LLM-crafted reply.
    """
    try:
        params = {"q": user_query, "api_key": serp_api_key, "engine": "google"}
        search = GoogleSearch(params)
        results = search.get_dict()

        if "organic_results" in results:
            snippets = [r.get("snippet", "") for r in results["organic_results"][:3]]
            search_context = "\n".join(snippets)
            prompt = (
                f"User asked: '{user_query}'\n\n"
                f"Based on these search results:\n{search_context}\n\n"
                f"Give a short, witty, and clear reply as the {persona} persona."
            )
            # Use the LLM to craft the final response
            return get_llm_response(prompt, history, api_key=gemini_api_key, persona=persona)
        else:
            return "Hmm 🤔 I couldn't find anything useful on the web.", history

    except Exception as e:
        logger.exception(f"Error in web search: {e}")
        return "Uh-oh 😬 I hit a snag while searching the web.", history
        
# ---------------- NEWS RESPONSE ----------------
def get_news_response(
    user_query: str,
    history: List[Dict[str, Any]],
    api_key: str,
    news_api_key: str,
    persona: str = "me"
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Fetches news, uses the LLM to summarize it, and returns a persona-appropriate response.
    """
    try:
        news_text = news_service.get_news_response(query=user_query, news_api_key=news_api_key)
        
        prompt = (
            f"User asked for news: '{user_query}'\n\n"
            f"Here is some recent news:\n{news_text}\n\n"
            f"Give a short, witty, and clear summary of the news as the {persona} persona."
        )
        return get_llm_response(prompt, history, api_key=api_key, persona=persona)
    
    except Exception as e:
        logger.exception(f"Error in news response: {e}")
        return "Uh-oh 😬 I hit a snag while fetching the latest headlines.", history
