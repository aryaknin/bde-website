"""Catalogue, paniers persistants et commandes de la boutique (montants en centimes)."""

import hashlib
import secrets

if __package__:
    from . import database
else:
    import database

MAX_QUANTITY = 99
ORDER_STATUSES = {
    "awaiting_payment": "En attente de paiement",
    "paid": "Payée · à préparer",
    "ready": "Prête à retirer",
    "collected": "Retirée",
    "cancelled": "Annulée",
    "expired": "Expirée",
}


def initialise_shop():
    with database.get_db() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(products)")}
        if "product_type" not in columns:
            db.execute("ALTER TABLE products ADD COLUMN product_type TEXT NOT NULL DEFAULT 'article'")
            db.execute("UPDATE products SET product_type = 'membership' WHERE name = 'Adhésion BDE 2026–2027'")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS shop_carts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                guest_hash TEXT UNIQUE,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS shop_cart_items (
                cart_id INTEGER NOT NULL REFERENCES shop_carts(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id),
                quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 99),
                PRIMARY KEY(cart_id, product_id)
            );
            CREATE TABLE IF NOT EXISTS shop_orders (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                checkout_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'awaiting_payment'
                    CHECK(status IN ('awaiting_payment','paid','ready','collected','cancelled','expired')),
                total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
                currency TEXT NOT NULL DEFAULT 'EUR',
                payment_provider TEXT,
                payment_method TEXT NOT NULL DEFAULT 'online'
                    CHECK(payment_method IN ('online','cash')),
                payment_reference TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT NOT NULL,
                paid_at TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(payment_provider, payment_reference)
            );
            CREATE TABLE IF NOT EXISTS shop_order_items (
                order_id TEXT NOT NULL REFERENCES shop_orders(id),
                product_id INTEGER NOT NULL REFERENCES products(id),
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 99),
                unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
                PRIMARY KEY(order_id, product_id)
            );
            CREATE INDEX IF NOT EXISTS shop_orders_user ON shop_orders(user_id, created_at);
            CREATE INDEX IF NOT EXISTS shop_orders_reservations ON shop_orders(status, expires_at);
        """)
        order_columns = {row["name"] for row in db.execute("PRAGMA table_info(shop_orders)")}
        if "payment_method" not in order_columns:
            db.execute("ALTER TABLE shop_orders ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'online'")


INVENTORY_SQL = """
    SELECT products.*,
        COALESCE((SELECT SUM(i.quantity) FROM shop_order_items i
            JOIN shop_orders o ON o.id = i.order_id
            WHERE i.product_id = products.id AND o.status = 'awaiting_payment'
            AND o.expires_at > CURRENT_TIMESTAMP), 0) AS reserved
    FROM products
