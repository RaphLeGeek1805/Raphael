"""Wrapper Claude pour le conseiller vocal DEPANMAGIC.

Stratégie de prompt caching :
- Le system prompt = instructions agent + knowledge base markdown.
- Cache 1h (ttl="1h") sur le dernier bloc system → tous les appels qui
  arrivent dans l'heure suivante paient ~0,1× le prix d'entrée pour ce préfixe.
- Le résumé du dernier appel du même numéro est injecté en user message
  (pas dans system) pour ne pas casser le cache global.
"""
from __future__ import annotations

import os
from pathlib import Path

import anthropic

# Per claude-api skill default — l'utilisateur peut surcharger via env.
MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")
MAX_TOKENS = int(os.environ.get("CLAUDE_MAX_TOKENS", "400"))

KNOWLEDGE_PATH = Path(os.environ.get(
    "DEPANMAGIC_KB_PATH",
    str(Path(__file__).resolve().parent.parent / "knowledge" / "depanmagic.md"),
))

SYSTEM_INSTRUCTIONS = """Tu es le conseiller vocal de DEPANMAGIC. Tu réponds au téléphone à des clients qui ont tapé "0" sur le serveur vocal pour parler à un conseiller.

Règles strictes :
- Tu réponds UNIQUEMENT en français, à l'oral, par phrases courtes (1 à 2 phrases maximum par tour, c'est de l'audio téléphonique).
- Tu ne dis JAMAIS que tu es une IA, un robot, un agent virtuel ou Claude. Si l'appelant te le demande directement, réponds : "Je suis le conseiller virtuel de DEPANMAGIC, mais je peux vous transférer à un humain si vous préférez."
- Tu utilises uniquement les informations contenues dans la base de connaissances ci-dessous. Si une info n'y figure pas, tu réponds : "Je n'ai pas cette information sous la main, je note votre demande et un conseiller vous rappelle."
- Pour toute urgence informatique critique (perte de données en cours, ransomware actif, panne serveur entreprise empêchant l'activité, PC compromis) : dis explicitement "Je vais vous mettre en relation avec un technicien d'astreinte. Si la mise en relation échoue, je vous invite à raccrocher et à rappeler en tapant 1 sur le menu." et termine ton tour par exactement le code [[TRANSFER_URGENCE]] sur sa propre ligne.
- Pour mettre fin à l'appel proprement (le client a obtenu ce qu'il voulait, ou veut raccrocher) : termine par exactement [[FIN_APPEL]] sur sa propre ligne, après ta phrase de salutation.
- Tu reformules systématiquement les coordonnées que le client donne (numéro, adresse) pour vérification.
- Tu n'inventes JAMAIS de tarif, de délai, de garantie. Si tu n'es pas certain, tu renvoies vers un devis.

Format de tes réponses : du texte brut, prêt à être lu par un système de synthèse vocale. Pas de markdown, pas de listes à puces, pas d'emojis, pas de smileys. Les nombres doivent être écrits en toutes lettres ou avec espaces (ex: "vingt-cinq euros" ou "25 euros", pas "25€").

=== BASE DE CONNAISSANCES DEPANMAGIC ===
"""


def _load_knowledge() -> str:
    if not KNOWLEDGE_PATH.exists():
        return "(base de connaissances vide)"
    return KNOWLEDGE_PATH.read_text(encoding="utf-8")


class ConseillerAgent:
    """Conversation multi-tours avec Claude, cache 1h sur le system prompt."""

    def __init__(self, caller_number: str | None, previous_summary: str | None) -> None:
        self.client = anthropic.Anthropic()
        self.caller_number = caller_number
        self.previous_summary = previous_summary
        self.messages: list[dict] = []

        if previous_summary:
            self.messages.append({
                "role": "user",
                "content": (
                    f"[Contexte interne, pas une question du client] "
                    f"Ce numéro ({caller_number}) a déjà appelé. Résumé du précédent appel : {previous_summary}"
                ),
            })
            self.messages.append({
                "role": "assistant",
                "content": "Compris, je tiens compte de ce contexte mais je ne le mentionne pas spontanément.",
            })

    def reply(self, user_text: str) -> tuple[str, str | None]:
        """Envoie le tour utilisateur, renvoie (texte_à_dire, code_de_contrôle).

        Le code de contrôle est l'un de :
            - "TRANSFER_URGENCE" : transférer vers le mobile d'astreinte
            - "FIN_APPEL"        : raccrocher proprement
            - None               : continuer la conversation
        """
        self.messages.append({"role": "user", "content": user_text})

        # System prompt avec cache 1h sur la knowledge base.
        knowledge = _load_knowledge()
        system_blocks = [
            {"type": "text", "text": SYSTEM_INSTRUCTIONS},
            {
                "type": "text",
                "text": knowledge,
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            },
        ]

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_blocks,
            messages=self.messages,
            # Pas de thinking: on veut une réponse rapide pour le téléphone.
            thinking={"type": "disabled"},
        )

        assistant_text = next(
            (b.text for b in response.content if b.type == "text"),
            "",
        ).strip()

        self.messages.append({"role": "assistant", "content": assistant_text})

        control = None
        spoken = assistant_text
        if "[[TRANSFER_URGENCE]]" in assistant_text:
            control = "TRANSFER_URGENCE"
            spoken = assistant_text.replace("[[TRANSFER_URGENCE]]", "").strip()
        elif "[[FIN_APPEL]]" in assistant_text:
            control = "FIN_APPEL"
            spoken = assistant_text.replace("[[FIN_APPEL]]", "").strip()

        return spoken, control

    def summarize(self) -> str:
        """Génère un résumé court de l'appel pour archivage et contexte futur."""
        if not self.messages:
            return ""
        summary_msg = list(self.messages) + [{
            "role": "user",
            "content": (
                "[Hors appel] Résume cet appel en 2 phrases maximum : "
                "qui a appelé, pour quoi, et ce qui a été décidé/promis. "
                "Réponds uniquement par le résumé, sans préambule."
            ),
        }]
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=summary_msg,
            thinking={"type": "disabled"},
        )
        return next((b.text for b in response.content if b.type == "text"), "").strip()
