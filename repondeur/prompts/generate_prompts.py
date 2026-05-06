#!/usr/bin/env python3
"""
Génère les annonces vocales françaises pour le répondeur DEPANMAGIC.

Lit prompts/scripts.txt (format `id|texte`) et produit pour chaque ligne un fichier
WAV 8 kHz / mono / PCM 16 bits dans sounds/custom/, format attendu par Asterisk.

Deux moteurs TTS supportés :
  - gTTS (par défaut, gratuit, nécessite une connexion internet)
  - piper (offline, voix de meilleure qualité, à installer séparément)

Utilisation :
    pip install gTTS pydub
    apt install ffmpeg
    python prompts/generate_prompts.py
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_FILE = ROOT / "prompts" / "scripts.txt"
OUTPUT_DIR = ROOT / "sounds" / "custom"


def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg est requis : `apt install ffmpeg` ou `brew install ffmpeg`.")


def parse_scripts() -> list[tuple[str, str]]:
    if not SCRIPTS_FILE.exists():
        sys.exit(f"Fichier introuvable : {SCRIPTS_FILE}")
    items: list[tuple[str, str]] = []
    for raw in SCRIPTS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            print(f"Ligne ignorée (séparateur manquant) : {line}", file=sys.stderr)
            continue
        prompt_id, text = line.split("|", 1)
        items.append((prompt_id.strip(), text.strip()))
    return items


def synthesize_gtts(text: str, mp3_path: Path) -> None:
    from gtts import gTTS

    tts = gTTS(text=text, lang="fr", tld="fr", slow=False)
    tts.save(str(mp3_path))


def synthesize_piper(text: str, wav_path: Path, model: str) -> None:
    proc = subprocess.run(
        ["piper", "--model", model, "--output_file", str(wav_path)],
        input=text.encode("utf-8"),
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        sys.exit(f"piper a échoué : {proc.stderr.decode(errors='replace')}")


def to_asterisk_wav(src: Path, dst: Path) -> None:
    """Convertit en WAV 8 kHz mono PCM 16 bits (format SLN8 compatible Asterisk)."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", str(src),
            "-ar", "8000",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            str(dst),
        ],
        check=True,
        capture_output=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère les annonces vocales DEPANMAGIC.")
    parser.add_argument("--engine", choices=["gtts", "piper"], default="gtts")
    parser.add_argument("--piper-model", default="fr_FR-siwis-medium.onnx",
                        help="Chemin vers le modèle Piper (.onnx)")
    args = parser.parse_args()

    ensure_ffmpeg()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    items = parse_scripts()
    if not items:
        sys.exit("Aucun script à générer.")

    tmp_dir = OUTPUT_DIR / ".tmp"
    tmp_dir.mkdir(exist_ok=True)

    for prompt_id, text in items:
        print(f"[+] {prompt_id} : {text[:60]}{'...' if len(text) > 60 else ''}")
        if args.engine == "gtts":
            tmp_audio = tmp_dir / f"{prompt_id}.mp3"
            synthesize_gtts(text, tmp_audio)
        else:
            tmp_audio = tmp_dir / f"{prompt_id}.wav"
            synthesize_piper(text, tmp_audio, args.piper_model)

        target = OUTPUT_DIR / f"{prompt_id}.wav"
        to_asterisk_wav(tmp_audio, target)
        tmp_audio.unlink(missing_ok=True)

    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"\n{len(items)} annonces générées dans {OUTPUT_DIR}")
    print("Copiez ce dossier dans /var/lib/asterisk/sounds/custom/ du conteneur "
          "(le docker-compose le monte automatiquement).")


if __name__ == "__main__":
    main()
