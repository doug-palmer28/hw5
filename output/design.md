# Agent Desk: Dashboard Design

The Campus Customs Agent Desk (`frontend/`, React + Vite + TypeScript) is where Doug picks a ticket, watches the agent team work it, approves anything that costs money, and sees the checking balance change. This file records the design choices.

## Design system: Yale Bulldog Blue

The look follows **yalebulldogblue.com**, using values taken from the store's own stylesheet, the same as `output/desk_tickets.html`. It replaces the Bauhaus style used elsewhere in the coursework.

| Token | Value | Used for |
|---|---|---|
| Bulldog navy | `#00366b` | Brand, titles, primary buttons, ticket numbers, "resolved" |
| Navy hover / secondary | `#1a4a7a` / `#335e89` | Button hover; Customer Service's color |
| Yale blue | `#286dc0` | Facilities' color, the Boss's tie |
| Text | `#1d1d1d` | Body text; the Boss's color |
| Panels | `#ffffff`, `#f4f4f4`, `#f6f6f6` | Cards, code chips, alternating feed rows |
| Cream | `#f5f3ed` | Footer, the shop-floor "ground", message drafts |
| Coral | `#f04f36` | **Only** for things that need Doug: approvals, money leaving, refusals |
| Teal | `#046e82` | Accounting's color, "see details" links |

- **Type:** Open Sans (Arial fallback). Headings are uppercase and bold, like the store's.
- **Shape:** square corners everywhere (the store's buttons and cards have radius 0), with thin `rgba(0,0,0,.15)` borders.
- **Store touches:** a navy announcement bar across the top (shop date, model, live status), a white masthead with a small letter-spaced wordmark over a big navy title, and outline buttons that fill on hover.

Color is used sparingly, as on the store site. Navy carries the brand; each agent gets one accent color; coral is saved for "you need to act" and "money went out", so those moments stand out.

## Layout

```
┌──────────────── navy announcement bar: shop date · model · ● Live ────────────────┐
│ CAMPUS CUSTOMS / AGENT DESK                     [ CHECKING $3,400.00 ▬▬▬ ] [RESET] │
├───────────────┬──────────────────────────────────────────────┬────────────────────┤
│ TICKETS       │ Ticket header: number · subject · quote ·    │ YOUR APPROVALS     │
│ 101 Bulldog…  │ facts · status · [RUN AGENT TEAM] or stamp   │  (little Doug)     │
│ 102 Rent due  ├──────────────────────────────────────────────┤  request cards     │
│ 103 Hoodies   │ THE FLOOR: 5 agents with speech bubbles      │  approve / reject  │
│               ├──────────────────────────────────────────────┤ LEDGER (money out) │
│               │ LIVE FEED (scrolls inside its own box)       │ DRAFTS (not sent)  │
│               ├──────────────────────────────────────────────┤                    │
│               │ WHAT EACH AGENT DID: 5 summary cards         │                    │
└───────────────┴──────────────────────────────────────────────┴────────────────────┘
```

- **Left, the queue:** every ticket as a card with a navy number tile (the same tile as `desk_tickets.html`), its type, subject, requester, and a status pill.
- **Center, the story:** the selected ticket at the top, then the agents, what they're saying live, and what each one ended up doing.
- **Right, Doug's column:** everything that needs or reflects a human decision (approvals, the money ledger, drafted messages). It's sticky, so the approve button stays on screen while the feed scrolls.
- **Top right, the money:** the checking balance is always visible, no matter which ticket is selected.
- Below 1280px the right column moves under the main area; below 820px everything stacks into one column.

## The agents: little people in Yale attire

Each agent is a small person built **entirely in HTML/CSS** (`components/AgentFigure.tsx`, `figures.css`), following the AGENTS.md rule that creatures and pictures are built in HTML. Everyone wears Yale navy or blue with a serif white **Y**, and each role adds props so you can tell who's who at a glance. They also have Yale-landmark first names.

| Agent | Name | Color | Outfit and props |
|---|---|---|---|
| Boss | Eli | `#1d1d1d` | Dark navy blazer, white shirt, **Yale-blue tie**, pocket square, distinguished grey hair |
| Inventory | Sterling | `#00366b` | **Yale baseball cap**, navy hoodie with drawstrings, **carrying a cardboard stock box** |
| Accounting | Penny | `#046e82` | **Green accountant's visor**, round **glasses**, teal sweater vest with a white collar, **calculator** in hand |
| Facilities | Harkness | `#286dc0` | **White hard hat with a navy Y**, Yale-blue work shirt, **brown tool belt with a pouch and a wrench** |
| Customer Service | Mory | `#335e89` | **Headset with a mic**, Yale polo with a white collar, coral **"HI!" name tag** |
| You (Doug) | — | coral | Navy **YALE hoodie**. Stands at the top of the approval panel |

The team has a range of skin tones and hair colors so it looks like a real campus staff.

**How a figure shows its state:**
- **Idle** ("Off the clock"): greyed out and faded, so you can see at a glance who isn't on this ticket. This matches the Problem 6 plan, where not every agent is needed for every ticket.
- **Working:** the figure bobs and waves one arm (the inventory agent holds the box steady), the speech bubble gets a glow in the role's color, the current tool name shows as a chip in the bubble, and animated typing dots appear. The status under the name plate turns green: "Working…".
- **Done:** full color, with a navy ✓ badge on the shoulder.
- **Failed:** a coral "!" badge, and the bubble says what went wrong.
- Motion turns off for people who have "reduce motion" set.

**Name plates** are solid blocks in each agent's role color, with the job title in uppercase and the name below, like a desk nameplate. Each agent's color is reused everywhere that agent appears: the bubble's top border, its feed rows, and its summary card. That way you can follow one agent through the whole page.

## Showing the work live

- **Speech bubbles** (the floor): what each agent is doing right now. Workers start with *"Boss asked: …"* (the exact instruction the boss gave them), then switch to their own words or *"Calling `get_lease`…"*, and end with their summary. The boss's bubble says who it's delegating to: *"Asking Facilities: verify the rent notice…"*.
- **Live feed:** the whole conversation in order, with one row per event and a left stripe in the agent's color. Tool calls show as monospace chips. Each finished loop has a "N tool calls: see arguments and results" link that opens the exact arguments and results, so nothing is hidden. Human decisions and payments get a pale coral background. Each new run starts with a divider ("AGENT TEAM STARTED", "FOLLOW-UP RUN STARTED…"). The feed scrolls **inside its own box**, so new events never pull the page away from the floor.
- **Where the live updates come from:** the backend now logs an `agent_step` event every time an agent decides to call tools, so the board shows tool calls as they happen, not only when an agent finishes. The board polls `/events` every 0.9s while agents work and every 2.5s when idle.

## What each agent did (summary cards)

There are five cards, one per agent, each with a role-colored top border and a small face:
- the agent's last summary (or the boss's report),
- up to three **facts with the tool they came from** (from the `WorkerReport`),
- **tool chips with counts** (`delegate ×2`, `get_lease`), so you can see which tools each agent used,
- agents not used on the ticket get a dashed, faded card: *"Not called on this ticket."*

