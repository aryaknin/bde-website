# BDE ORT Sup

Site local du bureau des élèves de l’ORT Sup à Montreuil.

Le projet repose sur **Flask, des modèles HTML Jinja, du CSS, du JavaScript natif et SQLite**.
Les pages sont rendues directement par Flask : les textes et les données sont présents dès
la première réponse du serveur.

Adresse du campus : **43 Rue Raspail, 93100 Montreuil**.

## État du site

- Accueil : image, texte, indicateur de défilement animé, présentation, chiffres et événements.
- Fenêtre de bienvenue à la première visite de l’accueil, puis masquée pendant 24 heures dans ce navigateur (cookie `bde_welcome_seen`), fermable par la croix, Échap ou un clic à l’extérieur.
- Compteur de membres calculé à partir des profils BDE visibles, actualisé toutes les 10 secondes sur l’accueil et au retour dans l’onglet.
- Navigation responsive, masquée en descendant et réaffichée en remontant, avec transitions de page.
- Événements et boutique alimentés par SQLite.
- Boutique avec fiches articles, photos, prix, stocks, paniers persistants et suivi des commandes.
- Gestion du catalogue et des stocks réservée aux administrateurs et au superadministrateur.
- Cartes d’événements ouvrant une fiche détaillée avec un accès au calendrier.
- Thème bleu ORT, logos et polices servis localement.
- Connexion par session, comptes membres, membres du BDE, administrateurs et superadministrateur protégé.
- Inscription publique par identifiant, e-mail et mot de passe, limitée au rôle membre.
- Création de comptes et gestion des droits depuis l’administration ; ajout d’événements par l’équipe BDE.
- Suivi annuel des cotisations avec statut, montant, historique et gestion administrative.
- Annuaire public du BDE avec portraits, fonctions, biographies, liens et fiches détaillées.
- Modification de son profil public depuis l’espace personnel et gestion complète depuis l’administration.
- Préparation d’un événement Google Agenda à partir d’un événement créé sur le site.
- API JSON conservée pour les prochaines fonctionnalités.

Le calendrier mensuel Google est intégré dans un cadre responsive. Lorsqu’un événement est
ouvert depuis la page Événements, sa fiche est mise en avant au-dessus du calendrier.
Les commandes peuvent être préparées et suivies ; le paiement réel et la synchronisation
Google OAuth restent à intégrer. Une commande ne devient jamais payée depuis le navigateur.
L’espace cotisation est prêt à recevoir un lien HelloAsso, mais aucun bouton ne prétend
effectuer un paiement tant que cette URL n’est pas configurée.

Les chiffres renseignés sont 1 pôle, 105 ans d’histoire pour ORT France et une création en
1921. Le nombre de membres correspond à la galerie BDE : les profils masqués sont exclus,
les profils ajoutés manuellement sont inclus s’ils sont visibles. Les comptes membres
simples sans profil BDE ne font pas partie de ce compteur. La cotisation est de 5 €.
Les événements et les autres articles, e-mails et réseaux sociaux restent des exemples.
La photo d’accueil est conservée comme visuel provisoire.

## Installation locale

Prérequis : Python 3.10 ou supérieur, pip et un navigateur. Pillow est installé avec les
dépendances pour valider et convertir les portraits envoyés.

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
│   ├── shop.py                # Routes boutique, formulaires et photos des articles
│   ├── shop_store.py          # Paniers, commandes, réservations et futur paiement vérifié
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
│   ├── shop/                 # Fiches articles, panier, commandes et administration
│   ├── index.html
│   ├── evenements.html
│   ├── billetterie.html
│   ├── calendrier.html
│   ├── bde.html
│   ├── login.html
│   ├── register.html
│   ├── account.html
│   ├── admin.html
│   ├── error.html
│   ├── demande-domaine.html
│   └── 404.html
├── static/
│   ├── css/site.css           # Styles, thème et responsive
│   ├── css/shop.css           # Catalogue, panier et gestion boutique
│   ├── js/site.js             # Navigation et fenêtres de dialogue
│   ├── fonts/                 # Inter et Bricolage Grotesque, variantes latines
│   ├── images/                # Deux logos ORT et la photo d’accueil
│   └── uploads/               # members/ et products/ : images ignorées par Git
├── tests/test_site.py         # Vérifications sur une base temporaire
├── tests/test_shop.py         # Stocks, rôles, paniers, commandes et paiement interne
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

