"""Boutique : tests isolés, jamais de commande ni de paiement dans la vraie base."""

import re
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from PIL import Image
from werkzeug.security import generate_password_hash

from backend import database, shop, shop_store as store
from backend.app import create_app
from backend.seed import seed_database


class ShopTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        for target, name, value in (
            (database, "DATABASE_PATH", self.folder / "shop.db"),
            (shop, "UPLOAD_FOLDER", self.folder / "uploads"),
        ):
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.app = create_app()
        self.app.config["TESTING"] = True
        seed_database()
        self.ids = {role: database.create_user(role, generate_password_hash("testing123"), role)
                    for role in ("member", "bde", "admin", "superadmin")}
        self.client = self.app.test_client()

    def token(self, client=None):
        client = client or self.client
        with client.session_transaction() as session:
            session.setdefault("_csrf_token", "test-csrf-token")
            return session["_csrf_token"]

    def post(self, path, data=None, client=None, **kwargs):
        client = client or self.client
        return client.post(path, data={"_csrf_token": self.token(client), **(data or {})}, **kwargs)

    def login(self, role="member", client=None):
        return self.post("/login.html", {"username": role, "password": "testing123", "next": "checkout"}, client)

    def add(self, quantity=1, client=None, product=2):
        return self.post(f"/panier/articles/{product}", {"quantity": str(quantity), "action": "add"}, client)

    def quote(self, client=None):
        response = (client or self.client).get("/commande.html")
        self.assertEqual(response.status_code, 200)
        return re.search(r'name="quote" value="([^"]+)"', response.get_data(as_text=True)).group(1)

    def prepare(self, quantity=1, role="member", client=None):
        self.login(role, client)
        self.add(quantity, client)
        quote = self.quote(client)
        response = self.post("/commande.html", {"quote": quote}, client)
        self.assertEqual(response.status_code, 303)
        return response.location.rsplit("/", 1)[1], quote

    @staticmethod
    def image():
        output = BytesIO()
        Image.new("RGB", (100, 100), "blue").save(output, "PNG")
        output.seek(0)
        return output

    def product_data(self, **overrides):
        return {"name": "Gourde ORT", "description": "Une gourde <test> pour le campus.",
                "price": "12.50", "stock": "10", "is_active": "1", "product_type": "article",
                "image": (self.image(), "photo.png"), **overrides}

    def test_catalogue_detail_and_empty_cart(self):
        for path in ("/billetterie.html", "/boutique/articles/2", "/panier.html"):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get("/boutique/articles/999").status_code, 404)
        self.assertEqual(store.product(1)["product_type"], "membership")
        self.add(product=1)
        self.assertEqual(store.cart_contents(store.find_cart(guest_token=self.client.get_cookie("bde_cart").value))["count"], 0)

    def test_only_admins_can_manage_shop(self):
        paths = ("/admin/boutique/articles/nouveau", "/admin/boutique/articles/2")
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 302)
        for role in ("member", "bde", "admin", "superadmin"):
            client = self.app.test_client()
            self.login(role, client)
            for path in paths:
                self.assertEqual(client.get(path).status_code, 200 if "admin" in role else 403)
            for path in ("/admin/boutique/articles/2/stock", "/admin/boutique/articles/2/visibilite"):
                self.assertEqual(self.post(path, {"stock": "12", "is_active": "1"}, client).status_code,
                                 303 if "admin" in role else 403)
        self.assertEqual(self.client.post("/panier/articles/2", data={"quantity": "1"}).status_code, 400)

    def test_admin_create_edit_upload_stock_and_archive(self):
        self.login("admin")
        response = self.post("/admin/boutique/articles/nouveau", self.product_data())
        self.assertEqual(response.status_code, 303)
        product = store.catalogue()[0]
        self.assertEqual((product["price_cents"], product["available"]), (1250, 10))
        photo = shop.UPLOAD_FOLDER / Path(product["image_url"]).name
        self.assertTrue(photo.is_file())
        with Image.open(photo) as image:
            self.assertEqual(image.format, "WEBP")
        self.assertIn("&lt;test&gt;", self.client.get(f"/boutique/articles/{product['id']}").get_data(as_text=True))
        data = self.product_data(price="15,90", stock="8", name="Gourde mise à jour")
        data.pop("image")
        self.assertEqual(self.post(f"/admin/boutique/articles/{product['id']}", data).status_code, 303)
        self.assertEqual(store.product(product["id"])["price_cents"], 1590)
        self.post(f"/admin/boutique/articles/{product['id']}/stock", {"stock": "0"})
        self.assertEqual(store.product(product["id"])["available"], 0)
        self.post(f"/admin/boutique/articles/{product['id']}/visibilite", {"is_active": "0"})
        self.assertIsNone(store.product(product["id"]))
        self.assertEqual(self.client.get(f"/boutique/articles/{product['id']}").status_code, 404)
        self.post(f"/admin/boutique/articles/{product['id']}/visibilite", {"is_active": "1"})
        self.assertIsNotNone(store.product(product["id"]))

    def test_invalid_prices_stock_images_and_lengths_rejected(self):
        self.login("admin")
        cases = [{"price": value} for value in ("NaN", "Infinity", "-1", "1.999", "10001", "")]
        cases += [{"stock": "-1"}, {"stock": "1.5"}, {"name": ""}, {"description": "a" * 5001},
                  {"image": (BytesIO(b"<svg onload='alert(1)'/>"), "photo.png")}]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(self.post("/admin/boutique/articles/nouveau", self.product_data(**case)).status_code, 400)
        self.assertEqual(len(store.catalogue()), 3)
        self.assertEqual(list(shop.UPLOAD_FOLDER.glob("*.webp")), [])

    def test_guest_cart_persists_and_is_private(self):
        response = self.add(2)
        cookie = self.client.get_cookie("bde_cart")
        self.assertTrue(cookie.http_only)
        self.assertIn("Max-Age=7776000", response.headers.get("Set-Cookie", ""))
        fresh = self.app.test_client()
        fresh.set_cookie("bde_cart", cookie.value)
        html = fresh.get("/panier.html").get_data(as_text=True)
        self.assertIn("60,00 €", html)
        self.assertIn('value="2"', html)
        self.assertIn("Ton panier est vide", self.app.test_client().get("/panier.html").get_data(as_text=True))
        self.post("/panier/articles/2", {"quantity": "0"})
        self.assertIn("Ton panier est vide", self.client.get("/panier.html").get_data(as_text=True))

    def test_login_merges_carts_and_logout_does_not_expose_account_cart(self):
        saved, _ = store.ensure_cart(self.ids["member"])
        store.change_quantity(saved, 2, 2)
        self.add(3)
        guest_token = self.client.get_cookie("bde_cart").value
        response = self.login()
        self.assertEqual(response.location, "/commande.html")
        self.assertIsNone(self.client.get_cookie("bde_cart"))
        self.assertEqual(store.cart_contents(saved)["count"], 5)
        self.assertIsNone(store.find_cart(guest_token=guest_token))
        self.post("/logout")
        self.assertIn("Ton panier est vide", self.client.get("/panier.html").get_data(as_text=True))
        self.login()
        self.assertEqual(store.cart_contents(store.find_cart(self.ids["member"]))["count"], 5)

    def test_register_keeps_guest_cart(self):
        self.add(1)
        response = self.post("/register.html", {"username": "NewShop", "email": "shop@example.test",
            "password": "testing123", "password_confirmation": "testing123", "next": "checkout"})
        self.assertEqual(response.location, "/commande.html")
        with self.client.session_transaction() as session:
            self.assertEqual(store.cart_contents(store.find_cart(session["user_id"]))["count"], 1)

    def test_invalid_quantities_stock_changes_and_hidden_products(self):
        self.login()
        for value in ("-1", "100", "1.5", "text", "51"):
            self.add(value)
        cart_id = store.find_cart(self.ids["member"])
        self.assertEqual(store.cart_contents(cart_id)["count"], 0)
        self.add(2)
        store.update_stock(2, 1)
        self.assertFalse(store.cart_contents(cart_id)["valid"])
        self.assertEqual(self.client.get("/commande.html").status_code, 302)
        store.update_stock(2, 5)
        store.set_visibility(2, False)
        self.assertFalse(store.cart_contents(cart_id)["valid"])
        self.post("/panier/articles/2", {"quantity": "0"})
        self.assertEqual(store.cart_contents(cart_id)["count"], 0)

    def test_checkout_pending_no_payment_forgery_and_double_submission(self):
        order_id, quote = self.prepare(2)
        order = store.order(order_id)
        self.assertEqual((order["status"], order["total_cents"]), ("awaiting_payment", 6000))
        self.assertEqual((store.product(2)["stock"], store.product(2)["available"]), (50, 48))
        self.assertEqual(store.cart_contents(store.find_cart(self.ids["member"]))["count"], 0)
        self.assertEqual(self.post("/commande.html", {"quote": quote, "status": "paid", "total": "1"}).location, f"/commandes/{order_id}")
        self.assertEqual(len(store.orders()), 1)
        self.assertEqual(store.order(order_id)["status"], "awaiting_payment")
        for path in (f"/commandes/{order_id}", "/commandes.html"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("En attente de paiement", response.get_data(as_text=True))
        self.assertFalse(store.fulfil_order(order_id, "ready"))
        self.assertFalse(store.fulfil_order(order_id, "paid"))

    def test_stale_price_and_tampered_quote_cannot_order(self):
        self.login()
        self.add()
        quote = self.quote()
        with database.get_db() as db:
            db.execute("UPDATE products SET price_cents=3500 WHERE id=2")
        self.post("/commande.html", {"quote": quote})
        self.assertEqual(store.orders(), [])
        self.post("/commande.html", {"quote": quote + "tampered"})
        self.assertEqual(store.orders(), [])
        self.assertEqual(store.cart_contents(store.find_cart(self.ids["member"]))["count"], 1)

    def test_order_privacy_cancellation_and_expiration(self):
        order_id, _ = self.prepare()
        other = self.app.test_client()
        self.login("bde", other)
        self.assertEqual(other.get(f"/commandes/{order_id}").status_code, 404)
        self.assertEqual(self.post(f"/commandes/{order_id}/annuler", client=other).status_code, 409)
        self.post(f"/commandes/{order_id}/annuler")
        self.assertEqual(store.product(2)["available"], 50)
        order_id, _ = self.prepare()
        with database.get_db() as db:
            db.execute("UPDATE shop_orders SET expires_at='2000-01-01 00:00:00' WHERE id=?", (order_id,))
        self.assertEqual(store.product(2)["available"], 50)
        self.assertEqual(store.order(order_id)["status"], "expired")
        with self.assertRaises(ValueError):
            store.confirm_verified_payment(order_id, "test", "expired-payment", 3000, "EUR")

    def test_reservations_prevent_oversell_even_with_concurrent_checkout(self):
        store.update_stock(2, 1)
        carts = []
        for role in ("member", "bde"):
            cart, _ = store.ensure_cart(self.ids[role])
            store.change_quantity(cart, 2, 1)
            carts.append((self.ids[role], cart, store.quote_items(store.cart_contents(cart)), role))
        barrier = Barrier(2)
        def buy(args):
            barrier.wait()
            try:
                return store.prepare_order(*args)
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(buy, carts))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(store.product(2)["available"], 0)
        with self.assertRaises(ValueError):
            store.update_stock(2, 0)

    def test_verified_payment_is_idempotent_and_only_paid_order_can_be_fulfilled(self):
        order_id, _ = self.prepare(2)
        for amount, currency in ((1, "EUR"), (6000, "USD")):
            with self.assertRaises(ValueError):
                store.confirm_verified_payment(order_id, "test", "payment-1", amount, currency)
        self.assertTrue(store.confirm_verified_payment(order_id, "test", "payment-1", 6000, "EUR"))
        self.assertFalse(store.confirm_verified_payment(order_id, "test", "payment-1", 6000, "EUR"))
        self.assertEqual(store.product(2)["stock"], 48)
        self.assertEqual(store.product(2)["reserved"], 0)
        self.assertFalse(store.cancel_order(order_id, self.ids["member"]))
        self.assertEqual(self.post(f"/admin/boutique/commandes/{order_id}/statut", {"status": "ready"}).status_code, 403)
        self.post("/logout")
        self.login("admin")
        self.assertEqual(self.post(f"/admin/boutique/commandes/{order_id}/statut", {"status": "ready"}).status_code, 303)
        self.assertEqual(store.order(order_id)["status"], "ready")
        self.post(f"/admin/boutique/commandes/{order_id}/statut", {"status": "collected"})
        self.assertEqual(store.order(order_id)["status"], "collected")

    def test_payment_reference_cannot_pay_two_orders(self):
        first, _ = self.prepare()
        second, _ = self.prepare()
        store.confirm_verified_payment(first, "test", "unique-ref", 3000, "EUR")
        with self.assertRaises(sqlite3.IntegrityError):
            store.confirm_verified_payment(second, "test", "unique-ref", 3000, "EUR")
        self.assertEqual(store.product(2)["stock"], 49)
        self.assertEqual(store.order(second)["status"], "awaiting_payment")


if __name__ == "__main__":
    unittest.main()
