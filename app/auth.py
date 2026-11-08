import secrets
from functools import wraps

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .models import ROLES, User

bp = Blueprint("auth", __name__)


@bp.before_app_request
def load_user_and_check_csrf():
    uid = session.get("user_id")
    g.user = db.session.get(User, uid) if uid else None
    if request.method == "POST":
        token = session.get("csrf")
        if not token or not secrets.compare_digest(token, request.form.get("csrf", "")):
            abort(400, "Your session expired. Reload the page and try again.")


@bp.app_context_processor
def inject_csrf():
    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]
    return {"csrf_token": csrf_token}


def login_required(*roles):
    """Require a signed-in user; with roles given, also require one of them."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("auth.get_started"))
            if roles and g.user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def _sign_in(user):
    csrf = session.get("csrf")
    session.clear()  # drop anything from the previous user
    session["user_id"] = user.id
    if csrf:
        session["csrf"] = csrf
    return redirect(url_for("main.workspace"))


@bp.route("/get-started", methods=["GET", "POST"])
def get_started():
    samples = {u.role: u for u in User.query.filter_by(is_sample=True)}
    if request.method == "POST":
        user = samples.get(request.form.get("role"))
        if user is None:
            abort(400)
        return _sign_in(user)
    return render_template("get_started.html", samples=[samples[r] for r in ROLES if r in samples])


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.password_hash and check_password_hash(user.password_hash, request.form.get("password", "")):
            return _sign_in(user)
        flash("That email and password don't match an account.", "error")
    return render_template("auth/login.html", email=request.form.get("email", ""))


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    managers = User.query.filter_by(role="manager").order_by(User.name).all()
    form = request.form
    if request.method == "POST":
        name = form.get("name", "").strip()
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        role = form.get("role", "")
        manager = db.session.get(User, form.get("manager_id", type=int) or 0)
        errors = {}
        if not name or len(name) > 120:
            errors["name"] = "Enter your full name."
        if "@" not in email or len(email) > 254:
            errors["email"] = "Enter a valid work email."
        elif User.query.filter_by(email=email).first():
            errors["email"] = "An account with this email already exists."
        if len(password) < 8:
            errors["password"] = "Use at least 8 characters."
        if role not in ROLES:
            errors["role"] = "Choose a role."
        if role == "employee" and (manager is None or manager.role != "manager"):
            errors["manager_id"] = "Choose the manager who reviews your claims."
        if not errors:
            user = User(name=name, email=email, role=role, password_hash=generate_password_hash(password),
                        manager=manager if manager and manager.role == "manager" else None)
            db.session.add(user)
            db.session.commit()
            response = _sign_in(user)
            flash(f"Welcome to Claimora, {name.split()[0]}.", "success")  # after sign-in clears the session
            return response
        return render_template("auth/signup.html", managers=managers, errors=errors, form=form), 400
    return render_template("auth/signup.html", managers=managers, errors={}, form=form)


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.index"))
