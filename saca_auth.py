"""
Sign-in, sessions and request security for the SACA app.

Three ways to use SACA on a shared phone or tablet:
  guest    "Continue as guest". No sign-in. Results are kept on the device for staff to see; the guest sees only the
           results from their own session.
  profile  A family member signs in with their name and PIN. They see only their own history.
  medic    A health worker signs in with a username and password. They see everyone who used this device.
           An "admin" medic also manages staff accounts, local contacts and settings.

The login screen has ONE form ("Name or username" + "PIN or password"); saca_store.unified_login() decides which
kind of account it is. Names that sign in are unique on the device, so a login is never ambiguous.

Security measures: password/PIN hashes only (pbkdf2-sha256), lockout after 5 failed tries for 5 minutes, CSRF token
on every form, 30-minute idle sign-out, HttpOnly + SameSite=Lax session cookie, security headers, no-store caching,
open-redirect-safe "next" links, audit log of sign-ins and changes (never symptom text).
"""
import os
import secrets
import time
from datetime import date
from functools import wraps
from urllib.parse import urlparse

from flask import (Blueprint, abort, flash, g, redirect, render_template, request, session, url_for)

import saca_store as store
from i18n import gettext as _

bp = Blueprint("auth", __name__)

IDLE_SECONDS = 30 * 60
GUEST_KEEP = 20
CSRF_EXEMPT = {"voice.transcribe", "voice.voice_js", "static", "main.healthz"}

CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; font-src 'self' data:; "
       "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")


# --------------------------------------------------------------------------------------------- setup
def load_secret_key():
    """SACA_SECRET_KEY, else a random key kept in the data folder (never in the repository)."""
    env = os.environ.get("SACA_SECRET_KEY")
    if env:
        return env
    path = os.path.join(store.data_dir(), "secret_key")
    if os.path.exists(path):
        with open(path, encoding="ascii") as f:
            key = f.read().strip()
        if len(key) >= 32:
            return key
    key = secrets.token_hex(32)
    with open(path, "w", encoding="ascii") as f:
        f.write(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def init_app(app):
    app.secret_key = app.secret_key or load_secret_key()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_NAME="saca_session",
        MAX_CONTENT_LENGTH=12 * 1024 * 1024,
    )
    app.before_request(_load_session)
    app.before_request(_check_csrf)
    app.after_request(_security_headers)
    app.jinja_env.globals.update(csrf_token=csrf_token)
    app.context_processor(lambda: {"actor_kind": g.get("kind"), "actor_user": g.get("user"),
                                   "actor_patient": g.get("patient"), "lang": g.get("lang", "en"),
                                   "today_iso": date.today().isoformat()})
    app.register_blueprint(bp)


# --------------------------------------------------------------------------------------------- session
def _sign_out(keep_lang=True):
    lang = session.get("lang")
    session.clear()
    if keep_lang and lang:
        session["lang"] = lang


def _load_session():
    g.kind, g.user, g.patient = None, None, None
    kind = session.get("kind")
    if not kind:
        return
    last = session.get("seen", 0)
    now = int(time.time())
    if now - last > IDLE_SECONDS:
        _sign_out()
        g.timed_out = True
        return
    session["seen"] = now
    if kind == "medic":
        user = store.get_user(session.get("user_id"))
        if not user or not user["active"]:
            _sign_out()
            return
        g.user = user
    elif kind == "profile":
        patient = store.get_patient(session.get("patient_id"))
        if not patient or not patient["has_pin"]:
            _sign_out()
            return
        g.patient = patient
    elif kind != "guest":
        _sign_out()
        return
    g.kind = kind


def start_session(kind, user=None, patient=None):
    _sign_out()
    session["kind"] = kind
    session["seen"] = int(time.time())
    session["csrf"] = secrets.token_urlsafe(32)
    if user:
        session["user_id"] = user["id"]
    if patient:
        session["patient_id"] = patient["id"]
    if kind == "guest":
        session["guest_ids"] = []
    session.permanent = False


def remember_guest_assessment(assessment_id):
    ids = list(session.get("guest_ids", []))
    ids.append(assessment_id)
    session["guest_ids"] = ids[-GUEST_KEEP:]


def guest_assessment_ids():
    return list(session.get("guest_ids", []))


# --------------------------------------------------------------------------------------------- csrf
def csrf_token():
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf"] = token
    return token


def _check_csrf():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.endpoint in CSRF_EXEMPT:
        if request.endpoint == "voice.transcribe" and not g.get("kind"):
            abort(403)
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    expected = session.get("csrf")
    if not expected or not sent or not secrets.compare_digest(sent, expected):
        abort(400, description="The form expired. Please go back, reload the page and try again.")


