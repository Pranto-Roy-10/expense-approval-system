# Design

The design direction I gave the AI, then each key screen as the AI first built it, followed by how it looks now, with the prompt that sums up how I took it from one to the other. The prompts are rewritten in clear English. The first-version screenshots come from the small previews captured while each screen was being built, enlarged to the same size as the latest ones, so their fine text is soft.

## Design direction

**"Ink & Saffron"**: a calm, paper-like finance tool. Warm off-white pages, near-black ink for text, and one saffron accent for actions and progress. It should feel trustworthy for money, not playful or AI-made.

| Role | Light | Dark | Used for |
|---|---|---|---|
| Page | `#FBFAF7` | `#0E0D0B` | Background |
| Surface | `#FFFFFF` | `#1A1815` | Cards, tables, dialogs |
| Text | `#1C1917` | `#F5F2EC` | Body and headings |
| Muted | `#57534E` | `#A8A29E` | Labels and secondary text |
| Saffron | `#F5A524` | `#F5B13D` | Buttons, progress, shapes |
| Saffron text | `#9A5200` | `#F5B13D` | Links and accents as text (4.5:1 contrast) |
| Border | `#E7E2D9` | `#2C2823` | Card and table lines |

- **Status colours:** Draft (stone), Submitted (amber), Approved (green), Rejected (rose), Paid (blue). They are the same in badges, timelines and the Excel export.
- **Typography:** Open Sans, with light headings and the key words in bold ("New **claim**"). IBM Plex Mono for claim codes and money, so numbers line up. Amounts in Taka with South Asian grouping (৳ 1,23,650.00).
- **Spacing and shape:** roomy cards, 0.75 rem corners, round "pill" buttons for main actions, soft low shadows. A faded half-decagon with an outer ring is the brand shape behind every page.
- **Components:** sidebar app shell, metric cards, tables with right-aligned mono numbers, status badges, labelled forms with errors next to the field, empty states, toasts and a themed confirmation dialog.
- **Motion:** GSAP for entrances, scroll reveals and floating cards. Short, never in the way of an action, and reduced to fades when "reduce motion" is on.
- **Light and dark:** every colour is a token with both values; the toggle remembers the choice.

## Landing page

> Make the landing page look professional, not AI-made. Use the Claimora name and an orange theme instead of blue, with a dark mode and GSAP animations. Show the real product on a phone and in a browser window, show amounts in Taka, keep the moving ticker bar, and put a faded half-decagon with an outer ring behind the content. Make the cards float smoothly.

**First landing page**

![First landing page](docs/design/landing-1-first.jpg)

**Latest landing page**

![Latest landing page](docs/design/landing-6-latest.png)

## Get started, sign in and sign up

> Build a Get started page with a sample user and a "Continue as [role]" button for each role, plus real sign-in and sign-up pages connected to the database. Give the sign-in page an animated side panel, and make all of them follow the landing page's design so they look professional, not plain.

**First Get started**

![First Get started](docs/design/get-started-1-first.jpg)

**Latest Get started**

![Latest Get started](docs/screenshots/02-get-started.png)

**First sign in**

![First sign in](docs/design/sign-in-1-first.jpg)

**Latest sign in**

![Latest sign in](docs/design/sign-in-2-latest.png)

**First sign up**

![First sign up](docs/design/signup-1-first.jpg)

**Latest sign up**

![Latest sign up](docs/design/signup-2-latest.png)

## Workspaces

> Redesign the workspace for every role so it looks professional and not AI-made, with no wasted space and no AI-looking colours. Add a left sidebar with the pages each role needs, give Finance a clear task list, and show what helps people understand their work at a glance.

**First employee workspace**

![First employee workspace](docs/design/employee-1-first.jpg)

**Latest employee workspace**

![Latest employee workspace](docs/screenshots/03-employee-workspace.png)

**First manager workspace**

![First manager workspace](docs/design/manager-1-first.jpg)

**Latest manager workspace**

![Latest manager workspace](docs/screenshots/06-manager-review-queue.png)

**First Finance workspace**

![First Finance workspace](docs/design/finance-1-first.jpg)

**Latest Finance workspace**

![Latest Finance workspace](docs/screenshots/07-finance-approvals.png)

## New claim

> Redesign the new-claim page so it looks professional and is scaled properly: one card per expense line, a large live total in Taka, and a summary that shows the receipts attached, who reviews the claim, whether Finance must sign off, and a checklist of what is still missing.

**First new claim**

![First new claim](docs/design/new-claim-1-first.jpg)

**Latest new claim**

![Latest new claim](docs/design/new-claim-4-latest.png)

## Claim detail and payment

> Make the claim page follow the landing page's design, and replace the browser's confirmation box with a themed dialog that shows the employee and amount, with Cancel and Confirm payment buttons, followed by a success toast.

**First claim detail**

![First claim detail](docs/design/claim-detail-1-first.jpg)

**Latest claim detail**

![Latest claim detail](docs/screenshots/05-claim-detail.png)

![Payment confirmation dialog](docs/design/confirm-dialog-latest.png)

## Finance dashboard

> Use the dashboard skill to build a professional Finance dashboard with proper charts and colours: spend by month and category, money waiting for sign-off and payment, how long payments wait, a list of what needs attention, and a searchable claims ledger with an Excel export.

**First dashboard**

![First dashboard](docs/design/dashboard-1-first.jpg)

**Latest dashboard**

![Latest dashboard](docs/screenshots/08-finance-dashboard.png)

## Profile

> Redesign every user's profile so it looks professional, not AI-like: no filler text, the information that helps people understand their own account and reporting line, and an option to edit it.

**First profile**

![First profile](docs/design/profile-1-first.jpg)

**Latest profile**

![Latest profile](docs/screenshots/09-profile.png)

## Notifications

> Show the messages that appear after an action as toast notifications with smooth animations, instead of a bar that pushes the page down.

**Notification first**

![Notification first](docs/design/notification-before.png)

**Notification latest**

![Notification latest](docs/design/notification-after.png)

## Phones

> Make every page work on a phone: show every card on the landing page and keep every table column, without changing the desktop design.

**Landing on a phone**

![Landing on a phone](docs/screenshots/11-mobile-landing.png)

**Workspace on a phone**

![Workspace on a phone](docs/screenshots/12-mobile-workspace.png)
