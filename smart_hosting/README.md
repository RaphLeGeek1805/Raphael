# ACCESKEY Smart Hosting

Plateforme de gestion d'accès automatisée pour locations saisonnières (Airbnb, Booking.com) : codes d'accès générés, envoyés et révoqués automatiquement sur les serrures connectées de vos biens.

---

## 1. Présentation

### Qu'est-ce que ACCESKEY Smart Hosting ?

Smart Hosting est l'offre SaaS d'ACCESKEY pour les hôtes de locations courte durée. Elle relie vos réservations aux serrures connectées :

- **Création automatique** d'un code d'accès unique par réservation, valable sur la période du séjour.
- **Envoi automatique** du code au voyageur (SMS / email) avant son arrivée.
- **Révocation automatique** du code à la fin du séjour.
- **Tableau de bord** multi-propriétés pour suivre l'état des serrures et des accès.
- **Portail revendeur** (plan Business) pour les professionnels qui gèrent le parc de leurs clients.

Trois plans : **Starter** (29 €/mois), **Pro** (69 €/mois), **Business** (149 €/mois). Essai gratuit 14 jours, sans carte bancaire, sans engagement.

### Positionnement

| Critère | ACCESKEY Smart Hosting | Nuki Smart Hosting | Tedee |
|---|---|---|---|
| Multi-marques de serrures | Oui (Nuki, Yale, Tedee, igloohome, Bold, toute serrure avec API) | Principalement Nuki | Principalement Tedee |
| Intégrations Airbnb / Booking.com | Oui (plan Pro et supérieur) | Selon offre | Selon offre |
| Portail revendeur | Oui (plan Business) | Non | Non |
| Accompagnement | Onboarding personnalisé et support téléphonique (Business) | Self-service | Self-service |

> Les comparaisons ci-dessus sont à valider avant diffusion commerciale.

### Stack technique

- **Backend** : Python, Flask (API REST), Flask-SQLAlchemy, Flask-JWT-Extended, Flask-CORS
- **Base de données** : SQLite en développement, PostgreSQL en production
- **Paiement** : Stripe (Checkout, portail client, webhooks)
- **Notifications** : Twilio (SMS) et SMTP (email), actuellement en mode stub tant que les identifiants ne sont pas renseignés
- **Frontend** : pages HTML/CSS/JS autonomes (portail hôte, page voyageur) et pages marketing intégrées dans Divi

---

## 2. Architecture

```
smart_hosting/
├── backend/                 # API Flask
│   ├── app.py               # Factory, enregistrement des blueprints, seed démo
│   ├── config.py            # Configuration (variables d'environnement)
│   ├── models.py            # User, Property, Lock, AccessCode, Booking, StripeCustomer
│   ├── requirements.txt
│   ├── routes/              # auth, properties, locks, access_codes, bookings, dashboard, billing
│   └── services/            # code_generator, lock_adapter (Nuki), notification (SMS/SMTP)
├── dashboard.html           # Portail hôte
├── guest_checkin.html       # Page voyageur (accès au code)
├── divi_landing_page.html   # Page marketing d'accueil (Divi)
├── divi_pricing_page.html   # Page tarifs (Divi)
├── admin_portal.html        # Portail revendeur ACCESKEY (prévu, non présent dans le dépôt)
└── design_reference/        # Tokens et captures relevés sur acceskey.fr
```

### Principes de l'API

- Préfixe unique `/api/`, authentification par JWT (`/api/auth/login`, `/api/auth/refresh`, `/api/auth/me`).
- Ressources : `/api/properties`, `/api/locks`, `/api/codes`, `/api/bookings`, `/api/dashboard`, `/api/billing`.
- Endpoint de santé : `GET /api/health`.

---

## 3. Lancement rapide (développement)

```bash
cd smart_hosting/backend
pip install -r requirements.txt
python app.py
```

L'API démarre sur **http://localhost:5000**.

Au premier lancement en mode développement, des données de démonstration sont créées :

- Compte hôte : `demo@acceskey.fr` / `Demo1234!`

> Ce compte est uniquement destiné au développement local. Ne jamais le conserver en production.

---

## 4. Variables d'environnement (production)

Toutes les valeurs sensibles doivent être définies dans l'environnement de l'hébergeur, jamais dans le code.

| Variable | Rôle | Valeur par défaut dans le code | Obligatoire en prod |
|---|---|---|---|
| `SECRET_KEY` | Clé secrète Flask | Valeur de développement | Oui, valeur forte et unique |
| `JWT_SECRET_KEY` | Signature des JWT (32 octets minimum) | Valeur de développement | Oui, valeur forte et unique |
| `DATABASE_URL` | URL de base (ex. `postgresql://…`) | `sqlite:///smart_hosting.db` | Oui |
| `FRONTEND_URL` | URL du portail hôte (redirections Stripe) | `http://localhost:3000` | Oui |
| `STRIPE_SECRET_KEY` | Clé secrète API Stripe | vide (mode mock) | Oui |
| `STRIPE_WEBHOOK_SECRET` | Secret de signature du webhook Stripe | vide | Oui |
| `STRIPE_PRICE_STARTER` | ID du prix Stripe du plan Starter | `price_starter_monthly` | Oui |
| `STRIPE_PRICE_PRO` | ID du prix Stripe du plan Pro | `price_pro_monthly` | Oui |
| `STRIPE_PRICE_BUSINESS` | ID du prix Stripe du plan Business | `price_business_monthly` | Oui |
| `TWILIO_ACCOUNT_SID` | Identifiant de compte Twilio | vide | Pour les SMS |
| `TWILIO_AUTH_TOKEN` | Jeton Twilio | vide | Pour les SMS |
| `TWILIO_PHONE_FROM` | Numéro expéditeur Twilio | `+33000000000` | Pour les SMS |
| `SMTP_HOST` | Serveur SMTP | `smtp.gmail.com` | Pour les emails |
| `SMTP_PORT` | Port SMTP | `587` | Pour les emails |
| `SMTP_USER` | Identifiant SMTP | vide | Pour les emails |
| `SMTP_PASSWORD` | Mot de passe SMTP | vide | Pour les emails |
| `EMAIL_FROM` | Expéditeur des emails | `noreply@acceskey.fr` | Oui |
| `FLASK_ENV` | `development` ou `production` | `development` | Oui |

