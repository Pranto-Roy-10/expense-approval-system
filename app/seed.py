"""Sample team and claims, loaded into an empty database so every workspace has work in it.
Claims are moved through the real rules, so their history matches what the app would record."""
from datetime import datetime, timedelta
from decimal import Decimal

from . import rules
from .extensions import db
from .models import Claim, LineItem, User, utcnow

# The sample story below is written as if today were noon on 9 November 2026. On loading, every date moves
# by the same amount so the story always ends "now": this month's figures and the last six months stay filled.
STORY_NOW = datetime(2026, 11, 9, 12)


def _user(name, email, role, title, manager=None, sample=False):
    user = User(name=name, email=email, role=role, title=title, manager=manager, is_sample=sample)
    db.session.add(user)
    return user


def _claim(owner, title, items, started, shift):
    claim = Claim(owner=owner, title=title, created_at=started, updated_at=started,
                  items=[LineItem(date=(datetime.fromisoformat(d) + shift).date(), category=c, description=desc,
                                  amount=Decimal(a), currency=cur, note=note)
                         for d, c, desc, a, cur, note in items])
    rules.record_created(claim, owner)
    return claim


def _steps(claim, started, *steps, gap=5):
    """Apply status changes `gap` hours apart and date their audit entries to match."""
    for n, step in enumerate(steps, 1):
        step(claim)
        claim.audit[-1].created_at = started + timedelta(hours=gap * n)
        claim.updated_at = claim.audit[-1].created_at
    claim.audit[0].created_at = started


def seed_if_empty():
    if User.query.first():
        return
    manager = _user("Tanvir Ahmed", "tanvir.ahmed@claimora.app", "manager", "Engineering Manager", sample=True)
    finance = _user("Farhana Islam", "farhana.islam@claimora.app", "finance", "Finance Lead", sample=True)
    nusrat = _user("Nusrat Jahan", "nusrat.jahan@claimora.app", "employee", "Software Engineer", manager, sample=True)
    rafiq = _user("Rafiq Hasan", "rafiq.hasan@claimora.app", "employee", "QA Engineer", manager)
    sadia = _user("Sadia Rahman", "sadia.rahman@claimora.app", "employee", "Product Designer", manager)
    db.session.flush()  # ids are needed by the approval rules
    _apply(_plan(manager, finance, nusrat, rafiq, sadia), shift=utcnow() - STORY_NOW)
    db.session.commit()


def _apply(plan, shift):
    for owner, title, items, started, steps, *gap in plan:
        started += shift
        claim = _claim(owner, title, items, started, shift)
        db.session.add(claim)
        db.session.flush()
        _steps(claim, started, *steps, gap=gap[0] if gap else 5)


