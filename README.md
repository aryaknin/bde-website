# BDE ORT Sup

Site local du bureau des élèves de l’ORT Sup à Montreuil.

Le projet repose sur **Flask, des modèles HTML Jinja, du CSS, du JavaScript natif et SQLite**.
Les pages sont rendues directement par Flask : les textes et les données sont présents dès
la première réponse du serveur.

Adresse du campus : **43 Rue Raspail, 93100 Montreuil**.

## État du site

- Accueil : image, texte, indicateur de défilement animé, présentation, chiffres et événements.
- Fenêtre de bienvenue à chaque chargement de l’accueil, fermable par la croix, Échap ou un clic à l’extérieur.
- Navigation responsive, masquée en descendant et réaffichée en remontant, avec transitions de page.
- Événements et boutique alimentés par SQLite.
- Cartes d’événements ouvrant une fiche détaillée avec un accès au calendrier.
- Thème bleu ORT, logos et polices servis localement.
- Connexion par session, comptes membres, administrateurs et superadministrateur protégé.
- Création de comptes, gestion des droits et ajout d’événements depuis l’interface admin.
- Préparation d’un événement Google Agenda à partir d’un événement créé sur le site.
- API JSON conservée pour les prochaines fonctionnalités.

Le calendrier mensuel Google est intégré dans un cadre responsive. Lorsqu’un événement est
ouvert depuis la page Événements, sa fiche est mise en avant au-dessus du calendrier.
Les commandes, les paiements et la synchronisation Google OAuth restent à développer.
Aucun bouton de paiement ne prétend effectuer une opération disponible.

Les événements, articles, compteurs, e-mails et réseaux sociaux sont des exemples.
Les chiffres historiques (1956, 70 ans, etc.) ne sont pas des informations validées sur l’ORT.
Ils devront être renseignés avec les vraies valeurs avant publication. La photo d’accueil
est conservée comme visuel provisoire.

## Installation locale

Prérequis : Python 3.10 ou supérieur, pip et un navigateur.

