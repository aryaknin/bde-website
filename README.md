# BDE ORT Sup

Site du Bureau des Élèves de l’ORT Sup Montreuil. C’est une application Flask rendue côté serveur avec des templates Jinja, une base SQLite et des fichiers statiques locaux. Elle est pensée pour le développement local puis le déploiement sur VPS.

Adresse : **43 Rue Raspail, 93100 Montreuil**.

## Références réelles du projet

Ces valeurs correspondent à l’installation actuelle. Les commandes ci-dessous peuvent être copiées-collées telles quelles depuis ce README.

| Élément | Valeur actuelle |
| --- | --- |
| Dossier local | `/home/ary/Bureau/BTS SIO/1ère année/BDE/bde-website` |
| Dépôt Git | `git@github.com:aryaknin/bde-website.git` |
| Branche à déployer | `main` |
| VPS | `51.210.254.136` |
| Connexion SSH | `ubuntu@51.210.254.136` |
| Dossier projet sur VPS | `/srv/bde-website` |
| Utilisateur de l’application | `bde` |
| Service Flask/Gunicorn | `bde-website` |
| Base de production | `/srv/bde-website/db/bde-ort-sup.db` |
| Fichiers envoyés | `/srv/bde-website/static/uploads/` |
| Visuels/logos | `/srv/bde-website/static/images/` |
| Application interne | `127.0.0.1:8000` |
| Site public | `bde-ortmontreuil.fr` |

Pour aller directement dans le projet local :

```bash
cd "/home/ary/Bureau/BTS SIO/1ère année/BDE/bde-website"
```

Pour ouvrir une session sur le VPS :

```bash
ssh ubuntu@51.210.254.136
```

## Fonctionnalités

- Identité ORT Sup : thème bleu, logos ORT, polices et visuels locaux.
- Accueil animé, navigation responsive et popup de bienvenue limitée à une fois toutes les 24 heures.
- Événements SQLite, détails en fenêtre modale et lien vers le calendrier Google intégré.
- Comptes avec les rôles `member`, `bde`, `admin` et `superadmin`.
- Annuaire BDE : photo, fonction, biographie, liens personnels et visibilité contrôlable.
- Espace personnel : profil, cotisation, panier et commandes.
- Administration : comptes, droits, profils BDE, cotisations, événements, boutique et commandes.
- Boutique : catalogue, photos, stock, panier persistant, réservation de stock et suivi des commandes.

Le paiement en ligne n’est pas encore relié à un prestataire. Une commande est préparée et le stock peut être réservé, mais elle ne peut pas être déclarée payée depuis le navigateur.

## Installation locale

Prérequis : Python 3.10+, `pip` et un navigateur. Node.js, npm et Prisma ne sont pas nécessaires.

Depuis le dossier du projet :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python3 backend/seed.py
python3 backend/manage.py create-superadmin --username VotreIdentifiant
python3 backend/app.py
```

Ouvre ensuite [http://127.0.0.1:5000](http://127.0.0.1:5000). Sous Windows, active l’environnement avec `.venv\Scripts\Activate.ps1`, puis utilise `python` si besoin.

Pour utiliser un autre port :

```bash
FLASK_PORT=5001 python3 backend/app.py
```

La première exécution crée `db/bde-ort-sup.db`, les tables nécessaires et un secret de session local dans `db/.session-secret`. Ne versionne jamais ces fichiers. `backend/seed.py` ajoute des données de démonstration uniquement quand les collections sont vides : ne l’utilise pas sur une base de production existante.

### Routine locale de développement

À chaque reprise de travail, utilise cette séquence :

```bash
cd "/home/ary/Bureau/BTS SIO/1ère année/BDE/bde-website"
source .venv/bin/activate
./scripts/sync-production-data.sh
python3 backend/app.py
```

La synchronisation demande le mot de passe `sudo` du VPS si nécessaire. Laisse le terminal Flask ouvert pendant le développement, puis utilise un second terminal pour Git ou les tests.

Pour vérifier rapidement le statut local et lancer les tests :

```bash
cd "/home/ary/Bureau/BTS SIO/1ère année/BDE/bde-website"
git status
source .venv/bin/activate
python3 -m unittest discover -s tests -v
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Les tests couvrent les rôles, événements, profils BDE, panier, stock, commandes et protections de paiement.

## Organisation

