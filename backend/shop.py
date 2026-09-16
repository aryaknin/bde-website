"""Interface boutique ; aucun encaissement avant l’intégration d’un prestataire."""

import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps
from uuid import uuid4
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from itsdangerous import BadSignature, URLSafeTimedSerializer
from PIL import Image, ImageOps, UnidentifiedImageError

if __package__:
    from . import database, shop_store as store
else:
    import database
    import shop_store as store

shop = Blueprint("shop", __name__)
UPLOAD_FOLDER = database.PROJECT_DIR / "static" / "uploads" / "products"
CART_COOKIE = "bde_cart"


def signed_quotes():
    return URLSafeTimedSerializer(current_app.secret_key, salt="bde-checkout-v1")


def attach_cart(user_id):
    store.merge_guest_cart(user_id, request.cookies.get(CART_COOKIE))
    g.clear_guest_cart = True


def cart_id(create=False):
    user_id = g.user["id"] if g.user else None
    token = request.cookies.get(CART_COOKIE)
    if create:
        identifier, new_token = store.ensure_cart(user_id, token)
        if new_token:
            g.new_cart_token = new_token
        return identifier
    return store.find_cart(user_id, token)


def authenticated(admin=False):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.user:
                return redirect(url_for("login", next="checkout" if not admin else ""))
            if admin and g.user["role"] not in ("admin", "superadmin"):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorate


@shop.app_context_processor
def shop_context():
    return {"cart_count": store.cart_contents(cart_id())["count"], "order_statuses": store.ORDER_STATUSES}


@shop.after_app_request
def cart_cookies(response):
    if getattr(g, "new_cart_token", None):
        response.set_cookie(CART_COOKIE, g.new_cart_token, max_age=90 * 86400,
                            httponly=True, samesite="Lax", secure=current_app.config["SESSION_COOKIE_SECURE"])
    if getattr(g, "clear_guest_cart", False):
        response.delete_cookie(CART_COOKIE, httponly=True, samesite="Lax",
                               secure=current_app.config["SESSION_COOKIE_SECURE"])
    if request.endpoint != "static":
        response.headers["Cache-Control"] = "private, no-store"
    return response


