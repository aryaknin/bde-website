# Déploiement de production — BDE ORT Sup

Ce document décrit le déploiement réel du site Flask du BDE sur un VPS OVHcloud. Il doit permettre à une autre personne de maintenir le serveur sans connaître l'historique du projet.

> Ne jamais inscrire dans ce fichier un mot de passe, une clé privée SSH, la valeur de `BDE_SECRET_KEY` ou des identifiants OVH/GitHub.

## Architecture

```text
Navigateur
    |
    | HTTPS (après configuration du certificat)
    v
Nginx (ports 80 et 443)
    |
    | proxy vers 127.0.0.1:8000
    v
Gunicorn / Flask (service systemd `bde-website`)
    |
    +-- SQLite : /srv/bde-website/db/bde-ort-sup.db
    +-- Images envoyées : /srv/bde-website/static/uploads/members/
```

Le code est récupéré depuis la branche Git `main`. La branche `gh-pages` ne sert plus à l'hébergement : GitHub Pages ne peut pas exécuter Flask ni les templates Jinja.

## Infrastructure

| Élément | Choix |
| --- | --- |
| Hébergeur | OVHcloud VPS |
| Système | Ubuntu 26.04 |
| Application | Flask + Gunicorn |
| Serveur web / TLS | Nginx + Certbot |
| Base de données actuelle | SQLite |
| Domaine | `bde-ortmontreuil.fr` |
| Compte SSH initial | `ubuntu` |
| Compte système de l'application | `bde` |
| Répertoire de l'application | `/srv/bde-website` |

Le VPS a 2 vCores, 4 Go de RAM et 40 Go de stockage. Les sauvegardes automatiques OVH sont activées.

## Règles de sécurité importantes

- Le compte `root` n'est pas utilisé pour la connexion SSH. Se connecter avec `ubuntu`, puis employer `sudo`.
- Utiliser un mot de passe unique, conservé dans un gestionnaire de mots de passe, puis passer à une clé SSH.
- Ne pas envoyer un mot de passe ou une clé privée par message, e-mail, capture d'écran ou commit Git.
- Le pare-feu UFW n'autorise que SSH (22), HTTP (80) et HTTPS (443).
- `BDE_SECRET_KEY` est stockée uniquement dans `/etc/bde-website.env`, avec des droits restrictifs.
- Le fichier SQLite et les photos sont ignorés par Git. Ils doivent être sauvegardés séparément.

## Première installation effectuée

### Paquets et pare-feu

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git nginx python3-venv python3-pip ufw fail2ban acl

sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
sudo ufw status verbose
```

Le résultat attendu comprend les règles `22/tcp (OpenSSH)` et `80,443/tcp (Nginx Full)`.

### Code et environnement Python

```bash
sudo adduser --system --group --home /srv/bde-website bde
sudo git clone https://github.com/aryaknin/bde-website.git /srv/bde-website
sudo chown -R bde:bde /srv/bde-website

sudo -u bde python3 -m venv /srv/bde-website/.venv
sudo -u bde /srv/bde-website/.venv/bin/pip install --upgrade pip
sudo -u bde /srv/bde-website/.venv/bin/pip install \
  -r /srv/bde-website/backend/requirements.txt gunicorn
```

Si le dépôt devient privé, ne pas enregistrer un mot de passe GitHub sur le VPS : créer une clé de déploiement en lecture seule dans GitHub.

### Variables d'environnement

Le fichier `/etc/bde-website.env` est créé sur le VPS et ne doit pas être versionné. Il contient :

```dotenv
BDE_SECRET_KEY=<valeur-aléatoire-secrète>
BDE_COOKIE_SECURE=1
```

Créer ou remplacer le fichier sans afficher le secret :

```bash
sudo sh -c 'printf "BDE_SECRET_KEY=%s\nBDE_COOKIE_SECURE=1\n" "$(openssl rand -hex 32)" > /etc/bde-website.env'
sudo chown root:bde /etc/bde-website.env
sudo chmod 640 /etc/bde-website.env
```

> Changer `BDE_SECRET_KEY` déconnecte les utilisateurs actifs, ce qui est normal.

### Service Gunicorn

Le service `/etc/systemd/system/bde-website.service` est :

```ini
[Unit]
Description=Site BDE ORT Sup (Gunicorn)
After=network.target