```text
bde-website/
├── backend/                 # Flask, SQLite et logique métier
│   ├── app.py               # Routes générales et point d’entrée
│   ├── database.py          # Schéma, migrations et requêtes
│   ├── shop.py              # Routes boutique
│   ├── shop_store.py        # Paniers, commandes, réservations
│   ├── manage.py            # Commandes d’administration
│   ├── seed.py              # Données de démonstration
│   └── requirements.txt
├── db/                      # SQLite et secret local, ignorés par Git
├── pages/                   # Templates Jinja
│   ├── partials/            # Navigation, pied de page, composants événements
│   └── shop/                # Catalogue, panier et gestion boutique
├── static/
│   ├── css/                 # site.css et shop.css
│   ├── js/site.js           # Interactions et transitions
│   ├── fonts/               # Polices locales
│   ├── images/              # Logos et visuels éditoriaux
│   └── uploads/             # Portraits et images produits, ignorés par Git
├── scripts/sync-production-data.sh
├── tests/
├── DEPLOYMENT.md            # Guide VPS détaillé
└── README.md
```

## Pages

| Page | Adresse | Rôle |
| --- | --- | --- |
| Accueil | `/index.html` | Présentation, statistiques et événements à venir. |
| Boutique | `/billetterie.html` | Catalogue, produits et cotisations. |
| Événements | `/evenements.html` | Liste, détail et accès calendrier. |
| Calendrier | `/calendrier.html` | Google Calendar public intégré. |
| BDE | `/bde.html` | Annuaire public des membres du BDE. |
| Connexion / inscription | `/login.html`, `/register.html` | Authentification. |
| Compte | `/compte.html` | Profil, cotisation, panier et commandes. |
| Administration | `/admin.html` | Gestion selon les permissions. |

La navigation se masque lors d’un défilement vers le bas et réapparaît en remontant. Les liens restent utilisables à toute position de la page.

## Rôles

| Rôle | Permissions |
| --- | --- |
| `member` | Compte, profil, panier, commandes et cotisation. |
| `bde` | Permissions membre, profil BDE et ajout d’événements. |
| `admin` | Comptes, profils BDE, cotisations, événements, catalogue, stocks et commandes. |
| `superadmin` | Tous les droits et gestion du compte superadministrateur protégé. |

L’inscription publique crée uniquement des comptes `member`. Un administrateur peut attribuer les rôles BDE et administrateur, mais ne peut pas modifier le superadministrateur protégé. N’écris jamais des identifiants, mots de passe ou clés API dans Git, ce fichier ou une capture publique.

Les comptes BDE, administrateurs et superadministrateurs peuvent apparaître dans l’annuaire. Les administrateurs peuvent également créer un profil manuel et définir sa visibilité, sa photo, sa fonction, sa biographie et ses liens.

## Base de données et contenu

La base locale par défaut est `db/bde-ort-sup.db`. Elle contient notamment utilisateurs, profils BDE, événements, cotisations, produits, paniers et commandes. `backend/database.py` initialise les tables et applique les évolutions légères au démarrage.

Les statistiques de l’accueil utilisent ces données :

- **Membres** : profils BDE visibles uniquement ; un profil masqué n’est pas compté.
- **Pôles** : 1.
- **ORT France** : 105 ans d’histoire, depuis 1921.
- **Cotisation BDE** : 5 €.

L’organisateur par défaut d’un événement est **BDE ORT Sup**. Il peut être remplacé ponctuellement dans le formulaire d’événement.

## Images et téléversements

`static/images/` contient les logos et visuels éditoriaux. `static/uploads/members/` contient les portraits BDE et `static/uploads/products/` les images produits. Les chemins de ces images sont enregistrés dans SQLite.

Copier la BDD seule ne suffit pas : sans `static/uploads/` et `static/images/`, les photos référencées provoqueront des erreurs 404. Sauvegarde toujours la base et ces dossiers ensemble.

## Événements et calendrier Google

Les événements affichés sur le site proviennent de SQLite. Leur fiche affiche titre, description, date, lieu et organisateur. Le bouton « Voir dans le calendrier » ouvre le calendrier Google et tente une recherche par titre.

Le calendrier actuel est une intégration publique par `iframe`. La création automatique d’événements dans Google nécessite à terme OAuth Google, un compte de service ou les autorisations appropriées : aucun mot de passe personnel ne doit être placé dans le code.

## Boutique et paiement

Les administrateurs et superadministrateurs créent et modifient les produits : titre, description, prix, stock, visibilité et image. Un produit peut être un article ou une cotisation.

Le panier persiste pour un visiteur puis est fusionné au compte à la connexion. La validation d’une commande réserve le stock temporairement. Le paiement reste volontairement désactivé jusqu’au choix d’un prestataire.

