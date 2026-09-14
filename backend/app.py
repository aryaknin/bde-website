"""Pages HTML Flask et API locale du BDE ORT Sup."""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, abort, jsonify, render_template

if __package__:
    from . import database
else:
    import database

PARIS = ZoneInfo("Europe/Paris")
MONTHS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
PAGES = {
    "index": "Accueil",
    "billetterie": "Boutique",
    "associations": "Associations",
    "evenements": "Événements",
    "calendrier": "Calendrier",
    "bde": "Le BDE",
    "rec": "Respect, écoute et consentement",
    "login": "Connexion",
    "demande-domaine": "Projet associatif",
}


def parse_date(value):
    date = datetime.fromisoformat(value)
    return date.replace(tzinfo=PARIS) if date.tzinfo is None else date.astimezone(PARIS)


def format_date(value):
    date = parse_date(value)
    return f"{DAYS[date.weekday()]} {date.day} {MONTHS[date.month - 1]} {date.year} à {date:%H:%M}"


def format_price(cents):
    return "Gratuit" if cents == 0 else f"{cents / 100:,.2f} €".replace(",", " ").replace(".", ",")


def create_app():
    database.initialise_database()
    app = Flask(
        __name__,
        template_folder=str(database.PROJECT_DIR / "pages"),
        static_folder=str(database.PROJECT_DIR / "static"),
        static_url_path="/static",
    )
    app.jinja_env.filters["date_fr"] = format_date
    app.jinja_env.filters["price"] = format_price

    @app.context_processor
    def shared_content():
        return {"site": database.site_settings(), "year": datetime.now(PARIS).year}

    def show_page(page):
        if page not in PAGES:
            abort(404)
        context = {"page": page, "title": PAGES[page]}
        if page in ("index", "evenements", "calendrier"):
            items = database.events()
            if page == "index":
                now = datetime.now(PARIS)
                items = [item for item in items if parse_date(item["ends_at"] or item["starts_at"]) >= now][:3]
            context["events"] = items
        elif page == "associations":
            context["associations"] = database.associations()
        elif page == "billetterie":
            context["products"] = database.products()
        return render_template(f"{page}.html", **context)

    @app.get("/")
    def home():
        return show_page("index")

    @app.get("/<page>.html")
    def public_page(page):
        return show_page(page)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/site")
    def site_api():
        return jsonify(database.site_settings())

    @app.get("/api/associations")
    def associations_api():
        return jsonify(database.associations())

    @app.get("/api/events")
    def events_api():
        return jsonify(database.events())

    @app.get("/api/products")
    def products_api():
        return jsonify(database.products())

    @app.get("/api/stats")
    def stats_api():
        return jsonify(database.stats())

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html", page="404", title="Page introuvable"), 404

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("FLASK_PORT", "5000")), debug=True)