[Service]
User=bde
Group=bde
WorkingDirectory=/srv/bde-website
EnvironmentFile=/etc/bde-website.env
ExecStart=/srv/bde-website/.venv/bin/gunicorn --workers 1 --bind 127.0.0.1:8000 backend.app:app
Restart=always
RestartSec=3
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

Le site utilise volontairement un seul worker Gunicorn, car SQLite ne convient pas aux écritures concurrentes de plusieurs processus.

Activation et vérification :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bde-website
sudo systemctl status bde-website --no-pager
```

Le statut attendu est `active (running)`.

### Nginx

Le fichier `/etc/nginx/sites-available/bde-website` est :

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name _;

    client_max_body_size 8m;

    location /static/ {
        alias /srv/bde-website/static/;
        access_log off;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Activation :

```bash
sudo ln -s /etc/nginx/sites-available/bde-website /etc/nginx/sites-enabled/bde-website
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Nginx doit pouvoir lire les ressources statiques sans pouvoir lire la base SQLite. Les ACL suivantes donnent uniquement cet accès :

```bash
sudo setfacl -m u:www-data:--x /srv/bde-website
sudo setfacl -R -m u:www-data:rX /srv/bde-website/static
sudo setfacl -R -d -m u:www-data:rX /srv/bde-website/static
```

Tester :

```bash
curl -I http://127.0.0.1/
curl -I http://127.0.0.1/static/css/site.css
```

Le CSS doit renvoyer `HTTP/1.1 200 OK` et `Content-Type: text/css`.

## DNS du domaine

Dans la **Zone DNS** OVH du domaine (et non dans « DNS secondaire » du VPS), créer :

| Type | Sous-domaine | Cible |
| --- | --- | --- |
| `A` | vide ou `@` | adresse IPv4 publique du VPS |
| `A` | `www` | adresse IPv4 publique du VPS |

Ne pas supprimer les enregistrements MX existants : ils peuvent être nécessaires à la messagerie. Après une modification DNS, la propagation prend généralement quelques minutes, parfois plusieurs heures.

Vérifier que ces deux adresses affichent le site en HTTP avant de demander un certificat :

```text
http://bde-ortmontreuil.fr
http://www.bde-ortmontreuil.fr
```

## HTTPS (à faire dès que le DNS est propagé)

Installer Certbot :

```bash
sudo apt install -y certbot python3-certbot-nginx
```

Remplacer `server_name _;` dans `/etc/nginx/sites-available/bde-website` par :

```nginx
server_name bde-ortmontreuil.fr www.bde-ortmontreuil.fr;
```

Puis vérifier et recharger Nginx :

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Créer et installer le certificat :

```bash
sudo certbot --nginx -d bde-ortmontreuil.fr -d www.bde-ortmontreuil.fr
```

Choisir la redirection automatique de HTTP vers HTTPS lorsque Certbot la propose. Tester ensuite :

```bash
sudo certbot renew --dry-run
```

Les certificats Let's Encrypt se renouvellent automatiquement ; le test confirme que le mécanisme est prêt.

## Mettre le site à jour

### 1. Envoyer les modifications vers GitHub

Sur l'ordinateur de développement, dans le dossier du projet :

```bash
git switch main
git add .
git commit -m "Décrire la modification"
git push origin main
```

### 2. Déployer la branche `main` sur le VPS

Se connecter au serveur :

```bash
ssh ubuntu@ADRESSE_IP_DU_VPS
```

Puis exécuter :

```bash
sudo -u bde git -C /srv/bde-website pull --ff-only
sudo -u bde /srv/bde-website/.venv/bin/pip install -r /srv/bde-website/backend/requirements.txt
sudo systemctl restart bde-website
sudo systemctl status bde-website --no-pager
```

`git pull --ff-only` évite de créer un merge inattendu sur le serveur. Cette procédure ne supprime pas la base SQLite ni les images, puisqu'elles sont ignorées par Git.

