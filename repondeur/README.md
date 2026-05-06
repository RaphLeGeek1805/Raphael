# Conseiller vocal IA DEPAN MAGIC (OVH CCS + Asterisk + Claude)

Agent vocal IA branché en aval d'**OVH Contact Center Solution** (mode expert)
sur le numéro **+33 1 84 16 21 10** (`0033184162110`).

## Architecture

```
PSTN ──▶ OVH CCS (cloud OVH) ──▶ Menu interactif (UI OVH)
                                  │
                       ┌──────────┼─────────────┐
                       ▼          ▼             ▼
                   touche 1   touche 2-4    touche 0
                   (urgence)  (devis…)    (conseiller IA)
                       │          │             │
                  appels sortants OVH       SIP transfer
                   (mobile/VM dans CCS)         │
                                                ▼
                                  ┌──────────────────────────┐
                                  │  Asterisk auto-hébergé   │
                                  │  (ce dépôt, dockerisé)   │
                                  │                          │
                                  │  AGI Python ─▶ Claude    │
                                  │       │       Opus 4.7   │
                                  │       ├─▶ Deepgram (STT) │
                                  │       └─▶ ElevenLabs (TTS)│
                                  │                          │
                                  │  Postgres : historique   │
                                  │  des appels + résumés    │
                                  └──────────────────────────┘
```

**Répartition des responsabilités** :

| Brique | Hébergé chez | Rôle |
|---|---|---|
| Menu vocal 1-4 | **OVH CCS** | Annonces TTS OVH, créneaux d'ouverture, voicemail, transfert mobile |
| Conseiller IA (touche 0) | **Notre Asterisk** | Boucle conversationnelle Claude ↔ caller |
| Knowledge base DEPAN MAGIC | **Notre Asterisk** | Markdown éditable, mis en cache 1h chez Anthropic |
| Historique appels IA | **Notre Postgres** | Mémoire inter-appels par numéro |
| Détection urgence | **Notre Asterisk** | Claude émet `[[TRANSFER_URGENCE]]` → SIP REFER vers une étape OVH CCS |

## Arborescence

```
repondeur/
├── asterisk/                       # Configuration Asterisk minimale
│   ├── pjsip.conf                  # Endpoint réception OVH CCS (par IP)
│   ├── extensions.conf             # Route unique : entrant → AGI Claude
│   ├── asterisk.conf, modules.conf, rtp.conf, logger.conf, manager.conf
├── ai-agent/                       # Agent vocal IA
│   ├── Dockerfile                  # Image Asterisk + venv Python + AGI
│   ├── agi/
│   │   ├── ai_conseiller.py        # AGI invoqué par le dialplan
│   │   ├── claude_agent.py         # Wrapper Claude (cache 1h sur la KB)
│   │   ├── stt.py                  # Deepgram fr
│   │   ├── tts.py                  # ElevenLabs (fallback gTTS)
│   │   └── db.py                   # Postgres
│   ├── knowledge/depanmagic.md     # KB extraite de depanmagic.fr
│   ├── db/schema.sql
│   └── admin/
│       ├── seed_db.py
│       └── review_calls.py
├── docker-compose.yml              # Asterisk(+AGI) + Postgres
├── entrypoint.sh
├── .env.example
└── README.md
```

## Étape 1 — Récupérer les paramètres OVH CCS

Dans le Manager OVH → **VoIP** → ligne `0033184162110` → **Configuration → Contact Center Solution** :

1. **Plages IP source** : OVH publie les plages IP utilisées par le CCS pour
   les transferts SIP externes. Notez-les. Vous les mettrez dans
   `OVH_CCS_ALLOWED_IPS`. Sans cette restriction, n'importe qui sur Internet
   pourrait pousser un INVITE à votre Asterisk.

2. **URL de transfert externe** : dans l'onglet **Menus interactifs**, créez
   une étape "Transférer vers SIP externe" qui pointera vers
   `sip:0@<IP-publique-de-votre-serveur>:5060` ou
   `sip:0@asterisk.depanmagic.fr:5060`.
   Cette étape sera reliée à la touche **0** du menu principal.

3. **(Optionnel) URL d'urgence** : créez une seconde étape "Appel sortant"
   qui appelle votre mobile d'astreinte, et notez son URI SIP interne. Vous
   pourrez la mettre dans `OVH_URGENCE_REFER_URI` pour que l'IA puisse y
   rediriger automatiquement les urgences détectées.

## Étape 2 — Provisionner le serveur

**Pré-requis** :
- VPS Linux (Debian 12 / Ubuntu 22.04+), 1 vCPU 2 Go RAM minimum.
- IP publique fixe (ou DDNS) — à mettre dans `EXTERNAL_IP`.
- Docker + Docker Compose v2.
- Ports ouverts dans le firewall UNIQUEMENT pour les plages OVH CCS :
  - **UDP 5060** (signaling SIP)
  - **UDP 10000-10100** (RTP)

Exemple `nftables`/`ufw` (à adapter à vos plages) :

```bash
sudo ufw allow proto udp from 92.222.144.0/24 to any port 5060
sudo ufw allow proto udp from 213.186.33.0/24 to any port 5060
sudo ufw allow proto udp from 92.222.144.0/24 to any port 10000:10100
sudo ufw allow proto udp from 213.186.33.0/24 to any port 10000:10100
```

