# Répondeur vocal DEPANMAGIC (Asterisk + trunk SIP OVH + agent IA Claude)

IVR hybride pour DEPANMAGIC raccordé à un trunk SIP OVH :
- Touches 1-4 du menu : routage classique (urgence, devis, suivi, infos).
- Touche 0 : **agent vocal IA** (Claude Opus 4.7) qui dialogue en français avec
  l'appelant, connaît la knowledge base DEPANMAGIC, mémorise les appels précédents
  d'un même numéro et peut transférer vers l'astreinte sur détection d'urgence.

## Arborescence

```
repondeur/
├── asterisk/              # Templates de configuration Asterisk
│   ├── pjsip.conf         # Trunk OVH + extensions internes
│   ├── extensions.conf    # Dialplan / IVR (option 0 → AGI Claude)
│   ├── voicemail.conf, asterisk.conf, modules.conf, rtp.conf, logger.conf, manager.conf
├── prompts/               # Textes + script TTS pour les annonces fixes
│   ├── scripts.txt
│   └── generate_prompts.py
├── sounds/custom/         # WAV générés (ignoré par git)
├── ai-agent/              # Agent vocal IA (option 0 du menu)
│   ├── Dockerfile         # Image Asterisk + venv Python + AGI
│   ├── requirements.txt
│   ├── agi/
│   │   ├── ai_conseiller.py    # AGI invoqué par le dialplan
│   │   ├── claude_agent.py     # Wrapper Claude (prompt caching 1h sur la KB)
│   │   ├── stt.py              # Speech-to-Text (Deepgram)
│   │   ├── tts.py              # Text-to-Speech (ElevenLabs ou gTTS)
│   │   └── db.py               # Persistance Postgres
│   ├── knowledge/
│   │   └── depanmagic.md       # Base de connaissances (éditable à chaud)
│   ├── db/schema.sql            # Tables calls / call_turns / extracted_facts
│   └── admin/
│       ├── seed_db.py           # Initialisation Postgres
│       └── review_calls.py      # Revue qualité (CLI)
├── docker-compose.yml     # Asterisk(+AGI) + Postgres + Postfix
├── entrypoint.sh
├── .env.example
└── README.md
```

## Menu vocal

| Touche | Action |
|--------|--------|
| 1      | Urgence dépannage → transfert vers mobile technicien, sinon messagerie 103 |
| 2      | Demande de devis → messagerie 101 |
| 3      | Suivi de dossier → messagerie 102 |
| 4      | Annonce horaires + retour menu |
| 0      | **Conseiller IA** Claude → dialogue libre avec base DEPANMAGIC (transfert astreinte si urgence détectée) |
| #      | Réécouter le menu |

Hors horaires (dimanche complet, lundi-vendredi 19h-8h, samedi après 12h) :
le standard bascule sur une annonce « fermé » qui propose uniquement
l'urgence (1) ou la messagerie (9).

## Côté OVH — récupérer les infos du trunk

1. Espace client OVH → **Téléphonie** → sélectionner la ligne SIP.
2. Onglet **Identifiants** : noter `Login` et `Mot de passe SIP`.
3. Onglet **Configuration** : autoriser uniquement l'IP publique du serveur Asterisk.
4. Vérifier que la ligne est bien en mode **SIP** (pas IPBX cloud OVH).

Serveur d'enregistrement utilisé : `sip.ovh.fr` (UDP 5060). Si votre offre
utilise `voip.ovh.com` ou un autre endpoint, modifier `pjsip.conf` en conséquence.

## Pré-requis serveur

- Linux x86_64 (Debian 12 / Ubuntu 22.04 testé)
- Docker + Docker Compose v2
- Ports ouverts sur le firewall :
  - **UDP 5060** (SIP) — autorisé uniquement depuis les plages IP OVH
  - **UDP 10000-10100** (RTP)
- IP publique fixe (ou DynDNS + mise à jour `EXTERNAL_IP`)

## Installation

```bash
git clone <ce-repo>
cd repondeur
cp .env.example .env
$EDITOR .env                       # remplir les identifiants OVH + emails
```

### 1. Générer les annonces vocales françaises

```bash
python -m venv .venv && source .venv/bin/activate
pip install gTTS
sudo apt install ffmpeg            # ou brew install ffmpeg
python prompts/generate_prompts.py
```

