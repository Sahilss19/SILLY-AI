# config.py
import os
from dotenv import load_dotenv
import logging
import google.generativeai as genai
import assemblyai as aai

load_dotenv()

MURF_API_KEY = os.getenv("MURF_API_KEY")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY")

if ASSEMBLYAI_API_KEY:
    try:
        aai.settings.api_key = ASSEMBLYAI_API_KEY
    except Exception:
        logging.warning("Could not configure AssemblyAI")
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception:
        logging.warning("Could not configure Gemini")
