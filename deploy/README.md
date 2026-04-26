# Déploiement Raphael — Ubuntu

Script `deploy.sh` qui installe et lance l'app Flask Raphael derrière nginx + gunicorn sur un serveur Ubuntu.

## Prérequis serveur
- Ubuntu 22.04 ou plus récent
- Utilisateur `ubuntu` avec accès `sudo`
- Ports 22 (SSH) et 80 (HTTP) ouverts

## Déploiement

Depuis votre machine locale :

```bash
# 1. Copier le script sur le serveur
scp deploy/deploy.sh ubuntu@51.254.133.40:~/

# 2. Lancer l'installation (clone le repo + installe tout)
ssh ubuntu@51.254.133.40 \
  "REPO_URL=https://github.com/RaphLeGeek1805/Raphael.git BRANCH=main bash ~/deploy.sh"
```

Le script :
1. Installe Python 3, nginx, git, et les libs système nécessaires
2. Clone le dépôt dans `/home/ubuntu/raphael`
3. Crée un virtualenv et installe les dépendances + gunicorn
4. Génère un `.env` avec un `SECRET_KEY` aléatoire
5. Installe un service systemd `raphael.service`
6. Configure nginx en reverse proxy sur le port 80

Une fois terminé, l'app répond sur `http://51.254.133.40/`.

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `APP_DIR` | `/home/ubuntu/raphael` | Dossier d'installation |
| `REPO_URL` | *(vide)* | URL git à cloner. Si vide, le code doit déjà être dans `APP_DIR` |
| `BRANCH` | `main` | Branche git à checkout |
| `DOMAIN` | `_` | `server_name` nginx (mettez votre nom de domaine si vous en avez un) |
| `PORT` | `8000` | Port interne gunicorn |
| `SECRET_KEY` | *(aléatoire)* | Clé secrète Flask |
| `SERPAPI_KEY` | *(vide)* | Clé SerpAPI optionnelle |
| `GITHUB_TOKEN` | *(vide)* | Token GitHub optionnel |

Exemple avec un domaine et une clé SerpAPI :

```bash
ssh ubuntu@51.254.133.40 \
  "REPO_URL=https://github.com/RaphLeGeek1805/Raphael.git \
   DOMAIN=raphael.example.com \
   SERPAPI_KEY=xxxxx \
   bash ~/deploy.sh"
```

## Mises à jour

Pour redéployer après un nouveau commit :

```bash
ssh ubuntu@51.254.133.40 \
  "cd /home/ubuntu/raphael && git pull && \
   .venv/bin/pip install -r requirements.txt && \
   sudo systemctl restart raphael"
```

## Commandes utiles

```bash
# Logs en temps réel
sudo journalctl -u raphael -f

# Redémarrer le service
sudo systemctl restart raphael

# État du service
sudo systemctl status raphael

# Tester la conf nginx
sudo nginx -t && sudo systemctl reload nginx
```

## HTTPS (optionnel)

Si vous avez un nom de domaine pointant vers le serveur :

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d raphael.example.com
```
