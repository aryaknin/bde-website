"""Connexion SQLite, schéma et lectures partagées par les pages et l’API."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_DIR / "db" / "bde-ort-sup.db"

# Valeurs de démonstration : les réglages déjà enregistrés sont conservés.
DEFAULT_SETTINGS = {
    "site_name": "BDE ORT Sup",
    "site_tagline": "La vie étudiante, par les étudiants.",
    "contact_email": "bde@ort-montreuil.fr",
    "campus_address": "43 Rue Raspail, 93100 Montreuil",
    "campus_maps_url": "https://www.google.com/maps/place//data=!4m2!3m1!1s0x47e6729d1120b84f:0xb4d4e94e68dc8081?sa=X&ved=1t:8290&ictx=111",
    "instagram_url": "https://www.instagram.com/bde.ortmontreuil",
    "linkedin_url": "#",
    "academic_year": "2026–2027",
    "institution_since": "1956",
    "poles_count": "30",
    "members_count": "26",
    "years_count": "70",
}


@contextmanager
def get_db():
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialise_database():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS site_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS associations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                contact_email TEXT,
                instagram_url TEXT,
                logo_url TEXT,
                is_featured INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                association_id INTEGER,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                ends_at TEXT,
                location TEXT NOT NULL,
                organizer_name TEXT,
                image_url TEXT,
                google_calendar_url TEXT,
                price_cents INTEGER NOT NULL DEFAULT 0,
                capacity INTEGER,
                published INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (association_id) REFERENCES associations(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                association_id INTEGER,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                price_cents INTEGER NOT NULL,
                stock INTEGER,
                image_url TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (association_id) REFERENCES associations(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member'
                    CHECK (role IN ('member', 'admin', 'superadmin')),
                is_protected INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_superadmin_only
                ON users(role) WHERE role = 'superadmin';
        """)
        # Migration légère pour les bases créées avant l'ajout du lien Google Agenda.
        event_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(events)")
        }
        if "google_calendar_url" not in event_columns:
            db.execute("ALTER TABLE events ADD COLUMN google_calendar_url TEXT")
        if "organizer_name" not in event_columns:
            db.execute("ALTER TABLE events ADD COLUMN organizer_name TEXT")
        db.executemany(
            "INSERT OR IGNORE INTO site_settings (key, value) VALUES (?, ?)",
            DEFAULT_SETTINGS.items(),
        )


def query(sql, parameters=(), booleans=()):
    with get_db() as db:
        rows = [dict(row) for row in db.execute(sql, parameters)]
    for row in rows:
        for field in booleans:
            row[field] = bool(row[field])
    return rows


def site_settings():
    return {row["key"]: row["value"] for row in query("SELECT key, value FROM site_settings")}


def events():
    return query("""
        SELECT events.id, events.association_id, events.title, events.description,
               events.starts_at, events.ends_at, events.location, events.image_url,
               events.google_calendar_url, events.price_cents, events.capacity, events.published,
               COALESCE(
                   NULLIF(events.organizer_name, ''),
                   (SELECT value FROM site_settings WHERE key = 'site_name'),
                   'BDE ORT Sup'
               ) AS organizer_name
        FROM events
        WHERE events.published = 1 ORDER BY julianday(events.starts_at) ASC
    """, booleans=("published",))


def event_by_id(event_id):
    items = query("""
        SELECT events.id, events.association_id, events.title, events.description,
               events.starts_at, events.ends_at, events.location, events.image_url,
               events.google_calendar_url, events.price_cents, events.capacity, events.published,
               COALESCE(
                   NULLIF(events.organizer_name, ''),
                   (SELECT value FROM site_settings WHERE key = 'site_name'),
                   'BDE ORT Sup'
               ) AS organizer_name
        FROM events
        WHERE events.id = ? AND events.published = 1
    """, (event_id,), booleans=("published",))
    return items[0] if items else None


def products():
    return query("""
        SELECT products.*, associations.name AS association_name, associations.slug AS association_slug
        FROM products LEFT JOIN associations ON associations.id = products.association_id
        WHERE products.is_active = 1 ORDER BY products.name ASC
    """, booleans=("is_active",))


def user_by_id(user_id):
    items = query("""
        SELECT id, username, role, is_protected, created_at
        FROM users WHERE id = ?
    """, (user_id,), booleans=("is_protected",))
    return items[0] if items else None


def user_credentials(username):
    items = query("""
        SELECT id, username, password_hash, role, is_protected, created_at
        FROM users WHERE username = ? COLLATE NOCASE
    """, (username,), booleans=("is_protected",))
    return items[0] if items else None


def users():
    return query("""
        SELECT id, username, role, is_protected, created_at
        FROM users
        ORDER BY CASE role WHEN 'superadmin' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,
                 username COLLATE NOCASE
    """, booleans=("is_protected",))


def create_user(username, password_hash, role="member", is_protected=False):
    if role not in ("member", "admin", "superadmin"):
        raise ValueError("Rôle inconnu")
    try:
        with get_db() as db:
            cursor = db.execute("""
                INSERT INTO users (username, password_hash, role, is_protected)
                VALUES (?, ?, ?, ?)
            """, (username, password_hash, role, int(is_protected)))
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def update_user_role(user_id, role):
    if role not in ("member", "admin"):
        return False
    with get_db() as db:
        cursor = db.execute("""
            UPDATE users SET role = ?
            WHERE id = ? AND is_protected = 0 AND role != 'superadmin'
        """, (role, user_id))
        return cursor.rowcount == 1


def create_event(data):
    with get_db() as db:
        cursor = db.execute("""
            INSERT INTO events (
                title, description, starts_at, ends_at, location, organizer_name,
                price_cents, capacity, published
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            data["title"], data["description"], data["starts_at"], data["ends_at"],
            data["location"], data["organizer_name"], data["price_cents"], data["capacity"],
        ))
        return cursor.lastrowid


def stats():
    with get_db() as db:
        return {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("events", "products")
        }