Depuis le dossier `bde-website` :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python3 backend/seed.py
python3 backend/manage.py create-superadmin --username VotreIdentifiant
python3 backend/app.py
```

Ouvrir ensuite [http://127.0.0.1:5000](http://127.0.0.1:5000).

Sous Windows, activer l’environnement avec `.venv\Scripts\Activate.ps1`
et utiliser `python` si `python3` n’est pas disponible. La dépendance `tzdata`
est installée automatiquement sous Windows pour les dates dans le fuseau Europe/Paris.

Le serveur reste limité à la machine locale. Pour changer de port sous Linux/macOS :

```bash
FLASK_PORT=5001 python3 backend/app.py
```

Sous PowerShell :

```powershell
$env:FLASK_PORT = "5001"
python backend/app.py
```

Aucun fichier `.env` n’est chargé automatiquement. Aucune installation Node/npm ni
commande de compilation n’est nécessaire.

## Organisation

```text
bde-website/
├── backend/
│   ├── app.py                 # Routes des pages, API et formatage des dates/prix
│   ├── database.py            # Connexion SQLite, schéma, réglages et requêtes
│   ├── manage.py              # Création interactive du superadministrateur
│   ├── seed.py                # Données de démonstration
│   └── requirements.txt       # Dépendances Python
├── db/
│   └── bde-ort-sup.db          # Base locale, ignorée par Git
├── pages/
│   ├── base.html              # Structure HTML commune
│   ├── partials/
│   │   ├── header.html        # Navigation
│   │   ├── footer.html        # Contacts et liens
│   │   ├── events.html        # Cartes d’événements communes
│   │   └── event-form.html    # Fenêtre admin de création d’événement
│   ├── index.html
│   ├── evenements.html
│   ├── billetterie.html
│   ├── calendrier.html
│   ├── bde.html
│   ├── login.html
│   ├── account.html
│   ├── admin.html
│   ├── demande-domaine.html
│   └── 404.html
├── static/
│   ├── css/site.css           # Styles, thème et responsive
│   ├── js/site.js             # Navigation et fenêtres de dialogue
│   ├── fonts/                # Inter et Bricolage Grotesque, variantes latines
│   └── images/               # Deux logos ORT et la photo d’accueil
├── tests/test_site.py         # Vérifications sur une base temporaire
├── .gitignore
└── README.md
```

Les fichiers HTML sont indentés et répartis par page. Jinja permet de partager les blocs
communs et d’insérer les valeurs provenant de SQLite. Il faut ouvrir les pages via Flask :
un double-clic sur un fichier HTML ne peut pas interpréter les balises Jinja.

Les URL des pages restent `/evenements.html`, `/calendrier.html`, etc.
Les ressources utilisent désormais le préfixe standard `/static/`, par exemple
`/static/css/site.css`. Les modèles communs et les fichiers Python/SQLite ne sont pas
exposés comme des pages publiques.

## Où faire les prochaines modifications

| Modification | Fichier |
| --- | --- |
| Couleurs, marges, typographie, mobile | `static/css/site.css` |
| Structure de l’accueil et pop-up | `pages/index.html` |
| Navigation, liens et contacts | `pages/partials/header.html`, `footer.html` |
| Contenu d’une page | Le fichier correspondant dans `pages/` |
| Interactions dans le navigateur | `static/js/site.js` |
| Routes et données fournies aux pages | `backend/app.py` |
| Schéma SQLite et requêtes | `backend/database.py` |
| Données de démonstration | `backend/seed.py` |

Les styles ne sont plus injectés par JavaScript. Le script ne remplace plus les textes,
les logos ou le contenu de la page après chargement. L’affichage des données fonctionne
aussi sans JavaScript ; le menu compact, les fenêtres et les transitions enrichies utilisent ce script.

## Base de données

Le fichier est `db/bde-ort-sup.db`. Il contient :

| Table | Contenu |
| --- | --- |
| `site_settings` | Nom, slogan, adresse, contacts, liens, compteurs |
| `associations` | Organisateurs internes liés aux événements et articles |
| `events` | Événements, horaires, lieux, organisateur facultatif, capacités, prix et lien Google |
| `products` | Articles, descriptions, stocks et prix |
| `users` | Identifiants, hash des mots de passe, rôles et protection du supercompte |

Les prix sont enregistrés en centimes. Les dates sont au format ISO 8601 avec
décalage horaire, puis affichées en français dans le fuseau Europe/Paris.
Seuls les événements publiés et les produits actifs sont affichés. L’accueil montre
au maximum trois événements à venir ou en cours ; la page Événements présente tous les
événements publiés. Le calendrier mensuel est fourni par Google Agenda.

### Modifier les valeurs affichées

Ouvrir la base avec un éditeur SQLite et modifier les lignes souhaitées, puis recharger
la page. Exemple SQL :

```sql
UPDATE site_settings SET value = '24' WHERE key = 'members_count';
UPDATE site_settings SET value = '2026' WHERE key = 'institution_since';
UPDATE site_settings SET value = '0' WHERE key = 'years_count';
UPDATE events SET title = 'Nouvelle soirée du BDE' WHERE id = 1;
UPDATE events SET organizer_name = 'Partenaire exceptionnel' WHERE id = 1;
UPDATE events
SET google_calendar_url = 'https://calendar.google.com/calendar/event?eid=...'
WHERE id = 1;
```

L’organisateur affiché est `BDE ORT Sup` lorsque `organizer_name` est vide ou vaut `NULL`.
Ce champ ne doit être renseigné que lorsqu’un événement est exceptionnellement organisé
par une autre structure ; aucune page séparée d’organisateurs n’est nécessaire.

Le champ `google_calendar_url` est facultatif. Il peut contenir le lien public publié depuis
Google Agenda pour ouvrir exactement l’événement correspondant. Sans ce lien, le bouton de
la page Calendrier lance une recherche Google Agenda à partir du titre enregistré dans SQLite.
Le contenu de l’iframe Google est isolé du site : le navigateur ne permet pas au JavaScript
local de sélectionner automatiquement un événement à l’intérieur de cette iframe.
Après la création d’un événement par un administrateur, le site fournit également un lien
Google Agenda prérempli. L’administrateur doit confirmer sa création dans Google. Une écriture
automatique nécessitera ultérieurement Google Calendar API, OAuth et des identifiants dédiés.

## Comptes et autorisations

Trois niveaux sont disponibles :

- `member` : accès à l’espace personnel ;
- `admin` : création d’événements, création de comptes et modification des rôles ;
- `superadmin` : mêmes droits, compte protégé contre toute modification depuis l’administration.

Les administrateurs peuvent promouvoir un compte en administrateur ou le repasser membre.
Ils ne peuvent ni modifier ni rétrograder le superadministrateur protégé. Les mots de passe
sont hashés par Werkzeug et ne sont jamais affichés dans l’administration.

Pour créer le premier supercompte dans une nouvelle base :

```bash
python3 backend/manage.py create-superadmin --username Ary
```

La commande demande le mot de passe deux fois sans l’afficher. Le secret de signature des
sessions est généré dans `db/.session-secret`, ignoré par Git. En hébergement, définir plutôt
`BDE_SECRET_KEY` et activer les cookies HTTPS avec `BDE_COOKIE_SECURE=1`.

Les quatre clés des chiffres d’accueil sont `poles_count`, `members_count`,
`years_count` et `institution_since`. Une valeur de zéro est conservée et affichée.

Les valeurs par défaut se trouvent dans `DEFAULT_SETTINGS` dans `backend/database.py`.
Modifier ces valeurs dans le code ne remplace pas un réglage déjà enregistré.
De même, modifier `backend/seed.py` ne met pas à jour les lignes d’une base existante.

### Initialiser ou conserver les données

`python3 backend/seed.py` crée les tables et remplit les collections encore entièrement vides.
Il ne remplace pas et ne duplique pas une collection qui contient déjà des lignes.
Démarrer Flask crée au besoin les tables et réglages, sans ajouter d’événements ni d’articles.

Pour repartir des exemples, arrêter Flask, sauvegarder la base ailleurs et déplacer
l’ancien fichier hors du dossier `db/`, puis exécuter à nouveau le script de remplissage.
Le nettoyage du projet n’a pas réinitialisé la base existante.

## API JSON

| Route GET | Réponse |
| --- | --- |
| `/api/health` | État du serveur |
| `/api/site` | Réglages du site |
| `/api/events` | Événements publiés avec leur organisateur |
| `/api/products` | Produits actifs |
| `/api/stats` | Nombre total d’événements et de produits |

Les pages et l’API utilisent les mêmes requêtes dans `backend/database.py`. Les routes qui
écrivent des comptes ou des événements sont protégées par session, rôle et jeton CSRF.

## Vérifications

```bash
python3 -B -m unittest discover -s tests -v
```

Ces vérifications utilisent une base SQLite temporaire ; elles ne modifient pas la base locale.
Elles contrôlent les pages et ressources, les données rendues dans le HTML, l’échappement,
les filtres de l’API, la connexion, les rôles, la protection du supercompte, les jetons CSRF
et la création d’événements.

## Nettoyage effectué

Le projet n’utilise plus les chunks Next.js/React/Turbopack ni les feuilles de styles compilées.
Les données d’hydratation, commentaires du miroir, scripts Cloudflare, anciens membres,
anciens événements codés en dur, liens d’authentification et intégrations externes du clone
ont été retirés. Les faux PDF et la fausse vidéo (fichiers contenant « 404 Not Found »),
les photos d’événements inutilisées et l’ancienne page d’association à identifiant fixe
ont également été supprimés.

La photo d’accueil, les deux logos et les deux polices utilisées ont été conservés et rangés
dans `static/`. Les réglages personnels d’Obsidian sont conservés et ignorés par Git.

Les documents officiels, les référents et les membres ORT seront ajoutés avec leurs vraies
informations. Aucun ancien document n’est présenté comme un document ORT.

## Suite du développement

1. Renseigner les vrais textes, images, contacts et chiffres.
2. Développer les fiches des membres et les inscriptions aux événements.
3. Configurer OAuth si la création automatique dans Google Agenda devient nécessaire.
4. Construire les inscriptions, commandes et paiements selon les besoins.
5. Choisir la base et l’hébergement de production, puis préparer le déploiement.

Le serveur Flask de développement ne doit pas être utilisé tel quel en production.
La configuration HTTPS, les secrets, les sauvegardes et un serveur applicatif de production
seront préparés lors de cette étape. Ne pas enregistrer de secrets ni de données personnelles
d’étudiants dans les fichiers HTML ou dans Git.
