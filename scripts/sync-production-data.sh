#!/usr/bin/env bash
# Récupère les données de production sans remplacer le code local.
# Prérequis locaux : bash, ssh, scp, tar, Python 3.
# Prérequis VPS : sudo, sqlite3 et tar.

set -Eeuo pipefail

PROJECT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REMOTE_HOST=${BDE_VPS_HOST:-ubuntu@51.210.254.136}
REMOTE_PROJECT=${BDE_VPS_PROJECT:-/srv/bde-website}
REMOTE_ARCHIVE_DIR=${BDE_VPS_ARCHIVE_DIR:-/home/ubuntu}
STAMP=$(date +%Y%m%d-%H%M%S)
REMOTE_ARCHIVE="$REMOTE_ARCHIVE_DIR/bde-production-sync-${STAMP}.tar.gz"
LOCAL_STAGE=$(mktemp -d "${TMPDIR:-/tmp}/bde-production-sync.XXXXXX")
LOCAL_ARCHIVE="$LOCAL_STAGE/snapshot.tar.gz"
BACKUP_DIR="$PROJECT_DIR/local-backups/production-sync-$STAMP"

cleanup_local() {
  rm -rf -- "$LOCAL_STAGE"
}
trap cleanup_local EXIT

if ! command -v ssh >/dev/null || ! command -v scp >/dev/null || ! command -v tar >/dev/null; then
  echo "Erreur : ssh, scp et tar doivent être installés localement." >&2
  exit 1
fi

echo "→ Création d’un instantané cohérent sur $REMOTE_HOST…"
# -tt permet à sudo de demander le mot de passe du VPS si nécessaire.
ssh -tt "$REMOTE_HOST" "bash -s -- $(printf '%q' "$REMOTE_PROJECT") $(printf '%q' "$REMOTE_ARCHIVE")" <<'REMOTE_SCRIPT'
set -Eeuo pipefail

project=$1
archive=$2
source_db="$project/db/bde-ort-sup.db"
archive_dir=$(dirname "$archive")
workdir=$(mktemp -d "$archive_dir/.bde-production-sync.XXXXXX")
export_db="$workdir/bde-ort-sup.db"
assets_archive="$workdir/static-data.tar.gz"
manifest="$workdir/manifest.txt"

cleanup() {
  sudo rm -rf -- "$workdir"
}
trap cleanup EXIT

if ! sudo test -f "$source_db"; then
  echo "Base introuvable : $source_db" >&2
  exit 1
fi

rm -f -- "$archive"

# VACUUM INTO produit une copie SQLite cohérente sans arrêter Gunicorn.
sudo sqlite3 "$source_db" "VACUUM INTO '$export_db';"
sudo sqlite3 "file:$export_db?mode=ro&immutable=1" "PRAGMA integrity_check;" | grep -qx "ok"

sudo sqlite3 "file:$export_db?mode=ro&immutable=1" <<'SQL' > "$manifest"
SELECT 'users', COUNT(*) FROM users;
SELECT 'events', COUNT(*) FROM events;
SELECT 'products', COUNT(*) FROM products;
SELECT 'bde_profiles', COUNT(*) FROM bde_profiles;
SQL

# La partie statique récupérée est limitée aux images, jamais au CSS/JS local.
sudo tar -C "$project/static" -czf "$assets_archive" uploads images
sudo chown "$(id -u):$(id -g)" "$export_db" "$assets_archive" "$manifest"
tar -C "$workdir" -czf "$archive" \
  "$(basename "$export_db")" \
  "$(basename "$assets_archive")" \
  "$(basename "$manifest")"
echo "Instantané prêt : $archive"
REMOTE_SCRIPT

echo "→ Téléchargement…"
scp "$REMOTE_HOST:$REMOTE_ARCHIVE" "$LOCAL_ARCHIVE"