"""


def inventory(db, product_id=None, include_hidden=False):
    conditions, parameters = [], []
    if product_id is not None:
        conditions.append("products.id = ?")
        parameters.append(product_id)
    if not include_hidden:
        conditions.append("products.is_active = 1")
    sql = INVENTORY_SQL + (" WHERE " + " AND ".join(conditions) if conditions else "")
    rows = [dict(row) for row in db.execute(sql + " ORDER BY products.id DESC", parameters)]
    for row in rows:
        row["available"] = None if row["stock"] is None else max(0, row["stock"] - row["reserved"])
    return rows


def catalogue(include_hidden=False):
    with database.get_db() as db:
        return inventory(db, include_hidden=include_hidden)


def product(product_id, include_hidden=False):
    with database.get_db() as db:
        rows = inventory(db, product_id, include_hidden)
        return rows[0] if rows else None


def save_product(data, product_id=None):
    with database.get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        if product_id:
            rows = inventory(db, product_id, True)
            if not rows:
                raise ValueError("Cet article n’existe plus.")
            if data["stock"] is not None and data["stock"] < rows[0]["reserved"]:
                raise ValueError("Le stock total ne peut pas être inférieur aux quantités réservées.")
            if rows[0]["reserved"] and data["product_type"] != rows[0]["product_type"]:
                raise ValueError("Attends la fin des réservations avant de changer le type de cet article.")
        values = tuple(data[key] for key in (
            "name", "description", "price_cents", "stock", "image_url", "is_active", "product_type"
        ))
        if product_id:
            db.execute("""UPDATE products SET name=?, description=?, price_cents=?, stock=?,
                image_url=?, is_active=?, product_type=? WHERE id=?""", values + (product_id,))
            return product_id
        return db.execute("""INSERT INTO products
            (name,description,price_cents,stock,image_url,is_active,product_type)
            VALUES (?,?,?,?,?,?,?)""", values).lastrowid


def update_stock(product_id, stock):
    with database.get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = inventory(db, product_id, True)
        if not rows or (stock is not None and stock < rows[0]["reserved"]):
            raise ValueError("Stock inférieur aux réservations actives.")
        db.execute("UPDATE products SET stock=? WHERE id=?", (stock, product_id))


def set_visibility(product_id, visible):
    with database.get_db() as db:
        db.execute("UPDATE products SET is_active=? WHERE id=?", (int(visible), product_id))


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest() if token else None


def find_cart(user_id=None, guest_token=None):
    with database.get_db() as db:
        if user_id:
            row = db.execute("SELECT id FROM shop_carts WHERE user_id=?", (user_id,)).fetchone()
        else:
            row = db.execute("SELECT id FROM shop_carts WHERE guest_hash=? AND user_id IS NULL",
                             (token_hash(guest_token),)).fetchone()
        return row["id"] if row else None


def ensure_cart(user_id=None, guest_token=None):
    cart_id = find_cart(user_id, guest_token)
    if cart_id:
        return cart_id, None
    token = None if user_id else secrets.token_urlsafe(32)
    with database.get_db() as db:
        db.execute("INSERT OR IGNORE INTO shop_carts(user_id,guest_hash) VALUES (?,?)",
                   (user_id, token_hash(token)))
    return find_cart(user_id, token), token


def merge_guest_cart(user_id, guest_token):
    """Transfère le panier invité au compte sans conserver d’accès invité à ce panier."""
    if not guest_token:
        return
    with database.get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        guest = db.execute("SELECT id FROM shop_carts WHERE guest_hash=? AND user_id IS NULL",
                           (token_hash(guest_token),)).fetchone()
        if not guest:
            return
        target = db.execute("SELECT id FROM shop_carts WHERE user_id=?", (user_id,)).fetchone()
        if not target:
            db.execute("UPDATE shop_carts SET user_id=?, guest_hash=NULL WHERE id=?", (user_id, guest["id"]))
            return
        for item in db.execute("SELECT product_id,quantity FROM shop_cart_items WHERE cart_id=?", (guest["id"],)).fetchall():
            db.execute("""INSERT INTO shop_cart_items(cart_id,product_id,quantity) VALUES (?,?,?)
                ON CONFLICT(cart_id,product_id) DO UPDATE SET quantity=MIN(99,quantity+excluded.quantity)""",
                       (target["id"], item["product_id"], item["quantity"]))
        db.execute("DELETE FROM shop_carts WHERE id=?", (guest["id"],))


def cart_contents(cart_id, db=None):
    if db is None:
        with database.get_db() as connection:
            return cart_contents(cart_id, connection)
    items = []
    if cart_id:
        quantities = db.execute("SELECT product_id,quantity FROM shop_cart_items WHERE cart_id=?", (cart_id,)).fetchall()
        for line in quantities:
            rows = inventory(db, line["product_id"], True)
            if not rows:
                continue
            item = rows[0]
            item["quantity"] = line["quantity"]
            item["subtotal"] = item["price_cents"] * item["quantity"]
            item["issue"] = None
            if not item["is_active"] or item["product_type"] == "membership":
                item["issue"] = "Cet article n’est plus disponible dans le panier."
            elif item["available"] is not None and item["quantity"] > item["available"]:
                item["issue"] = f"Stock insuffisant : {item['available']} disponible(s)."
            items.append(item)
    return {"items": items, "count": sum(i["quantity"] for i in items),
            "total": sum(i["subtotal"] for i in items), "valid": bool(items) and not any(i["issue"] for i in items)}


def change_quantity(cart_id, product_id, quantity, add=False):
    if not isinstance(quantity, int) or not 0 <= quantity <= MAX_QUANTITY:
        raise ValueError("Choisis une quantité entre 0 et 99.")
    with database.get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        if quantity == 0 and not add:
            db.execute("DELETE FROM shop_cart_items WHERE cart_id=? AND product_id=?", (cart_id, product_id))
            return
        rows = inventory(db, product_id)
        if not rows or rows[0]["product_type"] == "membership":
            raise ValueError("Cet article n’est pas disponible à la commande.")
        item = rows[0]
        old = db.execute("SELECT quantity FROM shop_cart_items WHERE cart_id=? AND product_id=?", (cart_id, product_id)).fetchone()
        if add and old:
            quantity += old["quantity"]
        if not 1 <= quantity <= MAX_QUANTITY:
            raise ValueError("Maximum 99 exemplaires par article.")
        if item["available"] is not None and quantity > item["available"]:
            raise ValueError(f"Il reste {item['available']} exemplaire(s) de cet article.")
        if not old and db.execute("SELECT COUNT(*) FROM shop_cart_items WHERE cart_id=?", (cart_id,)).fetchone()[0] >= 50:
            raise ValueError("Le panier est limité à 50 articles différents.")
        db.execute("""INSERT INTO shop_cart_items(cart_id,product_id,quantity) VALUES (?,?,?)
            ON CONFLICT(cart_id,product_id) DO UPDATE SET quantity=excluded.quantity""", (cart_id, product_id, quantity))
        db.execute("UPDATE shop_carts SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (cart_id,))


def quote_items(cart):
    return [[i["id"], i["quantity"], i["price_cents"]] for i in cart["items"]]


def expire_orders(db):
    db.execute("""UPDATE shop_orders SET status='expired',updated_at=CURRENT_TIMESTAMP
        WHERE status='awaiting_payment' AND expires_at <= CURRENT_TIMESTAMP""")


def prepare_order(user_id, cart_id, quote, checkout_key, payment_method="online"):
    if payment_method not in ("online", "cash"):
        raise ValueError("Choisis un moyen de paiement valide.")
    with database.get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        expire_orders(db)
        old = db.execute("SELECT id FROM shop_orders WHERE checkout_key=? AND user_id=?", (checkout_key, user_id)).fetchone()
        if old:
            return old["id"]
        owner = db.execute("SELECT user_id FROM shop_carts WHERE id=?", (cart_id,)).fetchone()
        if not owner or owner["user_id"] != user_id:
            raise ValueError("Ton panier n’est plus disponible.")
        cart = cart_contents(cart_id, db)
        if not cart["valid"]:
            raise ValueError("Vérifie les disponibilités dans ton panier avant de continuer.")
        if quote_items(cart) != quote:
            raise ValueError("Le panier ou un prix a changé. Vérifie le nouveau récapitulatif.")
        if db.execute("SELECT COUNT(*) FROM shop_orders WHERE user_id=? AND status='awaiting_payment'", (user_id,)).fetchone()[0] >= 3:
            raise ValueError("Tu as déjà trois commandes en attente. Annule-en une avant de continuer.")
        order_id = secrets.token_hex(12)
        expiry = "+7 days" if payment_method == "cash" else "+30 minutes"
        db.execute("""INSERT INTO shop_orders(id,user_id,checkout_key,total_cents,payment_method,expires_at)
            VALUES (?,?,?,?,?,datetime('now',?))""", (order_id,user_id,checkout_key,cart["total"],payment_method,expiry))
        db.executemany("""INSERT INTO shop_order_items(order_id,product_id,name,quantity,unit_price_cents)
            VALUES (?,?,?,?,?)""", [(order_id,i["id"],i["name"],i["quantity"],i["price_cents"]) for i in cart["items"]])
        db.execute("DELETE FROM shop_cart_items WHERE cart_id=?", (cart_id,))
        return order_id


def orders(user_id=None):
    with database.get_db() as db:
        expire_orders(db)
        sql = "SELECT o.*,u.username FROM shop_orders o JOIN users u ON u.id=o.user_id"
        rows = db.execute(sql + (" WHERE o.user_id=?" if user_id else "") + " ORDER BY o.created_at DESC,o.rowid DESC", (user_id,) if user_id else ())
        return [dict(row) for row in rows]


def order(order_id):
    with database.get_db() as db:
        expire_orders(db)
        row = db.execute("SELECT o.*,u.username FROM shop_orders o JOIN users u ON u.id=o.user_id WHERE o.id=?", (order_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["items"] = [dict(i) for i in db.execute("SELECT * FROM shop_order_items WHERE order_id=?", (order_id,))]
        return result


def cancel_order(order_id, user_id):
    with database.get_db() as db:
        expire_orders(db)
        return db.execute("""UPDATE shop_orders SET status='cancelled',updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND user_id=? AND status='awaiting_payment'""", (order_id,user_id)).rowcount == 1


def fulfil_order(order_id, status):
    if status not in ("paid", "ready", "collected"):
        return False
    with database.get_db() as db:
        row = db.execute("SELECT status,payment_method FROM shop_orders WHERE id=?", (order_id,)).fetchone()
        if not row:
            return False
        if status == "paid":
            if row["status"] != "awaiting_payment" or row["payment_method"] != "cash":
                return False
            return db.execute("""UPDATE shop_orders SET status='paid',payment_provider='cash',paid_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP WHERE id=?""", (order_id,)).rowcount == 1
        previous = {"ready": "paid", "collected": "ready"}[status]
        return db.execute("UPDATE shop_orders SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status=?",
                          (status,order_id,previous)).rowcount == 1


def confirm_verified_payment(order_id, provider, reference, amount_cents, currency):
    """Point interne pour le futur webhook authentifié. Aucune route publique ne l’appelle.

    Le prestataire devra garantir le montant, la devise, la référence et l’expiration de la session.
    Un paiement reçu après expiration doit être traité/remboursé par l’intégration à venir.
    """
    if not provider or not reference or currency != "EUR":
        raise ValueError("Confirmation de paiement invalide.")
    with database.get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM shop_orders WHERE id=?", (order_id,)).fetchone()
        if not row or row["total_cents"] != amount_cents:
            raise ValueError("Montant ou commande invalide.")
        if row["status"] in ("paid","ready","collected"):
            if row["payment_provider"] == provider and row["payment_reference"] == reference:
                return False
            raise ValueError("Cette commande a déjà été payée.")
        if row["status"] != "awaiting_payment" or db.execute("SELECT ? <= CURRENT_TIMESTAMP", (row["expires_at"],)).fetchone()[0]:
            raise ValueError("Cette réservation n’est plus active.")
        for item in db.execute("SELECT * FROM shop_order_items WHERE order_id=?", (order_id,)).fetchall():
            stock = db.execute("SELECT stock FROM products WHERE id=?", (item["product_id"],)).fetchone()
            if stock["stock"] is not None:
                updated = db.execute("UPDATE products SET stock=stock-? WHERE id=? AND stock>=?", (item["quantity"],item["product_id"],item["quantity"]))
                if updated.rowcount != 1:
                    raise ValueError("Stock insuffisant pour confirmer le paiement.")
        db.execute("""UPDATE shop_orders SET status='paid',payment_provider=?,payment_reference=?,
            paid_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (provider,reference,order_id))
        return True
