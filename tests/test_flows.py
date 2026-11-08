"""HTTP tests: sign-up and sign-in, access control, receipts and the full claim lifecycle."""
import io
from datetime import date

from app.extensions import db
from app.models import Claim, User, utcnow
from app.dashboard import finance_overview
from app.routes import taka

from .conftest import post, sign_in

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64
PDF = b"%PDF-1.4\n%test\n"


def claim_form(title="Client visit", lines=(("Travel", "Flight", "900", "BDT", ""),), action="draft", files=None):
    data = {"title": title, "action": action}
    for n, (category, description, amount, currency, note) in enumerate(lines):
        data.update({f"items-n{n}-id": "", f"items-n{n}-date": "2026-11-02", f"items-n{n}-category": category,
                     f"items-n{n}-description": description, f"items-n{n}-amount": amount,
                     f"items-n{n}-currency": currency, f"items-n{n}-note": note})
    for n, (name, content) in (files or {}).items():
        data[f"items-n{n}-receipt"] = (io.BytesIO(content), name)
    return data


def new_claim(client, **kwargs):
    res = post(client, "/claims/new", claim_form(**kwargs), content_type="multipart/form-data")
    assert res.status_code == 302, res.data
    return db.session.query(Claim).order_by(Claim.id.desc()).first()


# ---------- Getting in ----------

def test_get_started_offers_each_sample_role(client, team):
    page = client.get("/get-started").data
    for role in (b"Employee", b"Manager", b"Finance"):
        assert b"Continue as " + role in page
    assert b'href="/"' in page and b'href="/signup"' in page


def test_continue_as_role_signs_in_that_sample_user(client, team):
    client.get("/get-started")  # issues the form token
    with client.session_transaction() as s:
        token = s["csrf"]
    res = client.post("/get-started", data={"csrf": token, "role": "finance"})
    assert res.headers["Location"].endswith("/workspace")
    assert b"Farhana Islam" in client.get("/workspace").data


def test_post_without_token_is_refused(client, team):
    assert client.post("/get-started", data={"role": "finance"}).status_code == 400


def test_signup_creates_an_employee_and_signs_in(client, team):
    sign_in(client, None)
    res = post(client, "/signup", {"name": "Imran Hossain", "email": "Imran@Example.com", "password": "longenough",
                                    "role": "employee", "manager_id": team["manager"]})
    assert res.status_code == 302
    user = User.query.filter_by(email="imran@example.com").one()
    assert user.role == "employee" and user.manager_id == team["manager"] and user.password_hash != "longenough"
    assert b"My claims" in client.get("/workspace").data


def test_signup_validates_input(client, team):
    sign_in(client, None)
    base = {"name": "Imran", "email": "imran@example.com", "password": "longenough", "role": "employee",
            "manager_id": team["manager"]}
    for change, message in [({"email": "nusrat@example.com"}, b"already exists"),
                            ({"password": "short"}, b"at least 8"),
                            ({"manager_id": ""}, b"Choose the manager"),
                            ({"manager_id": team["finance"]}, b"Choose the manager"),
                            ({"role": "admin"}, b"Choose a role")]:
        res = post(client, "/signup", {**base, **change})
        assert res.status_code == 400 and message in res.data


def test_login_with_password(client, team):
    sign_in(client, None)
    post(client, "/signup", {"name": "Imran Hossain", "email": "imran@example.com", "password": "longenough",
                             "role": "finance"})
    post(client, "/logout")
    sign_in(client, None)
    assert b"don&#39;t match" in post(client, "/login", {"email": "imran@example.com", "password": "wrong"}).data
    assert post(client, "/login", {"email": "imran@example.com", "password": "longenough"}).status_code == 302


