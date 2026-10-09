# Campus Customs: a multi-agent shop (Homework 5)

Five Pydantic AI agents (**boss, inventory, accounting, facilities, customer service**) run the Campus Customs online shop. They work its tickets (a customer order, a rent notice, and a bulk-discount request) through one **MCP server** that wraps a SQLite database. A **FastAPI backend** runs the team, and a **React board** lets a human start the team, watch every agent work, and **approve anything that costs money**. No agent can pay, approve, or contact anyone outside the simulation. Every agent loop is recorded in an append-only, hash-chained audit trail.

All agents use **`gpt-6-luna`** (OpenAI, through the Portkey gateway, Responses API).

## What's in the repo

```
hw5/
├── AI_prompts.md            every prompt used to build this, word for word, by problem
├── requirements.txt         Python dependencies
├── .env.example             copy to .env and add your PORTKEY_API_KEY
├── .gitignore               keeps .env, .venv/, node_modules/ out of git
├── .mcp.json                registers the MCP server for Claude Code
├── README.md                this file
├── data/
│   ├── campus_customs.db       the ORIGINAL database (never modified)
│   └── campus_customs_new.db   the WORKING copy every agent reads and writes
├── mcp_server/
│   ├── server.py            FastMCP server: 21 tools, the simulation rules, and a --smoke test (the only shop tools layer)
│   └── README.md            what each tool does
├── frontend/                React + Vite + TypeScript "Agent Desk" board
├── backend/
│   ├── main.py              the five agents, agent loop, audit trail, MCP connection, FastAPI routes, terminal CLI
│   ├── models.py            data types (WorkerReport, BossDecision, audit entries, ...)
│   ├── prompts/             one prompt per agent (boss.md, inventory.md, accounting.md, facilities.md, customer_service.md)
└── output/
    ├── harness.md           full documentation: tables, tools, agents, routes, safety, tests, live session
    ├── mcp_smoke.json       MCP tool smoke test (Problem 4)
    ├── desk_tickets.html    per ticket: expected vs. actual, plus the Cash and Reflection tabs (double-click to open)
    ├── design.md            the board's design decisions
    ├── resolved_tickets.json  final status, outcome, agent contributions, and approvals per ticket
    ├── resolved_board.html  screenshots of the board for each resolved ticket
    ├── audit_trail.json     every agent loop, tool call, human decision, and payment
    └── github_url.txt       this repository's URL
```

## Requirements

- **Python 3.10 or newer** (tested on 3.13 and 3.14)
- **Node.js 20.19+ or 22.12+** (Vite 8 needs one of these; tested on Node 24). Check with `node --version`.
- A **Portkey API key** with access to `gpt-6-luna` (only needed for live agent runs). Without one, everything else works; pressing *Run agent team* fails with "PORTKEY_API_KEY is not set".

## One-time setup

From the repo root, create a virtual environment (on macOS/Linux, use `python3` for this one command):

```bash
python -m venv .venv
```

