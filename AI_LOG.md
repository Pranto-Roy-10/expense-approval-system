# AI Log

The tools I used, the key prompts, where the AI was wrong and how I caught it, and what I wrote by hand.

## Tools used

| Tool | What I used it for |
|---|---|
| **Claude Code** (Claude desktop app, Code tab) | Main coding agent: planning, Flask back end, templates, CSS and JavaScript, tests, Docker, README. It also ran the app in a headless browser to click through every page and take the README screenshots. |
| **ui-ux-pro-max skill** (for Claude Code) | Design direction for the landing page, workspaces, new-claim form and dashboard: palette, type, spacing and layout rules. |
| **Dashboard skill** (for Claude Code) | Structure of the Finance spend dashboard: KPI cards, charts and the claims ledger. |
| **ponytail skill** (for Claude Code) | Keeps changes small, and runs full-repository audits (`/ponytail-audit`) that report bugs, security risks and dead code in plain English. |
| **GitHub Copilot coding agent** | Fixed the failing CI run on pull request #4. |
| **GitHub Actions, pytest, Docker** | Check the AI's work: tests on every push, and a one-command run from a clean copy. |

## Key prompts

These are the prompts that shaped the project most, rewritten here in clear English. The originals were shorter and more casual.

### 1. Redesign the signed-in pages

> Use the dashboard skill to build the Finance dashboard and a profile page for every role. Use /ui-ux-pro-max to redesign the workspaces so they look professional rather than generated. Add an animation beside the sign-in form, and a left sidebar for navigation.

**What it changed:** the first version worked but looked plain. This prompt produced the sidebar app shell, the profile pages for each role and the first Finance dashboard.

### 2. Redesign the new-claim form

> The new-claim page does not look professional. Use /ui-ux-pro-max to redesign it: one card per expense line, a running total in Taka, and a summary panel that shows the receipts attached, who reviews the claim, whether Finance sign-off is needed, and a checklist of what is still missing before I can submit.

**What it changed:** the form now shows the claim total live, including USD and EUR converted at the company rates, and says before submitting whether the claim will go to Finance. Mistakes are visible while typing instead of only after the page reloads.

### 3. Make the Finance dashboard fill the screen with useful work

> The dashboard does not look professional and leaves empty space. Rebuild it with the dashboard skill so every panel has a job: spend by month and category, money waiting for sign-off and payment, how long payments wait, and a list of tasks Finance should do next.

**What it changed:** the dashboard gained KPI cards, a monthly stacked chart, a payables-aging panel, a "needs attention" task list and a searchable, sortable claims ledger with an Excel export of exactly the rows on screen.

### 4. Show messages as toast notifications

> The notifications that appear after an action should be toast notifications with smooth animations.

**What it changed:** messages such as "CLM-0028 submitted for review" slide in at the top right (at the bottom on phones), count down with a timer bar, pause while the pointer is over them, and slide out on their own or with a close button. Error messages stay longer than success messages.

### 5. Replace the browser's confirm box for payments

> Replace the native browser confirmation dialog with a custom confirmation modal matching Claimora's theme. Show the employee name and payment amount, with "Cancel" and "Confirm payment" buttons. After the payment is successfully recorded, show a success toast notification.

**What it changed:** "Mark as paid" now opens a themed dialog with the employee, claim and amount, focused on Cancel so Enter cannot pay by accident. Deleting a draft uses the same dialog in red. The toast afterwards names the employee and the amount paid.

## Where the AI was wrong and how I caught it

| Area | What the AI got wrong | How I caught it | Fix |
|---|---|---|---|
| Code | Claim titles starting with `=` became live formulas in the Excel and CSV exports. | A full audit; a test export of `=HYPERLINK(...)` produced a working formula. | Exported text is always plain text, with a test. |
| Code | Two "Mark as paid" clicks at once could pay one claim twice. | The audit; proven with two database sessions. | A changed claim can't be saved again, buttons lock after one click. |
| Code | The secret key defaulted to `"dev"`; its fix then signed everyone out on each restart. | The audit, then I kept being sent back to the role page. | A fixed key in a local `.env`, never committed. |
| Working | Back after submitting, then Submit again, created a duplicate claim. | Using the app like an employee. | A one-time code per form; a re-sent form opens the existing claim. |
| Design | The meal-note checklist item was ticked on claims with no meals. | I saw a tick on a rule that didn't apply. | It now shows "(none on this claim)". |
| Design | Its font-size "fix" for my 1440p monitor broke the approved layout. | I checked both versions on my monitor and rejected them. | Kept the original scaling; fixed only the phone layout. |
| Animation | Picking a role waited for an exit animation, so every click lagged. | I noticed the delay on Get started. | The page moves on at once; the button shows it's working. |
| Animation | Header buttons slid down on every page load. | I saw it each time a page opened. | The buttons now stay in place. |

## What I wrote by hand

- **`app/models.py`: the `LineItem` and `AuditEntry` models.** The data model decides whether the business rules can be enforced at all, so I wrote it myself and fixed the problems in my first version before anything was built on top. Amounts are stored as exact decimals in the currency the employee typed, so money never picks up rounding errors and the conversion to Taka happens in one place. Each audit entry records who acted, what they did, the status before and after, the comment and the time, which is exactly what the brief asks the audit trail to show.
- **`app/routes.py` and `app/__init__.py`: the workspace route and the blueprint registration.** I edited the route so that a manager sees only their own team's claims: the queue holds what is still waiting for them, oldest first, without the claims they already passed on to Finance. I also wired up the blueprints so every page was reachable. The AI later moved the "approved this month" count into the database query during an audit.
- **Design direction:** I chose the visual direction myself: the orange "Ink & Saffron" theme and the half-decagon shape used across the pages.
- **Design decisions:** I accepted or rejected each AI design. For example, I rejected both of its font-scaling changes and asked for one export button instead of two.
- **Planning:** I broke the brief into features and decided the order in which to build them.
- **Testing by use:** I ran the app myself and reported what felt wrong. The lag, the default-ticked checklist, the duplicate claim, the logouts and the font size on my monitor were all found this way.
- **Version control:** I created every branch, staged and committed the work in small pieces, and opened and merged the pull requests on GitHub.
