"""STT français : Deepgram (par défaut) ou Whisper local en fallback."""
from __future__ import annotations

import os
from pathlib import Path

import httpx

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
DEEPGRAM_MODEL = os.environ.get("DEEPGRAM_MODEL", "nova-2")
DEEPGRAM_URL = (
    "https://api.deepgram.com/v1/listen"
    f"?model={DEEPGRAM_MODEL}&language=fr&smart_format=true&punctuate=true"
)


def transcribe(wav_path: Path) -> tuple[str, float]:
    """Transcrit un WAV (8 kHz mono) en français.

    Retourne (texte, confiance_0_à_1). Vide si rien n'est détecté.
    """
    if not DEEPGRAM_API_KEY:
        raise RuntimeError(
            "DEEPGRAM_API_KEY n'est pas défini. Renseignez-le dans .env "
            "ou implémentez un fallback Whisper local."
        )

    audio_bytes = wav_path.read_bytes()
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/wav",
    }
    with httpx.Client(timeout=15.0) as client:
        r = client.post(DEEPGRAM_URL, headers=headers, content=audio_bytes)
    r.raise_for_status()
    data = r.json()
    try:
        alt = data["results"]["channels"][0]["alternatives"][0]
        return (alt.get("transcript", "").strip(), float(alt.get("confidence", 0.0)))
    except (KeyError, IndexError):
        return ("", 0.0)
