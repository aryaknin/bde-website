"""Données fictives pour développer le site en local."""

if __package__:
    from .database import get_db, initialise_database
else:
    from database import get_db, initialise_database


def seed_database():
    initialise_database()
    with get_db() as db:
        created = False
        association_rows = [
            ("BDE ORT Sup", "bde-ort-sup", "Le bureau des élèves qui anime le campus et accompagne les étudiants.", "Vie étudiante", "bde@ort-montreuil.fr", "https://www.instagram.com/bde.ortmontreuil", 1),
        ]
        if not db.execute("SELECT 1 FROM associations LIMIT 1").fetchone():
            db.executemany("""
                INSERT INTO associations
                    (name, slug, description, category, contact_email, instagram_url, is_featured)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, association_rows)
            created = True

        association_ids = {row["slug"]: row["id"] for row in db.execute("SELECT id, slug FROM associations")}
        event_rows = [
            (association_ids.get("bde-ort-sup"), "Soirée de rentrée", "Une première soirée pour se rencontrer et lancer l’année.", "2026-10-08T19:00:00+02:00", "2026-10-08T23:30:00+02:00", "Campus ORT Montreuil", 500, 120),
            (association_ids.get("bde-ort-sup"), "Tournoi de futsal", "Compose ton équipe et viens défendre les couleurs de ta promo.", "2026-10-17T14:00:00+02:00", "2026-10-17T18:00:00+02:00", "Gymnase municipal", 200, 64),
            (association_ids.get("bde-ort-sup"), "Soirée jeux & tournoi Mario Kart", "Une soirée conviviale, débutants bienvenus.", "2026-11-05T18:30:00+01:00", "2026-11-05T22:30:00+01:00", "Salle associative", 0, 40),
        ]
        if not db.execute("SELECT 1 FROM events LIMIT 1").fetchone():
            db.executemany("""
                INSERT INTO events
                    (association_id, title, description, starts_at, ends_at, location, price_cents, capacity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, event_rows)
            created = True

        membership_fee = int(db.execute(
            "SELECT value FROM site_settings WHERE key = 'membership_fee_cents'"
        ).fetchone()[0])
        product_rows = [
            (association_ids.get("bde-ort-sup"), "Adhésion BDE 2026–2027", "Soutiens les projets du BDE et profite des avantages adhérents.", membership_fee, None),
            (association_ids.get("bde-ort-sup"), "Sweat ORT Montreuil", "Sweat à capuche édition campus.", 3000, 50),
            (association_ids.get("bde-ort-sup"), "Inscription tournoi futsal", "Une place individuelle pour le tournoi de futsal.", 200, 64),
        ]
        if not db.execute("SELECT 1 FROM products LIMIT 1").fetchone():
            db.executemany("""
                INSERT INTO products (association_id, name, description, price_cents, stock, product_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [row + ("membership" if index == 0 else "article",) for index, row in enumerate(product_rows)])
            created = True
    return created


if __name__ == "__main__":
    created = seed_database()
    print("Données de démonstration créées." if created else "Base déjà initialisée : aucune donnée ajoutée.")