Les styles ne sont plus injectés par JavaScript. Les textes, logos et compteurs sont rendus
par Flask ; JavaScript rafraîchit uniquement les compteurs d’accueil depuis l’API. L’affichage des données fonctionne
aussi sans JavaScript ; le menu compact, les fenêtres et les transitions enrichies utilisent ce script.

## Base de données

Le fichier est `db/bde-ort-sup.db`. Il contient :

| Table | Contenu |
| --- | --- |
| `site_settings` | Nom, slogan, adresse, contacts, liens, compteurs |
| `associations` | Organisateurs internes liés aux événements et articles |
| `events` | Événements, horaires, lieux, organisateur facultatif, capacités, prix et lien Google |
| `products` | Articles, descriptions, stocks et prix |
| `shop_carts`, `shop_cart_items` | Paniers invités et comptes, avec leurs quantités |
| `shop_orders`, `shop_order_items` | Commandes, états, réservations et lignes figées |
| `users` | Identifiants, e-mails, hash des mots de passe, rôles et protection du supercompte |
| `bde_profiles` | Profils publics, fonctions, biographies, liens, photos, ordre et visibilité |
| `contributions` | Cotisations annuelles, montants, statuts, dates, références et notes internes |
| `schema_migrations` | Mises à jour de données déjà appliquées, pour ne pas les répéter au démarrage |

Les prix sont enregistrés en centimes. Les dates sont au format ISO 8601 avec
décalage horaire, puis affichées en français dans le fuseau Europe/Paris.
Seuls les événements publiés et les produits actifs sont affichés. L’accueil montre
au maximum trois événements à venir ou en cours ; la page Événements présente tous les
événements publiés. Le calendrier mensuel est fourni par Google Agenda.

### Modifier les valeurs affichées

Ouvrir la base avec un éditeur SQLite et modifier les lignes souhaitées, puis recharger
la page. Exemple SQL :

```sql
UPDATE site_settings SET value = '1' WHERE key = 'poles_count';
UPDATE site_settings SET value = '1921' WHERE key = 'institution_since';
UPDATE site_settings SET value = '105' WHERE key = 'years_count';
UPDATE events SET title = 'Nouvelle soirée du BDE' WHERE id = 1;
UPDATE events SET organizer_name = 'Partenaire exceptionnel' WHERE id = 1;
UPDATE events
SET google_calendar_url = 'https://calendar.google.com/calendar/event?eid=...'
WHERE id = 1;
UPDATE site_settings SET value = '500' WHERE key = 'membership_fee_cents';
UPDATE site_settings
SET value = 'https://www.helloasso.com/associations/votre-bde/adhesions/cotisation'
WHERE key = 'helloasso_membership_url';
```

`membership_fee_cents` est exprimé en centimes : `500` correspond à 5 €. Tant que
`helloasso_membership_url` est vide, l’espace personnel affiche clairement que le paiement
en ligne n’est pas encore disponible.

L’organisateur affiché est `BDE ORT Sup` lorsque `organizer_name` est vide ou vaut `NULL`.
Ce champ ne doit être renseigné que lorsqu’un événement est exceptionnellement organisé
par une autre structure ; aucune page séparée d’organisateurs n’est nécessaire.

Le champ `google_calendar_url` est facultatif. Il peut contenir le lien public publié depuis
Google Agenda pour ouvrir exactement l’événement correspondant. Sans ce lien, le bouton de
la page Calendrier lance une recherche Google Agenda à partir du titre enregistré dans SQLite.
Le contenu de l’iframe Google est isolé du site : le navigateur ne permet pas au JavaScript
local de sélectionner automatiquement un événement à l’intérieur de cette iframe.
Après la création d’un événement par un administrateur ou un membre du BDE, le site fournit
également un lien Google Agenda prérempli. La personne doit confirmer sa création dans Google. Une écriture
automatique nécessitera ultérieurement Google Calendar API, OAuth et des identifiants dédiés.

## Comptes et autorisations

Quatre niveaux sont disponibles :

- `member` : accès à l’espace personnel ;
- `bde` : profil public modifiable et création d’événements, sans gestion des comptes ;
- `admin` : création d’événements, création de comptes et modification des rôles ;
- `superadmin` : mêmes droits, compte protégé contre toute modification depuis l’administration.

Les administrateurs peuvent attribuer les rôles membre, membre du BDE ou administrateur.
Ils ne peuvent ni modifier ni rétrograder le superadministrateur protégé. Les mots de passe
sont hashés par Werkzeug et ne sont jamais affichés dans l’administration.