## Approvals: making the human decide

- The panel header shows **little Doug** in a Yale hoodie. When something is waiting, the panel gets a **coral top border, a coral count badge, and a soft coral glow**, and Doug starts bobbing.
- Each request card shows: **Payment** or **Price override**, the amount in large type, what it is ("Rent on lease #1", "Vendor invoice #501", or "8 × CC-HOOD-NAVY (M) at $X each"), who asked and why, and the **effect before you click**: *"Checking goes $3,400.00 → $1,000.00"*. If cash is short it says, in coral, that the payment will be refused.
- Buttons: **Approve & pay** (navy, filled) and **Reject** (outline). There's an optional note field. "Approving as Doug" can be edited and is remembered.
- The ticket card in the list shows a coral **"Needs you"** pill, so you know which ticket is waiting even from the list.
- Requests for the ticket you're looking at come first and have a coral outline.

## Cash: watching money go out the door

- **The balance card** (top right): label "CHECKING", the balance in large navy type, a thin bar showing what's left of the starting balance, and "Paid out / Waiting" totals.
- **When a payment goes through:** the number **counts down** to the new balance and turns **coral** while it moves, a coral **"−$2,400.00"** tag drops out of the corner, and the bar shrinks and flashes coral. Afterwards everything settles back to navy. If the browser tab is in the background, the number still lands on the right value.
- **Ledger** (right column): one line per payment, "Ticket 102 · approved by Doug −$2,400.00". Refused payments show "Refused" in coral.
- A toast confirms it: *"Paid $2,400.00. Checking is now $1,000.00."*

## Resolved tickets

- When the boss closes a ticket, the run button is replaced by a **rubber stamp, "RESOLVED ✓"**: a navy outline, tilted a few degrees, that thumps into place with a quick scale-down animation.
- In the list, the ticket's number tile turns light grey with navy text, a navy ✓ badge appears in the corner, and the pill becomes a solid navy **RESOLVED**.
- The ticket count at the top of the list updates ("2 open · 1 resolved").

## Other choices

- **Drafts** show on cream "paper" with a coral **"DRAFT · NOT SENT"** stamp, a constant reminder that nothing leaves the simulation.
- **Reset shop** is an outline button in the masthead. It asks for confirmation and is disabled while agents are working. After a reset, the board only shows events since that reset, so each "shop day" starts clean. The audit trail itself keeps everything.
- **Run button states:** "Run agent team" → "Team at work…" on this ticket → "Team busy" on other tickets. The backend runs one ticket at a time, because every ticket draws on the same checking account.
- **Status pills:** Open (grey outline), In progress (navy outline), **Needs you** (coral fill), Waiting on vendor (teal outline), **Resolved** (navy fill).
- **Connection status:** a green pulsing dot in the announcement bar ("Live" / "Agents working"). If the backend is down, the dot turns coral and a banner says how to start uvicorn.
- **Toasts** (bottom right, near-black with a colored edge) confirm runs started and finished, payments, and errors.
- **Accessibility:** buttons have clear focus outlines, status changes use `aria-live`, the figures are `aria-hidden` (the name plates carry the text), and motion respects "reduce motion".

## Routes the board calls

| Route | Where it's used |
|---|---|
| `GET /tickets` | Ticket list, open/resolved counts, resolved stamps |
| `GET /tickets/{id}` | Ticket header details (quote, SKU, invoice/lease) and drafts |
| `POST /tickets/{id}/run` | **Run agent team** button |
| `GET /runs` | Which ticket the team is on; disables run and reset while busy; "last run" line |
| `GET /runs/{run_id}` | Follows the run you started until it finishes, then shows a toast |
| `GET /events?after=N` | Speech bubbles, live feed, summary cards, ledger |
| `GET /approvals?status=pending` | Approval panel and "Needs you" pills |
| `POST /approvals/{id}` | **Approve & pay** / **Reject** |
| `GET /balance` | Balance card ("Waiting" = requests in flight) |
| `POST /reset` | **Reset shop** |
