from app.models import Claim, User
from app.seed import seed_if_empty


def test_sample_data_loads_through_the_rules_and_only_once(app):
    # every sample claim goes through the real rules, so a rule change that breaks one fails here, not at start-up
    seed_if_empty()
    assert User.query.filter_by(is_sample=True).count() == 3
    assert Claim.query.count() == 24
    assert {c.status for c in Claim.query} == {"draft", "submitted", "approved", "rejected", "paid"}
    seed_if_empty()
    assert Claim.query.count() == 24


def test_sample_story_always_ends_now(app):
    # whatever day the app is first started, this month has payments and no sample event lies in the future
    from app.dashboard import finance_overview
    from app.models import utcnow
    seed_if_empty()
    assert finance_overview()["kpis"]["paid_month"] > 0
    assert max(a.created_at for c in Claim.query for a in c.audit) <= utcnow()


def test_dashboard_chart_and_cards_agree(app):
    # this month's column is the "Approved this month" card; the panel total is the sum of the six columns
    from decimal import Decimal
    from app.dashboard import finance_overview
    seed_if_empty()
    o = finance_overview()
    column = lambda i: sum((Decimal(str(s["data"][i])) for s in o["chart"]["stacked"]), Decimal(0))
    assert column(5) == o["kpis"]["approved_month"] > 0
    assert sum(column(i) for i in range(6)) == o["trend_total"]
    assert sum(Decimal(str(a["total"])) for a in o["chart"]["aging"]) == o["kpis"]["payable"]


def test_approved_exports_follow_the_chosen_date_range(app):
    import csv
    import io
    from app.models import utcnow
    seed_if_empty()
    client = app.test_client()
    with client.session_transaction() as s:
        s["user_id"] = User.query.filter_by(role="finance").first().id
    now = utcnow()
    approved = [c.entered("approved") for c in Claim.query.filter(Claim.status.in_(("approved", "paid")))]
    months_back = lambda a: (now.year - a.year) * 12 + now.month - a.month
    for key, months in (("month", 1), ("3m", 3), ("12m", 12), ("all", None), ("nonsense", None)):
        res = client.get(f"/dashboard/approved.csv?range={key}")
        rows = list(csv.reader(io.StringIO(res.data.decode("utf-8-sig"))))[1:]
        expected = sum(1 for a in approved if months is None or months_back(a) < months)
        assert len(rows) == expected, key
        assert f"claimora-approved-{key if months or key == 'all' else 'all'}-" in res.headers["Content-Disposition"]
    assert 0 < len(list(csv.reader(io.StringIO(client.get("/dashboard/approved.csv?range=month").data.decode("utf-8-sig"))))) - 1 < len(approved)
    assert client.get("/dashboard/approved.xlsx?range=3m").status_code == 200