La page `/register.html` permet à un étudiant de créer son propre compte. Le serveur impose
toujours le rôle `member`, même si une autre valeur est envoyée manuellement. L’e-mail et
l’identifiant sont uniques, le mot de passe doit contenir au moins huit caractères et le
nouveau compte reçoit automatiquement sa cotisation pour l’année scolaire en cours. La
connexion accepte ensuite l’identifiant ou l’adresse e-mail.

L’espace personnel présente la cotisation actuelle et l’historique. Les statuts disponibles
sont `due` (à régler), `pending` (en attente), `paid` (payée) et `exempt` (exonérée). L’onglet
« Cotisations » de l’administration permet d’ajouter une année et de corriger le montant,
le statut, la date, le moyen de paiement, la référence externe et une note interne. Un
administrateur ordinaire ne peut pas modifier les cotisations du supercompte protégé.

Les comptes `bde`, `admin` et `superadmin` obtiennent automatiquement un profil sur la page
BDE. Un administrateur peut le masquer, modifier sa fonction et son ordre, ou créer un profil
manuel sans compte. Un profil lié à un compte se masque au lieu d’être supprimé. Un
administrateur ordinaire ne peut pas modifier le profil du supercompte protégé.

Depuis son espace, chaque personne de l’équipe peut modifier son nom public, sa biographie,
ses liens et son portrait. Les images JPEG, PNG et WebP de moins de 8 Mo sont recadrées au
format portrait et converties en WebP côté serveur. Les fichiers d’upload sont exclus de Git :
ils devront être sauvegardés séparément et placés sur un stockage persistant en production.

Pour créer le premier supercompte dans une nouvelle base :

```bash
python3 backend/manage.py create-superadmin --username Ary
```

La commande demande le mot de passe deux fois sans l’afficher. Le secret de signature des
sessions est généré dans `db/.session-secret`, ignoré par Git. En hébergement, définir plutôt
`BDE_SECRET_KEY` et activer les cookies HTTPS avec `BDE_COOKIE_SECURE=1`.

Les réglages d’accueil sont `poles_count`, `years_count` et `institution_since`.
`members_count` est calculé à chaque lecture par un `COUNT(*)` des profils BDE dont
`is_visible = 1`. Une ancienne valeur fixe dans les réglages n’a plus d’effet.
Une valeur de zéro est conservée et affichée. Pour retirer une personne du compteur,
utiliser « Masquer » dans Administration → Page BDE.

Les valeurs par défaut se trouvent dans `DEFAULT_SETTINGS` dans `backend/database.py`.
Modifier ces valeurs dans le code ne remplace pas un réglage déjà enregistré.
De même, modifier `backend/seed.py` ne met pas à jour les lignes d’une base existante.
Une migration ponctuelle applique les valeurs validées le 16 septembre 2026, corrige
l’adhésion de la boutique et les anciennes échéances à régler de 15 € pour 2026-2027.
Les cotisations payées, exonérées, en attente et celles des autres années sont conservées.

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
| `/api/home-stats` | Nombre de profils BDE visibles, pôles et années d’histoire, sans cache |

Les pages et l’API utilisent les mêmes requêtes dans `backend/database.py`. Les routes qui
écrivent des comptes ou des événements sont protégées par session, rôle et jeton CSRF.

## Boutique et commandes

### Gestion par les administrateurs

Depuis **Mon compte → Gérer la boutique**, ou **Administration → Boutique** :

- Ajouter un article avec titre, description, image JPEG/PNG/WebP, prix en euros et stock.
- Modifier les informations et remplacer l’image (8 Mo maximum, conversion WebP jusqu’à 1 600 px).
- Mettre à jour directement le stock : **0 = épuisé**, **vide = illimité**.
- Masquer/publier un article sans supprimer ses anciennes commandes.
- Consulter toutes les commandes et, après paiement vérifié, les marquer prêtes puis retirées.

Seuls `admin` et `superadmin` ont ces droits. Le rôle `bde` ne gère pas la boutique.
Les articles déjà présents sont conservés ; ceux sans photo affichent un visuel d’attente.
Pour des variantes (par exemple S, M, L), créer un article par variante afin de suivre
chaque stock séparément. Le type « Cotisation » renvoie vers l’espace cotisations :
il n’est pas commandable dans le panier, pour éviter une adhésion non rattachée au compte.

### Parcours client

