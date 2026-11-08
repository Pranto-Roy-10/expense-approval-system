import csv
from datetime import date
from io import BytesIO, StringIO
from decimal import Decimal

from flask import Blueprint, Response, flash, g, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .auth import login_required
from .dashboard import finance_overview
from .export import claims_workbook
from .extensions import db
from .models import AuditEntry, Claim, User, utcnow

bp = Blueprint("main", __name__)


@bp.app_context_processor
def inject_year():
    return {"year": date.today().year}


@bp.app_template_filter("taka")
def taka(amount, decimals=2):
    """Format an amount with South Asian digit grouping, e.g. 123650 -> 1,23,650.00."""
    whole, _, frac = f"{abs(amount):.{decimals}f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    text = ",".join(groups + [tail]) + (f".{frac}" if frac else "")
    return f"-{text}" if amount < 0 else text


@bp.get("/")
def index():
    return render_template("index.html")


@bp.app_template_filter("ago")
def ago(moment):
    """Whole days since a moment: 'today', '1 day', '12 days'."""
    if moment is None:
        return "–"
    days = (utcnow() - moment).days
    return "today" if days < 1 else f"{days} day{'s' if days != 1 else ''}"


def _this_month(moment):
    now = utcnow()
    return moment is not None and (moment.year, moment.month) == (now.year, now.month)


@bp.get("/workspace")
@login_required()
def workspace():
    user = g.user
    if user.role == "employee":
        claims = Claim.query.filter_by(owner_id=user.id).order_by(Claim.updated_at.desc()).all()
        return render_template("workspace/employee.html", claims=claims)

    if user.role == "manager":
        team = user.reports
        team_claims = Claim.query.filter(Claim.owner_id.in_([r.id for r in team]), Claim.status != "draft").all()
        queue = sorted((c for c in team_claims if c.status == "submitted" and not c.awaiting_finance),
                       key=lambda c: c.entered("submitted"))
        decisions = AuditEntry.query.filter(AuditEntry.actor_id == user.id,
                                            AuditEntry.to_status.in_(("approved", "rejected", "submitted")),
                                            AuditEntry.action != "Submitted").order_by(AuditEntry.id.desc()).limit(6).all()
        members = [{
            "user": r,
            "in_review": sum(1 for c in team_claims if c.owner_id == r.id and c.status == "submitted"),
            "returned": sum(1 for c in team_claims if c.owner_id == r.id and c.status == "rejected"),
            "paid": sum((c.total for c in team_claims if c.owner_id == r.id and c.status == "paid"), Decimal(0)),
        } for r in team]
        approved_month = [a.claim for a in AuditEntry.query.filter(AuditEntry.actor_id == user.id,
                                                                   AuditEntry.action.like("Approved%"))
                          if _this_month(a.created_at)]
        return render_template(
            "workspace/manager.html", queue=queue, decisions=decisions, members=members,
            oldest=queue[0].entered("submitted") if queue else None,
            approved_count=len(approved_month), approved_total=sum((c.total for c in approved_month), Decimal(0)))

    # Finance: second-level approvals and payments; spend analysis lives on /dashboard
    approvals = sorted(Claim.query.filter(Claim.status == "submitted", Claim.manager_approved_at.isnot(None)),
                       key=lambda c: c.manager_approved_at)
    payments = sorted(Claim.query.filter_by(status="approved"), key=lambda c: c.entered("approved"))
    paid = sorted(Claim.query.filter_by(status="paid"), key=lambda c: c.entered("paid"), reverse=True)
    paid_month = [c for c in paid if _this_month(c.entered("paid"))]
    return render_template(
        "workspace/finance.html", approvals=approvals, payments=payments, paid=paid[:8],
        paid_month=sum((c.total for c in paid_month), Decimal(0)), paid_month_count=len(paid_month))


@bp.get("/dashboard")
@login_required("finance")
def dashboard():
    return render_template("dashboard.html", **finance_overview())