def test_account_pages_stay_open_to_a_signed_in_tester(client, team):
    landing = client.get("/").data  # signed out: Sign in leads to the roles
    assert b'href="/get-started">Sign in' in landing and b"Open workspace" not in landing
    sign_in(client, team["employee"])
    landing = client.get("/").data  # signed in: straight to the workspace
    assert b'href="/workspace">Open workspace' in landing and b'href="/get-started"' not in landing
    for url in ("/get-started", "/login", "/signup"):
        page = client.get(url).data
        assert b"signed in as <strong>Nusrat Jahan</strong>" in page, url
        assert b'class="user-chip"' not in page, url  # the old account isn't shown as the current one
    assert b"Continue as Manager" in client.get("/get-started").data

    # choosing another role replaces the signed-in account
    post(client, "/get-started", {"role": "manager"})
    assert b"Tanvir Ahmed" in client.get("/workspace").data
    assert b"Review queue" in client.get("/workspace").data


def test_workspace_needs_sign_in(client):
    assert client.get("/workspace").headers["Location"].endswith("/get-started")


# ---------- Claims and access ----------

def test_employee_creates_edits_and_deletes_a_draft(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client)
    assert claim.status == "draft" and claim.total == 900
    res = post(client, f"/claims/{claim.id}/edit",
               claim_form(title="Client visit, Sylhet", lines=(("Travel", "Flight", "900", "BDT", ""),
                                                                ("Meals", "Lunch", "40", "BDT", ""))),
               content_type="multipart/form-data")
    assert res.status_code == 302
    db.session.expire_all()
    assert claim.title == "Client visit, Sylhet" and len(claim.items) == 2
    assert post(client, f"/claims/{claim.id}/delete").status_code == 302
    assert db.session.get(Claim, claim.id) is None


def test_invalid_claim_shows_the_error_and_saves_nothing(client, team):
    sign_in(client, team["employee"])
    res = post(client, "/claims/new", claim_form(lines=(("Meals", "Dinner", "900", "BDT", ""),)),
               content_type="multipart/form-data")
    assert res.status_code == 400 and b"need a note" in res.data
    assert Claim.query.count() == 0


def test_other_people_cannot_see_a_claim(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client, action="submit")
    for key in ("teammate", "outsider", "other_manager"):
        sign_in(client, team[key])
        assert client.get(f"/claims/{claim.id}").status_code == 404
    sign_in(client, team["manager"])
    assert client.get(f"/claims/{claim.id}").status_code == 200


def test_drafts_stay_private(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client)
    sign_in(client, team["manager"])
    assert client.get(f"/claims/{claim.id}").status_code == 404


def test_submitted_claim_cannot_be_edited_over_http(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client, action="submit")
    post(client, f"/claims/{claim.id}/edit", claim_form(title="Changed"), content_type="multipart/form-data")
    db.session.expire_all()
    assert claim.title == "Client visit"


def test_employee_cannot_approve_over_http(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client, action="submit")
    sign_in(client, team["teammate"])
    assert post(client, f"/claims/{claim.id}/approve").status_code == 403


# ---------- Receipts ----------

def test_receipts_are_stored_and_served_to_reviewers_only(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client, action="submit", files={0: ("taxi.png", PNG)})
    item = claim.items[0]
    assert item.receipt_name == "taxi.png" and item.receipt_file.endswith(".png")

    page = client.get(f"/claims/{claim.id}").data
    assert f"/claims/receipts/{item.id}".encode() in page and b"data-viewer" in page

    for key, status in (("employee", 200), ("manager", 200), ("finance", 200), ("teammate", 404), ("outsider", 404)):
        sign_in(client, team[key])
        res = client.get(f"/claims/receipts/{item.id}")
        assert res.status_code == status, key
        if status == 200:
            assert res.mimetype == "image/png" and res.data == PNG
            assert res.headers["X-Content-Type-Options"] == "nosniff"
            assert "inline" in res.headers["Content-Disposition"]
        res.close()  # receipts are streamed from disk; release the file handle


def test_pdf_receipt_is_served_inline(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client, files={0: ("hotel.pdf", PDF)})
    res = client.get(f"/claims/receipts/{claim.items[0].id}")
    assert res.mimetype == "application/pdf" and "inline" in res.headers["Content-Disposition"]
    res.close()


