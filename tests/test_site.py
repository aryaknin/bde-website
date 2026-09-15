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
from backend.app import PAGES, create_app
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

    def test_seed_restores_only_an_empty_event_collection(self):
        with database.get_db() as db:
            db.execute("DELETE FROM events")
        self.assertTrue(seed_database())
        self.assertEqual(len(database.events()), 3)
        self.assertFalse(seed_database())

    def test_seed_preserves_existing_data(self):
        with database.get_db() as db:
            db.execute("UPDATE site_settings SET value = '999' WHERE key = 'members_count'")
            db.execute("UPDATE events SET title = 'Mon événement' WHERE id = 1")
        self.assertFalse(seed_database())
        self.assertEqual(database.site_settings()["members_count"], "999")
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
