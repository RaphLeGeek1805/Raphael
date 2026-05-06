"""TTS français : ElevenLabs (par défaut, voix naturelle) ou gTTS (gratuit)."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import httpx

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "ThT5KcBeYPX3keUQqHPh")  # voix fr par défaut
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")


def _ffmpeg_to_8k_wav(src: Path, dst: Path) -> None:
    """Convertit en WAV 8 kHz mono PCM 16 bits, format attendu par Asterisk."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(src),
            "-ar", "8000", "-ac", "1", "-acodec", "pcm_s16le",
            str(dst),
        ],
        check=True,
        capture_output=True,
    )


def synthesize(text: str, out_wav: Path) -> None:
    """Génère un WAV 8 kHz mono prêt pour Playback() Asterisk."""
    if not text.strip():
        return

    if ELEVENLABS_API_KEY:
        _eleven(text, out_wav)
    else:
        _gtts(text, out_wav)


def _eleven(text: str, out_wav: Path) -> None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    with httpx.Client(timeout=20.0) as client:
        r = client.post(url, headers=headers, json=payload)
    r.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(r.content)
        mp3 = Path(tmp.name)
    try:
        _ffmpeg_to_8k_wav(mp3, out_wav)
    finally:
        mp3.unlink(missing_ok=True)


def _gtts(text: str, out_wav: Path) -> None:
    from gtts import gTTS
    tts = gTTS(text=text, lang="fr", tld="fr", slow=False)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        mp3 = Path(tmp.name)
    try:
        tts.save(str(mp3))
        _ffmpeg_to_8k_wav(mp3, out_wav)
    finally:
        mp3.unlink(missing_ok=True)
