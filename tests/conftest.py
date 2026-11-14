import os
from pathlib import Path
from uuid import uuid4

import pytest
from flask_migrate import upgrade
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app import create_app
from app.models import db
from scripts.seed_database import seed_network


@event.listens_for(Engine, "connect")
def sqlite_foreign_keys(connection, _):
    if type(connection).__module__ == "sqlite3":
        connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    url = os.environ.get("BUSADDA_TEST_DATABASE_URL")
    if url and not url.split("?")[0].endswith("/busadda_test"):
        pytest.fail("Use a dedicated database named busadda_test for integration tests.")
    if not url:
        url = f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.sqlite3'}"
    app = create_app({"TESTING": True, "SECRET_KEY": "tests-only",
                      "BUSADDA_STORAGE": "mysql", "SQLALCHEMY_DATABASE_URI": url})
    with app.app_context():
        upgrade(directory=str(Path(__file__).resolve().parents[1] / "migrations"))
        seed_network()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def email():
    return f"test-{uuid4().hex}@example.com"
