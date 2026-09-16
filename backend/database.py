"""Connexion SQLite, schéma et lectures partagées par les pages et l’API."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_DIR / "db" / "bde-ort-sup.db"

# Réglages initiaux : les modifications enregistrées sont conservées après migration.
DEFAULT_SETTINGS = {
    "site_name": "BDE ORT Sup",
    "site_tagline": "La vie étudiante, par les étudiants.",
    "contact_email": "bde@ort-montreuil.fr",
    "campus_address": "43 Rue Raspail, 93100 Montreuil",
    "campus_maps_url": "https://www.google.com/maps/place//data=!4m2!3m1!1s0x47e6729d1120b84f:0xb4d4e94e68dc8081?sa=X&ved=1t:8290&ictx=111",
    "instagram_url": "https://www.instagram.com/bde.ortmontreuil",
    "linkedin_url": "#",
    "academic_year": "2026–2027",
    "membership_fee_cents": "500",
    "helloasso_membership_url": "",
    "institution_since": "1921",
    "poles_count": "1",
    "years_count": "105",
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
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
                email TEXT COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member'
                    CHECK (role IN ('member', 'bde', 'admin', 'superadmin')),
                is_protected INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        user_table = db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()
        if user_table and "'bde'" not in user_table["sql"]:
            db.executescript("""
                DROP INDEX IF EXISTS one_superadmin_only;
                ALTER TABLE users RENAME TO users_before_bde_role;
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    email TEXT COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member'
                        CHECK (role IN ('member', 'bde', 'admin', 'superadmin')),
                    is_protected INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO users (id, username, email, password_hash, role, is_protected, created_at)
                    SELECT id, username, NULL, password_hash, role, is_protected, created_at
                    FROM users_before_bde_role;
                DROP TABLE users_before_bde_role;
            """)
        db.executescript("""
            CREATE UNIQUE INDEX IF NOT EXISTS one_superadmin_only
                ON users(role) WHERE role = 'superadmin';
            CREATE TABLE IF NOT EXISTS bde_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                display_name TEXT NOT NULL,
                team_role TEXT NOT NULL DEFAULT 'Membre du BDE',
                bio TEXT NOT NULL DEFAULT '',
                photo_path TEXT,
                instagram_url TEXT,
                linkedin_url TEXT,
                website_url TEXT,
                is_visible INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS contributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                school_year TEXT NOT NULL,
                amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
                status TEXT NOT NULL DEFAULT 'due'
                    CHECK (status IN ('due', 'pending', 'paid', 'exempt')),
                payment_method TEXT,
                external_reference TEXT,
                paid_at TEXT,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, school_year),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
        if "email" not in user_columns:
            db.execute("ALTER TABLE users ADD COLUMN email TEXT COLLATE NOCASE")
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique
            ON users(email COLLATE NOCASE)
            WHERE email IS NOT NULL AND email != ''
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
        db.execute("""
            INSERT INTO bde_profiles (user_id, display_name, team_role, is_visible)
            SELECT users.id, users.username, 'Membre du BDE', 1
            FROM users
            WHERE users.role IN ('bde', 'admin', 'superadmin')
              AND NOT EXISTS (
                  SELECT 1 FROM bde_profiles WHERE bde_profiles.user_id = users.id
              )
        """)
        migrate_home_settings(db)
    if __package__:
        from .shop_store import initialise_shop
    else:
        from shop_store import initialise_shop
    initialise_shop()


