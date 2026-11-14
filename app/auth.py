from email_validator import EmailNotValidError, validate_email
from datetime import timedelta

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from .models import utc_now
from .session_security import create_session_token, session_token_hash
from .storage import get_store

auth = Blueprint("auth", __name__)
DUMMY_HASH = generate_password_hash("dummy-password-for-timing")


def normalized_email(value):
    try:
        return validate_email(value, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return None


@auth.route("/signup", methods=["GET", "POST"])
@auth.route("/login", methods=["GET", "POST"])
def credentials():
    if current_user.is_authenticated:
        return redirect(url_for("web.page", view="plan"))
    signup = request.path == "/signup"
    error = ""
    name, email = "", ""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if signup:
            if not 2 <= len(name) <= 100:
                error = "Enter a name between 2 and 100 characters."
            elif not 10 <= len(password) <= 128:
                error = "Choose a password between 10 and 128 characters."
            elif password != request.form.get("confirmation"):
                error = "The passwords do not match."
            else:
                normalized = normalized_email(email)
                if normalized is None:
                    error = "Enter a valid email address."
                else:
                    email = normalized
            if not error:
                if get_store().create_user(name, email, generate_password_hash(password)):
                    flash("Account created. Sign in with your new credentials.", "success")
                    return redirect(url_for("auth.credentials"))
                error = "An account already exists for this email."
        else:
            normalized = normalized_email(email)
            user = get_store().find_user(normalized) if normalized else None
            valid_password = len(password) <= 128 and check_password_hash(
                user.password_hash if user else DUMMY_HASH, password
            )
            if user and valid_password:
                return sign_in(user, remember=request.form.get("remember") == "on")
            error = "Invalid email or password."
    return render_template("auth.html", signup=signup, error=error, name=name, email=email), 400 if error else 200


def sign_in(user, remember=False):
    session.clear()
    token_hash = create_session_token()
    duration = timedelta(days=14) if remember else timedelta(hours=12)
    get_store().add_session(token_hash, user.id, utc_now() + duration)
    login_user(user)
    session.permanent = remember
    session["_remember"] = "clear"
    return redirect(url_for("web.page", view="plan"))


@auth.post("/logout")
def logout():
    token_hash = session_token_hash()
    if token_hash:
        get_store().remove_session(token_hash)
    logout_user()
    session.clear()
    session["_remember"] = "clear"
    return redirect(url_for("auth.credentials"))