def test_fake_or_unsupported_receipts_are_refused(client, team):
    sign_in(client, team["employee"])
    for name, content, message in (("receipt.exe", b"MZ", b"must be a PDF"),
                                   ("receipt.png", b"<script>", b"doesn&#39;t look like a real PNG")):
        res = post(client, "/claims/new", claim_form(files={0: (name, content)}), content_type="multipart/form-data")
        assert res.status_code == 400 and message in res.data
    assert Claim.query.count() == 0


def test_replacing_and_removing_a_receipt_deletes_the_old_file(app, client, team):
    import os
    sign_in(client, team["employee"])
    claim = new_claim(client, files={0: ("a.png", PNG)})
    item = claim.items[0]
    old = os.path.join(app.config["RECEIPT_DIR"], item.receipt_file)
    form = claim_form(files={0: ("b.pdf", PDF)})
    form["items-n0-id"] = str(item.id)
    post(client, f"/claims/{claim.id}/edit", form, content_type="multipart/form-data")
    db.session.expire_all()
    assert not os.path.exists(old) and item.receipt_name == "b.pdf"

    form = claim_form()
    form.update({"items-n0-id": str(item.id), "items-n0-remove_receipt": "1"})
    post(client, f"/claims/{claim.id}/edit", form, content_type="multipart/form-data")
    db.session.expire_all()
    assert item.receipt_file is None and os.listdir(app.config["RECEIPT_DIR"]) == []


# ---------- End to end ----------

def test_full_claim_lifecycle(client, team):
    # Employee: create a claim over 1,000 with a receipt and submit it
    sign_in(client, team["employee"])
    claim = new_claim(client, action="submit", title="Client workshop",
                      lines=(("Travel", "Flight", "7800", "BDT", ""),
                             ("Meals", "Team dinner", "3450", "BDT", "Client dinner, 6 people")),
                      files={0: ("flight.pdf", PDF)})
    assert claim.status == "submitted"

    # Manager: rejects it with a comment
    sign_in(client, team["manager"])
    assert b"Client workshop" in client.get("/workspace").data
    post(client, f"/claims/{claim.id}/reject", {"comment": "Add the hotel receipt"})
    db.session.expire_all()
    assert claim.status == "rejected"

    # Employee: sees the comment, edits and resubmits
    sign_in(client, team["employee"])
    assert b"Add the hotel receipt" in client.get(f"/claims/{claim.id}").data
    form = claim_form(title="Client workshop", action="submit",
                      lines=(("Travel", "Flight", "7800", "BDT", ""),
                             ("Meals", "Team dinner", "3450", "BDT", "Client dinner, 6 people"),
                             ("Travel", "Hotel", "12400", "BDT", "")),
                      files={2: ("hotel.png", PNG)})
    form["items-n0-id"], form["items-n1-id"] = str(claim.items[0].id), str(claim.items[1].id)
    post(client, f"/claims/{claim.id}/edit", form, content_type="multipart/form-data")
    db.session.expire_all()
    assert claim.status == "submitted" and claim.total == 23650
    assert all(i.receipt_file for i in claim.items if i.description != "Team dinner")

    # Manager approves: over 1,000, so it moves on to Finance
    sign_in(client, team["manager"])
    post(client, f"/claims/{claim.id}/approve", {"comment": "Looks right"})
    db.session.expire_all()
    assert claim.awaiting_finance

    # Finance approves, then marks it paid
    sign_in(client, team["finance"])
    assert b"Client workshop" in client.get("/workspace").data
    post(client, f"/claims/{claim.id}/approve")
    post(client, f"/claims/{claim.id}/pay")
    db.session.expire_all()
    assert claim.status == "paid"

    # The audit trail shows every step, and the employee sees the final state
    assert [e.action for e in reversed(claim.audit)] == [
        "Created", "Submitted", "Rejected", "Resubmitted",
        "Approved by manager, sent to Finance", "Approved", "Marked as paid"]
    sign_in(client, team["employee"])
    page = client.get(f"/claims/{claim.id}").data.decode()
    assert "Marked as paid" in page and "Add the hotel receipt" in page and "23,650.00" in page