def migrate_home_settings(db):
    """Applique une seule fois les chiffres ORT et le tarif validés le 16/09/2026."""
    migration = "2026-09-16-home-statistics-and-membership-fee"
    if db.execute("SELECT 1 FROM schema_migrations WHERE name = ?", (migration,)).fetchone():
        return
    db.executemany("""
        INSERT INTO site_settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (
        ("poles_count", "1"), ("institution_since", "1921"),
        ("years_count", "105"), ("membership_fee_cents", "500"),
    ))
    db.execute("DELETE FROM site_settings WHERE key = 'members_count'")
    # Corrige uniquement les anciennes échéances standard non réglées de cette rentrée.
    db.execute("""
        UPDATE contributions SET amount_cents = 500, updated_at = CURRENT_TIMESTAMP
        WHERE school_year = '2026-2027' AND status = 'due' AND amount_cents = 1500
    """)
    db.execute("""
        UPDATE products SET price_cents = 500
        WHERE name = 'Adhésion BDE 2026–2027'
    """)
    db.execute("INSERT INTO schema_migrations (name) VALUES (?)", (migration,))


def query(sql, parameters=(), booleans=()):
    with get_db() as db:
        rows = [dict(row) for row in db.execute(sql, parameters)]
    for row in rows:
        for field in booleans:
            row[field] = bool(row[field])
    return rows


def site_settings():
    with get_db() as db:
        settings = {row["key"]: row["value"] for row in db.execute("SELECT key, value FROM site_settings")}
        # Même population que la galerie BDE : profils visibles, liés à un compte ou manuels.
        settings["members_count"] = str(db.execute(
            "SELECT COUNT(*) FROM bde_profiles WHERE is_visible = 1"
        ).fetchone()[0])
    return settings


def home_statistics():
    settings = site_settings()
    return {key: int(settings[key]) for key in ("poles_count", "members_count", "years_count")}


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
        SELECT id, username, email, role, is_protected, created_at
        FROM users WHERE id = ?
    """, (user_id,), booleans=("is_protected",))
    return items[0] if items else None


def user_credentials(identifier):
    items = query("""
        SELECT id, username, email, password_hash, role, is_protected, created_at
        FROM users
        WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE
    """, (identifier, identifier), booleans=("is_protected",))
    return items[0] if items else None


def users():
    return query("""
        SELECT id, username, email, role, is_protected, created_at
        FROM users
        ORDER BY CASE role WHEN 'superadmin' THEN 0 WHEN 'admin' THEN 1 WHEN 'bde' THEN 2 ELSE 3 END,
                 username COLLATE NOCASE
    """, booleans=("is_protected",))


def create_user(username, password_hash, role="member", is_protected=False, email=None):
    if role not in ("member", "bde", "admin", "superadmin"):
        raise ValueError("Rôle inconnu")
    try:
        with get_db() as db:
            identifiers = (username, email or username)
            existing = db.execute("""
                SELECT 1 FROM users
                WHERE lower(username) IN (lower(?), lower(?))
                   OR lower(COALESCE(email, '')) IN (lower(?), lower(?))
            """, identifiers + identifiers).fetchone()
            if existing:
                return None
            cursor = db.execute("""
                INSERT INTO users (username, email, password_hash, role, is_protected)
                VALUES (?, ?, ?, ?, ?)
            """, (username, email or None, password_hash, role, int(is_protected)))
            if role in ("bde", "admin", "superadmin"):
                db.execute("""
                    INSERT INTO bde_profiles (user_id, display_name, team_role, is_visible)
                    VALUES (?, ?, 'Membre du BDE', 1)
                """, (cursor.lastrowid, username))
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def update_user_role(user_id, role):
    if role not in ("member", "bde", "admin"):
        return False
    with get_db() as db:
        cursor = db.execute("""
            UPDATE users SET role = ?
            WHERE id = ? AND is_protected = 0 AND role != 'superadmin'
        """, (role, user_id))
        if cursor.rowcount != 1:
            return False
        user = db.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        if role in ("bde", "admin"):
            db.execute("""
                INSERT INTO bde_profiles (user_id, display_name, team_role, is_visible)
                VALUES (?, ?, 'Membre du BDE', 1)
                ON CONFLICT(user_id) DO UPDATE SET is_visible = 1, updated_at = CURRENT_TIMESTAMP
            """, (user_id, user["username"]))
        else:
            db.execute("""
                UPDATE bde_profiles SET is_visible = 0, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (user_id,))
        return True


def bde_profiles(visible_only=True):
    where = "WHERE bde_profiles.is_visible = 1" if visible_only else ""
    return query(f"""
        SELECT bde_profiles.*, users.username, users.role AS account_role
        FROM bde_profiles LEFT JOIN users ON users.id = bde_profiles.user_id
        {where}
        ORDER BY bde_profiles.sort_order ASC, bde_profiles.display_name COLLATE NOCASE ASC
    """, booleans=("is_visible",))


def bde_profile_by_id(profile_id):
    items = query("""
        SELECT bde_profiles.*, users.username, users.role AS account_role
        FROM bde_profiles LEFT JOIN users ON users.id = bde_profiles.user_id
        WHERE bde_profiles.id = ?
    """, (profile_id,), booleans=("is_visible",))
    return items[0] if items else None


def bde_profile_for_user(user_id):
    items = query("""
        SELECT bde_profiles.*, users.username, users.role AS account_role
        FROM bde_profiles JOIN users ON users.id = bde_profiles.user_id
        WHERE bde_profiles.user_id = ?
    """, (user_id,), booleans=("is_visible",))
    return items[0] if items else None


def create_manual_bde_profile(data):
    with get_db() as db:
        cursor = db.execute("""
            INSERT INTO bde_profiles (
                display_name, team_role, bio, photo_path, instagram_url,
                linkedin_url, website_url, is_visible, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            data["display_name"], data["team_role"], data["bio"], data["photo_path"],
            data["instagram_url"], data["linkedin_url"], data["website_url"], data["sort_order"],
        ))
        return cursor.lastrowid


