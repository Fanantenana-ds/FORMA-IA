"""Transcription audio française via Groq, sans stockage local de l'audio."""
import os

import httpx
from fastapi import HTTPException

from app.config.settings import settings

MAX_AUDIO_BYTES = 8 * 1024 * 1024
FORMATS = {"audio/webm": "webm", "video/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/wav": "wav", "audio/mpeg": "mp3"}


async def transcribe_audio(audio: bytes, content_type: str) -> str:
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime not in FORMATS:
        raise HTTPException(415, "Format audio non pris en charge. Utilisez WebM, Ogg, MP4, WAV ou MP3.")
    if not audio:
        raise HTTPException(400, "Enregistrement vide. Réessayez avec le microphone actif.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Enregistrement trop volumineux (maximum 8 Mo).")
    key = os.getenv("GROQ_API_KEY") or settings.GROQ_API_KEY
    if not key:
        raise HTTPException(503, "Transcription Groq non configurée. Utilisez la dictée navigateur ou le clavier.")
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                data={"model": os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo"), "language": "fr", "response_format": "json", "temperature": "0"},
                files={"file": (f"dictee.{FORMATS[mime]}", audio, mime)},
            )
        if response.status_code == 429:
            raise HTTPException(429, "Quota audio Groq atteint. Réessayez plus tard ou utilisez le clavier.")
        if response.status_code in {400, 413, 415, 422}:
            raise HTTPException(422, "Audio non exploitable. Enregistrez une nouvelle phrase courte.")
        if not response.is_success:
            raise HTTPException(502, "Le service de transcription est indisponible.")
        text = str(response.json().get("text") or "").strip()
        if not text:
            raise HTTPException(422, "Aucune parole reconnue. Vérifiez le micro et réessayez.")
        return text
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "La transcription n'a pas abouti. Vérifiez la connexion ou utilisez le clavier.") from exc