Quand HelloAsso, Stripe ou un autre service sera choisi, seul un webhook authentifié côté serveur devra confirmer le paiement : validation de signature, référence, montant et devise avant de marquer une commande payée. Ne crée pas de bouton qui simule un paiement.

## Récupérer la BDD et les assets du VPS

Pour mettre à jour ton environnement local avec les données de production et toutes les images associées, arrête d’abord Flask local puis lance :

```bash
cd "/home/ary/Bureau/BTS SIO/1ère année/BDE/bde-website"
./scripts/sync-production-data.sh
```

Le script récupère une copie SQLite ainsi que `static/uploads/` et `static/images/`, sans toucher à ton code local. Il crée une sauvegarde dans `local-backups/production-sync-...`, vérifie l’intégrité SQLite, les comptes d’objets et la présence des images référencées avant d’écraser les données locales. Une base distante vide ou une archive d’assets incomplète est refusée.

Le script utilise déjà les valeurs réelles suivantes :

```text
BDE_VPS_HOST=ubuntu@51.210.254.136
BDE_VPS_PROJECT=/srv/bde-website
BDE_VPS_ARCHIVE_DIR=/home/ubuntu
```

Pré-requis : accès SSH à `ubuntu@51.210.254.136` et autorisation `sudo` sur le VPS. Cette version explicite est strictement équivalente à la commande courte et peut être utilisée telle quelle :

```bash
BDE_VPS_HOST="ubuntu@51.210.254.136" \
BDE_VPS_PROJECT="/srv/bde-website" \
BDE_VPS_ARCHIVE_DIR="/home/ubuntu" \
./scripts/sync-production-data.sh
```

Cette commande synchronise les données **du VPS vers le local**. Elle ne déploie aucun code. Utilise Git pour le code et consulte [DEPLOYMENT.md](DEPLOYMENT.md) pour la procédure de déploiement complète.

### Ce que fait exactement le script

1. Il crée sur le VPS une copie SQLite cohérente avec `VACUUM INTO`, sans arrêter le site.
2. Il archive `static/uploads/` **et** `static/images/`.
3. Il télécharge cette archive sur le poste local et vérifie `PRAGMA integrity_check`.
4. Il compare les nombres d’utilisateurs, événements, produits et profils BDE.
5. Il vérifie que chaque image de profil ou produit enregistrée dans la base existe dans l’archive.
6. Il sauvegarde l’ancienne BDD locale et les anciens assets dans `local-backups/production-sync-AAAAmmjj-HHMMSS/`.
7. Seulement après ces vérifications, il remplace `db/bde-ort-sup.db` et extrait les images.

Si une étape échoue, la base locale n’est pas remplacée. Pour restaurer manuellement la dernière sauvegarde locale, remplace `DATE_DE_LA_SAUVEGARDE` par le nom réel du dossier :

```bash
cd "/home/ary/Bureau/BTS SIO/1ère année/BDE/bde-website"
cp "local-backups/production-sync-DATE_DE_LA_SAUVEGARDE/bde-ort-sup.db" db/bde-ort-sup.db
tar -xzf "local-backups/production-sync-DATE_DE_LA_SAUVEGARDE/static-data.tar.gz" -C static
```

## Déploiement

Le déploiement de référence utilise Gunicorn derrière Nginx, avec un utilisateur système dédié à l’application. Le guide [DEPLOYMENT.md](DEPLOYMENT.md) couvre la configuration VPS, systemd, Nginx, HTTPS, droits sur les uploads, sauvegardes et mises à jour.

Le code se met à jour par Git sur le serveur ; la base SQLite, les secrets et les fichiers téléversés restent hors Git. Fais une sauvegarde de la BDD et des assets avant toute mise à jour importante.

### Déployer une modification de code

Exécute d’abord les tests, puis envoie le code depuis le poste local :

```bash
cd "/home/ary/Bureau/BTS SIO/1ère année/BDE/bde-website"
source .venv/bin/activate
python3 -m unittest discover -s tests -v
git switch main
git add .
git commit -m "Décrire la modification"
git push origin main
```

Ensuite, déploie sur le VPS :

```bash
ssh ubuntu@51.210.254.136
sudo -u bde git -C /srv/bde-website pull --ff-only
sudo -u bde /srv/bde-website/.venv/bin/pip install -r /srv/bde-website/backend/requirements.txt
sudo systemctl restart bde-website
sudo systemctl status bde-website --no-pager
exit
```

Le statut final doit indiquer `active (running)`. `git pull --ff-only` est volontaire : il refuse un merge inattendu sur le serveur plutôt que de modifier le code de manière ambiguë.