def _plan(manager, finance, nusrat, rafiq, sadia):
    submit = lambda c: rules.submit(c, c.owner)
    m_ok = lambda c, note=None: rules.approve(c, manager, note)
    f_ok = lambda c, note=None: rules.approve(c, finance, note)
    pay = lambda c: rules.mark_paid(c, finance)
    t = lambda day, hour=9: datetime(2026, 10, 1, hour) + timedelta(days=day - 1)

    paid = [submit, m_ok, f_ok, pay]
    return [
        # Earlier months, already paid (steps a day or so apart)
        (rafiq, "Sprint review lunch", [("2026-06-11", "Meals", "Team lunch after sprint review", "2400", "BDT", "Sprint review lunch, 8 people.")],
         datetime(2026, 6, 11, 14), paid, 26),
        (nusrat, "Laptop stand", [("2026-06-23", "Office Supplies", "Adjustable laptop stand", "1850", "BDT", None)],
         datetime(2026, 6, 23, 10), paid, 30),
        (sadia, "Prototyping plugin", [("2026-07-08", "Software", "Prototyping plugin, annual", "25", "USD", None)],
         datetime(2026, 7, 8, 11), paid, 22),
        (rafiq, "Site visit, Khulna", [
            ("2026-07-20", "Travel", "Bus, Dhaka to Khulna and back", "2200", "BDT", None),
            ("2026-07-20", "Travel", "Guest house, 2 nights", "4500", "BDT", None),
        ], datetime(2026, 7, 21, 9), paid, 34),
        (nusrat, "Cloud certification exam", [("2026-08-05", "Other", "Associate certification exam fee", "150", "USD", None)],
         datetime(2026, 8, 5, 12), paid, 28),
        (sadia, "User interview travel", [("2026-08-19", "Travel", "Ride share to interview sites", "2800", "BDT", None)],
         datetime(2026, 8, 19, 16), paid, 20),
        (rafiq, "Second monitor", [("2026-09-03", "Office Supplies", "27-inch monitor for QA station", "14500", "BDT", None)],
         datetime(2026, 9, 3, 10), paid, 40),
        (nusrat, "Client dinner, Banani", [("2026-09-17", "Meals", "Dinner with client team", "3900", "BDT", "Dinner with the client's tech leads, 5 people.")],
         datetime(2026, 9, 17, 21), paid, 24),
        (sadia, "Stock photo licence", [("2026-09-25", "Software", "Stock photo pack for campaign", "30", "EUR", None)],
         datetime(2026, 9, 25, 13), paid, 30),

        (nusrat, "Train tickets, Sylhet", [("2026-10-06", "Travel", "Return train, Dhaka to Sylhet", "1640", "BDT", None)],
         t(6), [submit, m_ok, f_ok, pay]),
        (nusrat, "Design tool licence", [("2026-10-14", "Software", "Annual design tool seat", "18", "USD", None)],
         t(14), [submit, m_ok, lambda c: f_ok(c, "Renewal is in the software budget.")]),
        (nusrat, "Taxi to airport", [("2026-10-21", "Travel", "Taxi to Hazrat Shahjalal Airport", "650", "BDT", None)],
         t(21), [submit, lambda c: rules.reject(c, manager, "Receipt missing. Please attach it and resubmit.")]),
        (nusrat, "Client workshop, Chattogram", [
            ("2026-10-28", "Travel", "Return flight", "7800", "BDT", None),
            ("2026-10-28", "Travel", "Hotel, 2 nights", "12400", "BDT", None),
            ("2026-10-29", "Meals", "Team dinner with client", "3450", "BDT", "Dinner with the client's product team, 6 people."),
        ], t(29), [submit, lambda c: m_ok(c, "Workshop costs match the client brief.")]),
        (nusrat, "Home internet, October", [("2026-10-31", "Other", "Home broadband, October", "1500", "BDT", None)],
         t(31), [submit]),
        (nusrat, "Team offsite supplies", [
            ("2026-11-03", "Office Supplies", "Sticky notes and markers", "840", "BDT", None),
            ("2026-11-03", "Office Supplies", "Printed workshop boards", "1500", "BDT", None),
        ], t(34), []),
        (rafiq, "Conference pass, BASIS SoftExpo", [
            ("2026-11-02", "Other", "Conference pass", "3500", "BDT", None),
            ("2026-11-02", "Travel", "Ride share to venue", "1000", "BDT", None),
        ], t(33), [submit]),
        (sadia, "Client lunch, Gulshan", [
            ("2026-11-01", "Meals", "Lunch with client", "620", "BDT", "Lunch with the onboarding client, 3 people."),
            ("2026-11-01", "Travel", "Ride share", "160", "BDT", None),
        ], t(32), [submit]),
        (sadia, "Usability study incentives", [("2026-11-08", "Other", "Gift cards for 4 participants", "800", "BDT", None)],
         datetime(2026, 11, 8, 20), [submit, m_ok, pay]),  # paid an hour before "now", so this month has a payment

        # Finance work: manager-approved claims over 1,000 waiting for sign-off ...
        (rafiq, "Test devices for release", [
            ("2026-11-04", "Office Supplies", "Android test phone", "18500", "BDT", None),
            ("2026-11-04", "Office Supplies", "USB-C hub and cables", "2300", "BDT", None),
        ], t(35), [submit, lambda c: m_ok(c, "Needed for the November release testing.")]),
        (sadia, "Design conference, Bangkok", [
            ("2026-11-05", "Travel", "Return flight, Dhaka to Bangkok", "210", "USD", None),
            ("2026-11-05", "Travel", "Hotel, 3 nights", "240", "USD", None),
            ("2026-11-06", "Meals", "Speaker dinner", "35", "USD", "Dinner with two speakers after the design panel."),
        ], t(36, 11), [submit, lambda c: m_ok(c, "Approved as part of the learning budget.")]),
        (rafiq, "Cloud device testing", [("2026-11-06", "Software", "Device cloud, monthly plan", "45", "USD", None)],
         t(37), [submit, m_ok]),
        # ... and approved claims waiting to be paid
        (nusrat, "Keyboard and mouse", [("2026-11-03", "Office Supplies", "Wireless keyboard and mouse", "2750", "BDT", None)],
         t(34, 14), [submit, m_ok, lambda c: f_ok(c, "Within the equipment allowance.")]),
        (rafiq, "Release night dinner", [("2026-11-05", "Meals", "Dinner for the release team", "480", "BDT", "Release night, 4 people stayed late.")],
         t(36), [submit, m_ok]),
        (sadia, "Prototype printing", [("2026-11-06", "Office Supplies", "Printed paper prototypes", "950", "BDT", None)],
         t(37, 15), [submit, m_ok]),
    ]
