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
                image_url TEXT,
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
        """)
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


def associations():
    return query(
        "SELECT * FROM associations ORDER BY is_featured DESC, name ASC",
        booleans=("is_featured",),
    )


def events():
    return query("""
        SELECT events.*, associations.name AS association_name, associations.slug AS association_slug
        FROM events LEFT JOIN associations ON associations.id = events.association_id
        WHERE events.published = 1 ORDER BY julianday(events.starts_at) ASC
    """, booleans=("published",))


def products():
    return query("""
        SELECT products.*, associations.name AS association_name, associations.slug AS association_slug
        FROM products LEFT JOIN associations ON associations.id = products.association_id
        WHERE products.is_active = 1 ORDER BY products.name ASC
    """, booleans=("is_active",))


def stats():
    with get_db() as db:
        return {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("associations", "events", "products")
        }