def test_taka_uses_south_asian_grouping():
    assert taka(950) == "950.00"
    assert taka(23650) == "23,650.00"
    assert taka(182400, 0) == "1,82,400"
    assert taka(1234567.5) == "12,34,567.50"
    assert taka(-1500) == "-1,500.00"


def test_finance_dashboard_reports_paid_spend_and_is_finance_only(client, team):
    sign_in(client, team["employee"])
    claim = new_claim(client, action="submit", title="Printer paper",
                      lines=(("Office Supplies", "Paper", "900", "BDT", ""),))
    assert client.get("/dashboard").status_code in (302, 403)

    sign_in(client, team["manager"])
    post(client, f"/claims/{claim.id}/approve")  # under 1,000: no Finance sign-off
    sign_in(client, team["finance"])
    post(client, f"/claims/{claim.id}/pay")

    page = client.get("/dashboard").data.decode()
    assert "Printer paper" in page and "Nusrat Jahan" in page  # ledger
    assert 'href="/dashboard"' in page and 'aria-current="page"' in page  # sidebar

    paid_today = finance_overview(utcnow().date())["kpis"]  # the payment was recorded just now
    assert paid_today["paid_month"] == 900 and paid_today["payable_count"] == 0
    overview = finance_overview(date(2026, 11, 8))  # the line item is dated 2 Nov 2026
    assert overview["chart"]["stacked"] == [{"label": "Office Supplies", "slot": 2, "data": [0, 0, 0, 0, 0, 900.0]}]
    assert overview["categories"] == [("Office Supplies", 900)]


def test_profile_shows_account_details_for_every_role(client, team):
    sign_in(client, team["employee"])
    page = client.get("/profile").data.decode()
    assert "nusrat@example.com" in page and "Tanvir Ahmed" in page and "Sample account" in page
    assert 'href="/dashboard"' not in page  # no Finance link for employees

    sign_in(client, team["manager"])
    page = client.get("/profile").data.decode()
    assert "Direct reports" in page and "Nusrat Jahan" in page and "Rafiq Hasan" in page

    sign_in(client, team["finance"])
    assert client.get("/profile").status_code == 200


def test_editing_the_profile_validates_and_saves(client, team):
    from werkzeug.security import check_password_hash, generate_password_hash
    rafiq = db.session.get(User, team["teammate"])
    rafiq.password_hash = generate_password_hash("old-password")
    db.session.commit()
    sign_in(client, team["teammate"])
    assert b"Edit profile" in client.get("/profile/edit").data

    base = {"name": "Rafiq Hasan", "email": "rafiq@example.com", "title": "QA Lead", "manager_id": str(team["other_manager"])}
    res = post(client, "/profile/edit", {**base, "email": "nusrat@example.com"})
    assert res.status_code == 400 and b"Another account already uses this email." in res.data
    res = post(client, "/profile/edit", {**base, "current_password": "wrong", "new_password": "new-password", "confirm_password": "new-password"})
    assert res.status_code == 400 and b"Your current password is not correct." in res.data
    res = post(client, "/profile/edit", {**base, "manager_id": str(team["finance"])})
    assert res.status_code == 400  # only managers can review claims

    res = post(client, "/profile/edit", {**base, "current_password": "old-password", "new_password": "new-password", "confirm_password": "new-password"})
    assert res.status_code == 302
    db.session.expire_all()
    rafiq = db.session.get(User, team["teammate"])
    assert rafiq.title == "QA Lead" and rafiq.manager_id == team["other_manager"]
    assert check_password_hash(rafiq.password_hash, "new-password")
    assert b"Profile updated. Your password has been changed." in client.get("/profile").data


