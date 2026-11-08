"""Unit tests: one group per business rule in section 4.2 of the brief."""
from datetime import date
from decimal import Decimal

import pytest

from app import rules
from app.extensions import db
from app.models import Claim, LineItem, User
from app.rules import RuleError


def item(amount="100", category="Travel", currency="BDT", note=None, **kw):
    return LineItem(date=kw.get("day", date(2026, 11, 1)), category=category, description=kw.get("description", "Taxi"),
                    amount=Decimal(amount), currency=currency, note=note)


def make_claim(owner_id, *items, status="draft"):
    claim = Claim(owner_id=owner_id, title="Trip", status=status, items=list(items) or [item()])
    db.session.add(claim)
    db.session.flush()
    return claim


def user(team, key):
    return db.session.get(User, team[key])


# ---------- Line items ----------

def test_claim_needs_at_least_one_line_item():
    with pytest.raises(RuleError, match="at least one line item"):
        rules.validate_items([])


@pytest.mark.parametrize("field, value, message", [
    ("description", "  ", "description"),
    ("amount", Decimal("0"), "more than zero"),
    ("amount", Decimal("-5"), "more than zero"),
    ("amount", None, "more than zero"),
    ("date", None, "valid date"),
    ("currency", "GBP", "currency"),
])
def test_line_item_needs_every_field(field, value, message):
    line = item()
    setattr(line, field, value)
    with pytest.raises(RuleError, match=message):
        rules.validate_items([line])


def test_complete_line_item_passes():
    rules.validate_items([item(), item("50.00", "Meals")])


# ---------- Categories ----------

@pytest.mark.parametrize("category", ["Travel", "Meals", "Office Supplies", "Software", "Other"])
def test_allowed_categories(category):
    rules.validate_items([item("10", category)])


@pytest.mark.parametrize("category", ["Entertainment", "", "meals"])
def test_other_categories_are_rejected(category):
    with pytest.raises(RuleError, match="category"):
        rules.validate_items([item("10", category)])


# ---------- Meal limit ----------

def test_meal_over_50_needs_note():
    with pytest.raises(RuleError, match="need a note"):
        rules.validate_items([item("50.01", "Meals")])


def test_meal_over_50_with_note_passes():
    rules.validate_items([item("620", "Meals", note="Client lunch, 3 people")])


def test_meal_of_exactly_50_needs_no_note():
    rules.validate_items([item("50", "Meals")])


def test_meal_limit_uses_converted_amount():
    # 1 USD is ৳122, so a $1 meal is over the ৳50 limit
    with pytest.raises(RuleError, match="need a note"):
        rules.validate_items([item("1", "Meals", currency="USD")])


def test_blank_note_does_not_count():
    with pytest.raises(RuleError, match="need a note"):
        rules.validate_items([item("80", "Meals", note="   ")])


def test_meal_limit_does_not_apply_to_other_categories():
    rules.validate_items([item("5000", "Travel")])


def test_submit_enforces_line_rules(team):
    claim = make_claim(team["employee"], item("80", "Meals"))
    with pytest.raises(RuleError, match="need a note"):
        rules.submit(claim, user(team, "employee"))
    assert claim.status == "draft"


# ---------- Two-level approval ----------

def submitted(team, amount):
    claim = make_claim(team["employee"], item(amount))
    rules.submit(claim, user(team, "employee"))
    return claim


def test_claim_up_to_1000_needs_only_the_manager(team):
    claim = submitted(team, "1000")
    rules.approve(claim, user(team, "manager"))
    assert claim.status == "approved"


def test_claim_over_1000_goes_to_finance_after_manager(team):
    claim = submitted(team, "1000.01")
    rules.approve(claim, user(team, "manager"))
    assert claim.status == "submitted" and claim.awaiting_finance
    rules.approve(claim, user(team, "finance"))
    assert claim.status == "approved"


def test_threshold_uses_total_of_all_lines(team):
    claim = make_claim(team["employee"], item("600"), item("500"))
    rules.submit(claim, user(team, "employee"))
    rules.approve(claim, user(team, "manager"))
    assert claim.awaiting_finance


def test_finance_cannot_approve_before_manager(team):
    claim = submitted(team, "5000")
    with pytest.raises(RuleError, match="isn't waiting for your review"):
        rules.approve(claim, user(team, "finance"))


def test_manager_cannot_give_the_finance_approval(team):
    claim = submitted(team, "5000")
    rules.approve(claim, user(team, "manager"))
    with pytest.raises(RuleError, match="isn't waiting for your review"):
        rules.approve(claim, user(team, "manager"))


def test_only_the_employees_own_manager_reviews(team):
    claim = submitted(team, "200")
    with pytest.raises(RuleError, match="isn't waiting for your review"):
        rules.approve(claim, user(team, "other_manager"))


