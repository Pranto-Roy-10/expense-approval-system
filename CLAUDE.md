# CLAUDE.md

Context and rules for AI coding agents working on this repository.

## Project

Claimora is an expense-claim and approval system. Employees create claims with line items and receipts, managers review their team's claims, and Finance gives second-level approval to claims over ৳1,000 and records payments. Every status change is written to an audit trail.

- **Stack:** Python 3.13, Flask 3.1 with Jinja templates, Flask-SQLAlchemy and SQLite, plain CSS and JavaScript, GSAP and Chart.js from cdnjs/jsDelivr, XlsxWriter for exports.
- **Real authentication is out of scope:** the Get started page signs in as a sample user per role; sign-up with email and password also exists.

## Commands

```bash
python -m pip install -r requirements.txt
python run.py                      # http://127.0.0.1:5000, creates and seeds instance/expenses.db
python -m pytest -q                # every change must keep all tests passing
python -m pytest -q --cov=app      # coverage
docker compose up --build          # http://localhost:5000 (gunicorn, data in the "instance" volume)
```

To reset local data, delete `instance/expenses.db`; with Docker, `docker compose down -v`.

## Where things live

| Path | What it does |
|---|---|
| `app/rules.py` | Every business rule and status change. Writes the audit entry. No HTTP code. |
| `app/models.py` | `User`, `Claim`, `LineItem`, `AuditEntry`; categories and fixed currency rates. |
| `app/claims.py` | Create, edit, delete, submit, approve, reject, pay, receipt download. |
| `app/routes.py` | Landing page, role workspaces, Finance dashboard, exports, profile. |
| `app/auth.py` | Sign-in, sign-up, sign-out, CSRF check, `login_required(*roles)`. |
| `app/dashboard.py`, `app/export.py` | Dashboard figures; branded Excel workbook. |
| `app/seed.py` | Sample team and claims, pushed through the real rules. |
| `app/templates/`, `app/static/` | Jinja pages; `landing.css` (tokens), `app.css`, `lp.css`; `site.js`, `forms.js`, `app.js`, `dashboard.js`, `landing.js`. |
| `tests/` | `test_rules.py` (one group per business rule), `test_flows.py` (HTTP journeys, end-to-end lifecycle), `test_edge_cases.py` (bad input and refused actions), `test_seed.py`. Coverage is 100%; keep it there. |

## Business rules (enforce on the server, never only in the UI)

1. A claim has one or more line items, each with date, category, description, amount and currency.
2. Categories: Travel, Meals, Office Supplies, Software, Other.
3. A Meals line over ৳50 (after conversion) needs a note.
4. A claim total over ৳1,000 needs Finance approval after the manager's approval.
5. Nobody can approve or reject their own claim.
6. Every status change records who, what, when and the comment.

Statuses: Draft → Submitted → Approved → Paid, and Rejected back to the employee, who can edit and resubmit. Fixed rates: 1 USD = ৳122, 1 EUR = ৳132; all totals and thresholds use Taka.

## Rules for changes

- **All status changes go through `app/rules.py`.** Routes stay thin; never change `claim.status` anywhere else.
- **Every new rule or bug fix gets a test that fails without it.** Business rules belong in `tests/test_rules.py`; full journeys in `tests/test_flows.py`.
- **Every POST form includes `{{ csrf() }}`.** Every page checks the user's role with `login_required`.
- **Never trust form input:** validate on the server, cap text lengths, and write exported text as text (no spreadsheet formulas).
- **Money:** store amounts as `Numeric(12, 2)` in their own currency; convert with `LineItem.base_amount`; show with the `taka` filter (South Asian grouping, e.g. ৳ 1,23,650.00).
- **No secrets in the repository.** `.env` is git-ignored; `.env.example` lists the settings with no real values.
- **Keep it small:** reuse existing helpers (`Claim.entered`, `Claim.main_category`, the `metric`, `badge` and `empty` macros) before adding new ones, and leave no unused code.

## Design rules

- Follow the "Ink & Saffron" tokens in `app/static/css/landing.css`; never hard-code colours in templates. Every colour needs a light and a dark value.
- Open Sans for text, light headings with bold key words; IBM Plex Mono for claim codes and amounts.
- Every page uses the landing page's design language, including pages after sign-in.
- Keep the screen-width font scaling for large monitors in `landing.css` as it is.
- Phones: no sideways page scroll, every card visible, tables keep all columns and scroll inside themselves.
- Motion with GSAP only, short, never delaying an action, and reduced to fades under `prefers-reduced-motion`.
- Messages after an action are toasts; confirmations use the themed dialog in `base.html` (`data-confirm-*` attributes), never the browser's `confirm()`.
- Copy is production-ready: no AI, "demo" or placeholder wording anywhere in the app.

## Working with the owner

- Do not commit, push or create branches; the owner does this. Suggest a branch name and commit messages instead.
- Commands for the owner must work in Windows PowerShell 5.1: chain with `;` and `if ($?) { }`, never `&&`.
- The assessment brief (PDF) stays outside the repository.