Activate it:
- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`. If PowerShell says running scripts is disabled, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first, or use Command Prompt: `.venv\Scripts\activate.bat`.
- **macOS/Linux:** `source .venv/bin/activate`

Once it's active, `python` and `pip` refer to the virtual environment on every OS.

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and put your key in it (**Windows:** `copy .env.example .env` · **macOS/Linux:** `cp .env.example .env`). `.env` is gitignored and must never be committed.

```bash
cd frontend
npm install
cd ..
```

All commands below assume the virtual environment is **activated** and you're in the **repo root** unless a step says `cd`.

## 1. Copy the original database to the working copy (clean run)

`data/campus_customs.db` is the original and is never changed. Everything works on `data/campus_customs_new.db`. To get a clean working copy, copy the original over it. **Stop the backend first** if it's running.

```bash
python backend/main.py --reset
```

That's the same as copying the file by hand:
- **Windows (PowerShell):** `Copy-Item data\campus_customs.db data\campus_customs_new.db -Force`
- **Windows (Command Prompt):** `copy /Y data\campus_customs.db data\campus_customs_new.db`
- **macOS/Linux:** `cp data/campus_customs.db data/campus_customs_new.db`

The audit trail is *not* reset. It's append-only and keeps every run, separated by `db_reset` entries.

## 2. Start the MCP server

The backend starts the MCP server for you (it launches `mcp_server/server.py` over stdio when it boots), so **you don't need to run it separately to use the board.** To run it on its own:

```bash
python mcp_server/server.py
```

- **Test it:** `python mcp_server/server.py --smoke` calls the tools over MCP and writes `output/mcp_smoke.json`.
- **Use it from Claude Code:** `.mcp.json` registers it as `campus-customs` (command `python mcp_server/server.py`). Activate the virtual environment *before* starting Claude Code in the repo root, so `python` is the one with `fastmcp` installed.

## 3. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Main routes: `GET /tickets`, `POST /tickets/{id}/run`, `GET /events`, `GET /approvals`, `POST /approvals/{id}`, `POST /tickets/{id}/follow_up`, `GET /balance`, `POST /reset` (each one is described in `output/harness.md`)
- Starting the backend **never** starts the agents. Only the human does that, from the board.

## 4. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

The board opens at **http://localhost:5173** (the backend allows this origin). Keep the backend running; the board shows "Backend offline" if it isn't.

**If port 8000 is already taken** on your machine, start the backend on another port (e.g. `uvicorn main:app --reload --port 8010`) and tell the board where it is when you start it:
- **macOS/Linux:** `VITE_API_URL=http://localhost:8010 npm run dev`
- **Windows (PowerShell):** `$env:VITE_API_URL="http://localhost:8010"; npm run dev`

If 5173 is taken, Vite picks the next free port by itself, and the backend accepts any `localhost` port.

## 5. Reset, then run all three tickets

**Always reset before a full three-ticket run** (simulation rule 6). With the backend and board running:

1. Press **Reset shop** on the board (or `curl -X POST http://localhost:8000/reset`; in Windows PowerShell type `curl.exe`). Checking goes back to **$3,400.00**, all three tickets reopen, and approvals are cleared.
2. For each ticket, **101 → 102 → 103**:
   - Select it and press **Run agent team**. You can type a message to the boss first.
   - Watch the agents on the board. When a coral **Needs you** card appears, read the effect ("Checking goes $3,400.00 → $2,560.00") and press **Approve & pay** or **Reject**.
   - Press **Finish ticket** so the boss acts on your decision.

Expected result (see `output/desk_tickets.html` → Cash): $3,400.00 − $840.00 (invoice 501, ticket 101) − $2,400.00 (rent, ticket 102) = **$160.00**. Ticket 103's discount moves no money.

**Terminal alternative (no board):** `python backend/main.py --all` resets the database automatically, runs all three tickets, and asks for each approval in the terminal.

## Safety rules (enforced in code, not just in prompts)

Full rules: `SIMULATION_RULES` in `mcp_server/server.py`, served as the MCP resource `rules://simulation` and appended to every agent's prompt.

- **Human approval for every payment and discount.** Agents can only *request*. The approve and pay tools aren't in any agent's toolbox, and they refuse an agent's name as the approver.
- **No negative balance.** A payment that would overdraw checking is refused, and nothing changes.
- **Today is `desk.date_today`** (2026-08-31). Vendors ship only after they're paid. Money only goes out.
- **No outside contact.** Customer messages are saved as drafts and are never sent.
- **Everything is audited.** `python backend/main.py --verify-audit` checks the audit trail's hash chain.

## Quick checks

```bash
python mcp_server/server.py --smoke
python backend/main.py --verify-audit
```

The first starts the MCP server and calls its tools over the protocol (this rewrites `output/mcp_smoke.json`). The second confirms that no audit-trail entry has been edited or deleted.