def test_drafts_cannot_be_approved(team):
    claim = make_claim(team["employee"])
    with pytest.raises(RuleError):
        rules.approve(claim, user(team, "manager"))


# ---------- No self-approval ----------

def test_manager_cannot_approve_own_claim(team):
    # Rumana is a manager who reports to Tanvir; she still can't approve her own claim
    claim = make_claim(team["other_manager"], item("200"))
    rules.submit(claim, user(team, "other_manager"))
    with pytest.raises(RuleError, match="your own claim"):
        rules.approve(claim, user(team, "other_manager"))
    rules.approve(claim, user(team, "manager"))
    assert claim.status == "approved"


def test_finance_cannot_approve_own_claim(team):
    finance = user(team, "finance")
    finance.manager_id = team["manager"]
    claim = make_claim(finance.id, item("4000"))
    rules.submit(claim, finance)
    rules.approve(claim, user(team, "manager"))
    with pytest.raises(RuleError, match="your own claim"):
        rules.approve(claim, finance)


def test_cannot_reject_own_claim(team):
    claim = make_claim(team["other_manager"], item("200"))
    rules.submit(claim, user(team, "other_manager"))
    with pytest.raises(RuleError, match="your own claim"):
        rules.reject(claim, user(team, "other_manager"), "no")


# ---------- Reject and resubmit ----------

def test_reject_needs_a_comment(team):
    claim = submitted(team, "200")
    with pytest.raises(RuleError, match="comment"):
        rules.reject(claim, user(team, "manager"), "   ")
    assert claim.status == "submitted"


def test_rejected_claim_can_be_resubmitted(team):
    claim = submitted(team, "5000")
    rules.approve(claim, user(team, "manager"))
    rules.reject(claim, user(team, "finance"), "Hotel receipt missing")
    assert claim.status == "rejected" and not claim.awaiting_finance
    rules.submit(claim, user(team, "employee"))
    assert claim.status == "submitted" and claim.audit[-1].action == "Resubmitted"
    # it starts again at the manager, not Finance
    assert rules.can_review(claim, user(team, "manager"))


def test_submitted_claim_is_locked(team):
    claim = submitted(team, "200")
    assert not claim.editable
    with pytest.raises(RuleError, match="draft or rejected"):
        rules.submit(claim, user(team, "employee"))


def test_only_owner_can_submit(team):
    claim = make_claim(team["employee"])
    with pytest.raises(RuleError, match="created this claim"):
        rules.submit(claim, user(team, "teammate"))


def test_employee_without_manager_cannot_submit(team):
    loner = User(name="New Hire", email="new@example.com", role="employee")
    db.session.add(loner)
    db.session.flush()
    with pytest.raises(RuleError, match="manager assigned"):
        rules.submit(make_claim(loner.id), loner)


# ---------- Payment ----------

def test_finance_marks_approved_claim_paid(team):
    claim = submitted(team, "200")
    rules.approve(claim, user(team, "manager"))
    rules.mark_paid(claim, user(team, "finance"))
    assert claim.status == "paid"


def test_only_approved_claims_can_be_paid(team):
    claim = submitted(team, "200")
    with pytest.raises(RuleError, match="approved claims"):
        rules.mark_paid(claim, user(team, "finance"))


def test_only_finance_can_pay(team):
    claim = submitted(team, "200")
    rules.approve(claim, user(team, "manager"))
    with pytest.raises(RuleError, match="Only Finance"):
        rules.mark_paid(claim, user(team, "manager"))


# ---------- Audit trail ----------

def test_every_status_change_records_who_what_when_and_comment(team):
    claim = submitted(team, "5000")
    rules.approve(claim, user(team, "manager"), "Fine by me")
    rules.approve(claim, user(team, "finance"))
    rules.mark_paid(claim, user(team, "finance"))
    db.session.commit()
    trail = list(reversed(claim.audit))  # oldest first
    assert [(e.actor.name, e.from_status, e.to_status) for e in trail] == [
        ("Nusrat Jahan", "draft", "submitted"),
        ("Tanvir Ahmed", "submitted", "submitted"),
        ("Farhana Islam", "submitted", "approved"),
        ("Farhana Islam", "approved", "paid"),
    ]
    assert trail[1].comment == "Fine by me" and trail[1].action.startswith("Approved by manager")
    assert all(e.created_at is not None for e in trail)


def test_failed_change_records_nothing(team):
    claim = submitted(team, "200")
    before = len(claim.audit)
    with pytest.raises(RuleError):
        rules.reject(claim, user(team, "manager"), "")
    assert len(claim.audit) == before