@shop.app_template_filter("shop_date")
def shop_date(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).astimezone(
        ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y à %H:%M")


@shop.get("/boutique/articles/<int:product_id>")
def product_detail(product_id):
    product = store.product(product_id)
    if not product:
        abort(404)
    return render_template("shop/product.html", page="billetterie", title=product["name"], product=product)


@shop.get("/panier.html")
def cart():
    return render_template("shop/cart.html", page="cart", title="Mon panier", cart=store.cart_contents(cart_id()))


@shop.post("/panier/articles/<int:product_id>")
def cart_update(product_id):
    try:
        quantity = int(request.form.get("quantity", "1"))
        store.change_quantity(cart_id(create=True), product_id, quantity, add=request.form.get("action") == "add")
        flash("Article retiré du panier." if quantity == 0 else "Panier mis à jour.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("shop.cart"), code=303)


@shop.route("/commande.html", methods=("GET", "POST"))
@authenticated()
def checkout():
    identifier = cart_id()
    if request.method == "POST":
        try:
            quote = signed_quotes().loads(request.form.get("quote", ""), max_age=1800)
            if quote["user"] != g.user["id"]:
                raise ValueError("Ce récapitulatif ne correspond pas à ton compte.")
            order_id = store.prepare_order(g.user["id"], identifier, quote["items"], quote["key"])
            return redirect(url_for("shop.order_detail", order_id=order_id), code=303)
        except BadSignature:
            flash("Le récapitulatif a expiré ou est invalide. Vérifie à nouveau ton panier.", "error")
        except (ValueError, KeyError, TypeError) as error:
            flash(str(error) if isinstance(error, ValueError) else "Récapitulatif invalide.", "error")
        return redirect(url_for("shop.cart"), code=303)
    contents = store.cart_contents(identifier)
    if not contents["valid"]:
        flash("Ajoute des articles disponibles dans ton panier pour continuer.", "info")
        return redirect(url_for("shop.cart"))
    quote = signed_quotes().dumps({"user": g.user["id"], "items": store.quote_items(contents), "key": secrets.token_hex(24)})
    return render_template("shop/checkout.html", page="cart", title="Préparer ma commande", cart=contents, quote=quote)


@shop.get("/commandes.html")
@authenticated()
def my_orders():
    return render_template("shop/orders.html", page="account", title="Mes commandes", orders=store.orders(g.user["id"]))


@shop.get("/commandes/<order_id>")
@authenticated()
def order_detail(order_id):
    order = store.order(order_id)
    if not order or (order["user_id"] != g.user["id"] and g.user["role"] not in ("admin", "superadmin")):
        abort(404)
    return render_template("shop/order.html", page="account", title="Détail de la commande", order=order)


@shop.post("/commandes/<order_id>/annuler")
@authenticated()
def cancel(order_id):
    if not store.cancel_order(order_id, g.user["id"]):
        abort(409)
    flash("Commande annulée, les articles réservés sont à nouveau disponibles.", "success")
    return redirect(url_for("shop.order_detail", order_id=order_id), code=303)


@shop.post("/admin/boutique/commandes/<order_id>/statut")
@authenticated(admin=True)
def fulfil(order_id):
    if not store.fulfil_order(order_id, request.form.get("status")):
        flash("Transition impossible : le paiement doit être confirmé avant la préparation et le retrait.", "error")
    else:
        flash("Statut de la commande mis à jour.", "success")
    return redirect(url_for("shop.order_detail", order_id=order_id), code=303)


def product_form(existing):
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    if not 1 <= len(name) <= 120 or not 1 <= len(description) <= 5000:
        raise ValueError("Le titre (120 caractères maximum) et la description (5 000 maximum) sont obligatoires.")
    try:
        price = Decimal(request.form.get("price", "").replace(",", "."))
        if not price.is_finite() or not 0 <= price <= 10000 or price * 100 != (price * 100).to_integral_value():
            raise ValueError
        price_cents = int(price * 100)
    except (InvalidOperation, ValueError):
        raise ValueError("Indique un prix entre 0 et 10 000 €, avec au maximum deux décimales.")
    try:
        stock = int(request.form["stock"]) if request.form.get("stock", "").strip() else None
        if stock is not None and not 0 <= stock <= 1_000_000:
            raise ValueError
    except ValueError:
        raise ValueError("Le stock doit être un entier positif ou zéro, ou vide pour illimité.")
    product_type = request.form.get("product_type", "article")
    if product_type not in ("article", "membership"):
        raise ValueError("Type d’article invalide.")
    return {"name": name, "description": description, "price_cents": price_cents, "stock": stock,
            "image_url": existing.get("image_url") if existing else None,
            "is_active": int(request.form.get("is_active") == "1"), "product_type": product_type}


def read_product_image(upload):
    if not upload or not upload.filename:
        return None
    try:
        image = Image.open(upload.stream)
        if image.format not in ("JPEG", "PNG", "WEBP"):
            raise ValueError
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        return image
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise ValueError("L’image doit être un fichier JPEG, PNG ou WebP valide (8 Mo maximum).") from error


@shop.route("/admin/boutique/articles/nouveau", methods=("GET", "POST"))
@shop.route("/admin/boutique/articles/<int:product_id>", methods=("GET", "POST"))
@authenticated(admin=True)
def edit_product(product_id=None):
    existing = store.product(product_id, include_hidden=True) if product_id else None
    if product_id and not existing:
        abort(404)
    if request.method == "POST":
        new_file = None
        try:
            data = product_form(existing)
            image = read_product_image(request.files.get("image"))
            if image:
                UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
                filename = f"{uuid4().hex}.webp"
                new_file = UPLOAD_FOLDER / filename
                image.save(new_file, "WEBP", quality=88, method=6)
                data["image_url"] = f"uploads/products/{filename}"
            if not data["image_url"]:
                raise ValueError("Ajoute une image pour présenter cet article.")
            store.save_product(data, product_id)
            flash("Article enregistré. Le catalogue et le stock sont à jour.", "success")
            return redirect(url_for("admin_panel", onglet="boutique"), code=303)
        except ValueError as error:
            if new_file:
                new_file.unlink(missing_ok=True)
            flash(str(error), "error")
        return render_template("shop/edit.html", page="admin", title="Modifier un article", product=existing, values=request.form), 400
    values = {**(existing or {}), "price": f"{existing['price_cents'] / 100:.2f}" if existing else "",
              "stock": existing["stock"] if existing and existing["stock"] is not None else "",
              "is_active": str(existing["is_active"]) if existing else "1"}
    return render_template("shop/edit.html", page="admin", title="Modifier un article" if existing else "Nouvel article", product=existing, values=values)


@shop.post("/admin/boutique/articles/<int:product_id>/stock")
@authenticated(admin=True)
def stock_update(product_id):
    product = store.product(product_id, include_hidden=True)
    if not product:
        abort(404)
    try:
        raw = request.form.get("stock", "").strip()
        stock = int(raw) if raw else None
        if stock is not None and not 0 <= stock <= 1_000_000:
            raise ValueError("Le stock doit être compris entre 0 et 1 000 000.")
        store.update_stock(product_id, stock)
        flash("Stock mis à jour.", "success")
    except ValueError:
        flash("Stock invalide : entier positif ou vide (illimité), jamais inférieur aux réservations actives.", "error")
    return redirect(url_for("admin_panel", onglet="boutique"), code=303)


@shop.post("/admin/boutique/articles/<int:product_id>/visibilite")
@authenticated(admin=True)
def visibility(product_id):
    product = store.product(product_id, include_hidden=True)
    if not product:
        abort(404)
    store.set_visibility(product_id, request.form.get("is_active") == "1")
    flash("Visibilité de l’article mise à jour. Les anciennes commandes sont conservées.", "success")
    return redirect(url_for("admin_panel", onglet="boutique"), code=303)
