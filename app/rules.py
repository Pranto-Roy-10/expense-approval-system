"""Business rules for claims. Every status change goes through here, so the rules
hold no matter which page or request triggers it."""
from decimal import Decimal

from .models import CATEGORIES, RATES, AuditEntry, utcnow

MEAL_NOTE_LIMIT = Decimal("50")
FINANCE_THRESHOLD = Decimal("1000")


class RuleError(ValueError):
    """A request that breaks a business rule. The message is shown to the user."""


def validate_items(items):
    if not items:
        raise RuleError("Add at least one line item.")
    for n, item in enumerate(items, 1):
        if item.date is None:
            raise RuleError(f"Line {n}: enter a valid date.")
        if item.category not in CATEGORIES:
            raise RuleError(f"Line {n}: choose a category.")
        if not (item.description or "").strip():
            raise RuleError(f"Line {n}: add a description.")
        if item.currency not in RATES:
            raise RuleError(f"Line {n}: choose a currency.")
        if item.amount is None or item.amount <= 0:
            raise RuleError(f"Line {n}: the amount must be more than zero.")
        if item.category == "Meals" and item.base_amount > MEAL_NOTE_LIMIT and not (item.note or "").strip():
            raise RuleError(f"Line {n}: meals over ৳50 need a note.")


def _record(claim, actor, action, to_status, comment=None):
    claim.audit.append(AuditEntry(
        actor=actor, action=action, from_status=claim.status, to_status=to_status,
        comment=(comment or "").strip()[:1000] or None,  # the column holds 1,000 characters
    ))
    claim.status = to_status


def record_created(claim, actor):
    claim.audit.append(AuditEntry(actor=actor, action="Created", to_status="draft"))


def submit(claim, user):
    if claim.owner_id != user.id:
        raise RuleError("Only the person who created this claim can submit it.")
    if not claim.editable:
        raise RuleError("Only draft or rejected claims can be submitted.")
    if user.manager_id is None:
        raise RuleError("You need a manager assigned before you can submit claims.")
    validate_items(claim.items)
    action = "Resubmitted" if claim.status == "rejected" else "Submitted"
    claim.manager_approved_at = None
    _record(claim, user, action, "submitted")


def can_review(claim, user):
    """True when this user is the next approver for the claim."""
    if claim.status != "submitted" or claim.owner_id == user.id:
        return False
    if claim.awaiting_finance:
        return user.role == "finance"
    return user.role == "manager" and claim.owner.manager_id == user.id


def _check_reviewer(claim, user):
    if claim.owner_id == user.id:
        raise RuleError("You can't approve or reject your own claim.")
    if not can_review(claim, user):
        raise RuleError("This claim isn't waiting for your review.")


def approve(claim, user, comment=None):
    _check_reviewer(claim, user)
    if not claim.awaiting_finance and claim.total > FINANCE_THRESHOLD:
        claim.manager_approved_at = utcnow()
        _record(claim, user, "Approved by manager, sent to Finance", "submitted", comment)
    else:
        _record(claim, user, "Approved", "approved", comment)


def reject(claim, user, comment):
    _check_reviewer(claim, user)
    if not (comment or "").strip():
        raise RuleError("Add a comment so the employee knows what to fix.")
    claim.manager_approved_at = None
    _record(claim, user, "Rejected", "rejected", comment)


def mark_paid(claim, user):
    if user.role != "finance":
        raise RuleError("Only Finance can record payments.")
    if claim.status != "approved":
        raise RuleError("Only approved claims can be marked as paid.")
    _record(claim, user, "Marked as paid", "paid")