### Sauvegarder la production avant une mise à jour risquée

Cette commande crée une copie cohérente de la BDD et une archive des images dans `/home/ubuntu/bde-backups/` sur le VPS :

```bash
ssh ubuntu@51.210.254.136 '
  set -e
  DATE=$(date +%Y%m%d-%H%M%S)
  mkdir -p /home/ubuntu/bde-backups
  sudo sqlite3 /srv/bde-website/db/bde-ort-sup.db ".backup /home/ubuntu/bde-backups/bde-ort-sup-$DATE.db"
  sudo tar -C /srv/bde-website/static -czf /home/ubuntu/bde-backups/static-$DATE.tar.gz uploads images
  sudo chown ubuntu:ubuntu /home/ubuntu/bde-backups/bde-ort-sup-$DATE.db /home/ubuntu/bde-backups/static-$DATE.tar.gz
  ls -lh /home/ubuntu/bde-backups/*$DATE*
'
```

Pour recopier ensuite une sauvegarde précise vers le poste local, remplace `DATE` par la date affichée par la commande précédente :

```bash
cd "/home/ary/Bureau/BTS SIO/1ère année/BDE/bde-website"
mkdir -p local-backups/manuel-DATE
scp ubuntu@51.210.254.136:/home/ubuntu/bde-backups/bde-ort-sup-DATE.db local-backups/manuel-DATE/
scp ubuntu@51.210.254.136:/home/ubuntu/bde-backups/static-DATE.tar.gz local-backups/manuel-DATE/
```

### Vérifier le serveur et diagnostiquer une erreur

```bash
ssh ubuntu@51.210.254.136 '
  sudo systemctl status bde-website nginx --no-pager
  sudo journalctl -u bde-website -n 100 --no-pager
  sudo nginx -t
  sudo sqlite3 /srv/bde-website/db/bde-ort-sup.db "PRAGMA integrity_check;"
  sudo du -sh /srv/bde-website/db /srv/bde-website/static/uploads /srv/bde-website/static/images
'
```

En cas de `502 Bad Gateway`, relance uniquement le service puis lis les journaux :

```bash
ssh ubuntu@51.210.254.136 'sudo systemctl restart bde-website && sudo journalctl -u bde-website -n 100 --no-pager'
```

En cas d’images 404 alors que la BDD contient les profils, vérifie les fichiers et leurs droits :

```bash
ssh ubuntu@51.210.254.136 '
  sudo find /srv/bde-website/static/uploads -type f | head -30
  sudo setfacl -m u:www-data:--x /srv/bde-website
  sudo setfacl -R -m u:www-data:rX /srv/bde-website/static
  sudo systemctl reload nginx
'
```

### Retour arrière du code

Cette procédure restaure seulement le code, pas la BDD. Commence par identifier le commit stable :

```bash
ssh ubuntu@51.210.254.136 'sudo -u bde git -C /srv/bde-website log --oneline -10'
```

Après avoir choisi un hash, remplace `HASH_DU_COMMIT_STABLE` :

```bash
ssh ubuntu@51.210.254.136 '
  sudo -u bde git -C /srv/bde-website checkout HASH_DU_COMMIT_STABLE
  sudo systemctl restart bde-website
  sudo systemctl status bde-website --no-pager
'
```

Cette commande détache `HEAD` sur le serveur. Corrige ensuite la branche `main` localement et redéploie une version saine, sinon le prochain `git pull` ne pourra pas reprendre normalement.

## API JSON

```text
GET /api/health
GET /api/site
GET /api/events
GET /api/products
GET /api/stats
GET /api/home-stats
```

Ces endpoints servent aux futures intégrations, mais ne remplacent jamais les contrôles de droits Flask pour les opérations d’écriture.

## Sécurité et dépannage

- Utilise des mots de passe uniques pour les comptes avec privilèges.
- En production, active HTTPS et conserve les secrets dans des variables d’environnement ou fichiers protégés hors dépôt.
- Vérifie les permissions de `static/uploads/` : l’application doit écrire dedans, sans ouvrir le dossier à tous les utilisateurs système.
- Teste une restauration de sauvegarde avant d’en dépendre.

Si les données locales disparaissent, vérifie `db/bde-ort-sup.db`, relance Flask et restaure une copie dans `local-backups/` si nécessaire. Si les portraits ou produits renvoient une 404 après un import, relance `./scripts/sync-production-data.sh` pour récupérer aussi les assets. Si le calendrier est vide, vérifie qu’il est public et qu’aucune extension navigateur ne bloque les contenus intégrés.