Pour une voix offline de meilleure qualité, installer
[Piper](https://github.com/rhasspy/piper), télécharger le modèle
`fr_FR-siwis-medium.onnx` puis :

```bash
python prompts/generate_prompts.py --engine piper --piper-model /chemin/vers/fr_FR-siwis-medium.onnx
```

Vous pouvez aussi remplacer chaque WAV dans `sounds/custom/` par un
enregistrement studio (8 kHz, mono, PCM 16 bits).

### 2. Lancer Asterisk

```bash
docker compose up -d
docker compose logs -f asterisk
```

Vérifier que le trunk OVH est bien enregistré :

```bash
docker compose exec asterisk asterisk -rx "pjsip show registrations"
# Doit afficher "Registered" pour ovh-trunk
```

### 3. Tester un appel entrant

Appelez le numéro OVH depuis un mobile : vous devez entendre l'annonce de
bienvenue puis le menu. Toute touche pressée doit déclencher la branche
correspondante du dialplan.

### 4. Tester la messagerie vocale

```bash
docker compose exec asterisk asterisk -rx "voicemail show users"
```

Pour consulter une boîte depuis un poste interne (Linphone/Zoiper enregistré
en `100`), composer **\*98**.

## Utilisation au quotidien

| Tâche | Commande |
|-------|----------|
| Recharger le dialplan après modification | `docker compose exec asterisk asterisk -rx "dialplan reload"` |
| Recharger PJSIP (trunk/endpoints) | `docker compose exec asterisk asterisk -rx "pjsip reload"` |
| Voir les appels en cours | `docker compose exec asterisk asterisk -rx "core show channels"` |
| Logs détaillés | `docker compose logs -f asterisk` |
| Arrêter | `docker compose down` |

## Sécurité

- N'autoriser **UDP 5060** entrant qu'aux IP OVH (réduit drastiquement le
  brute-force SIP). Plages OVH publiées sur leur site support.
- Les mots de passe de `.env` ne doivent **jamais** être commités (le
  `.gitignore` du dossier les exclut).
- Activer `fail2ban` sur l'hôte avec un filtre `asterisk` pour bloquer les
  tentatives de scan.

## Personnalisation rapide

- **Changer le menu** : éditer `asterisk/extensions.conf` et `prompts/scripts.txt`,
  régénérer les annonces, puis `pjsip reload` + `dialplan reload`.
- **Ajouter un poste interne** : dupliquer le bloc `[100]` dans `pjsip.conf`
  (ex. `[101]`), ajouter sa boîte dans `voicemail.conf`.
- **Modifier les horaires d'ouverture** : adapter le `GotoIfTime` dans le
  contexte `[hours-check]` de `extensions.conf`.

## Conseiller vocal IA (option 0)

### Vue d'ensemble

Quand l'appelant tape `0`, le dialplan exécute l'AGI `ai_conseiller.py` qui
orchestre une boucle :

```
RECORD voix client → STT (Deepgram fr) → Claude (avec KB en cache) → TTS (ElevenLabs) → PLAY → loop
```

Caractéristiques :
- **Knowledge base** : `ai-agent/knowledge/depanmagic.md` est chargé dans le
  system prompt et **mis en cache 1h** côté Anthropic (prompt caching). Tous les
  appels qui arrivent dans l'heure suivante paient ~10 % du prix d'entrée pour
  ce préfixe. Modifiez le fichier puis redémarrez le service pour invalider.
- **Mémoire inter-appels** : à chaque appel, on retrouve le résumé du dernier
  appel terminé du même numéro (table `calls`) et on l'injecte dans le contexte.
- **Détection d'urgence** : Claude est instruit d'émettre `[[TRANSFER_URGENCE]]`
  s'il détecte une situation critique. Le dialplan reprend la main et bascule
  l'appel vers le mobile d'astreinte (`TECH_MOBILE`).
- **Garde-fous** : 12 tours max par appel, raccrochage automatique sur silence
  prolongé, fallback sur l'extension humaine 100 si l'AGI plante.

### Pré-requis supplémentaires

- Une **clé API Anthropic** (`ANTHROPIC_API_KEY`).
- Une **clé API Deepgram** (`DEEPGRAM_API_KEY`) pour la transcription FR.
- Une **clé API ElevenLabs** (`ELEVENLABS_API_KEY`) pour une voix naturelle ;
  si vide, fallback automatique sur gTTS (qualité moindre).
- ~50 Mo de RAM Postgres en plus.

### Authentification Claude

L'API Anthropic utilise une **clé API** (`x-api-key`), **pas OAuth** : OAuth
n'existe que pour les utilisateurs finaux de claude.ai. Pour un service
backend comme celui-ci, on configure `ANTHROPIC_API_KEY` dans `.env`.

### « Apprentissage continu »

Claude n'apprend pas de vos appels (le modèle est figé). Ce qu'on simule :

1. Chaque tour est sauvegardé dans Postgres (`call_turns`).
2. En fin d'appel, Claude génère un résumé court stocké dans `calls.summary`.
3. Au prochain appel du même numéro, ce résumé est injecté en contexte → l'agent
   "se souvient" du précédent échange.
4. La table `extracted_facts` est prévue pour qu'un conseiller humain valide des
   informations remontées par les appels et les reverse dans la knowledge base.

### Coût indicatif (estimation)

Pour un appel moyen de 8 tours (~1500 tokens d'entrée, 600 de sortie) :
- KB en cache (8K tokens, 1 écriture/h puis lecture) : ~0.001 $/appel
- I/O Claude Opus 4.7 : ~0.022 $/appel
- Deepgram (~30s d'audio) : ~0.002 $/appel
- ElevenLabs (~80 mots) : ~0.014 $/appel

**Total : ~0.04 $/appel** avec Opus 4.7. Bascule sur `claude-sonnet-4-6`
(`CLAUDE_MODEL` dans `.env`) pour diviser par ~3 en haute volumétrie.

### Tester l'agent IA

```bash
# Démarrage
docker compose up -d
docker compose logs -f asterisk | grep ai_conseiller

# Suivre un appel en direct (tail des transcriptions)
docker compose exec postgres psql -U depanmagic -c \
  "SELECT id, caller_number, started_at, outcome FROM calls ORDER BY id DESC LIMIT 5;"

# Détail d'un appel précis (transcription complète)
docker compose exec asterisk /opt/ai-agent/bin/python \
  /opt/ai-agent/admin/review_calls.py --call-id 42
```

### Modifier la base de connaissances

```bash
$EDITOR ai-agent/knowledge/depanmagic.md
docker compose restart asterisk    # invalide le cache prompt et recharge
```

## Branche de développement

Ce répondeur est développé sur la branche `dev`. Une fois validé en
recette, le merger via `fix-maj` puis vers `prod`.
