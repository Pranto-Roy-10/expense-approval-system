import os
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_from_directory, url_for
from sqlalchemy.orm.exc import StaleDataError
from werkzeug.utils import secure_filename

from . import rules
from .auth import login_required
from .extensions import db
from .models import CATEGORIES, RATES, Claim, LineItem
from .rules import RuleError

bp = Blueprint("claims", __name__, url_prefix="/claims")

# Receipt types we accept, with the bytes each real file starts with.
RECEIPT_TYPES = {
    ".pdf": ("application/pdf", (b"%PDF",)),
    ".png": ("image/png", (b"\x89PNG",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".webp": ("image/webp", (b"RIFF",)),
}
MAX_RECEIPT_BYTES = 5 * 1024 * 1024


def can_view(claim, user):
    if claim.owner_id == user.id:
        return True
    if claim.status == "draft":
        return False
    return user.role == "finance" or (user.role == "manager" and claim.owner.manager_id == user.id)


def get_claim(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    if not can_view(claim, g.user):
        abort(404)  # don't reveal that someone else's claim exists
    return claim


# ---------- Form rows ----------

def _rows_from_form():
    """Line item rows in the order they appear on the form, as raw strings."""
    keys = [k[len("items-"):-len("-description")] for k in request.form
            if k.startswith("items-") and k.endswith("-description")]
    rows = []
    for key in keys:
        field = lambda name: request.form.get(f"items-{key}-{name}", "").strip()
        rows.append({
            "key": key, "id": field("id"), "date": field("date"), "category": field("category"),
            "description": field("description"), "amount": field("amount"), "currency": field("currency"),
            "note": field("note"), "remove_receipt": bool(field("remove_receipt")),
            "upload": request.files.get(f"items-{key}-receipt"),
            "receipt_name": field("receipt_name"),
        })
    return rows


def _rows_from_claim(claim):
    return [{
        "key": str(i.id), "id": str(i.id), "date": i.date.isoformat(), "category": i.category,
        "description": i.description, "amount": f"{i.amount:.2f}", "currency": i.currency,
        "note": i.note or "", "remove_receipt": False, "upload": None, "receipt_name": i.receipt_name or "",
    } for i in claim.items]


def _typed(row):
    try:
        day = date.fromisoformat(row["date"])
    except ValueError:
        day = None
    try:
        amount = Decimal(row["amount"])
        amount = amount.quantize(Decimal("0.01")) if amount.is_finite() else None
    except InvalidOperation:
        amount = None
    return {"date": day, "category": row["category"], "description": row["description"][:240],
            "amount": amount, "currency": row["currency"], "note": row["note"][:500] or None}


def _check_upload(upload, n):
    if not upload or not upload.filename:
        return None
    ext = os.path.splitext(upload.filename)[1].lower()
    if ext not in RECEIPT_TYPES:
        raise RuleError(f"Line {n}: receipts must be a PDF, PNG, JPG or WEBP file.")
    upload.stream.seek(0, os.SEEK_END)
    size = upload.stream.tell()
    upload.stream.seek(0)
    if size > MAX_RECEIPT_BYTES:
        raise RuleError(f"Line {n}: receipts can be up to 5 MB.")
    head = upload.stream.read(8)
    upload.stream.seek(0)
    if not head.startswith(RECEIPT_TYPES[ext][1]):
        raise RuleError(f"Line {n}: that file doesn't look like a real {ext[1:].upper()}.")
    return ext


def _delete_receipt(stored):
    if stored:
        try:
            os.remove(os.path.join(current_app.config["RECEIPT_DIR"], stored))
        except FileNotFoundError:
            pass


def _save(claim):
    """Validate the posted form and apply it to the claim.
    Returns (error or None, rows, receipt files to delete once the change is committed)."""
    title = request.form.get("title", "").strip()[:160]
    rows = _rows_from_form()
    try:
        if not title:
            raise RuleError("Give the claim a title.")
        rules.validate_items([LineItem(**_typed(r)) for r in rows])
        exts = [_check_upload(r["upload"], n) for n, r in enumerate(rows, 1)]
    except RuleError as e:
        return str(e), rows, []

    existing = {str(i.id): i for i in claim.items}
    kept, stale = [], []
    for row, ext in zip(rows, exts):
        item = existing.pop(row["id"], None) or LineItem()
        for name, value in _typed(row).items():
            setattr(item, name, value)
        if ext or row["remove_receipt"]:
            stale.append(item.receipt_file)
            item.receipt_file = item.receipt_name = None
        if ext:
            item.receipt_file = f"{uuid4().hex}{ext}"
            item.receipt_name = secure_filename(row["upload"].filename) or f"receipt{ext}"
            row["upload"].save(os.path.join(current_app.config["RECEIPT_DIR"], item.receipt_file))
        kept.append(item)
    stale += [gone.receipt_file for gone in existing.values()]
    claim.title = title
    claim.items = kept
    return None, rows, stale


def _render_form(claim, rows, error=None):
    if error and any(r["upload"] and r["upload"].filename for r in rows):
        error += " Nothing was saved, so attach your new receipts again."  # browsers can't refill file inputs
    return render_template("claims/form.html", claim=claim, rows=rows, error=error,
                           title=request.form.get("title", claim.title or ""),
                           categories=CATEGORIES, currencies=RATES), (400 if error else 200)


def _after_save(claim, stale):
    """Save draft, or save and submit, depending on which button was pressed.
    Old receipt files are removed only after the commit, so a failed save never loses one."""
    target = url_for("claims.detail", claim_id=claim.id)
    if request.form.get("action") == "submit":
        try:
            rules.submit(claim, g.user)
            flash(f"{claim.code} submitted to {g.user.manager.name} for review.", "success")
        except RuleError as e:
            flash(str(e), "error")  # the edits are still kept as a draft
            target = url_for("claims.edit", claim_id=claim.id)
    else:
        flash(f"{claim.code} saved as a draft.", "success")
    db.session.commit()
    for stored in stale:
        _delete_receipt(stored)
    return redirect(target)


# ---------- Routes ----------

@bp.route("/new", methods=["GET", "POST"])
@login_required("employee")
def new():
    claim = Claim(owner_id=g.user.id)  # added to the session only once it is valid
    if request.method == "POST":
        error, rows, stale = _save(claim)
        if error:
            return _render_form(claim, rows, error)
        db.session.add(claim)
        rules.record_created(claim, g.user)
        db.session.flush()  # assigns the claim number used in the message
        return _after_save(claim, stale)
    blank = {"key": "n0", "id": "", "date": date.today().isoformat(), "category": "", "description": "",
             "amount": "", "currency": "BDT", "note": "", "remove_receipt": False, "upload": None, "receipt_name": ""}
    return _render_form(claim, [blank])


@bp.route("/<int:claim_id>/edit", methods=["GET", "POST"])
@login_required("employee")
def edit(claim_id):
    claim = get_claim(claim_id)
    if claim.owner_id != g.user.id or not claim.editable:
        flash("Only draft or rejected claims can be edited.", "error")
        return redirect(url_for("claims.detail", claim_id=claim.id))
    if request.method == "POST":
        error, rows, stale = _save(claim)
        if error:
            db.session.rollback()
            return _render_form(claim, rows, error)
        return _after_save(claim, stale)
    return _render_form(claim, _rows_from_claim(claim))


@bp.get("/<int:claim_id>")
@login_required()
def detail(claim_id):
    claim = get_claim(claim_id)
    return render_template("claims/detail.html", claim=claim, can_review=rules.can_review(claim, g.user))


@bp.post("/<int:claim_id>/delete")
@login_required("employee")
def delete(claim_id):
    claim = get_claim(claim_id)
    if claim.owner_id != g.user.id or claim.status != "draft":
        flash("Only drafts can be deleted.", "error")
        return redirect(url_for("claims.detail", claim_id=claim.id))
    stale = [item.receipt_file for item in claim.items]
    db.session.delete(claim)
    db.session.commit()
    for stored in stale:
        _delete_receipt(stored)
    flash(f"{claim.code} deleted.", "success")
    return redirect(url_for("main.workspace"))


def _transition(claim_id, action, success):
    claim = get_claim(claim_id)
    try:
        action(claim)
    except RuleError as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(url_for("claims.detail", claim_id=claim_id))
    try:
        db.session.commit()
    except StaleDataError:  # someone else changed the claim between our read and our save
        db.session.rollback()
        flash("This claim was just changed by someone else. Check it and try again.", "error")
        return redirect(url_for("claims.detail", claim_id=claim_id))
    flash(success.format(code=claim.code, label=claim.label.lower()), "success")
    return redirect(url_for("main.workspace") if g.user.role != "employee" else url_for("claims.detail", claim_id=claim_id))


@bp.post("/<int:claim_id>/submit")
@login_required("employee")
def submit(claim_id):
    return _transition(claim_id, lambda c: rules.submit(c, g.user), "{code} submitted for review.")


@bp.post("/<int:claim_id>/approve")
@login_required("manager", "finance")
def approve(claim_id):
    return _transition(claim_id, lambda c: rules.approve(c, g.user, request.form.get("comment")), "{code} approved. Status: {label}.")


@bp.post("/<int:claim_id>/reject")
@login_required("manager", "finance")
def reject(claim_id):
    return _transition(claim_id, lambda c: rules.reject(c, g.user, request.form.get("comment")), "{code} rejected and returned to the employee.")


@bp.post("/<int:claim_id>/pay")
@login_required("finance")
def pay(claim_id):
    return _transition(claim_id, lambda c: rules.mark_paid(c, g.user), "{code} marked as paid.")


@bp.get("/receipts/<int:item_id>")
@login_required()
def receipt(item_id):
    item = db.get_or_404(LineItem, item_id)
    if not item.receipt_file or not can_view(item.claim, g.user):
        abort(404)
    ext = os.path.splitext(item.receipt_file)[1]
    response = send_from_directory(current_app.config["RECEIPT_DIR"], item.receipt_file,
                                   mimetype=RECEIPT_TYPES[ext][0], download_name=item.receipt_name)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, max-age=300"
    return response
