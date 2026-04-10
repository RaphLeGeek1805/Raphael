# Deployer Raphael sur cPanel avec votre domaine

## Prerequis

- Un hebergement cPanel avec **Python Selector** (support Python 3.9+)
- Un nom de domaine pointe vers votre hebergement (DNS configures)
- Acces au cPanel de votre hebergement

---

## Etape 1 : Uploader les fichiers sur le serveur

### Option A : Via le Gestionnaire de fichiers cPanel

1. Connectez-vous a votre **cPanel**
2. Ouvrez le **Gestionnaire de fichiers** (File Manager)
3. Naviguez vers `/home/votre-username/` (votre repertoire home)
4. Creez un dossier `raphael` (ou le nom de votre choix)
5. Uploadez **tous les fichiers** du projet dans ce dossier

### Option B : Via Git (recommande)

1. Dans cPanel, allez dans **Git Version Control**
2. Cliquez sur **Create** (Creer)
3. Entrez l'URL du depot : `https://github.com/RaphLeGeek1805/Raphael.git`
4. Chemin du depot : `/home/votre-username/raphael`
5. Cliquez sur **Create**

---

## Etape 2 : Creer l'application Python dans cPanel

1. Dans cPanel, allez dans **Setup Python App** (ou "Python Selector")
2. Cliquez sur **CREATE APPLICATION**
3. Configurez comme suit :

| Parametre             | Valeur                                    |
|-----------------------|-------------------------------------------|
| **Python version**    | 3.9 ou superieur (3.11 recommande)        |
| **Application root**  | `raphael`                                 |
| **Application URL**   | Selectionnez votre domaine (ex: `mondomaine.com`) |
| **Application startup file** | `passenger_wsgi.py`              |
| **Application Entry point**  | `application`                    |

4. Cliquez sur **CREATE**

> cPanel va creer automatiquement un environnement virtuel Python et generer
> le fichier `.htaccess` dans le repertoire de votre domaine.

---

## Etape 3 : Installer les dependances

1. Apres la creation de l'app, cPanel affiche une commande pour activer
   l'environnement virtuel. Elle ressemble a :
   ```
   source /home/votre-username/virtualenv/raphael/3.11/bin/activate
   ```

2. **Option A** - Via l'interface cPanel :
   - Dans la page de votre app Python, section **Configuration files**
   - Ajoutez `requirements.txt` et cliquez sur **Run Pip Install**

3. **Option B** - Via le Terminal cPanel :
   ```bash
   # Copiez-collez la commande d'activation affichee par cPanel, puis :
   source /home/votre-username/virtualenv/raphael/3.11/bin/activate
   cd ~/raphael
   pip install -r requirements.txt
   ```

---

## Etape 4 : Configurer les variables d'environnement

Dans la page **Setup Python App** de votre application :

1. Cliquez sur **Add Variable** pour chaque variable :

| Variable        | Valeur                          | Obligatoire ? |
|-----------------|---------------------------------|---------------|
| `SECRET_KEY`    | Une cle secrete aleatoire longue | **Oui**       |
| `SERPAPI_KEY`   | Votre cle SerpAPI (Google Lens) | Non           |
| `GITHUB_TOKEN`  | Votre token GitHub              | Non           |

> **Important** : Changez `SECRET_KEY` par une valeur unique et secrete.
> Vous pouvez generer une cle avec :
> ```bash
> python3 -c "import secrets; print(secrets.token_hex(32))"
> ```

---

## Etape 5 : Pointer votre domaine vers l'application

### Si vous utilisez votre domaine principal :

1. Dans cPanel > **Setup Python App**, selectionnez votre domaine principal
   comme **Application URL**
2. L'application sera accessible sur `https://votre-domaine.com`

### Si vous utilisez un sous-domaine :

1. Allez dans cPanel > **Sous-domaines** (Subdomains)
2. Creez un sous-domaine (ex: `recherche.votre-domaine.com`)
3. Notez le **Document Root** du sous-domaine
4. Dans **Setup Python App**, selectionnez ce sous-domaine comme URL

### Configuration DNS (si pas encore fait) :

Chez votre registrar de domaine (OVH, Namecheap, Cloudflare, etc.) :

| Type  | Nom                | Valeur                          |
|-------|--------------------|---------------------------------|
| A     | `@` ou `domaine`   | IP de votre serveur cPanel      |
| A     | `www`              | IP de votre serveur cPanel      |

> L'IP de votre serveur se trouve dans cPanel > **Informations generales**
> (Server Information) ou dans la barre laterale droite.

---

## Etape 6 : Redemarrer et tester

1. Retournez dans **Setup Python App**
2. Cliquez sur **RESTART** pour redemarrer l'application
3. Visitez votre domaine dans le navigateur : `https://votre-domaine.com`
4. Verifiez que la page de recherche Raphael s'affiche

---

## Etape 7 : Activer HTTPS (SSL)

1. Dans cPanel, allez dans **SSL/TLS** ou **Let's Encrypt SSL**
2. Selectionnez votre domaine
3. Cliquez sur **Issue** (Emettre) pour obtenir un certificat gratuit
4. Activez la **redirection forcee HTTPS** dans cPanel > **Domains**

---

## Depannage

### L'application affiche une erreur 500
- Verifiez les logs : cPanel > **Errors** (Journaux d'erreurs)
- Verifiez que toutes les dependances sont installees
- Verifiez que `passenger_wsgi.py` est dans le bon repertoire

### La page ne se charge pas
- Verifiez que le DNS pointe vers la bonne IP
- Attendez 24-48h pour la propagation DNS
- Verifiez que l'app Python est demarree dans cPanel

### Les fichiers statiques (CSS/JS) ne se chargent pas
- Verifiez que le dossier `static/` est bien present
- Verifiez les permissions des fichiers (644 pour les fichiers, 755 pour les dossiers)

### Commande pour corriger les permissions :
```bash
cd ~/raphael
find . -type f -exec chmod 644 {} \;
find . -type d -exec chmod 755 {} \;
```

---

## Structure attendue sur le serveur

```
/home/votre-username/
└── raphael/
    ├── passenger_wsgi.py    <-- Point d'entree Passenger
    ├── .htaccess            <-- Genere par cPanel
    ├── app.py               <-- Application Flask
    ├── config.py            <-- Configuration
    ├── requirements.txt     <-- Dependances Python
    ├── templates/
    │   ├── base.html
    │   └── index.html
    ├── static/
    │   ├── css/style.css
    │   └── js/app.js
    ├── searchers/
    │   └── ...
    └── utils/
        └── ...
```
