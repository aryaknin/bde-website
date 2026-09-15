"""Pages HTML Flask, authentification et API locale du BDE ORT Sup."""

import os
import re
import secrets
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from urllib.parse import quote_plus, urlencode, urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps, UnidentifiedImageError

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

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
    "evenements": "Événements",
    "calendrier": "Calendrier",
    "bde": "Le BDE",
    "login": "Connexion",
    "register": "Créer un compte",
    "demande-domaine": "Projet étudiant",
}
TEAM_ROLES = ("bde", "admin", "superadmin")
CONTRIBUTION_STATUSES = {
    "due": "À régler",
    "pending": "En attente",
    "paid": "Payée",
    "exempt": "Exonérée",
}
UPLOAD_FOLDER = database.PROJECT_DIR / "static" / "uploads" / "members"
Image.MAX_IMAGE_PIXELS = 25_000_000


def parse_date(value):
    date = datetime.fromisoformat(value)
    return date.replace(tzinfo=PARIS) if date.tzinfo is None else date.astimezone(PARIS)


def format_date(value):
    date = parse_date(value)
    return f"{DAYS[date.weekday()]} {date.day} {MONTHS[date.month - 1]} {date.year} à {date:%H:%M}"


def format_price(cents):
    return "Gratuit" if cents == 0 else f"{cents / 100:,.2f} €".replace(",", " ").replace(".", ",")


def current_school_year(reference=None):
    reference = reference or datetime.now(PARIS)
    start = reference.year if reference.month >= 8 else reference.year - 1
    return f"{start}-{start + 1}"


def valid_email(value):
    return bool(
        value and len(value) <= 254
        and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value)
    )


def membership_configuration():
    settings = database.site_settings()
    try:
        fee_cents = max(0, int(settings.get("membership_fee_cents", "1500")))
    except ValueError:
        fee_cents = 1500
    try:
        payment_url = validated_profile_url(settings.get("helloasso_membership_url", ""))
    except ValueError:
        payment_url = None
    return current_school_year(), fee_cents, payment_url


def parse_contribution_form(form):
    school_year = form.get("school_year", "").strip()
    match = re.fullmatch(r"(20\d{2})-(20\d{2})", school_year)
    if not match or int(match.group(2)) != int(match.group(1)) + 1:
        return None, "L’année scolaire doit être au format 2026-2027."
    raw_amount = form.get("amount", "").strip().replace(",", ".")
    try:
        amount = Decimal(raw_amount)
        if amount < 0:
            raise InvalidOperation
        amount_cents = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return None, "Le montant de la cotisation est invalide."
    status = form.get("status", "due")
    if status not in CONTRIBUTION_STATUSES:
        return None, "Le statut de cotisation est invalide."

    paid_at = None
    raw_paid_at = form.get("paid_at", "").strip()
    if status == "paid":
        if raw_paid_at:
            try:
                paid_at = datetime.strptime(raw_paid_at, "%Y-%m-%dT%H:%M").replace(
                    tzinfo=PARIS
                ).isoformat()
            except ValueError:
                return None, "La date de paiement est invalide."
        else:
            paid_at = datetime.now(PARIS).isoformat(timespec="minutes")

    payment_method = form.get("payment_method", "").strip()
    external_reference = form.get("external_reference", "").strip()
    notes = form.get("notes", "").strip()
    if len(payment_method) > 80 or len(external_reference) > 120 or len(notes) > 1000:
        return None, "Un des champs de suivi de la cotisation est trop long."
    return {
        "school_year": school_year,
        "amount_cents": amount_cents,
        "status": status,
        "payment_method": payment_method or None,
        "external_reference": external_reference or None,
        "paid_at": paid_at,
        "notes": notes,
    }, None


def load_secret_key():
    """Charge le secret des sessions sans le placer dans Git."""
    configured = os.getenv("BDE_SECRET_KEY")
    if configured:
        return configured
    secret_path = database.DATABASE_PATH.parent / ".session-secret"
    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8").strip()
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    generated = secrets.token_hex(32)
    secret_path.write_text(generated, encoding="utf-8")
    try:
        secret_path.chmod(0o600)
    except OSError:
        pass
    return generated


