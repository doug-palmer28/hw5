# Campus Customs MCP Server

## What it's for

This is the **only** tools layer for the Campus Customs agent team: boss, inventory, accounting, facilities, and customer service. Every shop fact an agent sees, and every change an agent makes, goes through these tools. That way they all see the same numbers, and the safety rules are enforced in one place. The tools never make up values. If a lookup finds nothing, the tool returns an `error` message instead of guessing.

Built with [FastMCP](https://gofastmcp.com) (`fastmcp` 4.x). The server file is `server.py`.

## Database

- **File:** `../data/campus_customs_new.db` (`Homework 5/data/campus_customs_new.db`). Tests can point it somewhere else with the `CAMPUS_CUSTOMS_DB` environment variable.
- This is our working copy of the original `data/campus_customs.db`. The original is never changed. `python backend/main.py --reset` (or **Reset shop** on the board) copies it back over the working copy.
- **Original tables:** desk, inventory, pricing, vendors, leases, cash_accounts, payments, invoices, tickets.
- **Tables the server adds** (created on demand, so they come back after a reset): `case_notes`, `approval_requests`, `customer_drafts`, `stock_reservations`.
- The shop's "today" comes from the `desk` table (`2026-08-31`), not the computer clock. Overdue and due-soon numbers are counted from that date.

## Rules resource

`rules://simulation` serves `SIMULATION_RULES`, defined at the top of `server.py`, and the backend appends the same text to every agent's prompt. Those are the simulation rules every agent must follow: today is `desk.date_today`, every payment needs human approval, balances can never go negative, there is no real outside contact, and more.

## Tools

### Tickets and teamwork
| Tool | Tables | What it does |
|---|---|---|
| `list_tickets()` | tickets, desk | Every ticket with `state` = open/resolved (used by the backend) |
| `list_open_tickets()` | tickets, desk | Every ticket not resolved/declined, plus the shop date |
| `get_ticket(ticket_id)` | tickets, case_notes, desk | One ticket with its case notes |
| `update_ticket_status(ticket_id, status, note, updated_by)` | tickets, case_notes, approval_requests | Sets status. Refuses `resolved` while an approval is pending |
| `add_case_note(ticket_id, author, note)` | case_notes | Shares a finding with the team |
| `get_case_notes(ticket_id)` | case_notes | Reads the team's notes |

### Inventory
| Tool | Tables | What it does |
|---|---|---|
| `check_stock(sku)` | inventory, pricing | Qty and aisle per size, unit cost, list price |
| `reserve_stock(ticket_id, sku, size, qty, reserved_by)` | inventory, stock_reservations, approval_requests | Takes units off the shelf. Refuses if short, and refuses on price-override tickets until a human approves |
| `list_vendors()` | vendors | Specialty and lead days per vendor |

### Money (read)
| Tool | Tables | What it does |
|---|---|---|
| `get_invoice(invoice_id)` | invoices, vendors, desk, cash_accounts | Amount, status, days overdue, earliest arrival if paid today, checking balance |
| `get_lease(lease_id)` | leases, payments, desk, cash_accounts | Rent, next due date, days until due, rent already paid, checking balance |
| `get_cash_position()` | cash_accounts, invoices, leases, approval_requests, desk | Balance vs. open invoices, rent, and requests in flight |
| `list_payments()` | payments | Every payment and who approved it |
| `quote_price(sku, qty, unit_price)` | pricing | Order total, % off list, margin, below-cost flag (changes nothing) |

### Requests (agents ask, the human decides)
| Tool | Tables | What it does |
|---|---|---|
| `request_payment(ticket_id, payment_kind, ref_id, requested_by, reason)` | approval_requests, invoices/leases, cash_accounts | Creates a **pending** payment request. The amount comes from the DB. Duplicates are refused |
| `request_price_override(ticket_id, sku, size, qty, unit_price, requested_by, reason)` | approval_requests, pricing | Creates a **pending** discount request. Below-cost prices are refused |
| `list_approval_requests(ticket_id?, status?)` | approval_requests | Lists requests and their status |
| `draft_customer_message(ticket_id, recipient, subject, body, author)` | customer_drafts | Saves a **draft**. Nothing is ever sent |
| `list_customer_drafts(ticket_id?)` | customer_drafts | Lists drafts |

### Human only (no agent is given these)
| Tool | Tables | What it does |
|---|---|---|
| `human_record_decision(request_id, decision, approver, note)` | approval_requests, case_notes | Approves or rejects a pending request. Refuses agent names as the approver |
| `human_execute_payment(request_id)` | approval_requests, payments, cash_accounts, invoices | Pays a human-approved request. **Refuses if the balance would go negative** |

Write tools check that `author` / `requested_by` / `reserved_by` / `updated_by` is one of the five agent roles. Which agent can use which tool is set in `../backend/main.py` (`TOOL_ACCESS`, section 3) (`TOOL_ACCESS`), and it's documented in `../output/harness.md`.

## Setup

From the `Homework 5` folder:

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install fastmcp "pydantic-ai-slim[openai,mcp]" python-dotenv
```

To start the server over stdio by hand:

```bash
.venv/Scripts/python mcp_server/server.py
```

## Who connects to it

- **The agent team:** `backend/main.py` (section 3) launches this server over stdio and gives each agent a filtered view of it.
- **The backend:** `backend/main.py` (FastAPI) opens the same server when it starts and uses it for every route that reads or changes shop data. Only the backend's approval route calls the `human_` tools, and only when a person clicks.
- **The coder:** `../.mcp.json` registers it as `campus-customs` for Claude Code opened in `Homework 5`. Approve the server when Claude Code asks. Because the coder is a client too, it can see the `human_` tools. `CLAUDE.md` tells it never to call them.

## Tests

`--smoke` (Problem 4) starts this server as a real MCP subprocess, calls the first three tools and the rules resource over the protocol, and saves the prompt, tool name, arguments, and output to `output/mcp_smoke.json`:

```bash
python mcp_server/server.py --smoke
```

