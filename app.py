# app.py
from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging
import asyncio
import base64
import re
import json

# Import services and config
from services import stt, llm, tts
from config import ASSEMBLYAI_API_KEY, GEMINI_API_KEY, MURF_API_KEY, SERPAPI_API_KEY, NEWSAPI_API_KEY

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()

# Mount static files for CSS/JS
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home(request: Request):
    """Serves the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handles WebSocket connection for real-time transcription and voice response."""
    await websocket.accept()
    logging.info("WebSocket client connected.")

    loop = asyncio.get_event_loop()
    chat_history = []

    # Default to server-side keys if client does not provide them.
    api_keys = {
        "murf": MURF_API_KEY,
        "assemblyai": ASSEMBLYAI_API_KEY,
        "gemini": GEMINI_API_KEY,
        "serpapi": SERPAPI_API_KEY,
        "newsapi": NEWSAPI_API_KEY,
    }
    
    session_persona = "me"  # default persona
    
    async def handle_transcript(text: str):
        await websocket.send_json({"type": "final", "text": text})
        try:
            full_response, updated_history = "", chat_history
            
            if llm.should_fetch_news(text):
                full_response, updated_history = llm.get_news_response(
                    text, chat_history, api_key=api_keys.get("gemini"), news_api_key=api_keys.get("newsapi"), persona=session_persona
                )
            elif llm.should_search_web(text):
                full_response, updated_history = llm.get_web_response(
                    text, chat_history, gemini_api_key=api_keys.get("gemini"), serp_api_key=api_keys.get("serpapi"), persona=session_persona
                )
            else:
                full_response, updated_history = llm.get_llm_response(
                    text, chat_history, api_key=api_keys.get("gemini"), persona=session_persona
                )
            
            chat_history.clear()
            chat_history.extend(updated_history if updated_history else [])

            await websocket.send_json({"type": "assistant", "text": full_response})

            sentences = re.split(r'(?<=[.?!])\s+', full_response.strip())
            
            for sentence in sentences:
                if sentence.strip():
                    audio_bytes = await loop.run_in_executor(
                        None, tts.speak, sentence.strip(), api_keys.get("murf")
                    )
                    if audio_bytes:
                        b64_audio = base64.b64encode(audio_bytes).decode('utf-8')
                        await websocket.send_json({"type": "audio", "b64": b64_audio})

        except Exception as e:
            logging.exception(f"Error in LLM/TTS pipeline: {e}")
            await websocket.send_json({"type": "llm_error", "text": "Sorry, I hit a snag while processing your request."})

    def on_final_transcript(text: str):
        logging.info(f"Final transcript received: {text}")
        asyncio.run_coroutine_threadsafe(handle_transcript(text), loop)

    try:
        initial = await websocket.receive_text()
        try:
            config = json.loads(initial)
        except Exception:
            config = {}

        if isinstance(config, dict) and config.get("type") == "config":
            client_keys = config.get("keys", {})
            for k, v in client_keys.items():
                if v:
                    api_keys[k] = v
            session_persona = config.get("persona", session_persona)
            try:
                llm.init_model(api_keys.get("gemini"), session_persona)
            except Exception as e:
                logging.warning("Failed to init LLM model: %s", e)

        transcriber = stt.AssemblyAIStreamingTranscriber(
            on_final_callback=on_final_transcript, 
            api_key=api_keys.get("assemblyai")
        )

        while True:
            data = await websocket.receive_bytes()
            transcriber.stream_audio(data)
    except Exception as e:
        logging.info(f"WebSocket closed or error: {e}")
    finally:
        if 'transcriber' in locals() and transcriber:
            try:
                transcriber.close()
            except Exception:
                pass
        logging.info("Transcription resources released.")