@bp.get("/dashboard/export.xlsx")
@login_required("finance")
def dashboard_export():
    """The claims ledger as a branded Excel file: the rows the user sees, in the order they see them."""
    query = Claim.query.filter(Claim.status != "draft")
    if "ids" in request.args:
        ids = [int(x) for x in request.args["ids"].split(",") if x.isdigit()][:5000]
        rank = {claim_id: n for n, claim_id in enumerate(ids)}
        claims = sorted(query.filter(Claim.id.in_(ids)).all(), key=lambda c: rank[c.id]) if ids else []
    else:
        claims = query.order_by(Claim.updated_at.desc()).all()
    status_names = {"submitted": "In review", "approved": "Approved", "paid": "Paid", "rejected": "Rejected"}
    applied = [(label, value[:60]) for label, value in (
        ("Status", status_names.get(request.args.get("status", ""), "")),
        ("Category", request.args.get("category", "")),
        ("Employee", request.args.get("owner", "")),
        ("Search", request.args.get("q", "").strip()),
    ) if value]
    data = claims_workbook(claims, applied, exported_by=g.user.name)
    return send_file(BytesIO(data), as_attachment=True,
                     download_name=f"claimora-claims-{date.today().isoformat()}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _approved_claims():
    """Every approved claim; paid ones included, since they were approved first."""
    return Claim.query.filter(Claim.status.in_(("approved", "paid"))).order_by(Claim.id).all()


@bp.get("/dashboard/approved.xlsx")
@login_required("finance")
def approved_xlsx():
    """Approved claims in the same branded Excel layout as the ledger export."""
    data = claims_workbook(_approved_claims(), [("Status", "Approved and paid")], exported_by=g.user.name,
                           title="Approved claims")
    return send_file(BytesIO(data), as_attachment=True,
                     download_name=f"claimora-approved-{date.today().isoformat()}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.get("/dashboard/approved.csv")
@login_required("finance")
def approved_csv():
    """The same approved claims as plain CSV, for tools that can't read Excel files."""
    claims = _approved_claims()
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(["Claim ID", "Title", "Employee", "Manager", "Main category", "Approved on", "Status", "Total (BDT)"])
    for c in claims:
        approved = c.entered("approved")
        writer.writerow([c.code, c.title, c.owner.name, c.owner.manager.name if c.owner.manager else "",
                         max(c.items, key=lambda i: i.base_amount).category if c.items else "",
                         approved.strftime("%Y-%m-%d") if approved else "", c.label, f"{c.total:.2f}"])
    # BOM so Excel opens the UTF-8 text (names, ৳) correctly
    return Response("﻿" + out.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": f"attachment; filename=claimora-approved-{date.today().isoformat()}.csv"})


@bp.get("/profile")
@login_required()
def profile():
    user = g.user
    mine = AuditEntry.query.filter_by(actor_id=user.id)
    if user.role == "employee":
        claims = user.claims
        figures = [
            ("Drafts and returned", sum(c.status in ("draft", "rejected") for c in claims), None),
            ("In review", sum(c.status == "submitted" for c in claims), None),
            ("Awaiting payment", sum(c.status == "approved" for c in claims), None),
            ("Reimbursed", sum((c.total for c in claims if c.status == "paid"), Decimal(0)), "money"),
        ]
    elif user.role == "manager":
        team = [r.id for r in user.reports]
        waiting = Claim.query.filter(Claim.owner_id.in_(team), Claim.status == "submitted",
                                     Claim.manager_approved_at.is_(None)).count()
        figures = [
            ("Direct reports", len(team), None),
            ("Waiting for you", waiting, None),
            ("Approved by you", mine.filter(AuditEntry.action.like("Approved%")).count(), None),
            ("Returned by you", mine.filter_by(to_status="rejected").count(), None),
        ]
    else:
        paid = [a.claim for a in mine.filter_by(to_status="paid")]
        figures = [
            ("Awaiting sign-off", Claim.query.filter(Claim.status == "submitted",
                                                     Claim.manager_approved_at.isnot(None)).count(), None),
            ("Ready to pay", Claim.query.filter_by(status="approved").count(), None),
            ("Payments recorded", len(paid), None),
            ("Paid out by you", sum((c.total for c in paid), Decimal(0)), "money"),
        ]
    return render_template("profile.html", user=user, figures=figures,
                           last_action=mine.order_by(AuditEntry.id.desc()).first())


@bp.route("/profile/edit", methods=["GET", "POST"])
@login_required()
def profile_edit():
    user = g.user
    managers = User.query.filter(User.role == "manager", User.id != user.id).order_by(User.name).all()
    form = request.form
    if request.method == "GET":
        return render_template("profile_edit.html", user=user, managers=managers, errors={}, form={
            "name": user.name, "email": user.email, "title": user.title or "", "manager_id": str(user.manager_id or "")})

    name, email, title = form.get("name", "").strip(), form.get("email", "").strip().lower(), form.get("title", "").strip()
    current, new, confirm = form.get("current_password", ""), form.get("new_password", ""), form.get("confirm_password", "")
    errors = {}
    if not name or len(name) > 120:
        errors["name"] = "Enter your full name."
    if "@" not in email or len(email) > 254:
        errors["email"] = "Enter a valid work email."
    elif User.query.filter(User.email == email, User.id != user.id).first():
        errors["email"] = "Another account already uses this email."
    if len(title) > 120:
        errors["title"] = "Keep the job title under 120 characters."
    manager = user.manager
    if user.role == "employee":
        manager = db.session.get(User, form.get("manager_id", type=int) or 0)
        if manager is None or manager.role != "manager" or manager.id == user.id:
            errors["manager_id"] = "Choose the manager who reviews your claims."
    if (current or new or confirm) and not user.is_sample:
        if not user.password_hash or not check_password_hash(user.password_hash, current):
            errors["current_password"] = "Your current password is not correct."
        if len(new) < 8:
            errors["new_password"] = "Use at least 8 characters."
        elif new != confirm:
            errors["confirm_password"] = "The passwords don't match."
    if errors:
        return render_template("profile_edit.html", user=user, managers=managers, errors=errors, form=form), 400

    user.name, user.email, user.title, user.manager = name, email, title or None, manager
    if new and not user.is_sample:
        user.password_hash = generate_password_hash(new)
    db.session.commit()
    flash("Profile updated." + (" Your password has been changed." if new and not user.is_sample else ""), "success")
    return redirect(url_for("main.profile"))


@bp.get("/api/health")
def health():
    return jsonify(status="ok")