echo "→ Vérification de la base importée…"
tar -xzf "$LOCAL_ARCHIVE" -C "$LOCAL_STAGE"
EXPORTED_DB=$(find "$LOCAL_STAGE" -maxdepth 1 -type f -name '*.db' -print -quit)
ASSETS_ARCHIVE=$(find "$LOCAL_STAGE" -maxdepth 1 -type f -name 'static-data.tar.gz' -print -quit)
MANIFEST=$(find "$LOCAL_STAGE" -maxdepth 1 -type f -name '*-manifest.txt' -print -quit)

if [[ -z "$EXPORTED_DB" || -z "$ASSETS_ARCHIVE" || -z "$MANIFEST" ]]; then
  echo "Erreur : l’archive de production est incomplète ; aucune donnée locale n’a été remplacée." >&2
  exit 1
fi

python3 - "$EXPORTED_DB" "$MANIFEST" <<'PYTHON_SCRIPT'
import sqlite3
import sys
from pathlib import Path

database_path = Path(sys.argv[1]).resolve()
expected = {}
for line in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines():
    name, count = line.split("|", 1)
    expected[name] = int(count)

connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
try:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise SystemExit(f"Base corrompue : {integrity}")
    received = {
        name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        for name in expected
    }
finally:
    connection.close()

if received != expected:
    raise SystemExit(f"Copie incohérente : attendu {expected}, reçu {received}")
if not any(received.values()):
    raise SystemExit("Copie de production vide : import annulé par sécurité.")
print("Base validée :", ", ".join(f"{name}={count}" for name, count in received.items()))
PYTHON_SCRIPT

python3 - "$EXPORTED_DB" "$ASSETS_ARCHIVE" <<'PYTHON_SCRIPT'
import sqlite3
import sys
import tarfile
from pathlib import Path

database_path = Path(sys.argv[1]).resolve()
assets_path = Path(sys.argv[2])
connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
try:
    references = [
        row[0] for row in connection.execute("""
            SELECT photo_path FROM bde_profiles WHERE photo_path IS NOT NULL
            UNION ALL
            SELECT image_url FROM products WHERE image_url IS NOT NULL
        """)
    ]
finally:
    connection.close()

references = {
    path.lstrip("/") for path in references
    if not path.startswith(("http://", "https://"))
}
with tarfile.open(assets_path, "r:gz") as archive:
    available = set(archive.getnames())
missing = sorted(references - available)
if missing:
    raise SystemExit(
        "Archive statique incomplète : " + ", ".join(missing)
        + ". Aucune donnée locale n’a été remplacée."
    )
print(f"Images référencées validées : {len(references)}")
PYTHON_SCRIPT

echo "→ Sauvegarde locale dans $BACKUP_DIR…"
mkdir -p "$BACKUP_DIR"
if [[ -f "$PROJECT_DIR/db/bde-ort-sup.db" ]]; then
  cp -a "$PROJECT_DIR/db/bde-ort-sup.db" "$BACKUP_DIR/bde-ort-sup.db"
fi

STATIC_ENTRIES=()
[[ -d "$PROJECT_DIR/static/uploads" ]] && STATIC_ENTRIES+=(uploads)
[[ -d "$PROJECT_DIR/static/images" ]] && STATIC_ENTRIES+=(images)
if ((${#STATIC_ENTRIES[@]})); then
  tar -C "$PROJECT_DIR/static" -czf "$BACKUP_DIR/static-data.tar.gz" "${STATIC_ENTRIES[@]}"
fi

echo "→ Installation de la base, des images et des fichiers envoyés…"
cp "$EXPORTED_DB" "$PROJECT_DIR/db/bde-ort-sup.db"
tar -xzf "$ASSETS_ARCHIVE" -C "$PROJECT_DIR/static"

# L’archive temporaire appartient maintenant à l’utilisateur SSH, pas besoin de sudo.
ssh "$REMOTE_HOST" "rm -f -- $(printf '%q' "$REMOTE_ARCHIVE")" || \
  echo "Note : archive temporaire à supprimer plus tard sur le VPS : $REMOTE_ARCHIVE" >&2

echo
echo "Synchronisation terminée. Sauvegarde locale : $BACKUP_DIR"
echo "Démarre Flask avec : python3 backend/app.py"
