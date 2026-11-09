"""Edge cases over HTTP: bad input, refused actions and the less common paths through each page."""
import os
from datetime import date
from decimal import Decimal

from sqlalchemy import update

from app import create_app, rules
from app.config import TestConfig
from app.export import claims_workbook
from app.extensions import db
from app.models import Claim, LineItem, User, utcnow

from .conftest import CSRF, post, sign_in
from .test_flows import PDF, PNG, claim_form, new_claim


def flash_text(client):
    return client.get("/profile").get_data(as_text=True)


# ---------- Claim form ----------

def test_edit_page_opens_with_the_saved_lines_and_keeps_them_on_a_bad_save(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client)
    page = client.get(f"/claims/{claim.id}/edit")
    assert page.status_code == 200 and b"Flight" in page.data
    res = post(client, f"/claims/{claim.id}/edit", claim_form(lines=(("Meals", "Dinner", "900", "BDT", ""),)),
               content_type="multipart/form-data")
    assert res.status_code == 400 and b"need a note" in res.data
    db.session.expire_all()
    assert [i.description for i in claim.items] == ["Flight"]  # the saved claim is untouched


def test_missing_title_or_unreadable_date_or_amount_is_refused(client, team):
    sign_in(client, team["employee"])
    form = claim_form()
    form["items-n0-date"] = "not-a-date"
    assert b"valid date" in post(client, "/claims/new", form, content_type="multipart/form-data").data
    form = claim_form(lines=(("Travel", "Flight", "abc", "BDT", ""),))
    assert b"more than zero" in post(client, "/claims/new", form, content_type="multipart/form-data").data
    assert b"Give the claim a title." in post(client, "/claims/new", claim_form(title="  "), content_type="multipart/form-data").data
    assert Claim.query.count() == 0


def test_receipt_over_5_mb_is_refused(client, team):
    sign_in(client, team["employee"])
    big = PDF + b"0" * (5 * 1024 * 1024)
    res = post(client, "/claims/new", claim_form(files={0: ("big.pdf", big)}), content_type="multipart/form-data")
    assert res.status_code == 400 and b"up to 5 MB" in res.data
    assert Claim.query.count() == 0


def test_draft_can_be_deleted_even_if_its_receipt_file_is_already_gone(app, client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client, files={0: ("a.png", PNG)})
    os.remove(os.path.join(app.config["RECEIPT_DIR"], claim.items[0].receipt_file))
    assert post(client, f"/claims/{claim.id}/delete").status_code == 302
    assert db.session.get(Claim, claim.id) is None


def test_failed_submit_from_the_form_keeps_the_claim_as_a_draft(client, team):
    db.session.get(User, team["employee"]).manager_id = None
    db.session.commit()
    sign_in(client, team["employee"])
    res = post(client, "/claims/new", claim_form(action="submit"), content_type="multipart/form-data")
    claim = Claim.query.one()
    assert claim.status == "draft" and res.headers["Location"].endswith(f"/claims/{claim.id}/edit")
    assert "need a manager assigned" in flash_text(client)


# ---------- Buttons on the claim page ----------

def test_submit_button_on_the_claim_page(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client)
    post(client, f"/claims/{claim.id}/submit")
    db.session.expire_all()
    assert claim.status == "submitted"


def test_only_drafts_can_be_deleted(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client, action="submit")
    post(client, f"/claims/{claim.id}/delete")
    assert db.session.get(Claim, claim.id) is not None
    assert "Only drafts can be deleted." in flash_text(client)


def test_a_refused_action_shows_the_reason(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client, action="submit")
    sign_in(client, team["finance"])
    post(client, f"/claims/{claim.id}/pay")
    db.session.expire_all()
    assert claim.status == "submitted" and "Only approved claims can be marked as paid." in flash_text(client)


def test_a_claim_changed_by_someone_else_is_not_saved_over_it(client, team, monkeypatch):
    sign_in(client, team["employee"])
    claim = new_claim(client, action="submit", lines=(("Travel", "Taxi", "200", "BDT", ""),))
    sign_in(client, team["manager"])
    post(client, f"/claims/{claim.id}/approve")
    real_mark_paid = rules.mark_paid

    def paid_elsewhere_first(c, user):  # another request records the payment between our read and our save
        db.session.execute(update(Claim).where(Claim.id == c.id).values(updated_at=utcnow())
                           .execution_options(synchronize_session=False))
        real_mark_paid(c, user)

    monkeypatch.setattr(rules, "mark_paid", paid_elsewhere_first)
    sign_in(client, team["finance"])
    post(client, f"/claims/{claim.id}/pay")
    assert "just changed by someone else" in flash_text(client)
    db.session.expire_all()
    assert claim.status == "approved"


# ---------- Workspaces, dashboard and exports ----------