Si une modification inclut une migration de base de données, faire une sauvegarde avant le redémarrage.

## Sauvegardes

Les sauvegardes OVH sont une première protection, mais ne remplacent pas une sauvegarde applicative exploitable.

À sauvegarder au minimum :

```text
/srv/bde-website/db/bde-ort-sup.db
/srv/bde-website/static/uploads/members/
/etc/bde-website.env
```

Recommandations :

1. Créer une sauvegarde quotidienne de la base avec `sqlite3 .backup` (ne pas simplement copier un fichier pendant une écriture).
2. Archiver quotidiennement les images envoyées.
3. Conserver les sauvegardes hors du VPS (stockage OVH séparé, stockage chiffré ou autre emplacement administré par le BDE).
4. Tester une restauration au moins une fois avant l'ouverture officielle.

## Exploitation et maintenance

Le VPS et le service `bde-website` tournent en continu. Fermer le terminal ou l'ordinateur local ne coupe pas le site.

À faire :

| Fréquence | Action |
| --- | --- |
| À chaque modification | pousser `main`, récupérer sur le VPS, redémarrer Gunicorn |
| Mensuelle | mettre à jour Ubuntu et vérifier les sauvegardes |
| Après une mise à jour importante | tester l'accueil, la connexion, les formulaires et les images |
| Annuelle | vérifier le renouvellement du VPS et du domaine |

Mise à jour système :

```bash
sudo apt update && sudo apt upgrade -y
sudo systemctl reboot
```

Après un redémarrage, vérifier :

```bash
sudo systemctl status bde-website nginx --no-pager
```

## Dépannage

### Le site affiche « 502 Bad Gateway »

```bash
sudo systemctl status bde-website --no-pager
sudo journalctl -u bde-website -n 100 --no-pager
sudo systemctl restart bde-website
```

### Le CSS ou les images ne se chargent pas

```bash
curl -I http://127.0.0.1/static/css/site.css
sudo nginx -t
sudo setfacl -m u:www-data:--x /srv/bde-website
sudo setfacl -R -m u:www-data:rX /srv/bde-website/static
```

Une réponse `403 Forbidden` indique généralement que Nginx ne peut pas traverser le dossier `/srv/bde-website`.

### Le domaine n'affiche pas le site

1. Vérifier les deux enregistrements `A` dans la Zone DNS.
2. Attendre la propagation DNS.
3. Tester d'abord l'adresse HTTP, puis HTTPS.
4. Vérifier Nginx et le pare-feu :

```bash
sudo nginx -t
sudo ufw status verbose
```

### Retour en arrière après un mauvais déploiement

Sur le VPS :

```bash
cd /srv/bde-website
sudo -u bde git log --oneline -10
sudo -u bde git checkout COMMIT_A_RESTAURER
sudo systemctl restart bde-website
```

Ensuite, corriger la branche `main` sur GitHub/localement afin que le prochain déploiement ne réintroduise pas le problème.

## Points à valider avant l'ouverture publique

- [ ] DNS propagé pour le domaine racine et `www`.
- [ ] HTTPS actif et redirection HTTP vers HTTPS.
- [ ] Contenu fictif remplacé par les informations validées du BDE.
- [ ] Premier compte superadministrateur créé avec un mot de passe robuste.
- [ ] Connexion, création d'événement, profil et envoi d'image testés.
- [ ] Sauvegarde de la base et des images configurée et testée.
- [ ] Accès OVH, GitHub et domaine détenus par le BDE ou documentés pour la passation.
- [ ] Adresse e-mail et mentions légales/politique de confidentialité vérifiées si des données personnelles sont collectées.

## Évolutions recommandées

SQLite convient au lancement avec un faible trafic et un seul worker Gunicorn. Si le site reçoit davantage d'écritures simultanées (adhésions, billetterie, plusieurs administrateurs), migrer vers PostgreSQL et stocker les photos sur un stockage objet. Avant d'ajouter un vrai paiement, utiliser un prestataire de paiement reconnu et ne jamais stocker les coordonnées bancaires sur le VPS.
