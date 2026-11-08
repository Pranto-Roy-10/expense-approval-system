import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User

CSRF = "test-token"


@pytest.fixture
def app(tmp_path):
    class Config(TestConfig):
        RECEIPT_DIR = str(tmp_path / "receipts")

    app = create_app(Config)
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def team(app):
    """A manager with two reports, a second manager, and Finance. Returns user ids by key."""
    manager = User(name="Tanvir Ahmed", email="tanvir@example.com", role="manager", title="Manager", is_sample=True)
    other_manager = User(name="Rumana Chowdhury", email="rumana@example.com", role="manager", manager=manager)
    finance = User(name="Farhana Islam", email="farhana@example.com", role="finance", title="Finance Lead", is_sample=True)
    employee = User(name="Nusrat Jahan", email="nusrat@example.com", role="employee", title="Engineer",
                    manager=manager, is_sample=True)
    teammate = User(name="Rafiq Hasan", email="rafiq@example.com", role="employee", manager=manager)
    outsider = User(name="Sadia Rahman", email="sadia@example.com", role="employee", manager=other_manager)
    users = dict(manager=manager, other_manager=other_manager, finance=finance,
                 employee=employee, teammate=teammate, outsider=outsider)
    db.session.add_all(users.values())
    db.session.commit()
    return {key: u.id for key, u in users.items()}


def sign_in(client, user_id):
    with client.session_transaction() as s:
        s["user_id"] = user_id
        s["csrf"] = CSRF


def post(client, url, data=None, **kwargs):
    return client.post(url, data={"csrf": CSRF, **(data or {})}, **kwargs)
