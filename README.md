# BDE ORT Sup

Site local du bureau des élèves de l’ORT Sup à Montreuil.

Le projet repose sur **Flask, des modèles HTML Jinja, du CSS, du JavaScript natif et SQLite**.
Les pages sont rendues directement par Flask : les textes et les données sont présents dès
la première réponse du serveur.

Adresse du campus : **43 Rue Raspail, 93100 Montreuil**.

## État du site

- Accueil : image, texte, indicateur de défilement animé, présentation, chiffres et événements.
- Fenêtre de bienvenue à chaque chargement de l’accueil, fermable par la croix, Échap ou un clic à l’extérieur.
- Navigation responsive, masquée en descendant et réaffichée en remontant.
- Associations, événements, boutique et agenda alimentés par SQLite.
- Thème bleu ORT, logos et polices servis localement.
- Pages BDE, REC, connexion et projet associatif prêtes à être complétées.
- API JSON conservée pour les prochaines fonctionnalités.

L’agenda présente actuellement une liste chronologique. Le calendrier mensuel, les fiches
d’associations, les comptes, l’administration, les commandes et les paiements restent à développer.
Aucun bouton de connexion ou de paiement ne prétend effectuer une opération disponible.

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
│   ├── seed.py                # Associations, événements et produits de démonstration
│   └── requirements.txt       # Dépendances Python
├── db/
│   └── bde-ort-sup.db          # Base locale, ignorée par Git
├── pages/
│   ├── base.html              # Structure HTML commune
│   ├── partials/
│   │   ├── header.html        # Navigation
│   │   ├── footer.html        # Contacts et liens
│   │   └── events.html        # Cartes d’événements communes
│   ├── index.html
│   ├── associations.html
│   ├── evenements.html
│   ├── billetterie.html
│   ├── calendrier.html
│   ├── bde.html
│   ├── rec.html
│   ├── login.html
│   ├── demande-domaine.html
│   └── 404.html
├── static/
│   ├── css/site.css           # Styles, thème et responsive
│   ├── js/site.js             # Navigation et dialogue de bienvenue
│   ├── fonts/                # Inter et Bricolage Grotesque, variantes latines
│   └── images/               # Deux logos ORT et la photo d’accueil
├── tests/test_site.py         # Vérifications sur une base temporaire
├── .gitignore
└── README.md
```

Les fichiers HTML sont indentés et répartis par page. Jinja permet de partager les blocs
communs et d’insérer les valeurs provenant de SQLite. Il faut ouvrir les pages via Flask :
un double-clic sur un fichier HTML ne peut pas interpréter les balises Jinja.

Les URL des pages restent `/associations.html`, `/evenements.html`, etc.
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
aussi sans JavaScript ; seul le menu compact et le dialogue nécessitent ce script.

## Base de données

Le fichier est `db/bde-ort-sup.db`. Il contient :

| Table | Contenu |
| --- | --- |
| `site_settings` | Nom, slogan, adresse, contacts, liens, compteurs |
| `associations` | Associations, catégories et contacts |
| `events` | Événements, horaires, lieux, capacités et prix |
| `products` | Articles, descriptions, stocks et prix |

Les prix sont enregistrés en centimes. Les dates sont au format ISO 8601 avec
décalage horaire, puis affichées en français dans le fuseau Europe/Paris.
Seuls les événements publiés et les produits actifs sont affichés. L’accueil montre
au maximum trois événements à venir ou en cours ; les pages Événements et Calendrier
présentent tous les événements publiés.

### Modifier les valeurs affichées

Ouvrir la base avec un éditeur SQLite et modifier les lignes souhaitées, puis recharger
la page. Exemple SQL :

```sql
UPDATE site_settings SET value = '24' WHERE key = 'members_count';
UPDATE site_settings SET value = '2026' WHERE key = 'institution_since';
UPDATE site_settings SET value = '0' WHERE key = 'years_count';
UPDATE events SET title = 'Nouvelle soirée du BDE' WHERE id = 1;
```

Les quatre clés des chiffres d’accueil sont `poles_count`, `members_count`,
`years_count` et `institution_since`. Une valeur de zéro est conservée et affichée.

Les valeurs par défaut se trouvent dans `DEFAULT_SETTINGS` dans `backend/database.py`.
Modifier ces valeurs dans le code ne remplace pas un réglage déjà enregistré.
De même, modifier `backend/seed.py` ne met pas à jour les lignes d’une base existante.

### Initialiser ou conserver les données

`python3 backend/seed.py` crée les tables et remplit une nouvelle base.
Il n’ajoute pas de doublons lorsqu’une association existe déjà.
Démarrer Flask crée au besoin les tables et réglages, sans ajouter d’événements ni d’articles.

Pour repartir des exemples, arrêter Flask, sauvegarder la base ailleurs et déplacer
l’ancien fichier hors du dossier `db/`, puis exécuter à nouveau le script de remplissage.
Le nettoyage du projet n’a pas réinitialisé la base existante.

## API JSON

| Route GET | Réponse |
| --- | --- |
| `/api/health` | État du serveur |
| `/api/site` | Réglages du site |
| `/api/associations` | Associations |
| `/api/events` | Événements publiés avec leur association |
| `/api/products` | Produits actifs avec leur association |
| `/api/stats` | Nombre total d’associations, événements et produits |

Les pages et l’API utilisent les mêmes requêtes dans `backend/database.py`.
Il n’existe pas encore de routes d’écriture ou d’authentification.

## Vérifications

```bash
python3 -B -m unittest discover -s tests -v
```

Ces vérifications utilisent une base SQLite temporaire ; elles ne modifient pas la base locale.
Elles contrôlent les pages et ressources, les données rendues dans le HTML, l’échappement
des textes, les listes vides, les filtres de l’API et la conservation des données existantes.

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
2. Développer les fiches d’associations, membres et événements.
3. Ajouter l’administration et les comptes avec les droits d’accès nécessaires.
4. Construire les inscriptions, commandes et paiements selon les besoins.
5. Choisir la base et l’hébergement de production, puis préparer le déploiement.

Le serveur Flask de développement ne doit pas être utilisé tel quel en production.
La configuration HTTPS, les secrets, les sauvegardes et un serveur applicatif de production
seront préparés lors de cette étape. Ne pas enregistrer de secrets ni de données personnelles
d’étudiants dans les fichiers HTML ou dans Git.
