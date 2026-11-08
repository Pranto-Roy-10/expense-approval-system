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