def update_bde_profile(profile_id, data, include_team_fields=False):
    assignments = [
        "display_name = ?", "bio = ?", "photo_path = ?", "instagram_url = ?",
        "linkedin_url = ?", "website_url = ?", "updated_at = CURRENT_TIMESTAMP",
    ]
    values = [
        data["display_name"], data["bio"], data["photo_path"], data["instagram_url"],
        data["linkedin_url"], data["website_url"],
    ]
    if include_team_fields:
        assignments.extend(("team_role = ?", "sort_order = ?"))
        values.extend((data["team_role"], data["sort_order"]))
    values.append(profile_id)
    with get_db() as db:
        cursor = db.execute(
            f"UPDATE bde_profiles SET {', '.join(assignments)} WHERE id = ?", values
        )
        return cursor.rowcount == 1


def set_bde_profile_visibility(profile_id, visible):
    with get_db() as db:
        cursor = db.execute("""
            UPDATE bde_profiles SET is_visible = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (int(visible), profile_id))
        return cursor.rowcount == 1


def delete_manual_bde_profile(profile_id):
    with get_db() as db:
        cursor = db.execute(
            "DELETE FROM bde_profiles WHERE id = ? AND user_id IS NULL", (profile_id,)
        )
        return cursor.rowcount == 1


def ensure_contributions(school_year, amount_cents):
    """Crée l’échéance annuelle manquante pour tous les comptes existants."""
    with get_db() as db:
        db.execute("""
            INSERT OR IGNORE INTO contributions (user_id, school_year, amount_cents)
            SELECT id, ?, ? FROM users
        """, (school_year, amount_cents))


def create_contribution(user_id, school_year, amount_cents, status="due"):
    if status not in ("due", "pending", "paid", "exempt"):
        return None
    try:
        with get_db() as db:
            cursor = db.execute("""
                INSERT INTO contributions (user_id, school_year, amount_cents, status)
                SELECT id, ?, ?, ? FROM users WHERE id = ?
            """, (school_year, amount_cents, status, user_id))
            return cursor.lastrowid if cursor.rowcount == 1 else None
    except sqlite3.IntegrityError:
        return None


def contributions_for_user(user_id):
    return query("""
        SELECT * FROM contributions
        WHERE user_id = ?
        ORDER BY school_year DESC, id DESC
    """, (user_id,))


def contributions_with_users():
    return query("""
        SELECT contributions.*, users.username, users.email,
               users.role AS account_role, users.is_protected AS account_is_protected
        FROM contributions JOIN users ON users.id = contributions.user_id
        ORDER BY contributions.school_year DESC,
                 CASE contributions.status
                     WHEN 'pending' THEN 0 WHEN 'due' THEN 1
                     WHEN 'paid' THEN 2 ELSE 3
                 END,
                 users.username COLLATE NOCASE
    """, booleans=("account_is_protected",))


def contribution_by_id(contribution_id):
    items = query("""
        SELECT contributions.*, users.username, users.email,
               users.role AS account_role, users.is_protected AS account_is_protected
        FROM contributions JOIN users ON users.id = contributions.user_id
        WHERE contributions.id = ?
    """, (contribution_id,), booleans=("account_is_protected",))
    return items[0] if items else None


def update_contribution(contribution_id, data):
    if data["status"] not in ("due", "pending", "paid", "exempt"):
        return False
    try:
        with get_db() as db:
            cursor = db.execute("""
                UPDATE contributions
                SET school_year = ?, amount_cents = ?, status = ?, payment_method = ?,
                    external_reference = ?, paid_at = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                data["school_year"], data["amount_cents"], data["status"],
                data["payment_method"], data["external_reference"], data["paid_at"],
                data["notes"], contribution_id,
            ))
            return cursor.rowcount == 1
    except sqlite3.IntegrityError:
        return False


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