1. Parcourir `/billetterie.html`, ouvrir une fiche et ajouter les quantités souhaitées.
2. Modifier/retirer les articles dans `/panier.html` ; tous les totaux sont recalculés côté serveur.
3. Se connecter ou créer un compte pour accéder au récapitulatif `/commande.html`.
4. Préparer la commande : elle apparaît dans `/commandes.html` et **attend un paiement**.
5. Après le futur paiement vérifié, retrait gratuit au BDE, à l’adresse du campus.

Le panier invité est enregistré en SQLite, identifié par un cookie opaque `bde_cart`
HttpOnly/SameSite=Lax de **90 jours** (seul son hash est en base). Le panier d’un compte
est conservé en base, fusionné avec le panier invité à la connexion ou à l’inscription,
et accessible sur les autres appareils après connexion. La déconnexion ne l’expose pas
au visiteur suivant. Effacer les cookies fait perdre l’accès à un panier invité.

Le panier seul ne réserve aucun stock. La préparation réserve les articles **30 minutes**,
avec une vérification atomique SQLite pour empêcher deux commandes d’obtenir le dernier
exemplaire. Les réservations expirées sont immédiatement exclues du stock réservé ; leur
statut est actualisé à la lecture des commandes. Aucun cron n’est nécessaire en local.
L’annulation libère aussi les réservations. Le stock physique n’est décrémenté qu’après
confirmation de paiement. Un admin ne peut pas le réduire sous les réservations actives.

Les prix et intitulés de la commande sont figés ; une modification ultérieure du catalogue
ne change pas l’historique. Si un prix change entre le récapitulatif et sa validation, la
commande est refusée et le client doit revoir le panier. Un double clic ne duplique pas
la commande. Limites : 99 unités par article, 50 articles distincts par panier et trois
commandes en attente par compte.

### Paiement : volontairement désactivé

**Aucun paiement réel n’est disponible.** Le bouton l’indique explicitement et les
commandes de préparation expirent sans être confirmées. Aucun formulaire ne collecte
de carte bancaire et aucune route ne permet de déclarer soi-même un achat payé.

`shop_store.confirm_verified_payment(...)` est un point d’intégration **interne**, testé
sur des bases temporaires et non exposé en HTTP. Quand le prestataire sera choisi, il
faudra ajouter la création de session de paiement et un webhook authentifié : vérification
de signature, statut réellement encaissé, compte marchand, commande, montant en centimes,
devise EUR et référence unique. Cette fonction valide montant/devise et assure l’idempotence
ainsi que la déduction atomique du stock. Elle ne vérifie pas elle-même une signature de prestataire.
Le retour du navigateur depuis le paiement ne doit jamais suffire à confirmer une commande.
Les remboursements, paiements tardifs après expiration et notifications restent à intégrer
avec ce prestataire avant toute mise en production.

Sauvegarder ensemble `db/` et `static/uploads/`, dont les photos produits ne sont pas dans Git.
Les migrations ajoutent les tables automatiquement au démarrage sans réinitialiser la base.

## Vérifications

```bash
python3 -B -m unittest discover -s tests -v
```

Ces vérifications utilisent une base SQLite temporaire ; elles ne modifient pas la base locale.
Elles contrôlent les pages et ressources, les données rendues dans le HTML, l’échappement,
les filtres de l’API, l’inscription, la connexion, les quatre rôles, la protection du
supercompte, les jetons CSRF, la création d’événements, les cotisations, les profils publics
et la validation des portraits. Les tests boutique couvrent aussi les images, le panier
persistant et sa fusion, les permissions admin, les ruptures de stock, deux commandes
simultanées, les changements de prix, les doubles soumissions, l’expiration, l’annulation,
la confidentialité des commandes et l’idempotence du futur paiement vérifié.

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
2. Renseigner les fonctions, biographies, liens et véritables portraits des membres du BDE.
3. Configurer OAuth si la création automatique dans Google Agenda devient nécessaire.
4. Choisir le prestataire, relier les cotisations et les paiements boutique avec webhooks vérifiés.
5. Choisir la base et l’hébergement de production, puis préparer le déploiement.

Le serveur Flask de développement ne doit pas être utilisé tel quel en production.
La configuration HTTPS, les secrets, les sauvegardes et un serveur applicatif de production
seront préparés lors de cette étape. Ne pas enregistrer de secrets ni de données personnelles
d’étudiants dans les fichiers HTML ou dans Git.