def test_status_wording_payables_aging_and_full_export(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client, action="submit", lines=(("Travel", "Taxi", "200", "BDT", ""),))
    big = new_claim(client, action="submit", title="Conference", lines=(("Travel", "Flights", "4000", "BDT", ""),))
    assert "With Tanvir Ahmed" in client.get("/workspace").get_data(as_text=True)
    sign_in(client, team["manager"])
    post(client, f"/claims/{claim.id}/approve")
    post(client, f"/claims/{big.id}/approve")  # over ৳1,000: on to Finance
    sign_in(client, team["employee"])
    workspace = client.get("/workspace").get_data(as_text=True)
    assert "Payment pending" in workspace and "With Finance" in workspace
    sign_in(client, team["finance"])
    assert "0–7 days" in client.get("/dashboard").get_data(as_text=True)
    res = client.get("/dashboard/export.xlsx")  # no filter: every non-draft claim
    assert res.status_code == 200 and res.data[:2] == b"PK"


def test_export_leaves_the_date_blank_for_a_claim_never_submitted(team):
    claim = Claim(owner_id=team["employee"], title="Unsent", status="draft",
                  items=[LineItem(date=date(2026, 11, 1), category="Other", description="x", amount=Decimal("5"), currency="BDT")])
    db.session.add(claim)
    db.session.flush()
    assert claims_workbook([claim], [], exported_by="Test")[:2] == b"PK"


# ---------- Accounts ----------

def test_unknown_role_and_bad_sign_up_details_are_refused(client, team):
    with client.session_transaction() as s:  # a signed-out visitor with a valid form token
        s["csrf"] = CSRF
    res = post(client, "/get-started", {"role": "admin"})
    assert res.status_code == 400 and b"session expired" not in res.data
    res = post(client, "/signup", {"name": "", "email": "no-at-sign", "password": "longenough", "role": "finance"})
    assert res.status_code == 400 and b"Enter your full name." in res.data and b"Enter a valid work email." in res.data


def test_profile_edit_reports_every_problem(client, team):
    from werkzeug.security import generate_password_hash
    db.session.get(User, team["teammate"]).password_hash = generate_password_hash("old-password")
    db.session.commit()
    sign_in(client, team["teammate"])
    res = post(client, "/profile/edit", {"name": "", "email": "bad", "title": "x" * 121, "manager_id": str(team["manager"]),
                                         "current_password": "old-password", "new_password": "short", "confirm_password": "short"})
    page = res.get_data(as_text=True)
    assert res.status_code == 400
    for message in ("Enter your full name.", "Enter a valid work email.", "under 120 characters", "at least 8 characters"):
        assert message in page
    res = post(client, "/profile/edit", {"name": "Rafiq Hasan", "email": "rafiq@example.com", "manager_id": str(team["manager"]),
                                         "current_password": "old-password", "new_password": "long-enough", "confirm_password": "different"})
    assert res.status_code == 400 and "don&#39;t match" in res.get_data(as_text=True)


# ---------- Start-up ----------

def test_app_loads_the_sample_data_on_first_start():
    class Config(TestConfig):
        SEED_SAMPLE_DATA = True

    app = create_app(Config)
    with app.app_context():
        assert Claim.query.count() == 24
        db.session.remove()
        db.engine.dispose()


def test_unknown_pages_show_the_claimora_404_page(client, team):
    res = client.get("/no-such-page")
    assert res.status_code == 404 and b"Page <strong>not found</strong>" in res.data and b"Go to the home page" in res.data
    sign_in(client, team["outsider"])
    res = client.get("/claims/99999")  # a claim that doesn't exist, while signed in
    assert res.status_code == 404 and b"Go to your workspace" in res.data


def test_pages_take_limits_and_rates_from_the_rules(app, client, team):
    from app.models import RATES
    assert app.jinja_env.globals["finance_threshold"] == rules.FINANCE_THRESHOLD
    sign_in(client, team["employee"])
    form = client.get("/claims/new").get_data(as_text=True)
    assert f"USD at ৳{RATES['USD']:,.0f}" in form and f"EUR at ৳{RATES['EUR']:,.0f}" in form
    assert f'data-threshold="{rules.FINANCE_THRESHOLD}"' in form and f"Meals over ৳{rules.MEAL_NOTE_LIMIT:,.0f} have a note" in form


def test_exports_are_never_cached_by_the_browser(client, team):
    # a cached copy would show old figures after the data changed
    sign_in(client, team["finance"])
    for url in ("/dashboard/export.xlsx", "/dashboard/approved.xlsx?range=month", "/dashboard/approved.csv?range=all"):
        res = client.get(url)
        assert res.headers["Cache-Control"] == "no-store" and "Expires" not in res.headers, url