def test_finance_exports_a_branded_excel_file_in_the_shown_order(client, team):
    import zipfile
    sign_in(client, team["employee"])
    first = new_claim(client, action="submit", title="Taxi to client")
    second = new_claim(client, action="submit", title="Team lunch",
                       lines=(("Meals", "Lunch", "40", "BDT", ""),))
    assert client.get("/dashboard/export.xlsx").status_code in (302, 403)

    sign_in(client, team["finance"])
    res = client.get(f"/dashboard/export.xlsx?ids={second.id},{first.id}&status=submitted")
    assert res.status_code == 200
    assert res.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "claimora-claims-" in res.headers["Content-Disposition"]
    book = zipfile.ZipFile(io.BytesIO(res.data))
    assert {"xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"} <= set(book.namelist())  # Claims + Summary
    strings = book.read("xl/sharedStrings.xml").decode()
    assert "Claimora" in strings and "Claims ledger" in strings and "Status: In review" in strings
    assert strings.index("Team lunch") < strings.index("Taxi to client")  # the order the user had on screen


def test_finance_exports_approved_claims_as_csv(client, team):
    sign_in(client, team["employee"])
    approved = new_claim(client, action="submit", title="Printer ink", lines=(("Office Supplies", "Ink", "900", "BDT", ""),))
    new_claim(client, action="submit", title="Still in review")
    sign_in(client, team["manager"])
    post(client, f"/claims/{approved.id}/approve")  # under 1,000: approved straight away

    sign_in(client, team["finance"])
    res = client.get("/dashboard/approved.csv")
    assert res.status_code == 200 and res.mimetype == "text/csv"
    lines = res.data.decode("utf-8-sig").splitlines()
    assert lines[0].startswith("Claim ID,Title,Employee")
    assert len(lines) == 2 and "Printer ink" in lines[1] and lines[1].endswith(",Approved,900.00")

    # the same claims as a branded workbook
    import zipfile
    book = zipfile.ZipFile(io.BytesIO(client.get("/dashboard/approved.xlsx").data))
    strings = book.read("xl/sharedStrings.xml").decode()
    assert "Approved claims" in strings and "Status: Approved and paid" in strings
    assert "Printer ink" in strings and "Still in review" not in strings


def test_exports_keep_formula_like_titles_as_text(client, team):
    import zipfile
    sign_in(client, team["employee"])
    claim = new_claim(client, action="submit", title='=HYPERLINK("http://x","Open")',
                      lines=(("Office Supplies", "Ink", "900", "BDT", ""),))
    sign_in(client, team["manager"])
    post(client, f"/claims/{claim.id}/approve")

    sign_in(client, team["finance"])
    csv_text = client.get("/dashboard/approved.csv").data.decode("utf-8-sig")
    assert "'=HYPERLINK" in csv_text
    book = zipfile.ZipFile(io.BytesIO(client.get("/dashboard/approved.xlsx").data))
    assert "HYPERLINK" not in book.read("xl/worksheets/sheet1.xml").decode()  # not written as a formula
    assert "=HYPERLINK" in book.read("xl/sharedStrings.xml").decode()  # kept as plain text


def test_too_large_upload_returns_to_the_form_with_a_message(app, client, team):
    app.config["MAX_CONTENT_LENGTH"] = 1024
    sign_in(client, team["employee"])
    res = post(client, "/claims/new", claim_form(files={0: ("big.pdf", PDF + b"0" * 4096)}),
               content_type="multipart/form-data")
    assert res.status_code == 302 and res.headers["Location"].endswith("/claims/new")
    assert b"too large together" in client.get("/claims/new").data
    assert Claim.query.count() == 0


def test_ledger_shows_the_newest_claims_and_says_how_many_are_left_out(monkeypatch, client, team):
    from app import dashboard
    monkeypatch.setattr(dashboard, "LEDGER_ROWS", 1)
    sign_in(client, team["employee"])
    new_claim(client, action="submit", title="Older claim")
    new_claim(client, action="submit", title="Newer claim")
    sign_in(client, team["finance"])
    page = client.get("/dashboard").data
    assert b"1 older ones are left out" in page and b"data-capped" in page
    assert b"Newer claim" in page and b"Older claim" not in page