def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", CSP)
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store"
    return response


# --------------------------------------------------------------------------------------------- guards
def safe_next(target, default="main.home"):
    if target:
        parts = urlparse(target)
        if not parts.scheme and not parts.netloc and target.startswith("/") and not target.startswith("//") \
                and "\\" not in target:
            return target
    return url_for(default)


def _to_login():
    """Send a signed-out visitor to the login screen, keeping where they were going and why they were signed out."""
    return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None,
                            timeout=1 if g.get("timed_out") else None))


def signed_in(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.get("kind"):
            return _to_login()
        return view(*args, **kwargs)
    return wrapper


def medic_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.get("kind") != "medic":
            if not g.get("kind"):
                return _to_login()
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.get("kind") != "medic" or g.user["role"] != "admin":
            if not g.get("kind"):
                return redirect(url_for("auth.login"))
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def actor_user_id():
    return g.user["id"] if g.get("user") else None


# --------------------------------------------------------------------------------------------- routes
LOGIN_ERRORS = {
    "invalid": "That name and PIN or password do not match. Please try again.",
    "locked": "Too many wrong tries. Please wait 5 minutes and try again.",
    "inactive": "This staff account is switched off. Ask the administrator.",
}


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.get("kind") and request.method == "GET":
        return redirect(url_for("main.home"))
    error = None
    name = ""
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()[:80]
        secret = request.form.get("secret") or ""
        if not name or not secret:
            error = _("Please enter your name and your PIN or password.")
        else:
            kind, record, problem = store.unified_login(name, secret)
            if kind == "medic":
                start_session("medic", user=record)
                store.log_event(record["id"], "login", "staff")
                return redirect(safe_next(request.form.get("next")))
            if kind == "profile":
                start_session("profile", patient=record)
                store.log_event(None, "login", f"profile {record['patient_code']}")
                return redirect(safe_next(request.form.get("next")))
            store.log_event(None, "login_failed", problem)
            error = _(LOGIN_ERRORS.get(problem, LOGIN_ERRORS["invalid"]))
    return render_template("login.html", error=error, name=name, next=request.values.get("next", ""),
                           needs_setup=store.user_count() == 0,
                           timed_out=g.get("timed_out") or request.args.get("timeout") == "1"), (401 if error else 200)


GUEST_NEXT_OK = ("/assess", "/body-map", "/contacts", "/about", "/history")


@bp.post("/guest")
def guest():
    start_session("guest")
    target = safe_next(request.form.get("next"))
    if not target.startswith(GUEST_NEXT_OK):  # a guest cannot open staff pages, so do not send them there
        target = url_for("main.home")
    return redirect(target)


@bp.post("/logout")
def logout():
    if g.get("user"):
        store.log_event(g.user["id"], "logout")
    _sign_out()
    return redirect(url_for("auth.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    """A family member creates their own profile (name, date of birth, sex, PIN) and is signed in."""
    if g.get("kind") in ("profile", "medic"):
        return redirect(url_for("main.home"))
    form, errors = {}, {}
    if request.method == "POST":
        form = request.form.to_dict()
        clean, errors = store.validate_patient(form, require_pin=True)
        if not errors:
            problem = store.pin_name_problem(clean["full_name"])
            if problem:
                errors["full_name"] = problem
        if not errors:
            patient_id = store.create_patient(clean, registered_by="self")
            store.log_event(None, "profile_created", f"P-{patient_id:04d} self")
            start_session("profile", patient=store.get_patient(patient_id))
            flash(_("Your profile is ready. Remember your PIN: you need it to see your history."))
            return redirect(url_for("main.home"))
    return render_template("register.html", form=form, errors=errors, translate_errors=True)


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First run only: create the first administrator account."""
    if store.user_count() > 0:
        return redirect(url_for("auth.login"))
    error, form = None, {}
    if request.method == "POST":
        form = request.form.to_dict()
        if (form.get("password") or "") != (form.get("password_confirm") or ""):
            error = "The two passwords do not match."
        else:
            user_id, error = store.create_user(form.get("username"), form.get("display_name"),
                                               form.get("password"), role="admin")
            if not error:
                store.log_event(user_id, "setup_admin_created")
                start_session("medic", user=store.get_user(user_id))
                flash(_("Administrator account created. You are signed in."))
                return redirect(url_for("main.home"))
    return render_template("setup.html", error=error, form=form)


@bp.get("/lang/<code>")
def set_language(code):
    if code in ("en", "sw"):
        session["lang"] = code
    return redirect(safe_next(request.args.get("next")))
