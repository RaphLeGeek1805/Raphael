#!/usr/bin/env python3
"""AGI Asterisk : conseiller vocal IA DEPANMAGIC.

Invoqué depuis le dialplan sur la touche 0 :
    exten => 0,1,AGI(ai_conseiller.py)

Boucle : RECORD utterance → STT → Claude → TTS → STREAM FILE → loop.
La conversation se termine quand Claude renvoie [[FIN_APPEL]] ou
[[TRANSFER_URGENCE]], ou que le client raccroche / reste muet.
"""
from __future__ import annotations

import logging
import sys
import time
import uuid
from pathlib import Path

# Permet d'importer les modules frères quand AGI lance le script en standalone.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from asterisk.agi import AGI  # type: ignore

import db
import stt
import tts
from claude_agent import ConseillerAgent

LOG = logging.getLogger("ai_conseiller")
logging.basicConfig(
    filename="/var/log/asterisk/ai_conseiller.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

WORKDIR = Path("/var/spool/asterisk/ai-agent")
WORKDIR.mkdir(parents=True, exist_ok=True)

# Paramètres de la boucle
MAX_TURNS = 12              # garde-fou anti-boucle infinie
RECORD_MAX_SEC = 15         # durée max d'un tour utilisateur
RECORD_SILENCE = 2          # arrêt après 2s de silence
NO_INPUT_RETRIES = 2        # tolérance avant de raccrocher si silence


def _record_user(agi: AGI, basename: str) -> Path:
    """Enregistre la voix du client jusqu'à silence ou MAX_SEC. Retourne le WAV."""
    target = WORKDIR / f"{basename}-user"
    agi.record_file(
        str(target),
        format="wav",
        escape_digits="#",
        timeout=RECORD_MAX_SEC * 1000,
        offset=0,
        beep="",
        silence=RECORD_SILENCE,
    )
    return target.with_suffix(".wav")


def _say(agi: AGI, text: str, basename: str, turn: int) -> None:
    """TTS la réponse et la joue à l'appelant."""
    out = WORKDIR / f"{basename}-bot-{turn:02d}.wav"
    tts.synthesize(text, out)
    # stream_file attend le chemin SANS extension
    agi.stream_file(str(out.with_suffix("")))


def main() -> None:
    agi = AGI()
    env = agi.env
    asterisk_uid = env.get("agi_uniqueid", str(uuid.uuid4()))
    caller = env.get("agi_callerid") or env.get("agi_calleridname")
    LOG.info("appel entrant uid=%s caller=%s", asterisk_uid, caller)

    basename = asterisk_uid.replace(".", "-")
    call_id = db.open_call(asterisk_uid, caller)
    previous = db.previous_call_summary(caller) if caller else None
    if previous:
        LOG.info("contexte précédent injecté pour %s : %s", caller, previous)

    agent = ConseillerAgent(caller_number=caller, previous_summary=previous)
    outcome = "hangup"
    handoff = None
    silent_streak = 0

    # Première phrase déclenchée côté agent (sans tour utilisateur)
    opening, _ = agent.reply("[Le client vient d'appuyer sur 0 pour parler à un conseiller. Salue-le brièvement et demande-lui en quoi tu peux l'aider.]")
    _say(agi, opening, basename, 0)
    db.append_turn(call_id, 0, "assistant", opening)

    try:
        for turn in range(1, MAX_TURNS + 1):
            t0 = time.monotonic()
            wav = _record_user(agi, f"{basename}-{turn:02d}")
            if not wav.exists() or wav.stat().st_size < 1024:
                silent_streak += 1
                if silent_streak >= NO_INPUT_RETRIES:
                    LOG.info("silence persistant, raccroche")
                    _say(agi, "Je ne vous entends pas, je raccroche. À très bientôt.", basename, turn)
                    outcome = "hangup_silence"
                    break
                _say(agi, "Vous êtes toujours là ?", basename, turn)
                continue

            silent_streak = 0
            text, confidence = stt.transcribe(wav)
            wav.unlink(missing_ok=True)
            LOG.info("tour %d user (conf=%.2f): %s", turn, confidence, text)

            if not text:
                _say(agi, "Pardon, je n'ai pas saisi. Pouvez-vous répéter ?", basename, turn)
                continue

            db.append_turn(call_id, turn * 2 - 1, "user", text, stt_confidence=confidence)

            spoken, control = agent.reply(text)
            latency = int((time.monotonic() - t0) * 1000)
            db.append_turn(call_id, turn * 2, "assistant", spoken, latency_ms=latency)
            LOG.info("tour %d bot (latence=%dms ctrl=%s): %s", turn, latency, control, spoken)

            if spoken:
                _say(agi, spoken, basename, turn)

            if control == "TRANSFER_URGENCE":
                outcome = "urgence_transfer"
                handoff = "astreinte"
                # Le dialplan reprend la main et redirige (cf. extensions.conf)
                agi.set_variable("AI_HANDOFF", "URGENCE")
                break
            if control == "FIN_APPEL":
                outcome = "info"
                break
        else:
            LOG.info("MAX_TURNS atteint, fin de l'appel")
            _say(agi, "Pour aller plus loin, un conseiller va vous rappeler. Bonne journée.", basename, MAX_TURNS)
            outcome = "info"

        summary = ""
        try:
            summary = agent.summarize()
        except Exception as exc:  # noqa: BLE001
            LOG.warning("résumé impossible : %s", exc)
        db.close_call(call_id, outcome=outcome, summary=summary, handoff_to=handoff)
        LOG.info("appel uid=%s clos outcome=%s handoff=%s", asterisk_uid, outcome, handoff)

    except Exception as exc:  # noqa: BLE001
        LOG.exception("erreur AGI : %s", exc)
        try:
            _say(agi, "Désolé, un problème technique est survenu. Un conseiller va vous rappeler.", basename, 99)
        except Exception:  # noqa: BLE001
            pass
        db.close_call(call_id, outcome="error", summary=f"erreur: {exc}", handoff_to=None)


if __name__ == "__main__":
    main()
