from datetime import datetime, timezone
from decimal import Decimal

from .extensions import db

ROLES = ("employee", "manager", "finance")
CATEGORIES = ("Travel", "Meals", "Office Supplies", "Software", "Other")
# Fixed conversion to the base currency (BDT). Rules and totals use base amounts.
RATES = {"BDT": Decimal("1"), "USD": Decimal("122"), "EUR": Decimal("132")}

STATUS_LABELS = {
    "draft": "Draft",
    "submitted": "Submitted",
    "approved": "Approved",
    "rejected": "Rejected",
    "paid": "Paid",
}


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))  # empty for the sample accounts
    role = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(120))
    is_sample = db.Column(db.Boolean, default=False, nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    manager = db.relationship("User", remote_side=[id], backref="reports")

    @property
    def initials(self):
        return "".join(part[0] for part in self.name.split()[:2]).upper()


class Claim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(20), default="draft", nullable=False)
    # set when the manager approves a claim that still needs Finance
    manager_approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    owner = db.relationship("User", backref="claims")
    items = db.relationship("LineItem", backref="claim", cascade="all, delete-orphan", order_by="LineItem.date")
    audit = db.relationship("AuditEntry", backref="claim", cascade="all, delete-orphan", order_by="AuditEntry.id.desc()")

    @property
    def code(self):
        return f"CLM-{self.id:04d}"

    @property
    def total(self):
        return sum((item.base_amount for item in self.items), Decimal("0"))

    @property
    def awaiting_finance(self):
        return self.status == "submitted" and self.manager_approved_at is not None

    @property
    def label(self):
        return "Awaiting Finance" if self.awaiting_finance else STATUS_LABELS[self.status]

    @property
    def stage(self):
        """Where the claim is, in plain words, for status columns."""
        if self.status == "submitted":
            if self.awaiting_finance:
                return "With Finance"
            return f"With {self.owner.manager.name}" if self.owner.manager else "With manager"
        return {"draft": "Not submitted", "rejected": "Returned to you", "approved": "Payment pending",
                "paid": "Paid"}[self.status]

    @property
    def receipts(self):
        return sum(1 for item in self.items if item.receipt_file)

    def entered(self, status):
        """When the claim last moved into a status, from its audit trail."""
        return next((a.created_at for a in self.audit if a.to_status == status), None)

    @property
    def editable(self):
        return self.status in ("draft", "rejected")


class LineItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claim.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(40), nullable=False)
    description = db.Column(db.String(240), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default="BDT", nullable=False)
    note = db.Column(db.String(500))
    receipt_file = db.Column(db.String(80))   # stored name inside RECEIPT_DIR
    receipt_name = db.Column(db.String(255))  # original file name, for display

    @property
    def base_amount(self):
        return (Decimal(self.amount) * RATES[self.currency]).quantize(Decimal("0.01"))

    @property
    def receipt_is_pdf(self):
        return bool(self.receipt_file) and self.receipt_file.endswith(".pdf")


class AuditEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claim.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(60), nullable=False)
    from_status = db.Column(db.String(20))
    to_status = db.Column(db.String(20), nullable=False)
    comment = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    actor = db.relationship("User")
