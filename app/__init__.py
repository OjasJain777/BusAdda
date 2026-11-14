import os
from datetime import timedelta
from secrets import token_hex

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError

from .models import db
from .network import NetworkCache, load_demo_network
from .session_security import session_token_hash
from .storage import MemoryStore, SQLStore, get_store

login = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


@login.user_loader
def load_user(user_id):
    token_hash = session_token_hash()
    if not user_id.isdecimal() or token_hash is None:
        return None
    return get_store().authenticated_user(token_hash, int(user_id))


def create_app(config=None):
    load_dotenv()
    app = Flask(__name__)
    secure = os.environ.get("SESSION_COOKIE_SECURE", "1" if os.environ.get("VERCEL") == "1" else "0") == "1"
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        BUSADDA_STORAGE=os.environ.get("BUSADDA_STORAGE") or None,
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL"),
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=secure,
        REMEMBER_COOKIE_HTTPONLY=True, REMEMBER_COOKIE_SAMESITE="Lax", REMEMBER_COOKIE_SECURE=secure,
        REMEMBER_COOKIE_DURATION=timedelta(days=14), PERMANENT_SESSION_LIFETIME=timedelta(days=14),
        SESSION_REFRESH_EACH_REQUEST=False,
        MAX_CONTENT_LENGTH=32 * 1024,
    )
    if config is not None:
        app.config.update(config)
    storage = app.config["BUSADDA_STORAGE"]
    if storage is None:
        storage = "mysql" if app.config["SQLALCHEMY_DATABASE_URI"] else "memory"
        app.config["BUSADDA_STORAGE"] = storage
    if storage not in {"memory", "mysql"}:
        raise RuntimeError("BUSADDA_STORAGE must be mysql or memory.")
    if not app.secret_key:
        if storage == "mysql":
            raise RuntimeError("Set SECRET_KEY before running BusAdda with MySQL.")
        app.secret_key = token_hex(32)

    if storage == "mysql":
        if not app.config["SQLALCHEMY_DATABASE_URI"]:
            raise RuntimeError("Set DATABASE_URL or choose BUSADDA_STORAGE=memory.")
        db.init_app(app)
        migrate.init_app(app, db)
        from scripts.seed_database import seed_command

        app.cli.add_command(seed_command)
        app.extensions["busadda_store"] = SQLStore()
        app.extensions["bus_network"] = NetworkCache()
    else:
        app.extensions["busadda_store"] = MemoryStore()
        app.extensions["bus_network"] = NetworkCache(load_demo_network)

    login.init_app(app)
    csrf.init_app(app)
    from .auth import auth
    from .views import api, web

    app.register_blueprint(auth)
    app.register_blueprint(web)
    app.register_blueprint(api)

    @app.errorhandler(CSRFError)
    def csrf_error(_):
        return error_page("This form session expired. Reload the page and try again.", 400)

    @app.errorhandler(404)
    def missing(_):
        return error_page("We couldn't find that page.", 404)

    @app.errorhandler(413)
    def too_large(_):
        return error_page("This request is too large.", 413)

    @app.errorhandler(500)
    def failure(_):
        return error_page("BusAdda couldn't complete the request. Try again shortly.", 500)

    def error_page(message, code):
        if request.path.startswith("/api/"):
            return jsonify(error=message), code
        return render_template("error.html", message=message, code=code), code

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; "
            "img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
        )
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    return app
