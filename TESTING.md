# Testing

## How to run the tests

```bash
python -m pip install -r requirements.txt
```

```bash
python -m pytest -q
```

With coverage:

```bash
python -m pytest -q --cov=app --cov-report=term
```

The tests use an in-memory database, so they never touch real data. GitHub Actions runs them on every push.

## Coverage

**100%**, with 97 tests passing. Every business rule in the brief has its own unit tests in `tests/test_rules.py`, and `test_full_claim_lifecycle` takes one claim through every status: submitted, rejected, resubmitted, approved by the manager and Finance, and paid.

## Edge cases tested

**Amounts and limits**
- A Meals line of exactly ৳50 needs no note; ৳50.01 does.
- The meal limit uses the converted amount: a $1 meal is ৳122, so it needs a note.
- A note of only spaces does not count.
- A claim of exactly ৳1,000 needs only the manager; ৳1,000.01 also needs Finance.
- The ৳1,000 threshold uses the total of all lines, not a single line.
- Zero, negative, missing or unreadable amounts are refused, as are a missing title or description, an unreadable date, an unknown currency and unknown categories.

**Who can do what**
- Nobody can approve or reject their own claim.
- Only the employee's own manager can review; Finance cannot approve before the manager.
- Only approved claims can be paid, and only by Finance.
- A submitted claim is locked, even against requests sent directly.
- Other people cannot open someone else's claim, and drafts stay private.
- Pages need sign-in, and every form without a valid security token is refused.

**Rejection and resubmission**
- A rejection needs a comment; a blank one is refused.
- A rejected claim can be edited and resubmitted, and goes back to the manager.

**Data safety**
- A failed action writes nothing to the audit trail.
- Two payments of the same claim at the same moment cannot both be saved.
- Sending the same new-claim form twice (for example after pressing Back) makes one claim, not two.
- A bad save on the edit page leaves the saved claim untouched.

**Receipts**
- Receipts are shown only to the owner, their manager and Finance.
- Fake or unsupported files and receipts over 5 MB are refused.
- Replacing or removing a receipt deletes the old file.

**Exports**
- Claim titles starting with `=` are written as plain text in Excel and CSV, never as formulas.
- The approved-claims export includes only approved and paid claims, limited to the chosen range (this month, last 3 or 12 months, or all time).
