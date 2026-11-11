# AccesKey.fr — Design Reference Analysis
Captured: 2026-11-11 — Playwright headless Chromium, viewport 1440px desktop / 375px mobile

---

## Palette de couleurs exacte

### Couleurs principales (custom properties CSS)

| Token CSS                | Valeur hex/rgba          | Usage                        |
|--------------------------|--------------------------|------------------------------|
| `--accent-primary`       | `#0071e3`                | Bleu primaire (CTA, liens)   |
| `--accent-light`         | `#0077ed`                | Bleu légèrement plus clair   |
| `--accent-bright`        | `#40a0ff`                | Bleu brillant (gradient end) |
| `--accent-glow`          | `rgba(0,113,227,0.1)`    | Halo/ombre bleu              |
| `--gcid-primary-color`   | `#2086ff`                | Couleur primaire Divi        |
| `--gcid-link-color`      | `#2ea3f2`                | Liens (computed: rgb(46,163,242)) |
| `--text-primary`         | `#1a1a2e`                | Texte H1 principal           |
| `--text-secondary`       | `#64748b`                | Texte secondaire             |
| `--text-muted`           | `#94a3b8`                | Texte atténué                |
| `--gcid-heading-color`   | `#666666`                | Titres Divi                  |
| `--gcid-body-color`      | `#666666`                | Corps texte Divi             |
| `--bg-deep`              | `#ffffff`                | Fond principal               |
| `--bg-elevated`          | `#f8f9fa`                | Fond sections surélevées     |
| `--bg-card`              | `#ffffff`                | Fond cartes                  |

### Couleurs computed (utilisées sur éléments réels)

| Couleur RGB               | Hex équivalent | Usage identifié                     |
|---------------------------|----------------|-------------------------------------|
| `rgb(26, 26, 46)`         | `#1a1a2e`      | H1, titres sombres, dark section bg |
| `rgb(15, 23, 42)`         | `#0f172a`      | H2, quasi-noir                      |
| `rgb(10, 10, 11)`         | `#0a0a0b`      | Très sombre (footer)                |
| `rgb(11, 18, 32)`         | `#0b1220`      | Sombre profond                      |
| `rgb(0, 113, 227)`        | `#0071e3`      | Boutons CTA, accent principal       |
| `rgb(46, 163, 242)`       | `#2ea3f2`      | Liens, couleur active               |
| `rgb(29, 29, 31)`         | `#1d1d1f`      | Texte très sombre (Apple-like)      |
| `rgb(102, 102, 102)`      | `#666666`      | Texte body par défaut               |
| `rgb(100, 116, 139)`      | `#64748b`      | Texte secondaire (slate-500)        |
| `rgb(71, 85, 105)`        | `#475569`      | Texte tertiaire (slate-600)         |
| `rgb(148, 163, 184)`      | `#94a3b8`      | Texte atténué (slate-400)           |
| `rgb(134, 134, 139)`      | `#86868b`      | Texte subtil (Apple grey)           |
| `rgb(255, 90, 60)`        | `#ff5a3c`      | Accent orange/rouge (warning/badge) |
| `rgb(34, 197, 94)`        | `#22c55e`      | Vert succès                         |
| `rgb(234, 179, 8)`        | `#eab308`      | Jaune avertissement                 |
| `rgb(241, 245, 249)`      | `#f1f5f9`      | Fond très clair (slate-100)         |
| `rgb(232, 242, 254)`      | `#e8f2fe`      | Fond bleu très clair                |
| `rgb(238, 242, 246)`      | `#eef2f6`      | Fond gris-bleu clair                |

### Gradient principal
```css
--gradient-accent: linear-gradient(135deg, #0071e3 0%, #0077ed 50%, #40a0ff 100%);
```

---

## Typographie

### Polices utilisées