## Étape 3 — Configurer et lancer

```bash
git clone <ce-repo>
cd repondeur
cp .env.example .env
$EDITOR .env                       # remplir IP, plages CCS, clés API, mots de passe
docker compose up -d --build
docker compose logs -f asterisk
```

Vérifier que l'endpoint `ovh-ccs` est OK :

```bash
docker compose exec asterisk asterisk -rx "pjsip show endpoint ovh-ccs"
docker compose exec asterisk asterisk -rx "pjsip show identifies"
```

## Étape 4 — Tester

### Test local (sans OVH, depuis un softphone)

1. Ouvrez Linphone/Zoiper, configurez un compte SIP :
   - Serveur : `<IP-publique-Asterisk>`
   - Login : `100`
   - Mot de passe : `EXT_100_PASSWORD` du `.env`
2. Composez **9** : vous tombez directement sur l'agent IA Claude.
3. Composez **\*97** : simulation d'urgence (test du chemin REFER).

### Test bout-en-bout (depuis un téléphone)

1. Appelez le **+33 1 84 16 21 10**.
2. Tapez **0** dans le menu OVH.
3. Vous êtes en relation avec Claude. Posez une question :
   - *"Combien coûte une intervention à domicile ?"* → 80 € la première heure (diagnostic inclus).
   - *"Vous intervenez à Boulogne ?"* → Oui, même forfait 30 €.
   - *"Je suis enfermé et mon PC vient d'être chiffré par un ransomware !"* → Claude doit dire qu'il vous met en relation avec l'astreinte et émettre `[[TRANSFER_URGENCE]]`.

### Suivi des appels

```bash
# Dernier 10 appels traités par l'IA
docker compose exec asterisk /opt/ai-agent/bin/python /opt/ai-agent/admin/review_calls.py --limit 10

# Détail d'un appel précis (transcription complète)
docker compose exec asterisk /opt/ai-agent/bin/python /opt/ai-agent/admin/review_calls.py --call-id 42

# Logs AGI en direct
docker compose exec asterisk tail -f /var/log/asterisk/ai_conseiller.log
```

## Modifier la base de connaissances

```bash
$EDITOR ai-agent/knowledge/depanmagic.md
docker compose restart asterisk    # invalide le cache Anthropic et recharge
```

## Coût indicatif

Pour un appel moyen de 8 tours (~1500 tokens entrée, 600 sortie) :

| Brique | Coût |
|---|---|
| Cache KB Anthropic (8K tokens, 1 écriture/h puis lectures) | ~0,001 $/appel |
| Claude Opus 4.7 (I/O) | ~0,022 $/appel |
| Deepgram (~30s d'audio FR) | ~0,002 $/appel |
| ElevenLabs (~80 mots) | ~0,014 $/appel |
| **Total** | **~0,04 $/appel** |

Bascule sur `claude-sonnet-4-6` (`CLAUDE_MODEL` dans `.env`) → ~0,015 $/appel.

## Mémoire inter-appels

Claude n'apprend pas de vos appels (le modèle est figé). Ce qu'on simule :

1. Chaque tour est sauvegardé dans `call_turns` (Postgres).
2. En fin d'appel, Claude génère un résumé court → stocké dans `calls.summary`.
3. Au prochain appel **du même numéro** (CallerID transmis par OVH CCS), ce
   résumé est injecté en contexte → l'agent "se souvient" du précédent échange.
4. La table `extracted_facts` est prévue pour qu'un humain valide des infos
   remontées par les appels et les reverse dans la KB.

## Sécurité

- **Restreindre absolument UDP 5060 aux plages IP OVH CCS** au niveau firewall
  ET dans `pjsip.conf` (variable `OVH_CCS_ALLOWED_IPS`). Sinon : flood SIP +
  brute force.
- Le `.env` contient toutes les clés API : ne **jamais** le commiter
  (`.gitignore` exclut déjà ce qu'il faut).
- `fail2ban` recommandé sur le serveur avec un filtre Asterisk standard.

## Points de configuration restants

À renseigner dans le `.env` avant la mise en service :

- [ ] `EXTERNAL_IP` : IP publique fixe du VPS hébergeant Asterisk.
- [ ] `OVH_CCS_ALLOWED_IPS` : plages IP du CCS OVH (à récupérer dans le Manager).
- [ ] `OVH_URGENCE_REFER_URI` : URI SIP de l'étape "appel astreinte" du CCS (optionnel).
- [ ] `ANTHROPIC_API_KEY` : clé Anthropic (https://console.anthropic.com).
- [ ] `DEEPGRAM_API_KEY` : clé Deepgram (https://console.deepgram.com).
- [ ] `ELEVENLABS_API_KEY` : clé ElevenLabs (sinon fallback gTTS).
- [ ] `PG_PASSWORD`, `EXT_100_PASSWORD`, `AMI_PASSWORD` : mots de passe internes.

À configurer dans l'UI OVH :

- [ ] Étape "Transfert SIP externe" sur la touche 0 → vers
      `sip:0@<EXTERNAL_IP>:5060`.
- [ ] Étape "Appel sortant astreinte" + son URI SIP interne (pour le REFER urgence).
- [ ] Plages IP autorisées en sortie de votre Asterisk vers le CCS.

## Branche de développement

Développé sur `dev`. Une fois validé en recette, merger via `fix-maj` puis vers `prod`.
