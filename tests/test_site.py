"""Vérifications de la migration Flask, avec une base temporaire indépendante."""

import re
import tempfile
import unittest
from io import BytesIO
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urljoin, urlsplit

from PIL import Image
from werkzeug.security import generate_password_hash

from backend import app as app_module
from backend import database
from backend.app import PAGES, create_app, current_school_year
from backend.seed import seed_database


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = set()

    def handle_starttag(self, tag, attributes):
        for name, value in attributes:
            if name in ("href", "src") and value:
                self.urls.add(value)


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.database_patch = patch.object(
            database, "DATABASE_PATH", Path(self.folder.name) / "test.db"
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        self.upload_patch = patch.object(
            app_module, "UPLOAD_FOLDER", Path(self.folder.name) / "member-uploads"
        )
        self.upload_patch.start()
        self.addCleanup(self.upload_patch.stop)
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        seed_database()
        self.super_id = database.create_user(
            "SuperTest", generate_password_hash("super-test-pass"), "superadmin", is_protected=True
        )
        self.admin_id = database.create_user(
            "AdminTest", generate_password_hash("admin123"), "admin"
        )
        self.member_id = database.create_user(
            "MembreTest", generate_password_hash("membre123"), "member"
        )

    def csrf_token(self, client, route):
        html = client.get(route).get_data(as_text=True)
        match = re.search(r'name="_csrf_token" value="([^"]+)"', html)
        self.assertIsNotNone(match)
        return match.group(1)

    def login_as(self, client, username, password):
        token = self.csrf_token(client, "/login.html")
        return client.post(
            "/login.html",
            data={"_csrf_token": token, "username": username, "password": password},
        )

    @staticmethod
    def sample_image():
        image = BytesIO()
        Image.new("RGB", (120, 160), "#07558c").save(image, "PNG")
        image.seek(0)
        return image

    def test_public_pages_and_local_resources(self):
        urls = set()
        for route in ["/"] + [f"/{page}.html" for page in PAGES]:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn('lang="fr"', html)
                parser = PageLinks()
                parser.feed(html)
                urls.update(urljoin(route, url) for url in parser.urls)
        with self.client.get("/static/css/site.css") as response:
            css = response.get_data(as_text=True)
        for url in re.findall(r'url\("([^"]+)"\)', css):
            urls.add(urljoin("/static/css/site.css", url))
        for url in urls:
            parsed = urlsplit(url)
            if not parsed.scheme and not parsed.netloc:
                with self.subTest(asset=url):
                    with self.client.get(parsed.path) as response:
                        self.assertEqual(response.status_code, 200)

    def test_database_values_render_without_javascript(self):
        with database.get_db() as db:
            db.executemany(
                "UPDATE site_settings SET value = ? WHERE key = ?",
                [("BDE <Test>", "site_name"), ("0", "poles_count"),
                 ("12 rue de test", "campus_address")],
            )
            db.execute(
                "UPDATE events SET title = ?, starts_at = ?, ends_at = ? WHERE id = 1",
                ("Événement <test>", "2099-10-08T19:00:00+02:00", "2099-10-08T23:00:00+02:00"),
            )
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("BDE &lt;Test&gt;", html)
        self.assertNotIn("BDE <Test>", html)
        self.assertIn("<dd>0</dd>", html)
        self.assertIn("12 rue de test", html)
        self.assertIn("Événement &lt;test&gt;", html)
        self.assertIn("Événement <test>", self.client.get("/api/events").json[-1]["title"])

    def test_home_counts_follow_visible_bde_profiles(self):
        self.assertEqual(self.client.get("/api/home-stats").json, {
            "poles_count": 10, "members_count": 2, "years_count": 105,
        })
        self.assertEqual(len(database.bde_profiles()), 2)
        with database.get_db() as db:
            db.execute("INSERT INTO site_settings (key, value) VALUES ('members_count', '999')")
        self.assertEqual(self.client.get("/api/site").json["members_count"], "2")
        self.login_as(self.client, "SuperTest", "super-test-pass")
        token = self.csrf_token(self.client, "/admin.html")
        profile = database.bde_profile_for_user(self.admin_id)
        for visible, count in (("0", 1), ("1", 2)):
            with self.subTest(visible=visible):
                self.client.post(
                    f"/admin/profiles/{profile['id']}/visibility",
                    data={"_csrf_token": token, "visible": visible},
                )
                response = self.client.get("/api/home-stats")
                self.assertEqual(response.json["members_count"], count)
                self.assertIn("no-store", response.headers["Cache-Control"])
                html = self.client.get("/").get_data(as_text=True)
                self.assertRegex(html, rf'data-home-stat="members_count">\s*<dt>.*?</dt>\s*<dd>{count}</dd>')
        for profile in database.bde_profiles():
            database.set_bde_profile_visibility(profile["id"], False)
        self.assertEqual(self.client.get("/api/home-stats").json["members_count"], 0)
        self.assertEqual(database.site_settings()["members_count"], "0")

    def test_home_welcome_is_shown_once_per_24_hours(self):
        first = self.client.get("/")
        self.assertIn("data-welcome", first.get_data(as_text=True))
        welcome_cookie = next(
            value for value in first.headers.getlist("Set-Cookie")
            if value.startswith("bde_welcome_seen=")
        )
        self.assertIn("Max-Age=86400", welcome_cookie)
        for route in ("/evenements.html", "/", "/index.html"):
            response = self.client.get(route)
            self.assertNotIn("data-welcome", response.get_data(as_text=True))
            self.assertFalse(any(
                value.startswith("bde_welcome_seen=")
                for value in response.headers.getlist("Set-Cookie")
            ))
        self.login_as(self.client, "SuperTest", "super-test-pass")
        self.assertNotIn("data-welcome", self.client.get("/").get_data(as_text=True))
        # Un cookie arrivé à expiration n’est plus envoyé par le navigateur.
        self.client.delete_cookie("bde_welcome_seen")
        self.assertIn("data-welcome", self.client.get("/index.html").get_data(as_text=True))

    def test_home_settings_migration_preserves_payment_history(self):
        old_due = database.create_contribution(self.member_id, "2026-2027", 1500)
        paid = database.create_contribution(self.admin_id, "2026-2027", 1500, "paid")
        past_due = database.create_contribution(self.member_id, "2025-2026", 1500)
        with database.get_db() as db:
            db.execute("DELETE FROM schema_migrations WHERE name = ?", (
                "2026-09-16-home-statistics-and-membership-fee",
            ))
            db.executemany("UPDATE site_settings SET value = ? WHERE key = ?", (
                ("30", "poles_count"), ("1956", "institution_since"),
                ("70", "years_count"), ("1500", "membership_fee_cents"),
            ))
            db.execute("UPDATE products SET price_cents = 1000 WHERE name = 'Adhésion BDE 2026–2027'")
        database.initialise_database()
        settings = database.site_settings()
        self.assertEqual([settings[key] for key in (
            "poles_count", "institution_since", "years_count", "membership_fee_cents"
        )], ["1", "1921", "105", "500"])
        self.assertEqual(database.contribution_by_id(old_due)["amount_cents"], 500)
        self.assertEqual(database.contribution_by_id(paid)["amount_cents"], 1500)
        self.assertEqual(database.contribution_by_id(past_due)["amount_cents"], 1500)
        self.assertEqual(database.products()[0]["price_cents"], 500)
        with database.get_db() as db:
            db.execute("UPDATE contributions SET amount_cents = 1500 WHERE id = ?", (old_due,))
        database.initialise_database()
        self.assertEqual(database.contribution_by_id(old_due)["amount_cents"], 1500)

    def test_api_filters_and_existing_contracts(self):
        with database.get_db() as db:
            db.execute("UPDATE events SET published = 0 WHERE id = 1")
            db.execute("UPDATE products SET is_active = 0 WHERE id = 1")
        self.assertEqual(self.client.get("/api/health").json, {"status": "ok"})
        events = self.client.get("/api/events").json
        products = self.client.get("/api/products").json
        self.assertEqual(len(events), 2)
        self.assertEqual(len(products), 2)
        self.assertTrue(all(event["published"] is True for event in events))
        self.assertTrue(all(product["is_active"] is True for product in products))
        self.assertEqual(events[0]["organizer_name"], "BDE ORT Sup")
        self.assertEqual(self.client.get("/api/stats").json, {"events": 3, "products": 3})

    def test_empty_lists_are_readable(self):
        with database.get_db() as db:
            db.execute("DELETE FROM events")
            db.execute("DELETE FROM products")
            db.execute("DELETE FROM associations")
        self.assertIn("Aucun événement", self.client.get("/").get_data(as_text=True))
        self.assertIn("Aucun article", self.client.get("/billetterie.html").get_data(as_text=True))

    def test_google_calendar_is_embedded(self):
        html = self.client.get("/calendrier.html").get_data(as_text=True)
        self.assertIn('class="calendar-window"', html)
        self.assertIn('title="Calendrier officiel du BDE ORT Sup"', html)
        self.assertIn("calendar.google.com/calendar/embed", html)
        self.assertIn("wkst=2", html)

    def test_project_and_contact_forms_send_validated_messages(self):
        events_html = self.client.get("/evenements.html").get_data(as_text=True)
        self.assertIn('href="/demande-domaine.html"', events_html)
        self.assertIn('href="/contact.html"', events_html)

        project_page = self.client.get("/demande-domaine.html").get_data(as_text=True)
        self.assertIn("Propose ton", project_page)
        token = self.csrf_token(self.client, "/demande-domaine.html")
        with patch.object(app_module, "send_inquiry_email", return_value=True) as sender:
            response = self.client.post("/demande-domaine.html", data={
                "_csrf_token": token,
                "name": "Camille Martin",
                "email": "camille@example.com",
                "subject": "Atelier photographie",
                "project_type": "Atelier",
                "class_group": "BTS SIO 1",
                "message": "Un atelier pour apprendre les bases de la photographie.",
                "availability": "Le jeudi après-midi.",
                "website": "",
            })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/demande-domaine.html"))
        self.assertEqual(sender.call_args.args[0], "project")
        self.assertEqual(sender.call_args.args[1]["subject"], "Atelier photographie")

        token = self.csrf_token(self.client, "/contact.html")
        with patch.object(app_module, "send_inquiry_email", return_value=True) as sender:
            response = self.client.post("/contact.html", data={
                "_csrf_token": token,
                "name": "Alex Dupont",
                "email": "alex@example.com",
                "subject": "Question sur la cotisation",
                "message": "Bonjour, je souhaite obtenir un renseignement sur la cotisation.",
                "website": "",
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(sender.call_args.args[0], "contact")

    def test_project_form_rejects_invalid_and_spam_submissions(self):
        token = self.csrf_token(self.client, "/demande-domaine.html")
        response = self.client.post("/demande-domaine.html", data={
            "_csrf_token": token,
            "name": "A",
            "email": "adresse-invalide",
            "subject": "Idée",
            "message": "Court",
            "website": "robot.example",
        })
        self.assertIn("n’a pas pu être envoyé", response.get_data(as_text=True))

    def test_login_and_protected_account(self):
        credentials = database.user_credentials("supertest")
        self.assertNotEqual(credentials["password_hash"], "super-test-pass")
        self.assertIsNone(database.create_user(
            "SecondSuper", generate_password_hash("another-test-pass"),
            "superadmin", is_protected=True,
        ))

        response = self.login_as(self.client, "SuperTest", "super-test-pass")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/compte.html"))
        account = self.client.get("/compte.html").get_data(as_text=True)
        self.assertIn("Bonjour SuperTest", account)
        self.assertIn("Superadministrateur protégé", account)

    def test_password_change_and_one_time_reset_link(self):
        self.login_as(self.client, "MembreTest", "membre123")
        token = self.csrf_token(self.client, "/compte.html")
        response = self.client.post("/compte/mot-de-passe", data={
            "_csrf_token": token,
            "current_password": "membre123",
            "password": "nouveau-mot-de-passe",
            "password_confirmation": "nouveau-mot-de-passe",
        })
        self.assertEqual(response.status_code, 302)
        self.client.post("/logout", data={"_csrf_token": token})
        self.assertEqual(
            self.login_as(self.client, "MembreTest", "nouveau-mot-de-passe").status_code, 302
        )
        self.client.post("/logout", data={"_csrf_token": self.csrf_token(self.client, "/compte.html")})

        reset_token = self.csrf_token(self.client, "/mot-de-passe-oublie.html")
        with patch.object(app_module, "send_password_reset_email", return_value=True) as sender:
            response = self.client.post("/mot-de-passe-oublie.html", data={
                "_csrf_token": reset_token, "email": "membretest"
            })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(sender.called)

        reset_token = self.csrf_token(self.client, "/mot-de-passe-oublie.html")
        with database.get_db() as db:
            db.execute("UPDATE users SET email = ? WHERE id = ?", ("membre@example.com", self.member_id))
        with patch.object(app_module, "send_password_reset_email", return_value=True) as sender:
            self.client.post("/mot-de-passe-oublie.html", data={
                "_csrf_token": reset_token, "email": "membre@example.com"
            })
        self.assertTrue(sender.called)
        reset_path = urlsplit(sender.call_args.args[2]).path
        raw_token = reset_path.rsplit("/", 1)[-1]
        csrf = self.csrf_token(self.client, reset_path)
        response = self.client.post(reset_path, data={
            "_csrf_token": csrf,
            "password": "mot-de-passe-reinitialise",
            "password_confirmation": "mot-de-passe-reinitialise",
        })
        self.assertTrue(response.location.endswith("/login.html"))
        self.assertEqual(
            self.login_as(self.client, "membre@example.com", "mot-de-passe-reinitialise").status_code, 302
        )
        self.client.get("/logout")
        self.assertIn(
            "invalide ou a expiré", self.client.get(
                f"/reinitialiser-mot-de-passe/{raw_token}", follow_redirects=True
            ).get_data(as_text=True)
        )

    def test_public_registration_creates_member_and_contribution(self):
        self.assertIn("Créer un compte", self.client.get("/").get_data(as_text=True))
        token = self.csrf_token(self.client, "/register.html")
        response = self.client.post("/register.html", data={
            "_csrf_token": token,
            "username": "NouvelleEtudiante",
            "email": "nouvelle@example.com",
            "password": "motdepasse123",
            "password_confirmation": "motdepasse123",
            "role": "superadmin",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/compte.html"))
        user = database.user_credentials("nouvelle@example.com")
        self.assertEqual(user["username"], "NouvelleEtudiante")
        self.assertEqual(user["role"], "member")
        self.assertNotEqual(user["password_hash"], "motdepasse123")
        contributions = database.contributions_for_user(user["id"])
        self.assertEqual(len(contributions), 1)
        self.assertEqual(contributions[0]["school_year"], current_school_year())
        self.assertEqual(contributions[0]["status"], "due")
        self.assertEqual(contributions[0]["amount_cents"], 500)
        account = self.client.get("/compte.html").get_data(as_text=True)
        self.assertIn("Ma cotisation", account)
        self.assertIn("À régler", account)
        self.assertIn("Paiement en ligne bientôt disponible", account)

    def test_registration_rejects_invalid_or_duplicate_data(self):
        token = self.csrf_token(self.client, "/register.html")
        invalid = self.client.post("/register.html", data={
            "_csrf_token": token,
            "username": "InscriptionTest",
            "email": "adresse-invalide",
            "password": "motdepasse123",
            "password_confirmation": "motdepasse123",
        })
        self.assertIn("adresse e-mail valide", invalid.get_data(as_text=True))
        self.assertIsNone(database.user_credentials("InscriptionTest"))

        database.create_user(
            "EmailExistant", generate_password_hash("motdepasse123"),
            email="existant@example.com",
        )
        duplicate = self.client.post("/register.html", data={
            "_csrf_token": token,
            "username": "AutreIdentifiant",
            "email": "existant@example.com",
            "password": "motdepasse123",
            "password_confirmation": "motdepasse123",
        })
        self.assertIn("déjà utilisé", duplicate.get_data(as_text=True))
        self.assertIsNone(database.user_credentials("AutreIdentifiant"))

    def test_invalid_login_and_csrf_are_rejected(self):
        token = self.csrf_token(self.client, "/login.html")
        response = self.client.post(
            "/login.html",
            data={"_csrf_token": token, "username": "SuperTest", "password": "incorrect"},
        )
        self.assertIn("Identifiant ou mot de passe incorrect", response.get_data(as_text=True))
        self.assertEqual(
            self.client.post(
                "/login.html", data={"username": "SuperTest", "password": "super-test-pass"}
            ).status_code,
            400,
        )

    def test_admin_can_create_accounts_and_manage_roles(self):
        client = self.app.test_client()
        self.login_as(client, "AdminTest", "admin123")
        token = self.csrf_token(client, "/admin.html")
        response = client.post("/admin/users/create", data={
            "_csrf_token": token,
            "username": "NouveauCompte",
            "password": "secret123",
            "role": "member",
        })
        self.assertEqual(response.status_code, 302)
        created = database.user_credentials("nouveaucompte")
        self.assertIsNotNone(created)
        self.assertEqual(created["role"], "member")

        client.post(
            f"/admin/users/{created['id']}/role",
            data={"_csrf_token": token, "role": "admin"},
        )
        self.assertEqual(database.user_by_id(created["id"])["role"], "admin")

        client.post(
            f"/admin/users/{self.super_id}/role",
            data={"_csrf_token": token, "role": "member"},
        )
        self.assertEqual(database.user_by_id(self.super_id)["role"], "superadmin")

        response = client.post("/admin/users/create", data={
            "_csrf_token": token,
            "username": "CompteBDE",
            "password": "equipe123",
            "role": "bde",
        })
        self.assertEqual(response.status_code, 302)
        bde_user = database.user_credentials("CompteBDE")
        self.assertEqual(bde_user["role"], "bde")
        self.assertTrue(database.bde_profile_for_user(bde_user["id"])["is_visible"])

    def test_bde_role_can_create_events_but_not_manage_accounts(self):
        bde_id = database.create_user(
            "EquipeBDE", generate_password_hash("equipe-test"), "bde"
        )
        self.assertIsNotNone(bde_id)
        profile = database.bde_profile_for_user(bde_id)
        self.assertTrue(profile["is_visible"])

        client = self.app.test_client()
        self.login_as(client, "EquipeBDE", "equipe-test")
        self.assertTrue(client.get("/admin.html").location.endswith("/compte.html"))
        events_html = client.get("/evenements.html").get_data(as_text=True)
        self.assertIn("data-admin-event-open", events_html)
        token = self.csrf_token(client, "/evenements.html")
        response = client.post("/admin/events/create", data={
            "_csrf_token": token,
            "title": "Événement créé par le BDE",
            "description": "Un événement de test.",
            "start_date": "2027-01-12",
            "start_time": "18:00",
            "end_date": "",
            "end_time": "",
            "location": "ORT Montreuil",
            "organizer_name": "",
            "price": "0",
            "capacity": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(database.events()[-1]["title"], "Événement créé par le BDE")

    def test_role_changes_control_default_bde_profile_visibility(self):
        self.assertIsNone(database.bde_profile_for_user(self.member_id))
        self.assertTrue(database.update_user_role(self.member_id, "bde"))
        profile = database.bde_profile_for_user(self.member_id)
        self.assertTrue(profile["is_visible"])
        self.assertIn("MembreTest", self.client.get("/bde.html").get_data(as_text=True))
        self.assertTrue(database.update_user_role(self.member_id, "member"))
        self.assertFalse(database.bde_profile_for_user(self.member_id)["is_visible"])
        self.assertNotIn("MembreTest", self.client.get("/bde.html").get_data(as_text=True))

    def test_bde_member_can_upload_and_edit_public_profile(self):
        bde_id = database.create_user(
            "ProfilBDE", generate_password_hash("profil-test"), "bde"
        )
        client = self.app.test_client()
        self.login_as(client, "ProfilBDE", "profil-test")
        token = self.csrf_token(client, "/compte.html")
        response = client.post(
            "/compte/profil",
            data={
                "_csrf_token": token,
                "display_name": "Camille Martin",
                "bio": "Une courte biographie publique.",
                "instagram_url": "https://instagram.com/camille",
                "linkedin_url": "",
                "website_url": "https://example.com",
                "photo": (self.sample_image(), "portrait.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        profile = database.bde_profile_for_user(bde_id)
        self.assertEqual(profile["display_name"], "Camille Martin")
        self.assertTrue(profile["photo_path"].endswith(".webp"))
        filename = Path(profile["photo_path"]).name
        self.assertTrue((app_module.UPLOAD_FOLDER / filename).is_file())
        page = client.get("/bde.html").get_data(as_text=True)
        self.assertIn("Camille Martin", page)
        self.assertIn("Une courte biographie publique.", page)
        self.assertIn("data-member-trigger", page)

    def test_admin_can_manage_manual_bde_profiles(self):
        client = self.app.test_client()
        self.login_as(client, "AdminTest", "admin123")
        token = self.csrf_token(client, "/admin.html?onglet=bde")
        protected_profile = database.bde_profile_for_user(self.super_id)
        client.post(
            f"/admin/profiles/{protected_profile['id']}/visibility",
            data={"_csrf_token": token, "visible": "0"},
        )
        self.assertTrue(database.bde_profile_for_user(self.super_id)["is_visible"])
        response = client.post(
            "/admin/profiles/create",
            data={
                "_csrf_token": token,
                "display_name": "Alex Dupont",
                "team_role": "Trésorier",
                "bio": "Gestion du budget et des projets.",
                "sort_order": "2",
                "instagram_url": "",
                "linkedin_url": "https://linkedin.com/in/alex",
                "website_url": "",
                "photo": (self.sample_image(), "alex.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        profile = next(p for p in database.bde_profiles(False) if p["display_name"] == "Alex Dupont")
        self.assertIsNone(profile["user_id"])
        self.assertIn("Trésorier", self.client.get("/bde.html").get_data(as_text=True))

        client.post(
            f"/admin/profiles/{profile['id']}/visibility",
            data={"_csrf_token": token, "visible": "0"},
        )
        self.assertNotIn("Alex Dupont", self.client.get("/bde.html").get_data(as_text=True))
        client.post(
            f"/admin/profiles/{profile['id']}/delete",
            data={"_csrf_token": token},
        )
        self.assertIsNone(database.bde_profile_by_id(profile["id"]))

    def test_admin_can_manage_contributions_but_not_protected_account(self):
        client = self.app.test_client()
        self.login_as(client, "AdminTest", "admin123")
        admin_page = client.get("/admin.html?onglet=cotisations")
        html = admin_page.get_data(as_text=True)
        self.assertIn("Cotisations", html)
        self.assertIn('data-admin-panel="cotisations"', html)
        token = self.csrf_token(client, "/admin.html?onglet=cotisations")

        contribution = next(
            item for item in database.contributions_with_users()
            if item["user_id"] == self.member_id
        )
        response = client.post(
            f"/admin/contributions/{contribution['id']}/update",
            data={
                "_csrf_token": token,
                "school_year": current_school_year(),
                "amount": "20,00",
                "status": "paid",
                "payment_method": "Espèces",
                "external_reference": "RECU-42",
                "paid_at": "2026-09-15T14:30",
                "notes": "Remis au bureau.",
            },
        )
        self.assertEqual(response.status_code, 302)
        updated = database.contribution_by_id(contribution["id"])
        self.assertEqual(updated["amount_cents"], 2000)
        self.assertEqual(updated["status"], "paid")
        self.assertEqual(updated["external_reference"], "RECU-42")

        protected = next(
            item for item in database.contributions_with_users()
            if item["user_id"] == self.super_id
        )
        client.post(
            f"/admin/contributions/{protected['id']}/update",
            data={
                "_csrf_token": token,
                "school_year": current_school_year(),
                "amount": "0",
                "status": "exempt",
                "payment_method": "",
                "external_reference": "",
                "paid_at": "",
                "notes": "",
            },
        )
        self.assertEqual(database.contribution_by_id(protected["id"])["status"], "due")

        member_client = self.app.test_client()
        self.login_as(member_client, "MembreTest", "membre123")
        member_account = member_client.get("/compte.html").get_data(as_text=True)
        self.assertIn("20,00 €", member_account)
        self.assertIn("Payée", member_account)
        self.assertIn("Espèces", member_account)

    def test_member_cannot_open_admin_panel_or_create_event(self):
        client = self.app.test_client()
        self.login_as(client, "MembreTest", "membre123")
        response = client.get("/admin.html")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/compte.html"))
        events_html = client.get("/evenements.html").get_data(as_text=True)
        self.assertNotIn("data-admin-event-open", events_html)
        token = self.csrf_token(client, "/compte.html")
        response = client.post("/admin/events/create", data={"_csrf_token": token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(database.events()), 3)

    def test_admin_can_create_event_and_prepare_google_calendar(self):
        client = self.app.test_client()
        self.login_as(client, "AdminTest", "admin123")
        token = self.csrf_token(client, "/evenements.html")
        response = client.post("/admin/events/create", data={
            "_csrf_token": token,
            "title": "Réunion des délégués",
            "description": "Préparation du prochain projet étudiant.",
            "start_date": "2026-12-03",
            "start_time": "18:00",
            "end_date": "2026-12-03",
            "end_time": "19:30",
            "location": "Campus ORT Montreuil",
            "organizer_name": "",
            "price": "0",
            "capacity": "30",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("/compte.html?event_created=", response.location)
        created = database.events()[-1]
        self.assertEqual(created["title"], "Réunion des délégués")
        self.assertEqual(created["organizer_name"], "BDE ORT Sup")
        confirmation = client.get(response.location).get_data(as_text=True)
        self.assertIn("Ajouter à Google Agenda", confirmation)
        self.assertIn("calendar.google.com/calendar/render?", confirmation)
        self.assertIn("R%C3%A9union+des+d%C3%A9l%C3%A9gu%C3%A9s", confirmation)

    def test_event_details_and_calendar_selection(self):
        html = self.client.get("/evenements.html").get_data(as_text=True)
        self.assertEqual(html.count("data-event-trigger"), 3)
        self.assertIn('id="event-dialog-1"', html)
        self.assertIn("Date et début", html)
        self.assertIn("Capacité", html)
        self.assertIn("Organisateur", html)
        self.assertIn("BDE ORT Sup", html)
        self.assertIn("Voir dans le calendrier", html)
        self.assertIn("/calendrier.html?event=1#evenement-selectionne", html)

        calendar = self.client.get("/calendrier.html?event=1").get_data(as_text=True)
        self.assertIn('id="evenement-selectionne"', calendar)
        self.assertIn("Soirée de rentrée", calendar)
        self.assertIn("Rechercher dans Google Agenda", calendar)
        self.assertIn("q=Soir%C3%A9e+de+rentr%C3%A9e", calendar)

    def test_external_qr_requires_team_login_and_explicit_check_in(self):
        database.register_for_event(1, self.member_id)
        token = app_module.URLSafeTimedSerializer(
            self.app.secret_key, salt="bde-event-presence-v1"
        ).dumps({"event_id": 1, "user_id": self.member_id})
        check_in_url = f"/bde/presences/valider/{token}"

        response = self.client.get(check_in_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login.html"))

        response = self.login_as(self.client, "AdminTest", "admin123")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith(check_in_url))

        confirmation = self.client.get(check_in_url)
        self.assertEqual(confirmation.status_code, 200)
        self.assertIn("MembreTest", confirmation.get_data(as_text=True))
        scanner_page = self.client.get("/bde/presences.html").get_data(as_text=True)
        self.assertIn("Poste de contrôle prêt", scanner_page)
        self.assertIn("État des entrées par événement", scanner_page)
        admin_events = self.client.get("/admin.html?onglet=events").get_data(as_text=True)
        self.assertIn('href="/bde/presences.html"', admin_events)
        self.assertIn("Scanner les présences", admin_events)
        registration = database.event_registrations_for_event(1)[0]
        self.assertIsNone(registration["checked_in_at"])

        csrf = self.csrf_token(self.client, check_in_url)
        validated = self.client.post(check_in_url, data={"_csrf_token": csrf})
        self.assertEqual(validated.status_code, 200)
        self.assertIn("Entrée validée", validated.get_data(as_text=True))
        registration = database.event_registrations_for_event(1)[0]
        self.assertIsNotNone(registration["checked_in_at"])

        repeated = self.client.post(check_in_url, data={"_csrf_token": csrf})
        self.assertIn("Déjà enregistré", repeated.get_data(as_text=True))

    def test_direct_google_event_url_is_used_when_available(self):
        with database.get_db() as db:
            db.execute(
                "UPDATE events SET google_calendar_url = ? WHERE id = 1",
                ("https://calendar.google.com/calendar/event?eid=exemple",),
            )
        html = self.client.get("/calendrier.html?event=1").get_data(as_text=True)
        self.assertIn("Ouvrir dans Google Agenda", html)
        self.assertIn("calendar/event?eid=exemple", html)

    def test_event_can_have_a_specific_organizer(self):
        with database.get_db() as db:
            db.execute("UPDATE events SET organizer_name = ? WHERE id = 1", ("Club partenaire",))
        event = database.event_by_id(1)
        self.assertEqual(event["organizer_name"], "Club partenaire")
        self.assertIn("Club partenaire", self.client.get("/evenements.html").get_data(as_text=True))

    def test_admin_can_delete_event_and_its_registrations(self):
        database.register_for_event(1, self.member_id)
        self.login_as(self.client, "AdminTest", "admin123")
        csrf = self.csrf_token(self.client, "/admin.html?onglet=events")
        response = self.client.post(
            "/admin/evenements/1/supprimer",
            data={"_csrf_token": csrf},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin.html?onglet=events"))
        self.assertIsNone(database.event_by_id(1))
        self.assertEqual(database.event_registrations_for_event(1), [])

    def test_seed_restores_only_an_empty_event_collection(self):
        with database.get_db() as db:
            db.execute("DELETE FROM events")
        self.assertTrue(seed_database())
        self.assertEqual(len(database.events()), 3)
        self.assertFalse(seed_database())

    def test_seed_preserves_existing_data(self):
        with database.get_db() as db:
            db.execute("UPDATE site_settings SET value = '2' WHERE key = 'poles_count'")
            db.execute("UPDATE events SET title = 'Mon événement' WHERE id = 1")
        self.assertFalse(seed_database())
        self.assertEqual(database.site_settings()["poles_count"], "2")
        self.assertEqual(database.events()[0]["title"], "Mon événement")
        self.assertEqual(database.stats(), {"events": 3, "products": 3})

    def test_unknown_routes_do_not_expose_files(self):
        for route in ("/base.html", "/partials/header.html", "/backend/app.py",
                      "/db/bde-ort-sup.db", "/associations.html", "/rec.html", "/inconnue.html"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 404)
                self.assertIn("Page introuvable", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
