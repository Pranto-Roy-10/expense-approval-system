"""Numbers for the Finance dashboard. Everything is in base currency (BDT) unless noted."""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from .models import CATEGORIES, AuditEntry, Claim

AGING = (("0–7 days", 0, 7), ("8–14 days", 8, 14), ("15–30 days", 15, 30), ("Over 30 days", 31, None))
ZERO = Decimal(0)


def _when(claim, status, pick=max):
    """When the claim last (or first) moved into a status, from its audit trail."""
    times = [a.created_at for a in claim.audit if a.to_status == status]
    return pick(times) if times else None


def _month(d):
    return d.year * 12 + d.month - 1


def _change(now, before):
    """Percent change, or None when there is nothing to compare against."""
    return None if not before else float((now - before) / before * 100)


def finance_overview(today=None):
    today = today or date.today()
    now = datetime.combine(today, datetime.max.time())
    this_month, last_month = _month(today), _month(today) - 1
    claims = Claim.query.filter(Claim.status != "draft").order_by(Claim.updated_at.desc()).all()
    spent = [c for c in claims if c.status in ("approved", "paid")]
    days = lambda since: (now - since).days if since else 0

    # ---- Headline figures ----
    paid_in, approved_in = defaultdict(Decimal), defaultdict(Decimal)
    waits = []
    for c in spent:
        approved_at = _when(c, "approved")
        if approved_at:
            approved_in[_month(approved_at)] += c.total
        if c.status == "paid":
            paid_at, submitted_at = _when(c, "paid"), _when(c, "submitted", min)
            paid_in[_month(paid_at)] += c.total
            if submitted_at:
                waits.append((paid_at - submitted_at).total_seconds() / 86400)

    payables = sorted((c for c in claims if c.status == "approved"), key=lambda c: _when(c, "approved"))
    signoff = sorted((c for c in claims if c.awaiting_finance), key=lambda c: c.manager_approved_at)
    decisions = AuditEntry.query.filter(AuditEntry.to_status.in_(("approved", "rejected"))).all()
    rejected = sum(1 for a in decisions if a.to_status == "rejected")

    kpis = {
        "paid_month": paid_in[this_month], "paid_change": _change(paid_in[this_month], paid_in[last_month]),
        "approved_month": approved_in[this_month],
        "approved_change": _change(approved_in[this_month], approved_in[last_month]),
        "payable": sum((c.total for c in payables), ZERO), "payable_count": len(payables),
        "payable_oldest": days(_when(payables[0], "approved")) if payables else None,
        "signoff": sum((c.total for c in signoff), ZERO), "signoff_count": len(signoff),
        "signoff_oldest": days(signoff[0].manager_approved_at) if signoff else None,
        "avg_days": sum(waits) / len(waits) if waits else None, "paid_count": len(waits),
        "reject_rate": rejected / len(decisions) * 100 if decisions else None, "decisions": len(decisions),
    }

    # ---- Spend by expense month and category (last six months, empty months kept) ----
    months = list(range(this_month - 5, this_month + 1))
    stacked = {cat: [ZERO] * 6 for cat in CATEGORIES}
    by_category, by_currency = defaultdict(Decimal), {}
    for c in spent:
        for item in c.items:
            by_category[item.category] += item.base_amount
            cur = by_currency.setdefault(item.currency, {"code": item.currency, "original": ZERO, "base": ZERO})
            cur["original"] += item.amount
            cur["base"] += item.base_amount
            slot = _month(item.date) - months[0]
            if 0 <= slot < 6:
                stacked[item.category][slot] += item.base_amount
    spend = sum(by_category.values(), ZERO)

    # ---- Payables aging: days since final approval ----
    aging = [{"label": label, "count": 0, "total": ZERO} for label, _, _ in AGING]
    for c in payables:
        age = days(_when(c, "approved"))
        bucket = next(i for i, (_, lo, hi) in enumerate(AGING) if age >= lo and (hi is None or age <= hi))
        aging[bucket]["count"] += 1
        aging[bucket]["total"] += c.total

    # ---- Pipeline, claimants, attention list ----
    pipeline = [
        ("With managers", [c for c in claims if c.status == "submitted" and not c.awaiting_finance]),
        ("Awaiting Finance", signoff),
        ("Ready to pay", payables),
        ("Paid", [c for c in claims if c.status == "paid"]),
        ("Rejected", [c for c in claims if c.status == "rejected"]),
    ]
    pipeline = [{"label": label, "count": len(group), "total": sum((c.total for c in group), ZERO)}
                for label, group in pipeline]

    owners = {}
    for c in spent:
        o = owners.setdefault(c.owner_id, {"user": c.owner, "count": 0, "total": ZERO})
        o["count"] += 1
        o["total"] += c.total

    attention = [{"claim": c, "kind": "Sign-off", "age": days(c.manager_approved_at)} for c in signoff]
    attention += [{"claim": c, "kind": "Payment", "age": days(_when(c, "approved"))} for c in payables]
    attention.sort(key=lambda a: -a["age"])

    ledger = [{
        "claim": c,
        "category": max(c.items, key=lambda i: i.base_amount).category if c.items else "",
        "submitted": _when(c, "submitted", min),
    } for c in claims]

    chart = {
        "months": [date(m // 12, m % 12 + 1, 1).strftime("%b %Y") for m in months],
        "stacked": [{"label": cat, "slot": i, "data": [float(v) for v in stacked[cat]]}
                    for i, cat in enumerate(CATEGORIES) if any(stacked[cat])],
        "categories": [{"label": cat, "slot": CATEGORIES.index(cat), "total": float(v)}
                       for cat, v in sorted(by_category.items(), key=lambda kv: -kv[1])],
        "aging": [{"label": a["label"], "total": float(a["total"]), "count": a["count"]} for a in aging],
    }
    return {
        "today": today, "kpis": kpis, "chart": chart, "spend": spend, "aging": aging, "pipeline": pipeline,
        "categories": sorted(by_category.items(), key=lambda kv: -kv[1]),
        "currencies": sorted(by_currency.values(), key=lambda c: -c["base"]),
        "claimants": sorted(owners.values(), key=lambda o: -o["total"])[:5],
        "attention": attention[:6], "ledger": ledger,
        "owners": sorted({c.owner.name for c in claims}),
    }