def parse_event_form(form):
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    location = form.get("location", "").strip()
    if not title or not description or not location:
        return None, "Le titre, la description et le lieu sont obligatoires."
    try:
        starts_at = datetime.strptime(
            f"{form.get('start_date', '')} {form.get('start_time', '')}", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=PARIS)
    except ValueError:
        return None, "La date et l’heure de début sont invalides."

    end_date = form.get("end_date", "").strip()
    end_time = form.get("end_time", "").strip()
    ends_at = None
    if end_date or end_time:
        if not end_time:
            return None, "Indique une heure de fin ou laisse les deux champs de fin vides."
        try:
            ends_at = datetime.strptime(
                f"{end_date or form.get('start_date', '')} {end_time}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=PARIS)
        except ValueError:
            return None, "La date ou l’heure de fin est invalide."
        if ends_at <= starts_at:
            return None, "La fin de l’événement doit être postérieure au début."

    raw_price = form.get("price", "0").strip().replace(",", ".") or "0"
    try:
        price = Decimal(raw_price)
        if price < 0:
            raise InvalidOperation
        price_cents = int((price * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return None, "Le tarif indiqué est invalide."

    capacity = None
    raw_capacity = form.get("capacity", "").strip()
    if raw_capacity:
        try:
            capacity = int(raw_capacity)
            if capacity <= 0:
                raise ValueError
        except ValueError:
            return None, "La capacité doit être un nombre entier supérieur à zéro."

    return {
        "title": title,
        "description": description,
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat() if ends_at else None,
        "location": location,
        "organizer_name": form.get("organizer_name", "").strip() or None,
        "price_cents": price_cents,
        "capacity": capacity,
    }, None


def google_event_creation_url(event):
    start = parse_date(event["starts_at"])
    end = parse_date(event["ends_at"]) if event["ends_at"] else start + timedelta(hours=2)
    parameters = {
        "action": "TEMPLATE",
        "text": event["title"],
        "dates": f"{start:%Y%m%dT%H%M%S}/{end:%Y%m%dT%H%M%S}",
        "ctz": "Europe/Paris",
        "details": f"{event['description']}\n\nOrganisé par {event['organizer_name']}",
        "location": event["location"],
    }
    return f"https://calendar.google.com/calendar/render?{urlencode(parameters)}"


def validated_profile_url(value):
    value = value.strip()
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Les liens personnels doivent être des adresses http:// ou https:// valides.")
    return value


def save_profile_photo(upload):
    if not upload or not upload.filename:
        return None
    try:
        image = Image.open(upload.stream)
        if image.format not in ("JPEG", "PNG", "WEBP"):
            raise ValueError("Format non pris en charge")
        image = ImageOps.exif_transpose(image).convert("RGB")
        image = ImageOps.fit(image, (800, 1000), method=Image.Resampling.LANCZOS)
        UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4().hex}.webp"
        image.save(UPLOAD_FOLDER / filename, "WEBP", quality=86, method=6)
        return f"uploads/members/{filename}"
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise ValueError("La photo doit être une image JPEG, PNG ou WebP valide.") from error


def parse_profile_form(form, files, existing=None, include_team_fields=False):
    display_name = form.get("display_name", "").strip()
    bio = form.get("bio", "").strip()
    if not display_name or len(display_name) > 100:
        return None, "Le nom public est obligatoire et limité à 100 caractères."
    if len(bio) > 1500:
        return None, "La biographie est limitée à 1 500 caractères."
    try:
        instagram_url = validated_profile_url(form.get("instagram_url", ""))
        linkedin_url = validated_profile_url(form.get("linkedin_url", ""))
        website_url = validated_profile_url(form.get("website_url", ""))
        new_photo = save_profile_photo(files.get("photo"))
    except ValueError as error:
        return None, str(error)

    data = {
        "display_name": display_name,
        "bio": bio,
        "photo_path": new_photo or (existing["photo_path"] if existing else None),
        "instagram_url": instagram_url,
        "linkedin_url": linkedin_url,
        "website_url": website_url,
        "team_role": (existing["team_role"] if existing else "Membre du BDE"),
        "sort_order": (existing["sort_order"] if existing else 0),
    }
    if include_team_fields:
        team_role = form.get("team_role", "").strip()
        if not team_role or len(team_role) > 100:
            return None, "Le rôle dans le BDE est obligatoire et limité à 100 caractères."
        try:
            sort_order = int(form.get("sort_order", "0") or 0)
        except ValueError:
            return None, "L’ordre d’affichage doit être un nombre entier."
        data.update(team_role=team_role, sort_order=sort_order)
    return data, None


def create_app():
    database.initialise_database()
    app = Flask(
        __name__,
        template_folder=str(database.PROJECT_DIR / "pages"),
        static_folder=str(database.PROJECT_DIR / "static"),
        static_url_path="/static",
    )
    app.config.update(
        SECRET_KEY=load_secret_key(),
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("BDE_COOKIE_SECURE") == "1",
    )
    app.jinja_env.filters["date_fr"] = format_date
    app.jinja_env.filters["price"] = format_price

    def csrf_token():
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def load_user_and_check_csrf():
        user_id = session.get("user_id")
        g.user = database.user_by_id(user_id) if user_id else None
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            expected = session.get("_csrf_token", "")
            submitted = request.form.get("_csrf_token", "")
            if not expected or not secrets.compare_digest(expected, submitted):
                abort(400)

    @app.context_processor
    def shared_content():
        return {
            "site": database.site_settings(),
            "year": datetime.now(PARIS).year,
            "current_user": g.user,
            "contribution_statuses": CONTRIBUTION_STATUSES,
        }

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.user:
                flash("Connecte-toi pour accéder à ton espace.", "info")
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.user:
                flash("Connecte-toi avec un compte administrateur.", "info")
                return redirect(url_for("login"))
            if g.user["role"] not in ("admin", "superadmin"):
                flash("Ton compte n’a pas les droits administrateur.", "error")
                return redirect(url_for("account"))
            return view(*args, **kwargs)
        return wrapped

    def team_member_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not g.user:
                flash("Connecte-toi pour accéder à cet outil.", "info")
                return redirect(url_for("login"))
            if g.user["role"] not in TEAM_ROLES:
                flash("Ton compte ne fait pas partie de l’équipe BDE.", "error")
                return redirect(url_for("account"))
            return view(*args, **kwargs)
        return wrapped

    def show_page(page):
        if page not in PAGES:
            abort(404)
        context = {"page": page, "title": PAGES[page]}
        if page in ("index", "evenements"):
            items = database.events()
            if page == "index":
                now = datetime.now(PARIS)
                items = [item for item in items if parse_date(item["ends_at"] or item["starts_at"]) >= now][:3]
            context["events"] = items
            context["event_details"] = page == "evenements"
        elif page == "billetterie":
            context["products"] = database.products()
        elif page == "bde":
            context["profiles"] = database.bde_profiles()
        elif page == "calendrier":
            event_id = request.args.get("event", type=int)
            selected_event = database.event_by_id(event_id) if event_id else None
            context["selected_event"] = selected_event
            if selected_event:
                context["google_calendar_search_url"] = (
                    "https://calendar.google.com/calendar/u/0/r/search?q="
                    f"{quote_plus(selected_event['title'])}"
                )
        return render_template(f"{page}.html", **context)

    @app.get("/")
    def home():
        return show_page("index")

    @app.route("/register.html", methods=("GET", "POST"))
    def register():
        if g.user:
            return redirect(url_for("account"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirmation = request.form.get("password_confirmation", "")
            if len(username) < 3 or len(username) > 40:
                flash("L’identifiant doit contenir entre 3 et 40 caractères.", "error")
            elif not valid_email(email):
                flash("Saisis une adresse e-mail valide.", "error")
            elif len(password) < 8:
                flash("Le mot de passe doit contenir au moins 8 caractères.", "error")
            elif password != confirmation:
                flash("Les deux mots de passe ne correspondent pas.", "error")
            else:
                user_id = database.create_user(
                    username, generate_password_hash(password), "member", email=email
                )
                if not user_id:
                    flash("Cet identifiant ou cette adresse e-mail est déjà utilisé.", "error")
                else:
                    school_year, fee_cents, _ = membership_configuration()
                    database.create_contribution(user_id, school_year, fee_cents)
                    session.clear()
                    session["user_id"] = user_id
                    csrf_token()
                    flash("Ton compte a été créé. Bienvenue au BDE ORT Sup !", "success")
                    return redirect(url_for("account"))
        return render_template("register.html", page="register", title="Créer un compte")

    @app.route("/login.html", methods=("GET", "POST"))
    def login():
        if g.user:
            return redirect(url_for("account"))
        if request.method == "POST":
            identifier = request.form.get("username", "").strip()
            credentials = database.user_credentials(identifier)
            password = request.form.get("password", "")
            if not credentials or not check_password_hash(credentials["password_hash"], password):
                flash("Identifiant ou mot de passe incorrect.", "error")
            else:
                session.clear()
                session["user_id"] = credentials["id"]
                csrf_token()
                flash(f"Bienvenue {credentials['username']}.", "success")
                return redirect(url_for("account"))
        return render_template("login.html", page="login", title="Connexion")

    @app.post("/logout")
    @login_required
    def logout():
        session.clear()
        flash("Tu es maintenant déconnecté.", "success")
        return redirect(url_for("home"))

    @app.get("/compte.html")
    @login_required
    def account():
        created_event = None
        google_create_url = None
        school_year, fee_cents, payment_url = membership_configuration()
        database.ensure_contributions(school_year, fee_cents)
        contributions = database.contributions_for_user(g.user["id"])
        current_contribution = next(
            (item for item in contributions if item["school_year"] == school_year), None
        )
        event_id = request.args.get("event_created", type=int)
        if event_id and g.user["role"] in TEAM_ROLES:
            created_event = database.event_by_id(event_id)
            if created_event:
                google_create_url = google_event_creation_url(created_event)
        return render_template(
            "account.html", page="account", title="Mon espace",
            created_event=created_event, google_create_url=google_create_url,
            contributions=contributions, current_contribution=current_contribution,
            current_school_year=school_year, helloasso_membership_url=payment_url,
            bde_profile=database.bde_profile_for_user(g.user["id"])
            if g.user["role"] in TEAM_ROLES else None,
        )

    @app.get("/admin.html")
    @admin_required
    def admin_panel():
        school_year, fee_cents, _ = membership_configuration()
        database.ensure_contributions(school_year, fee_cents)
        active_tab = request.args.get("onglet", "accounts")
        if active_tab not in ("accounts", "bde", "cotisations"):
            active_tab = "accounts"
        return render_template(
            "admin.html", page="admin", title="Administration",
            users=database.users(), profiles=database.bde_profiles(visible_only=False),
            contributions=database.contributions_with_users(),
            current_school_year=school_year, default_membership_fee_cents=fee_cents,
            active_admin_tab=active_tab,
        )

    @app.post("/admin/users/create")
    @admin_required
    def create_user():
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "member")
        if len(username) < 3 or len(username) > 40:
            flash("L’identifiant doit contenir entre 3 et 40 caractères.", "error")
        elif email and not valid_email(email):
            flash("L’adresse e-mail est invalide.", "error")
        elif len(password) < 6:
            flash("Le mot de passe doit contenir au moins 6 caractères.", "error")
        elif role not in ("member", "bde", "admin"):
            flash("Le niveau d’autorité choisi est invalide.", "error")
        else:
            user_id = database.create_user(
                username, generate_password_hash(password), role, email=email or None
            )
            if user_id:
                school_year, fee_cents, _ = membership_configuration()
                database.create_contribution(user_id, school_year, fee_cents)
                flash(f"Le compte {username} a été créé.", "success")
            else:
                flash("Cet identifiant ou cette adresse e-mail est déjà utilisé.", "error")
        return redirect(url_for("admin_panel"))

    @app.post("/admin/users/<int:user_id>/role")
    @admin_required
    def update_user_role(user_id):
        role = request.form.get("role", "")
        if database.update_user_role(user_id, role):
            flash("Le niveau d’autorité a été mis à jour.", "success")
        else:
            flash("Ce compte est protégé ou le niveau demandé est invalide.", "error")
        return redirect(url_for("admin_panel"))

    def contribution_for_admin(contribution_id):
        contribution = database.contribution_by_id(contribution_id)
        if not contribution:
            return None
        if contribution["account_is_protected"] and g.user["role"] != "superadmin":
            return None
        return contribution

    @app.post("/admin/contributions/create")
    @admin_required
    def create_contribution():
        user_id = request.form.get("user_id", type=int)
        user = database.user_by_id(user_id) if user_id else None
        if not user or (user["is_protected"] and g.user["role"] != "superadmin"):
            flash("Ce compte est introuvable ou protégé.", "error")
            return redirect(url_for("admin_panel", onglet="cotisations"))
        data, error = parse_contribution_form(request.form)
        if error:
            flash(error, "error")
        else:
            contribution_id = database.create_contribution(
                user_id, data["school_year"], data["amount_cents"], data["status"]
            )
            if contribution_id:
                database.update_contribution(contribution_id, data)
                flash("La cotisation a été ajoutée.", "success")
            else:
                flash("Une cotisation existe déjà pour ce compte et cette année.", "error")
        return redirect(url_for("admin_panel", onglet="cotisations"))

    @app.post("/admin/contributions/<int:contribution_id>/update")
    @admin_required
    def update_contribution(contribution_id):
        contribution = contribution_for_admin(contribution_id)
        if not contribution:
            flash("Cette cotisation est introuvable ou protégée.", "error")
            return redirect(url_for("admin_panel", onglet="cotisations"))
        data, error = parse_contribution_form(request.form)
        if error:
            flash(error, "error")
        else:
            updated = database.update_contribution(contribution_id, data)
            if updated:
                flash("La cotisation a été mise à jour.", "success")
            else:
                flash("Cette année existe déjà pour ce compte.", "error")
        return redirect(url_for("admin_panel", onglet="cotisations"))

    @app.post("/admin/events/create")
    @team_member_required
    def create_event():
        data, error = parse_event_form(request.form)
        if error:
            flash(error, "error")
            return redirect(url_for("public_page", page="evenements", ajouter=1) + "#ajouter-evenement")
        event_id = database.create_event(data)
        flash("L’événement a été ajouté au site.", "success")
        return redirect(url_for("account", event_created=event_id))

    @app.post("/compte/profil")
    @team_member_required
    def update_own_profile():
        profile = database.bde_profile_for_user(g.user["id"])
        if not profile:
            flash("Aucun profil BDE n’est lié à ce compte.", "error")
            return redirect(url_for("account"))
        data, error = parse_profile_form(request.form, request.files, existing=profile)
        if error:
            flash(error, "error")
        elif database.update_bde_profile(profile["id"], data):
            flash("Ton profil public a été mis à jour.", "success")
        return redirect(url_for("account"))

    def protected_profile_for_admin(profile_id):
        profile = database.bde_profile_by_id(profile_id)
        if not profile:
            return None
        if profile["account_role"] == "superadmin" and g.user["role"] != "superadmin":
            return None
        return profile

    @app.post("/admin/profiles/create")
    @admin_required
    def create_bde_profile():
        data, error = parse_profile_form(
            request.form, request.files, include_team_fields=True
        )
        if error:
            flash(error, "error")
        else:
            database.create_manual_bde_profile(data)
            flash("Le profil a été ajouté à la page BDE.", "success")
        return redirect(url_for("admin_panel", onglet="bde"))

    @app.post("/admin/profiles/<int:profile_id>/update")
    @admin_required
    def update_bde_profile(profile_id):
        profile = protected_profile_for_admin(profile_id)
        if not profile:
            flash("Ce profil est introuvable ou protégé.", "error")
            return redirect(url_for("admin_panel", onglet="bde"))
        data, error = parse_profile_form(
            request.form, request.files, existing=profile, include_team_fields=True
        )
        if error:
            flash(error, "error")
        elif database.update_bde_profile(profile_id, data, include_team_fields=True):
            flash("Le profil BDE a été mis à jour.", "success")
        return redirect(url_for("admin_panel", onglet="bde"))

    @app.post("/admin/profiles/<int:profile_id>/visibility")
    @admin_required
    def set_bde_profile_visibility(profile_id):
        profile = protected_profile_for_admin(profile_id)
        if not profile:
            flash("Ce profil est introuvable ou protégé.", "error")
        else:
            visible = request.form.get("visible") == "1"
            database.set_bde_profile_visibility(profile_id, visible)
            flash("La visibilité du profil a été mise à jour.", "success")
        return redirect(url_for("admin_panel", onglet="bde"))

    @app.post("/admin/profiles/<int:profile_id>/delete")
    @admin_required
    def delete_bde_profile(profile_id):
        profile = protected_profile_for_admin(profile_id)
        if not profile:
            flash("Ce profil est introuvable ou protégé.", "error")
        elif profile["user_id"] is not None:
            flash("Un profil lié à un compte doit être masqué plutôt que supprimé.", "error")
        elif database.delete_manual_bde_profile(profile_id):
            flash("Le profil manuel a été supprimé.", "success")
        return redirect(url_for("admin_panel", onglet="bde"))

    @app.get("/<page>.html")
    def public_page(page):
        return show_page(page)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/site")
    def site_api():
        return jsonify(database.site_settings())

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

    @app.errorhandler(413)
    def upload_too_large(error):
        return render_template(
            "error.html", page="error", title="Image trop volumineuse",
            heading="Image trop volumineuse",
            message="La photo envoyée doit peser moins de 8 Mo.",
        ), 413

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("FLASK_PORT", "5000")), debug=True)
