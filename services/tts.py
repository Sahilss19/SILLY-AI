# services/tts.py
import requests
from typing import List, Dict, Any
from murf import Murf
from pathlib import Path
import logging
import os

logger = logging.getLogger(__name__)

MURF_API_URL = "https://api.murf.ai/v1/speech"

# Ensure uploads folder exists (two levels up -> project root / uploads)
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

def speak(text: str, api_key: str, output_file: str = "stream_output.wav", voice_id: str = "en-IN-priya"):
    """
    Convert text to speech using Murf API and save audio in uploads folder.
    Returns bytes of the generated audio or None on failure.
    """
    if not api_key:
        logger.error("Murf API key is missing.")
        return None

    try:
        client = Murf(api_key=api_key)
    except Exception as e:
        logger.exception("Failed to create Murf client: %s", e)
        return None

    file_path = UPLOADS_DIR / output_file

    # Start with a clean file
    try:
        open(file_path, "wb").close()
    except Exception:
        pass

    try:
        res = client.text_to_speech.stream(
            text=text,
            voice_id=voice_id,
            style="Conversational"
        )
    except Exception as e:
        logger.exception("Murf text_to_speech error: %s", e)
        return None

    audio_bytes = b""
    try:
        for audio_chunk in res:
            audio_bytes += audio_chunk
            with open(file_path, "ab") as f:
                f.write(audio_chunk)
    except Exception as e:
        logger.exception("Error while reading streaming audio chunks: %s", e)
        return None

    return audio_bytes
