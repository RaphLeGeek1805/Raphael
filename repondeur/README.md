# Répondeur vocal DEPANMAGIC (Asterisk + trunk SIP OVH)

IVR français pour DEPANMAGIC raccordé à un trunk SIP OVH. Asterisk dockerisé,
annonces générées par TTS, messagerie vocale envoyée par e-mail.

## Arborescence

```
repondeur/
├── asterisk/              # Templates de configuration Asterisk
│   ├── pjsip.conf         # Trunk OVH + extensions internes
│   ├── extensions.conf    # Dialplan / IVR (menu vocal)
│   ├── voicemail.conf     # Messageries vocales
│   ├── asterisk.conf
│   ├── modules.conf
│   ├── rtp.conf
│   ├── logger.conf
│   └── manager.conf
├── prompts/
│   ├── scripts.txt        # Textes des annonces vocales
│   └── generate_prompts.py
├── sounds/custom/         # WAV générés (ignoré par git)
├── docker-compose.yml
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
| 0      | Conseiller → poste interne 100, sinon messagerie 100 |
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

## Branche de développement

Ce répondeur est développé sur la branche `dev`. Une fois validé en
recette, le merger via `fix-maj` puis vers `prod`.