**Police principale (headings):** `Poppins, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
**Police secondaire (body/nav):** `Poppins, -apple-system, BlinkMacSystemFont, "SF Pro Display", sans-serif`
**Police Divi fallback:** `"Open Sans", Arial, sans-serif`

Variables Divi :
- `--et_global_heading_font: 'Open Sans'`
- `--et_global_body_font: 'Open Sans'`
- Mais en pratique : **Poppins** est la police réelle chargée

### Tailles et poids (computed)

| Élément  | Font-size | Font-weight | Line-height    | Letter-spacing |
|----------|-----------|-------------|----------------|----------------|
| H1       | 36px      | 700         | 43.2px (1.2)   | -0.72px        |
| H2       | 28px      | 700         | 30.8px (1.1)   | -0.56px        |
| H3       | 24px      | 700         | 27.6px (1.15)  | -0.36px        |
| Body     | 14px      | 500 (Divi)  | 1.7em          | normal         |
| Liens    | 14px      | 500         | 23.8px (1.7)   | normal         |
| Boutons  | 13px      | 500         | normal         | normal         |

### Preset font sizes (WP)
- Small: 13px
- Medium: 20px
- Large: 36px
- X-Large: 42px

---

## Espacements et layout

```css
--content-width: 80%;
--content-max-width: 1080px;        /* WP global wide-size aussi: 1080px */
--wp--style--global--content-size: 823px;
--section-padding: 56px;
--section-gutter: 60px;
--row-gutter-horizontal: 5.5%;
--row-gutter-vertical: 40px;
--module-gutter: 30px;
```

### Preset spacing (WP)
| Token              | Valeur      |
|--------------------|-------------|
| `--spacing--20`    | 0.44rem ~7px|
| `--spacing--30`    | 0.67rem ~11px|
| `--spacing--40`    | 1rem = 16px  |
| `--spacing--50`    | 1.5rem = 24px|
| `--spacing--60`    | 2.25rem = 36px|
| `--spacing--70`    | 3.38rem = 54px|
| `--spacing--80`    | 5.06rem = 81px|

---

## Border radius

```css
--radius-sm: 12px;
--radius-md: 20px;
--radius-lg: 32px;
```

---

## Ombres (box-shadow)

```css
--shadow-sm: 0 4px 20px rgba(0,0,0,0.04);
--shadow-md: 0 10px 40px rgba(0,0,0,0.08);
--shadow-lg: 0 25px 80px rgba(0,0,0,0.1);
```

---

## Transitions / Easing

```css
--ease-out-expo: cubic-bezier(0.19, 1, 0.22, 1);
--ease-out-back: cubic-bezier(0.34, 1.56, 0.64, 1);
```

---

## Structure de navigation

**CMS:** WordPress + Divi Builder

### Menu principal (desktop)
Le header utilise la classe `.akh__header` (custom theme/plugin). Structure :
1. **Logo** AccesKey (image PNG/WebP) → lien accueil
2. **Badge partenaire Nuki** (officiel)
3. **Mega menu avec dropdowns :**
   - Particulier — *Sécurisez votre domicile*
   - Airbnb & Location — *Codes temporaires automatiques*
   - Entreprise — *Contrôle d'accès pro*
   - Domotique — *HomeKit, Google Home, Alexa*
   - Alarme & caméra — *Ajax*
4. **Produits :** Nuki 4.0 Pro, Yale Linus L2, Tedee Pro USB-C, Bold Smart Cylinder
5. **Arrondissements Paris :** Paris 1er, 4e, 7e, 8e, … (géolocalisation SEO)

### URL structure
- Accueil : `https://acceskey.fr/`
- Particulier : `/serrure-connectee-particulier/`
- Airbnb/Location : `/serrure-connectee/`
- Entreprise : `/controle-acces-entreprise/`
- Domotique : `/domotique/`
- Alarme : `/alarme-camera-ajax/`
- Nuki : `/installation-nuki-paris/`
- Yale : `/installation-yale-paris/`
- Tedee : `/installation-tedee-paris/`
- Bold : `/installation-bold-paris/`

---

## Composants identifiés

### 1. Header fixe (sticky)
- Fond blanc semi-transparent avec blur glassmorphism : `rgba(255,255,255,0.96)` → `rgba(255,255,255,0.98)`
- Box-shadow légère au scroll
- Hauteur ~70-80px
- Logo + nav + CTA button