### Intégrations listées mais non branchées dans le code actuel

Ces variables apparaissent dans la configuration prévue mais ne sont pas encore lues par le code :

| Variable | État |
|---|---|
| `NUKI_BRIDGE_HOST`, `NUKI_BRIDGE_TOKEN` | Lues par `services/lock_adapter.py` via la configuration Flask, mais absentes de `config.py`. À ajouter à `config.py` pour être alimentées par l'environnement. Sans elles, l'adaptateur Nuki fonctionne en stub (journalisation seule). |
| `AIRBNB_WEBHOOK_SECRET`, `BOOKING_WEBHOOK_SECRET` | Aucune route de webhook Airbnb ou Booking.com n'existe encore. Les réservations sont aujourd'hui créées via `/api/bookings`. |

---

## 5. Déploiement

### Hébergement recommandé

- **Railway** ou **Render** : déploiement simple depuis Git, PostgreSQL managé, variables d'environnement dans l'interface.
- **VPS OVH** : pour un contrôle complet (reverse proxy, sauvegardes, hébergement en France).

### Serveur WSGI

`python app.py` lance le serveur de développement Flask, à ne pas utiliser en production. Ajouter un serveur WSGI (par exemple `gunicorn`) à `requirements.txt` et lancer :

```bash
gunicorn -w 4 -b 0.0.0.0:$PORT "app:create_app()"
```

> `gunicorn` n'est pas encore dans `requirements.txt` : l'ajouter avant le premier déploiement.

### Base de données

- Passer `DATABASE_URL` sur PostgreSQL en production.
- Sauvegardes quotidiennes et test de restauration avant la mise en ligne.

### DNS

| Sous-domaine | Cible |
|---|---|
| `smart-hosting.acceskey.fr` | Application Smart Hosting (API et portail) |
| `client.acceskey.fr` | Odoo existant (espace client ACCESKEY) |

---

## 6. Intégration Divi (acceskey.fr)

- Coller le contenu de `divi_landing_page.html` ou `divi_pricing_page.html` dans un **Code Module** Divi.
- Fond de section : `#ffffff` (Design > Background dans Divi). Les pages ne posent jamais de fond sur `body`.
- Padding de la ligne et du module à 0 pour éviter un double espacement.
- Masquer le header Divi par défaut si le header ACCESKEY est utilisé à la place :

```css
#main-header { display: none !important; }
```

- Les shortcodes WordPress (ex. `[trustindex]`) ne s'exécutent pas dans un Code Module : utiliser un Text Module.

---

## 7. Configuration Stripe

1. Dans le Stripe Dashboard, créer **3 produits** : Starter (29 €), Pro (69 €), Business (149 €), en récurrence mensuelle.
2. Copier chaque **price ID** (`price_…`) dans les variables `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_BUSINESS`.
3. Renseigner `STRIPE_SECRET_KEY` (clé secrète) et récupérer le secret de signature du webhook dans `STRIPE_WEBHOOK_SECRET`.
4. Créer un endpoint webhook :

   **https://smart-hosting.acceskey.fr/api/billing/webhook**

   Événements à écouter :
   - `checkout.session.completed` : passe le compte au plan souscrit
   - événement de suppression ou d'annulation d'abonnement : repasse le compte en plan `free`

Sans `STRIPE_SECRET_KEY`, les routes de facturation renvoient des URL de simulation (mode mock).

---

## 8. Commercialisation ACCESKEY

### Modèle revendeur

- ACCESKEY facture aux revendeurs avec une marge de **20 à 30 %**.
- Le plan **Business** inclut le portail revendeur pour gérer le parc de leurs clients.

### Plans

| Plan | Prix HT / mois | Public cible |
|---|---|---|
| Starter | 29 € | Hôte avec 1 bien |
| Pro | 69 € | Hôte multi-biens, intégrations Airbnb et Booking.com |
| Business | 149 € | Conciergeries, revendeurs, API |

Facturation mensuelle ou annuelle (-20 % en annuel). TVA 20 % applicable en sus.

### Onboarding

- Un appel de **30 minutes** pour cadrer le parc (nombre de biens, marques de serrures, plateformes de réservation).
- Accès à un **environnement de démonstration** pour que le client teste avant de passer en production.
- Le plan Business comprend un onboarding personnalisé.
