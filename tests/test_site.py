"""Vérifications de la migration Flask, avec une base temporaire indépendante."""

import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urljoin, urlsplit

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
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        seed_database()

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
        self.assertEqual(len(self.client.get("/api/associations").json), 3)
        events = self.client.get("/api/events").json
        products = self.client.get("/api/products").json
        self.assertEqual(len(events), 2)
        self.assertEqual(len(products), 2)
        self.assertTrue(all(event["published"] is True for event in events))
        self.assertTrue(all(product["is_active"] is True for product in products))
        self.assertIn("association_name", events[0])
        self.assertEqual(self.client.get("/api/stats").json, {"associations": 3, "events": 3, "products": 3})

    def test_empty_lists_are_readable(self):
        with database.get_db() as db:
            db.execute("DELETE FROM events")
            db.execute("DELETE FROM products")
            db.execute("DELETE FROM associations")
        self.assertIn("Aucun événement", self.client.get("/").get_data(as_text=True))
        self.assertIn("Aucun événement", self.client.get("/calendrier.html").get_data(as_text=True))
        self.assertIn("Aucun article", self.client.get("/billetterie.html").get_data(as_text=True))
        self.assertIn("bientôt présentées", self.client.get("/associations.html").get_data(as_text=True))

    def test_seed_preserves_existing_data(self):
        with database.get_db() as db:
            db.execute("UPDATE site_settings SET value = '999' WHERE key = 'members_count'")
            db.execute("UPDATE events SET title = 'Mon événement' WHERE id = 1")
        self.assertFalse(seed_database())
        self.assertEqual(database.site_settings()["members_count"], "999")
        self.assertEqual(database.events()[0]["title"], "Mon événement")
        self.assertEqual(database.stats(), {"associations": 3, "events": 3, "products": 3})

    def test_unknown_routes_do_not_expose_files(self):
        for route in ("/base.html", "/partials/header.html", "/backend/app.py",
                      "/db/bde-ort-sup.db", "/inconnue.html"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 404)
                self.assertIn("Page introuvable", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