### 2. Hero Section
- Fond : `#1a1a2e` (sombre) ou blanc selon page
- Titre H1 36px+ Poppins 700, lettre-spacing négatif
- Sous-titre en Poppins 500
- CTA bouton bleu `#0071e3` avec gradient
- Sections alternées : fond blanc ↔ fond sombre `#1a1a2e`

### 3. Cards / Blocs services
- Fond blanc avec border-radius 20px (`--radius-md`)
- Box-shadow `--shadow-md`
- Badge/Tag accent coloré
- Icône + Titre H3 + Description + Lien

### 4. Sections dark (fond sombre)
- Background `#1a1a2e` ou `#0b1220`
- Texte blanc `#ffffff`
- Accents bleu `#0071e3` / `#40a0ff`
- Cards avec fond `rgba(255,255,255,0.08)`

### 5. Boutons CTA
- **Primaire :** fond `#0071e3`, texte blanc, border-radius 12px (`--radius-sm`)
- **Gradient :** `linear-gradient(135deg, #0071e3, #0077ed, #40a0ff)`
- Hover : élévation légère, shadow renforcée
- Padding typique : 14px 28px environ

### 6. Footer
- Fond très sombre `#0a0a0b` ou `#0b1220`
- Texte blanc/gris atténué
- Liens en blanc avec opacité
- Logo + liens + mentions légales

---

## Thème CMS

**CMS :** WordPress
**Builder :** Divi (Elegant Themes)
**Custom Theme :** AccesKey custom (`.akh__*` prefix pour éléments personnalisés)

---

## Différences avec les tokens du skill ACCESKEY

> **Note :** Le skill AccesKey peut utiliser des valeurs légèrement différentes. Voici ce qui a été constaté sur le site réel.

| Aspect            | Skill (référence)                    | Site réel (extrait)                |
|-------------------|--------------------------------------|------------------------------------|
| Police principale | Probablement système                 | **Poppins** (confirmé)             |
| Bleu principal    | Variable                             | `#0071e3` (confirmé exact)         |
| Background sombre | Variable                             | `#1a1a2e` (confirmé exact)         |
| Border radius     | Variable                             | 12/20/32px (sm/md/lg)              |
| Font body         | Variable                             | 14px / Open Sans (Divi) mais Poppins en rendu |
| Gradient          | Variable                             | `135deg, #0071e3, #0077ed, #40a0ff`|

---

## Fichiers générés

| Fichier                    | Contenu                                      |
|----------------------------|----------------------------------------------|
| `acceskey_desktop.png`     | Screenshot full-page desktop 1440px          |
| `acceskey_mobile.png`      | Screenshot full-page mobile 375px            |
| `acceskey_domotique.png`   | Screenshot page /domotique/ desktop          |
| `extracted_styles.css`     | Toutes les règles CSS de la page (168 Ko)    |
| `css_variables.json`       | 86 custom properties CSS `:root`             |
| `visual_tokens.json`       | Computed styles par type d'élément           |
| `colors_used.json`         | Couleurs computed uniques sur la page        |
| `header.html`              | HTML complet du header/navigation            |
| `nav_links.json`           | Tous les liens nav avec texte et URL         |
| `meta_info.json`           | Title et description de la page              |

---

## Résumé exécutif pour Smart Hosting

Pour répliquer fidèlement le style AccesKey dans les pages Smart Hosting :

1. **Police :** Charger Poppins depuis Google Fonts (weights 400, 500, 700)
2. **Palette :** Bleu `#0071e3` comme accent principal, fonds `#1a1a2e` pour sections dark, blanc `#ffffff` pour sections light
3. **Border-radius :** 12px (small), 20px (medium), 32px (large)
4. **Typographie :** Letter-spacing négatif sur headings (-0.02em), font-weight 700 pour H1/H2/H3
5. **Ombres :** Légères et diffuses (opacity 4-10%)
6. **Transitions :** `cubic-bezier(0.19, 1, 0.22, 1)` pour effets fluides
7. **Layout :** max-width 1080px, padding sections 56px
