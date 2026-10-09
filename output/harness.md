# Harness

This file documents the harness for the Homework 5 multi-agent Campus Customs shop. A team of five Pydantic AI agents (boss, inventory, accounting, facilities, customer service), all on `gpt-6-luna`, works the shop's tickets through one MCP server. A FastAPI backend runs them, and a React board lets Doug start the team, watch it work, and approve anything that costs money.

## At a glance

```
React board (frontend/, :5173) ──HTTP──▶ FastAPI backend (backend/main.py, :8000)
                                              │  starts agent runs, records Doug's approvals
                                              ▼
                     Boss agent ──delegate──▶ Inventory · Accounting · Facilities · Customer service
                          │  (each agent sees only its slice of the tools)
                          ▼
              campus-customs MCP server (mcp_server/server.py) ──▶ data/campus_customs_new.db
                          │
       every agent loop, tool call, human decision, payment ──▶ output/audit_trail.json (append-only)
```

**Run it** (details in `README.md`): start the backend (`uvicorn main:app --reload --port 8000`, from `backend/`) and the board (`npm run dev`, from `frontend/`, at http://localhost:5173). Nothing runs until Doug presses **Run agent team**.

| Path | What it is |
|---|---|
| `mcp_server/server.py` | The only shop tools layer: 21 tools (19 for agents, 2 human-only), the simulation rules (`SIMULATION_RULES`, served as `rules://simulation`), and `--smoke` |
| `backend/` | `main.py` holds everything in numbered sections: 1 config/model, 2 audit trail, 3 MCP connection, 4 agent loop, 5 the five agents, 6 running tickets and reset, 7 FastAPI routes, 8 terminal CLI. Data types are in `models.py`, prompts in `prompts/*.md` |
| `frontend/` | React + Vite + TypeScript Agent Desk |
| `data/` | `campus_customs.db` (original, never edited) and `campus_customs_new.db` (working copy) |
| `output/` | This harness, `audit_trail.json`, `desk_tickets.html`, `resolved_tickets.json`, `resolved_board.html` (screenshots embedded), `design.md`, `mcp_smoke.json`, `github_url.txt` |
| `AI_prompts.md` | Every prompt for the project, word for word |

## Simulation rules

The full rules are `SIMULATION_RULES` at the top of `mcp_server/server.py`, appended to every agent's prompt. Agents can also read them from the MCP server as the `rules://simulation` resource. Summary:

1. **Today** is `desk.date_today`, never the real clock.
2. **Vendors ship only after they're paid**, and they take `vendors.lead_days` once paid.
3. **Every payment needs human approval** from Doug. No agent can approve one, not even the boss. `payments.approved_by` must name the human.
4. **No negative balances.** The payment tool refuses if there isn't enough cash.
5. **Money only goes out.** No income in the simulation.
6. **Reset before every full run** with **Reset shop** / `POST /reset`, or `python backend/main.py --reset` (copies the original database over the working copy).
7. **No outside contact.** No real emails, calls, or messages. Agents only talk to Doug.
8. **Don't invent data.**

## Database

- **Original:** `data/campus_customs.db` (unzipped from `data (4).zip`, left untouched)
- **Working copy:** `data/campus_customs_new.db` (a byte-for-byte copy; all future changes go here)
- **Shop date:** `2026-08-31` (from the `desk` table)

## Tables

### desk
- **Fields:** `date_today`, `notes`
- **Why it matters:** It's the shop's "today" (2026-08-31). Agents use it to tell what is due or overdue instead of using the real clock.

### inventory
- **Fields:** `sku`, `name`, `size`, `qty`, `location` (key: `sku` + `size`)
- **Why it matters:** The inventory agent checks here to see if an order can be filled from stock, and where the item is in the store.

### pricing
- **Fields:** `sku`, `unit_cost`, `list_price`
- **Why it matters:** It sets the lowest price a discount can go to (cost) and the normal price (list) for customer quotes and price-override decisions.

### vendors
- **Fields:** `id`, `name`, `specialty`, `lead_days`
- **Why it matters:** It shows who can restock or deliver each kind of item, and how many days they take. That decides the dates we promise customers.

### leases
- **Fields:** `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`
- **Why it matters:** The facilities agent reads it to check a rent notice against the real lease amount and due date.

### cash_accounts
- **Fields:** `name`, `balance`, `date`
- **Why it matters:** It is the only cash the shop has. Accounting has to check that every payment fits in the balance.

### payments
- **Fields:** `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`
- **Why it matters:** It records every payment and who approved it, so the dashboard can show which agent spent money and the boss's approval can be checked. It starts empty.

### invoices
- **Fields:** `id`, `vendor_id`, `amount`, `due_date`, `status`, `description`
- **Why it matters:** It lists the bills the shop owes vendors. Accounting pays them, and some bills are tied to customer orders.

### tickets
- **Fields:** `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`
- **Why it matters:** It's the agents' work queue. The boss reads each ticket's `type` to send it to the right agent, and the links (`sku`, `lease_id`, `invoice_id`) point to the data the agent needs.

## Open tickets

All three tickets are `open`, and all were created on the shop date (2026-08-31).

| ID | Type | Requester | Ask | Links |
|---|---|---|---|---|
| 101 | customer_order | Tauhid Zaman | 1 × Classic Bulldog Tee, size S | sku `CC-TEE-WHITE`, invoice 501 |
| 102 | rent_notice | Elm City Properties | Shop rent due in 2 days | lease 1 |
| 103 | price_override | Yale AI Club | 20 × Basic Hoodie, size M, at a bulk discount | sku `CC-HOOD-NAVY` |

### What the data says about each ticket

- **101 (tee order):** Size S of `CC-TEE-WHITE` has **0 in stock**. The ticket is linked to invoice **501**, an $840 "Rush reprint CC-TEE-WHITE S" from Bulldog Print Co (5-day lead time). That invoice was due **2026-08-28**, so it is **already overdue**. This order probably can't be filled until the reprint invoice is paid and the stock arrives. Customer service will need to tell the customer the item is delayed.
- **102 (rent):** Lease 1 (Chapel Street shop) is **$2,400**, next due **2026-09-02**. This matches the "2 days" in the email. This one goes to facilities, and accounting makes the payment.
- **103 (bulk hoodies):** Only **8 size M** are in stock (plus S 4, L 14, XL 6). That is 12 short of the 20 they asked for. The hoodie costs $22 and lists for $58, so a discount has to stay above $22. A 20-hoodie order is $1,160 at list price. A price override sounds like something the boss should approve.

### Things that connect the tickets

- **Cash is tight.** Checking has **$3,400**. Rent ($2,400) plus invoice 501 ($840) is $3,240, which would leave only **$160**. The tickets compete for the same money, so the boss has to decide what gets paid first.
- **Nothing has been paid yet.** The `payments` table is empty, and its `approved_by` field means each payment should record who approved it.
- **Two products are out of stock in some sizes:** the tee in S and the Crest Mug (`CC-MUG-CREST`, 0 left). No ticket asks for the mug yet.

## MCP server

`mcp_server/server.py` is a FastMCP server named `campus-customs`. It reads from `data/campus_customs_new.db`. Every agent gets its data through these tools. The tools never make up values. A lookup that finds nothing returns an `error` instead of a guess. Days are counted from the shop's date in `desk`, not the real clock. See `mcp_server/README.md` for setup.

### The first three tools (Problem 3)

In Problem 5, `get_invoice` was extended to also return `earliest_arrival_if_paid_today` (shop date + vendor lead days) for unpaid invoices, and `get_lease` to also return rent payments already recorded. The full tool list is under [Agent team](#agent-team-problem-5).

#### `check_stock(sku)`
- **Reads:** `inventory`, `pricing`
- **Helps with:** Ticket 101 (Bulldog tee order) and ticket 103 (bulk hoodie discount)
- **How it helps:** For 101, it shows the inventory and customer service agents that `CC-TEE-WHITE` size S has 0 on hand (M has 5, L 3, XL 2), so the order can't ship from stock and the customer needs to be told. For 103, it shows that `CC-HOOD-NAVY` size M has only 8 of the 20 requested (S 4, L 14, XL 6). It also gives the $22 unit cost and $58 list price, so the boss knows any bulk discount must stay above $22 per hoodie, and that 20 hoodies at list price would be $1,160.

#### `get_invoice(invoice_id)`
- **Reads:** `invoices`, `vendors`, `desk`, `cash_accounts`
- **Helps with:** Ticket 101 (Bulldog tee order, linked to invoice 501)
- **How it helps:** It shows that invoice 501 is an $840 "Rush reprint CC-TEE-WHITE S" from Bulldog Print Co (apparel reprint, 5-day lead time). It is still `open`, was due 2026-08-28, and is 3 days overdue as of 2026-08-31. It also shows the $3,400 checking balance. So accounting can see the tee order is waiting on this unpaid reprint, and customer service can tell the customer the shirt will take about 5 days after payment.

#### `get_lease(lease_id)`
- **Reads:** `leases`, `desk`, `cash_accounts`
- **Helps with:** Ticket 102 (rent notice from Elm City Properties, linked to lease 1)
- **How it helps:** It lets facilities check the landlord's email against the lease on file. Lease 1 is the Chapel Street shop, landlord Elm City Properties, $2,400 a month, next due 2026-09-02. That is 2 days after the shop date, which matches "rent due in 2 days." It also shows the $3,400 checking balance, so accounting can see that paying rent plus invoice 501 ($3,240 total) leaves only $160.

## Agent team (Problem 5)

The team is built in Pydantic AI (`backend/`). Every agent runs on **`gpt-6-luna`** through the Portkey gateway (`backend/main.py`, section 1), using the **OpenAI Responses API** (`OpenAIResponsesModel`, `/v1/responses`). The first live run on the chat-completions endpoint failed with *"Function tools with reasoning_effort are not supported for gpt-6-luna … use /v1/responses"*. Our agents depend entirely on tools, so we switched endpoints rather than turning reasoning off. The model name is hard-coded, not set by an environment variable, so nothing can quietly switch it. Each agent's instructions are its prompt file in `backend/prompts/` followed by the full simulation rules.

| Agent | File | Prompt | Job |
|---|---|---|---|
| Boss | `main.py` §5 | `prompts/boss.md` | Reads each ticket and the whole queue, delegates to workers, weighs cash across tickets, sets ticket status, and reports to the human with what needs approving |
| Inventory | `main.py` §5 | `prompts/inventory.md` | Stock by size, shortfalls, restock timing (vendors ship only after they're paid), reserving stock |
| Accounting | `main.py` §5 | `prompts/accounting.md` | Cash position, invoices, rent, discount math. **Files** payment and price-override requests. Never pays |
| Facilities | `main.py` §5 | `prompts/facilities.md` | Checks rent notices against the lease (who, what space, when, how much, already paid?) |
| Customer service | `main.py` §5 | `prompts/customer_service.md` | Writes honest **drafts** to customers and other outside parties. Nothing is sent |

The four workers share one builder (`build_worker` in `main.py`) and return a `WorkerReport`. The boss returns a `BossDecision`. All data types are in `backend/models.py`.

### How delegation and sharing work

- **Boss → worker:** the boss has one extra tool, `delegate(worker, instructions)`. It runs that worker's full agent loop and gives the boss its `WorkerReport`. Workers can't delegate.
- **Worker ↔ worker:** workers share findings in two ways. (1) The boss passes facts from one worker's report into the next worker's instructions. (2) Every agent can write to and read the ticket's **case notes** (`add_case_note` / `get_case_notes`, stored in the database), so customer service can read what inventory and accounting found before writing a draft.
- **Every fact must cite a tool.** `WorkerReport.facts` is a list of `{source_tool, detail}`. That makes invented facts easy to spot in the audit trail.

### Agent loops (`main.py` §4 and §6)

An **agent loop** is one `agent.run()`: the model reads its instructions, calls tools, reads the results, and repeats until it returns its structured output. `run_loop()` wraps every loop so it's audited.

For each ticket, Doug drives three steps (shared code in `main.py` §6, used by both the board and the terminal CLI):
1. **Boss loop** (*Run agent team*, optionally with a message to the boss). The boss works the ticket and delegates; each delegation is a nested worker loop. Any payment or discount comes out as a **pending** approval request. If the boss needs information, it asks Doug a `question_for_human`.
2. **Human decision** (the coral approval cards on the board, or a terminal prompt). Doug approves or rejects each request. Approved payments are executed right away by the human-only MCP tool, which refuses if cash is short. This step starts no agents.
3. **Boss follow-up loop** (*Finish ticket*). The boss gets every decision Doug made on the ticket, rebuilt from the database, has the workers act on them (update the customer draft, set aside stock), and sets the final status.

```bash
python backend/main.py --ticket 101
python backend/main.py --all
python backend/main.py --reset
python backend/main.py --verify-audit
```

`--all` resets the database first (rule 6). `--approvals skip` leaves requests pending (for approving later from the dashboard).

### MCP tools by agent

All shop facts come from `data/campus_customs_new.db` through the one MCP server. There is no second tools layer. Each agent gets a **filtered view** of the server (`TOOL_ACCESS` in `main.py` §3), so it only sees the tools its job needs.

| Tool | Tables | R/W | Boss | Inv | Acct | Fac | CS | What it's for |
|---|---|---|:-:|:-:|:-:|:-:|:-:|---|
| `list_tickets` | tickets, desk | R | ✓ | | | | | Every ticket, open and closed, with `state` = open/resolved (used by the backend's `/tickets`) |
| `list_open_tickets` | tickets, desk | R | ✓ | | | | | The whole queue, so the boss sees tickets competing for cash and stock |
| `get_ticket` | tickets, case_notes, desk | R | ✓ | ✓ | ✓ | ✓ | ✓ | One ticket with its links and the team's notes |
| `get_case_notes` | case_notes | R | ✓ | ✓ | ✓ | ✓ | ✓ | Read what teammates found |
| `add_case_note` | case_notes | W | ✓ | ✓ | ✓ | ✓ | ✓ | Share a finding with the team |
| `update_ticket_status` | tickets, case_notes, approval_requests | W | ✓ | | | | | Set status. Refuses `resolved` while an approval is pending |
| `check_stock` | inventory, pricing | R | | ✓ | | | ✓ | Qty by size, aisle, unit cost, list price |
| `reserve_stock` | inventory, stock_reservations, approval_requests | W | | ✓ | | | | Take units off the shelf. Refuses if short, and refuses on price-override tickets until a human approves |
| `list_vendors` | vendors | R | | ✓ | ✓ | | | Who supplies what, and lead days |
| `get_invoice` | invoices, vendors, desk, cash_accounts | R | | ✓ | ✓ | | ✓ | Invoice status, days overdue, earliest arrival if paid today |
| `get_lease` | leases, payments, desk, cash_accounts | R | | | ✓ | ✓ | | Rent, due date, days until due, rent already paid |
| `get_cash_position` | cash_accounts, invoices, leases, approval_requests, desk | R | ✓ | | ✓ | ✓ | | Balance vs. everything competing for it |
| `list_payments` | payments | R | | | ✓ | ✓ | | Payments made and who approved them |
| `quote_price` | pricing | R | | | ✓ | | ✓ | Discount math: total, % off, margin, below-cost flag |
| `request_payment` | approval_requests, invoices/leases, cash_accounts, case_notes | W | | | ✓ | | | **Ask** the human to approve a payment. Amount comes from the DB, not the agent |
| `request_price_override` | approval_requests, pricing, case_notes | W | | | ✓ | | | **Ask** the human to approve a discount. Refuses below cost |
| `list_approval_requests` | approval_requests | R | ✓ | | ✓ | ✓ | ✓ | What's pending, approved, rejected, paid, refused |
| `draft_customer_message` | customer_drafts, case_notes | W | | | | | ✓ | Save a message as a **draft**. Never sent |
| `list_customer_drafts` | customer_drafts | R | ✓ | | | | ✓ | Read saved drafts |
| `human_record_decision` | approval_requests, case_notes | W | — | — | — | — | — | **Human only.** Approve/reject a request |
| `human_execute_payment` | approval_requests, payments, cash_accounts, invoices, case_notes | W | — | — | — | — | — | **Human only.** Pay an approved request. Refuses if cash is short |

Plus the resource `rules://simulation` (`SIMULATION_RULES`).

### Tables added for the agents

The MCP server creates these on demand (`CREATE TABLE IF NOT EXISTS`), so they come back automatically after a reset restores the original database.

| Table | Fields | Why it matters for the agents |
|---|---|---|
| `case_notes` | id, ticket_id, author, note, shop_date | The team's shared notebook per ticket. It's how workers pass findings to each other |
| `approval_requests` | id, kind, ticket_id, payment_kind, ref_id, sku, size, qty, unit_price, amount, requested_by, reason, status, decided_by, decision_note, shop_date | The only path to moving money or discounting. Agents create `pending` rows, and only a human can move them on |
| `customer_drafts` | id, ticket_id, recipient, subject, body, author, status (`draft_not_sent`), shop_date | Where "contacting" a customer lands. Nothing leaves the simulation |
| `stock_reservations` | id, ticket_id, sku, size, qty, reserved_by, shop_date | Shows which ticket took which units off the shelf |

## Audit trail

`output/audit_trail.json` records every agent loop. The file is created on the first real run.

- **What's recorded:** for each loop, a `loop_started` entry (agent, ticket, prompt), an `agent_step` entry each time the model calls tools (what it said plus the tool calls, written live as it works), and a `loop_finished` entry (every tool call with its arguments and result, the number of model requests, and the structured output), or `loop_failed` with the error. Human decisions (`human_decision`), payments (`payment_executed` / `payment_refused`), and `run_started` / `run_finished` are recorded too.
- **Who did what:** each entry has `run_id`, `loop_id`, and `parent_loop_id`. A worker loop points to the boss loop that delegated it, so the dashboard can rebuild the tree.
- **Append-only:** new entries are written by overwriting only the closing `]` at the end of the file. The bytes of earlier entries are never touched.
- **Tamper-evident:** each entry stores `prev_hash` and its own `hash` (SHA-256). Editing or deleting an old entry breaks the chain, and `python backend/main.py --verify-audit` reports it.
- **Robust writes:** the file lives in a OneDrive folder, and during one live run a write was cut off (the file ended in `,\n{`). After that, every later log attempt failed and so did the run. Now each append retries, and if a write fails partway it rolls the file back to its exact previous bytes. If the file is ever found cut off, `repair()` drops only the incomplete fragment after the last complete entry and logs an `audit_repaired` entry. The one real repair removed 3 bytes; all 429 earlier entries were kept and the chain still verifies. An offline audit-robustness suite checks both behaviors (5/5).
- **Time:** `logged_at` is the real clock (when the entry was written, for auditing). Business dates inside the tool results are the shop date.

## Safety and guardrails

The business wants agents that are useful but can't spend money, mislead customers, or go rogue. Each guardrail is **enforced in code**, not just asked for in a prompt:

| Risk | Guardrail | Where it's enforced |
|---|---|---|
| An agent pays a bill on its own | Agents only *request* payments. Paying needs `human_execute_payment`, which no agent can see, and which refuses anything not approved by a human | `TOOL_ACCESS` allowlists; `main.py` refuses to start if a `human_` tool is ever added to an agent; server checks `status='approved'` |
| An agent approves its own request | Approval is the human-only `human_record_decision`. It refuses an agent role (or anything containing "agent") as the approver | `server.py` |
| Overdrawing the account | `human_execute_payment` re-checks the balance inside a locked transaction and refuses if it would go below $0. Nothing changes, and the refusal is noted | `server.py` (`BEGIN IMMEDIATE`) |
| Paying the wrong amount | `request_payment` takes the amount from the invoice or lease in the database. The agent can't type a number | `server.py` |
| Paying twice | Duplicate pending/approved requests are refused; a paid request can't be executed again; paid invoices can't be requested; rent already paid for the current period (the month before `next_due`) can't be requested again | `server.py` |
| Giving away product | Discounts below unit cost are refused. Every discount needs human approval, and stock can't be reserved for a discounted order until then | `request_price_override`, `reserve_stock` |
| Selling stock we don't have | `reserve_stock` refuses if on-hand qty is short | `server.py` |
| Closing a ticket with loose ends | `update_ticket_status` refuses `resolved` while an approval is pending | `server.py` |
| Contacting real people | There's no send tool. Customer service can only save drafts (`draft_not_sent`) | Tool design |
| Invented facts | Every worker fact must cite its source tool. Prompts forbid guessing, and tools return `error` instead of guessing | `models.py`, prompts, `server.py` |
| An agent pretending to be someone else | Every write tool checks `author` / `requested_by` against the five known roles | `server.py` |
| Runaway loops / cost | One ticket's whole loop tree is capped at 40 model requests and 80 tool calls, and the boss can delegate at most 8 times per loop | `main.py` §4 (`TICKET_LIMITS`), §5 (`MAX_DELEGATIONS`) |
| Wrong model | `gpt-6-luna` is hard-coded | `main.py` §1 |
| Wrong "today" | Every date is counted from `desk.date_today` | `server.py` |
| Hidden actions | Every loop, tool call, human decision, and payment is in the hash-chained, append-only audit trail | `main.py` §2 |
| Stale state between runs | `--all` resets the database to the original before running | `main.py` `reset_database()` |

## Backend routes (Problem 7)

`backend/main.py` is a FastAPI app. It reads shop data through the same MCP server the agents use, so there's still only one tools layer. Start it from the `backend` folder:

```bash
..\.venv\Scripts\uvicorn main:app --reload --port 8000
```

(With the venv activated, that's just `uvicorn main:app --reload --port 8000`.) Interactive docs: http://localhost:8000/docs.

- `GET /tickets`: every ticket with its status and `state` (open or resolved).
- `GET /tickets/{id}`: one ticket with its case notes, approval requests, and message drafts.
- `POST /tickets/{id}/run`: Doug starts the agent team (boss first pass) on that ticket in the background, and it returns a `run_id` right away (202). The optional body `{"instructions": "..."}` carries Doug's words to the boss, e.g. an answer to its question. They're logged as a `human_instruction` audit event and added to the boss's prompt. They're never treated as an approval.
- `GET /runs`: every run since the server started (queued / running / finished / failed), newest first.
- `GET /runs/{run_id}`: one run's status and the boss's final `BossDecision`.
- `GET /events?after=N`: audit-trail events after sequence N (what each agent was asked, said, and did, plus every tool call). The board polls this with the last `seq` it saw; it can be filtered by `ticket_id` or `run_id`.
- `GET /approvals?status=pending`: payment and price-override requests waiting on Doug (`status=all` shows every request).
- `POST /approvals/{request_id}`: Doug's click. Body `{"decision": "approve" | "reject", "approver": "Doug", "note": ""}`. It records the decision and pays an approved payment immediately (refused if cash is short). It does **not** start any agents.
- `POST /tickets/{id}/follow_up`: Doug's **Finish ticket** click. The boss finishes the ticket using every decision Doug made on it, rebuilt from `approval_requests` and `payments` in the database (so it works after a server restart). It's refused (409) while a request is still pending, or if nothing has been decided yet.
- `GET /balance`: the current checking balance plus open invoices, rent, and requests in flight.
- `POST /reset`: restores the database to the original values for a fresh run (refused while agents are running; the audit trail is kept).

**Only Doug starts agents:** nothing runs on its own. Starting the server, approving, and resetting never launch an agent; only `POST /tickets/{id}/run` (Run agent team) and `POST /tickets/{id}/follow_up` (Finish ticket) do, and Doug clicks both.

**How runs work:** runs go one ticket at a time (a queue behind one lock), because every ticket draws on the same checking account. Run status is kept in memory, so it's lost when the server restarts. The audit trail is not.

**Safety:** an approval only happens when a human calls `POST /approvals/{id}`. The agents have no HTTP tool, the API refuses agent names as the approver (via `human_record_decision`), and CORS only allows `localhost` / `127.0.0.1` pages to call the backend.

## Agent dashboard (Problem 8)

`frontend/` is a React + Vite + TypeScript board that calls every backend route. The full design write-up is in `output/design.md`.

**Run it** (two terminals):

```bash
cd backend
..\.venv\Scripts\uvicorn main:app --reload --port 8000
```

```bash
cd frontend
npm run dev
```

The board can't do anything unless the backend is running; if it isn't, the board shows "Backend offline".

`npm run dev` serves the board at http://localhost:5173 and opens it in the browser. The backend's CORS allows `http://localhost:5173` and `http://127.0.0.1:5173` (plus other localhost ports, in case Vite has to pick another one).

**What it does:** lists the tickets → you pick one → **Run agent team** → the five agents (little HTML people in Yale attire) show what they're saying and which tools they're calling, live → coral **approval cards** make you approve or reject anything that costs money → the **checking balance** counts down when money goes out → the boss's follow-up marks the ticket **Resolved** with a stamp → **What each agent did** cards summarize each agent's work and the tools it used.

**Fixes after the first live runs (Problem 9):**
- *Ticket 103 said "needs you" while the approvals panel said "nothing is waiting."* The boss had asked Doug a question (what price to offer), but the board only knew about approval requests. Now `BossDecision` has a `question_for_human` field, the boss prompt says to set `waiting_on_human` only for a pending approval or a real question, and the board shows the question with a reply box. The approvals panel lists "Question from the boss" cards too.
- *Ticket 101 kept offering "Finish ticket," which never finished it.* It was correctly `waiting_on_vendor`: the tee ships 5 days after payment and the shop date never moves. "Finish ticket" now only appears when Doug has decided something since the boss last looked, and the board explains in plain words that the ticket rests there.
- *Agents thought rent was still owed after it was paid.* `get_cash_position` listed every lease as due. It now splits `rent_still_due` from `rent_already_paid_this_period`, and `get_invoice` reports `paid_at` and `expected_arrival` once an invoice is paid.
- *Plain English.* Every ticket gets a **"What's happening"** panel (what's going on, and what, if anything, Doug needs to do). Bubbles and the feed describe actions in words ("Checking the shelves for the white Bulldog tee"), not tool names. Agents are told to write their summaries for a shop owner. The exact tools, arguments, and results are still one click away under **Details** and **Tools used**.

**Backend change for the board:** `run_loop` now steps through each agent loop with `agent.iter()` and writes an `agent_step` audit event every time the model calls tools. That makes the board live at the tool-call level. It's also a more complete audit trail.

## Tests and checks

**In the repo:**

```bash
python mcp_server/server.py --smoke     # MCP tools over the protocol -> output/mcp_smoke.json (Problem 4)
python backend/main.py --verify-audit   # audit-trail hash chain
```

**During development** (kept out of the submitted repo, to match the required structure), offline suites ran against a scripted stand-in model, a scratch copy of the database, and a scratch audit file. They never called the model or touched the real data:

| Suite | What it checked | Result |
|---|---|---|
| Agent team | Boss → facilities → accounting on ticket 102 through the real MCP server, plus every guardrail: no agent sees a `human_` tool; payment without approval refused; "accounting" and "Boss Agent" can't approve; overdraft refused with nothing changed; below-cost discount refused; reserving missing stock refused; rent can't be requested twice; worker loops link to their boss loop; live `agent_step` events; audit chain verifies; an edited entry is detected | **25/25** |
| API | Every route, loaded the way `uvicorn main:app` loads it: run → events → approvals → an "accounting" approval refused → Doug approves (approving starts no agents) → rent shows paid, not due → *Finish ticket* resolves → reset back to $3,400 → a message from Doug reaches the boss's prompt | **26/26** |
| Audit robustness | A cut-off file is repaired (only the fragment dropped, the repair logged, the chain intact), and a failed write is rolled back byte-for-byte | **5/5** |

A demo backend (the real FastAPI app with a scripted model for ticket 102) was used to click through the board in Problem 8 without spending model calls.

## Live session: resolving the tickets (Problem 9)

On Oct 9, 2026 (shop date 2026-08-31) the working database was reset to the original values (audit seq 431). Doug then ran all three tickets from the board: he started each one, approved each request, and pressed *Finish ticket*. The session is audit seq **432–565** (6 runs, every one finished, none failed), and the hash chain verifies.

| Ticket | Agents that worked | Doug's part | Cash | Final status |
|---|---|---|---|---|
| **101** Bulldog tee, size S | Boss → Inventory + Accounting → Customer service; wrap-up: Inventory, Customer service | Approved #1: pay invoice 501 | −$840.00 | `waiting_on_vendor` (tee due Sept 5; the shop date never advances) |
| **102** Rent due | Boss → Facilities + Accounting; wrap-up: Facilities, Accounting | Approved #2: rent on lease 1 | −$2,400.00 | `resolved` |
| **103** Bulk hoodies | Boss → Inventory → Accounting + Customer service; wrap-up: all three | Told the boss "See if we have enough and if we can afford to this one. We are running low on cash."; approved #3: $49.30 × 20 (15% off) | $0.00 | `in_progress` (waiting on the club to pick a quantity) |

**Cash:** $3,400.00 → −$840.00 → $2,560.00 → −$2,400.00 → **$160.00**, which equals `cash_accounts.checking` in the working DB. Both `payments` rows have `approved_by = Doug`.

**Compared to the Problem 6 plan:** 101 and 102 matched (same agents, tools, requests, amounts, and end states). The one difference is that the boss sent two workers *in parallel* where the plan had them one after the other. 103 mostly matched, but accounting filed the discount for all 20 hoodies instead of the 8 in stock (flagged as subject to supply; `reserve_stock` can never take more than 8). Facilities was correctly left out of 101 and 103, and inventory and customer service out of 102.

**Deliverables:**
- `output/desk_tickets.html`: Expected (unchanged) vs. Actual on each ticket tab, plus the itemized Cash tab.
- `output/resolved_tickets.json`: per ticket, the final status, a short outcome, what each agent contributed, and the human approvals, plus the cash reconciliation.
- `output/resolved_board.html`: React board screenshots for each ticket, embedded in the page (taken with headless Edge at `http://localhost:5173/?ticket=N`).
- `output/audit_trail.json`: every loop, step, tool call, instruction, decision, and payment from the session.

**Problems the earlier live attempts exposed, now fixed** (details in the sections above):
1. gpt-6-luna refused tools on `/v1/chat/completions`, so the agents moved to the Responses API.
2. The board showed a cut-off loop as still working, so it now trusts only live runs.
3. Approving auto-started the follow-up, so only Doug starts runs now (*Finish ticket*).
4. *Finish ticket* kept showing on a ticket that was correctly waiting on the vendor.
5. The boss's question had nowhere to appear. Now there's `question_for_human` plus a reply box.
6. Paid rent was still listed as due.
7. An audit write was cut off mid-entry, so writes now retry and roll back, and a cut-off tail is repaired and logged.
8. A failed run could stay stuck as "running".
