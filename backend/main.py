"""Campus Customs backend: the agent team and the FastAPI app.

This one file holds everything the backend needs (the data types live in
models.py, the prompts in prompts/*.md):

    1. Config and the team's model (gpt-6-luna via Portkey, Responses API)
    2. Audit trail: append-only, hash-chained output/audit_trail.json
    3. MCP connection: the one shop tools layer, filtered per agent
    4. The agent loop every agent runs through (audited at every step)
    5. The five agents: boss (delegates) + inventory, accounting, facilities, customer service
    6. Running tickets: boss first pass -> human decision -> boss follow-up, and reset
    7. FastAPI routes for the React board
    8. Terminal CLI

Start the API from the backend folder:
    uvicorn main:app --reload --port 8000

Terminal tools (from the repo root):
    python backend/main.py --reset           # copy the original DB over the working copy
    python backend/main.py --all             # reset, then run all tickets, approving in the terminal
    python backend/main.py --ticket 101
    python backend/main.py --verify-audit    # check the audit trail's hash chain

Shop data is read and changed only through the campus-customs MCP server. A
human click on /approvals/{id} is the only way a payment or discount gets
approved, and nothing starts agents on its own: only POST /tickets/{id}/run and
POST /tickets/{id}/follow_up do, and only the human calls them.
"""

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone
from functools import cache
from pathlib import Path
from typing import Any, Literal

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent                                    # the repo root (hw5/)
for _p in (str(BACKEND), str(ROOT)):                    # `uvicorn main:app` and `python backend/main.py`
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastmcp.client.transports import StdioTransport  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from pydantic_ai import Agent, RunContext, capture_run_messages  # noqa: E402
from pydantic_ai.mcp import MCPToolset  # noqa: E402
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.openai import OpenAIResponsesModel  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.usage import RunUsage, UsageLimits  # noqa: E402

from mcp_server.server import SIMULATION_RULES  # noqa: E402  (the rules live with the MCP server)
from models import AuditEntry, BossDecision, RunDeps, ToolCallRecord, WorkerReport, WorkerRole  # noqa: E402


# ============================================================ 1. config and model

PROMPTS_DIR = BACKEND / "prompts"
MCP_SERVER = ROOT / "mcp_server" / "server.py"
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
# Tests point these at scratch copies so they never touch the real files.
WORKING_DB = Path(os.getenv("CAMPUS_CUSTOMS_DB", ROOT / "data" / "campus_customs_new.db"))
AUDIT_PATH = Path(os.getenv("CAMPUS_CUSTOMS_AUDIT", ROOT / "output" / "audit_trail.json"))

# Every agent on the team runs on this model. Not configurable on purpose.
MODEL_NAME = "gpt-6-luna"


@cache
def team_model() -> OpenAIResponsesModel:
    """gpt-6-luna through the Portkey gateway. Key: PORTKEY_API_KEY in .env at the repo root.

    Uses the OpenAI Responses API (/v1/responses). gpt-6-luna rejects function
    tools on /v1/chat/completions ("Function tools with reasoning_effort are not
    supported ... use /v1/responses"), and every agent here depends on tools.
    """
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / ".env")
    key = os.environ.get("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Copy .env.example to .env and add your key.")
    client = AsyncOpenAI(
        api_key=key,
        base_url=os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1"),
        default_headers={"x-portkey-api-key": key, "x-portkey-provider": "openai"},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def load_instructions(role: str) -> str:
    """The agent's own prompt followed by the shared simulation rules."""
    prompt = (PROMPTS_DIR / f"{role}.md").read_text(encoding="utf-8")
    return f"{prompt}\n\n---\n\n{SIMULATION_RULES}"


# ============================================================ 2. audit trail
#
# output/audit_trail.json is a JSON array. New entries are written by
# overwriting only the closing bracket at the end of the file, so the bytes of
# earlier entries are never touched. Each entry stores the hash of the one
# before it; editing or deleting an old entry breaks the chain (audit_verify).
#
# The file lives in a OneDrive folder, which can briefly lock it while syncing:
# each append is retried, a write that fails partway is rolled back to the exact
# previous bytes, and a file found cut off mid-entry is repaired by dropping
# only the incomplete fragment (logged as `audit_repaired`).

_TAIL = b"\n]\n"
_GENESIS = "0" * 64
_audit_lock = threading.Lock()


def _digest(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def _audit_read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _complete_prefix(raw: bytes) -> tuple[list[dict], int]:
    """Parse entries from the start of a (possibly cut-off) array.
    Returns the complete entries and the byte offset just after the last one."""
    text = raw.decode("utf-8", errors="replace")
    dec = json.JSONDecoder()
    i = text.index("[") + 1
    entries, end = [], i
    while True:
        while i < len(text) and text[i] in " \r\n\t,":
            i += 1
        if i >= len(text) or text[i] != "{":
            break
        try:
            obj, j = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            break
        entries.append(obj)
        end = i = j
    return entries, len(text[:end].encode("utf-8"))


def audit_repair(path: Path = AUDIT_PATH) -> dict | None:
    """Fix a file that was cut off mid-write. Returns what was done, or None if it was fine."""
    raw = path.read_bytes()
    try:
        json.loads(raw)
        if not raw.endswith(_TAIL):
            # Valid file with a different ending (e.g. a Windows CRLF checkout from git):
            # rewrite only the closing bracket. No entry changes, so nothing to log.
            end = len(raw.rstrip().removesuffix(b"]").rstrip())
            with path.open("r+b") as f:
                f.truncate(end)
                f.seek(end)
                f.write(_TAIL)
        return None
    except json.JSONDecodeError:
        pass
    entries, end = _complete_prefix(raw)
    dropped = len(raw) - end
    with path.open("r+b") as f:
        f.truncate(end)
        f.seek(end)
        f.write(_TAIL)
        f.flush()
        os.fsync(f.fileno())
    json.loads(path.read_bytes())
    return {"kept_entries": len(entries), "last_seq": entries[-1]["seq"] if entries else 0,
            "dropped_bytes_of_incomplete_entry": dropped}


def _write_tail(path: Path, data: bytes) -> None:
    """Replace the closing bracket with `data`, rolling back on any failure."""
    size = path.stat().st_size
    with path.open("r+b") as f:
        f.seek(size - len(_TAIL))
        if f.read() != _TAIL:
            raise RuntimeError(f"{path} doesn't end the way the audit writer left it.")
        try:
            f.seek(size - len(_TAIL))
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        except OSError:
            f.seek(size - len(_TAIL))       # put the file back exactly as it was
            f.write(_TAIL)
            f.truncate(size)
            f.flush()
            raise


def _audit_append_locked(path: Path, **fields) -> dict:
    entries = _audit_read(path)
    last = entries[-1] if entries else None
    entry = AuditEntry(
        seq=(last["seq"] + 1) if last else 1,
        prev_hash=last["hash"] if last else _GENESIS,
        logged_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **fields,
    ).model_dump(mode="json")
    entry["hash"] = _digest(entry)
    blob = json.dumps(entry, indent=2, default=str).encode()

    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(b"[\n" + blob + _TAIL)
        return entry
    for attempt in range(6):
        try:
            _write_tail(path, b",\n" + blob + _TAIL)
            return entry
        except OSError:
            if attempt == 5:
                raise
            time.sleep(0.25 * (attempt + 1))   # e.g. OneDrive briefly holding the file
    return entry


def audit_append(path: Path = AUDIT_PATH, **fields) -> dict:
    """Add one entry to the end of the trail and return it."""
    with _audit_lock:
        repaired = audit_repair(path) if path.exists() else None
        if repaired:
            _audit_append_locked(path, event="audit_repaired", run_id="audit", agent="audit", output=repaired)
        return _audit_append_locked(path, **fields)


def audit_verify(path: Path = AUDIT_PATH) -> dict:
    """Check the hash chain. Returns {'ok': bool, 'entries': n, 'problem': ...}."""
    prev = _GENESIS
    entries = _audit_read(path)
    for i, e in enumerate(entries, start=1):
        if e.get("seq") != i or e.get("prev_hash") != prev or _digest(e) != e.get("hash"):
            return {"ok": False, "entries": len(entries), "problem": f"entry seq={e.get('seq')} (position {i})"}
        prev = e["hash"]
    return {"ok": True, "entries": len(entries), "problem": None}


# ============================================================ 3. MCP connection (the one shop tools layer)
#
# Every agent gets a filtered view of the same server, showing only the tools in
# its TOOL_ACCESS allowlist. Human-only tools (prefix `human_`) are in no
# allowlist, so no agent can approve a request or move money.

READ_TICKETS = {"get_ticket", "get_case_notes", "add_case_note"}

TOOL_ACCESS: dict[str, set[str]] = {
    "boss": READ_TICKETS | {
        "list_tickets", "list_open_tickets", "update_ticket_status", "get_cash_position",
        "list_approval_requests", "list_customer_drafts",
    },
    "inventory": READ_TICKETS | {
        "check_stock", "list_vendors", "get_invoice", "reserve_stock",
    },
    "accounting": READ_TICKETS | {
        "get_invoice", "get_lease", "get_cash_position", "list_payments", "list_vendors",
        "list_approval_requests", "quote_price", "request_payment", "request_price_override",
    },
    "facilities": READ_TICKETS | {
        "get_lease", "list_payments", "list_approval_requests", "get_cash_position",
    },
    "customer_service": READ_TICKETS | {
        "check_stock", "get_invoice", "quote_price", "list_approval_requests",
        "draft_customer_message", "list_customer_drafts",
    },
}

# Hard stop: refuse to start if anyone ever adds a human-only tool to an agent.
for _role, _tools in TOOL_ACCESS.items():
    _leak = {t for t in _tools if t.startswith("human_")}
    if _leak:
        raise RuntimeError(f"Agent '{_role}' must not get human-only tools: {_leak}")


@cache
def shop_server() -> MCPToolset:
    """One MCP connection shared by the whole team (launched over stdio)."""
    env = {k: os.environ[k] for k in ("CAMPUS_CUSTOMS_DB",) if k in os.environ}
    transport = StdioTransport(command=sys.executable, args=[str(MCP_SERVER)], cwd=str(ROOT), env=env or None)
    return MCPToolset(transport, id="campus-customs", tool_error_behavior="failed")


def tools_for(role: str):
    """The slice of the MCP server this agent is allowed to use."""
    allowed = TOOL_ACCESS[role]
    return shop_server().filtered(lambda ctx, tool_def: tool_def.name in allowed)


async def call_tool(tool: str, **args) -> dict:
    """Call the shop's MCP server directly (the shared server must be open)."""
    return await shop_server().direct_call_tool(tool, args)


# ============================================================ 4. the agent loop
#
# One call to run_loop is one agent loop: the model reads its instructions,
# calls MCP tools (or, for the boss, delegates), and repeats until it returns its
# structured output. Each loop is audited when it starts, at every step where the
# model calls tools (`agent_step`, so the board can show the work live), and when
# it finishes or fails, with every tool call and result.

# Guardrail: cap how much one ticket's loop tree can do (boss + delegations share it).
TICKET_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=80)


def _tool_calls(messages) -> list[ToolCallRecord]:
    calls: dict[str, ToolCallRecord] = {}
    for msg in messages:
        for part in getattr(msg, "parts", []):
            if isinstance(part, ToolCallPart):
                calls[part.tool_call_id] = ToolCallRecord(tool=part.tool_name, args=part.args_as_dict())
            elif isinstance(part, ToolReturnPart) and part.tool_call_id in calls:
                content = part.content
                calls[part.tool_call_id].result = (
                    content.model_dump(mode="json") if hasattr(content, "model_dump") else content
                )
    return list(calls.values())


def _log_step(response: ModelResponse, base: dict) -> None:
    """Live event for the board: what the agent just said and which tools it's calling."""
    calls = [ToolCallRecord(tool=p.tool_name, args=p.args_as_dict())
             for p in response.parts
             if isinstance(p, ToolCallPart) and not p.tool_name.startswith("final_result")]
    said = " ".join(p.content for p in response.parts if isinstance(p, TextPart)).strip()
    if calls or said:
        audit_append(event="agent_step", tool_calls=calls, output=said or None, **base)


def _dump(output: Any) -> Any:
    return output.model_dump(mode="json") if hasattr(output, "model_dump") else output


async def run_loop(agent: Agent, role: str, prompt: str, deps: RunDeps, usage: RunUsage | None = None) -> Any:
    """Run one agent loop, auditing it start to finish. Returns the agent's output."""
    loop_deps = replace(deps, loop_id=f"{role}-{uuid.uuid4().hex[:8]}", delegations=0)
    base = dict(run_id=deps.run_id, loop_id=loop_deps.loop_id, parent_loop_id=deps.loop_id or None,
                agent=role, model=MODEL_NAME, ticket_id=deps.ticket_id)
    audit_append(event="loop_started", prompt=prompt, **base)

    with capture_run_messages() as messages:
        try:
            async with agent.iter(
                prompt, deps=loop_deps, model=team_model(), usage=usage, usage_limits=TICKET_LIMITS,
            ) as run:
                async for node in run:
                    if Agent.is_call_tools_node(node):
                        _log_step(node.model_response, base)
            result = run.result
        except Exception as exc:
            audit_append(event="loop_failed", tool_calls=_tool_calls(messages),
                         error=f"{type(exc).__name__}: {exc}", **base)
            raise

    new = result.new_messages()
    audit_append(event="loop_finished", tool_calls=_tool_calls(new),
                 model_requests=sum(isinstance(m, ModelResponse) for m in new),
                 output=_dump(result.output), **base)
    return result.output


# ============================================================ 5. the five agents

def build_worker(role: str) -> Agent[RunDeps, WorkerReport]:
    """A worker agent: its prompt + the rules, its slice of the MCP tools, a WorkerReport out."""
    return Agent(name=role, deps_type=RunDeps, output_type=WorkerReport,
                 instructions=load_instructions(role), toolsets=[tools_for(role)], retries=2)


inventory_agent = build_worker("inventory")              # stock, sizes, aisles, vendor restock timing
accounting_agent = build_worker("accounting")            # cash, invoices, rent, pricing; requests approvals, never pays
facilities_agent = build_worker("facilities")            # the shop's lease; verifies rent notices
customer_service_agent = build_worker("customer_service")  # drafts (never sends) messages

WORKERS = {
    "inventory": inventory_agent,
    "accounting": accounting_agent,
    "facilities": facilities_agent,
    "customer_service": customer_service_agent,
}

# Guardrail: the boss can't hand out work forever in a single loop.
MAX_DELEGATIONS = 8

boss_agent = Agent(  # triages tickets, delegates to workers, reports to the human
    name="boss", deps_type=RunDeps, output_type=BossDecision,
    instructions=load_instructions("boss"), toolsets=[tools_for("boss")], retries=2,
)


@boss_agent.tool
async def delegate(ctx: RunContext[RunDeps], worker: WorkerRole, instructions: str) -> WorkerReport | str:
    """Hand a task to one worker agent and get its report back.

    Args:
        worker: inventory, accounting, facilities, or customer_service.
        instructions: Exactly what you need: the ticket id, what to check or do,
            and any facts from other workers it should use.
    """
    if ctx.deps.delegations >= MAX_DELEGATIONS:
        return f"Refused: delegation limit ({MAX_DELEGATIONS}) reached for this loop. Wrap up."
    ctx.deps.delegations += 1
    return await run_loop(WORKERS[worker], worker, instructions, ctx.deps, usage=ctx.usage)


# ============================================================ 6. running tickets
#
# Each ticket goes through three steps, all started by the human:
#   1. boss_first_pass: the boss reads the ticket and delegates. Payments and
#      discounts can only come out as *pending* approval requests.
#   2. decide: the human approves or rejects each request. Approved payments are
#      executed by the human-only MCP tool, which refuses if cash would go negative.
#   3. boss_follow_up: with the human's decisions, the boss finishes the ticket.

def new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:8]}"


def reset_database(run_id: str = "reset") -> str:
    """Copy the original DB over the working copy (simulation rule 6). The audit trail is kept."""
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    audit_append(event="db_reset", run_id=run_id, agent="runner",
                 output=f"{WORKING_DB.name} restored from {ORIGINAL_DB.name}")
    return str(WORKING_DB)


async def boss_first_pass(ticket_id: int, run_id: str, instructions: str = "") -> BossDecision:
    prompt = (f"Work ticket {ticket_id}. Read it and its case notes, check the cash position and the "
              f"other open tickets, delegate to the right workers, and report back.")
    if instructions.strip():
        prompt += (f"\n\nDoug (the human operator) says: \"{instructions.strip()}\"\n"
                   f"Follow his direction. It answers any question you asked him earlier, but it is not "
                   f"an approval: payments and discounts still need his approval click.")
    return await run_loop(boss_agent, "boss", prompt, RunDeps(run_id=run_id, ticket_id=ticket_id))


async def decide(request_id: int, decision: str, approver: str, note: str, run_id: str) -> dict:
    """Record a human decision and, for an approved payment, pay it. Every step is audited."""
    reqs = (await call_tool("list_approval_requests"))["requests"]
    req = next((r for r in reqs if r["id"] == request_id), None)
    if req is None:
        return {"error": f"No approval request {request_id}."}

    result = await call_tool("human_record_decision", request_id=request_id,
                             decision=decision, approver=approver, note=note)
    outcome = {"request": req, "decision": result}
    if "error" in result:
        return outcome
    audit_append(event="human_decision", run_id=run_id, agent=f"human:{approver}",
                 ticket_id=req["ticket_id"], output=result)

    if result.get("status") == "approved" and req["kind"] == "payment":
        paid = await call_tool("human_execute_payment", request_id=request_id)
        audit_append(event="payment_refused" if "error" in paid else "payment_executed",
                     run_id=run_id, agent=f"human:{approver}", ticket_id=req["ticket_id"], output=paid)
        outcome["payment"] = paid
    return outcome


async def decided_outcomes(ticket_id: int) -> list[dict]:
    """Every human decision on a ticket, rebuilt from the database (survives restarts)."""
    reqs = (await call_tool("list_approval_requests", ticket_id=ticket_id))["requests"]
    payments = (await call_tool("list_payments"))["payments"]
    outcomes = []
    for r in reqs:
        if r["status"] == "pending":
            continue
        outcome = {"request": r, "decision": {"request_id": r["id"], "status": r["status"],
                                              "decided_by": r["decided_by"], "note": r["decision_note"]}}
        if r["kind"] == "payment":
            paid = next((p for p in payments if p["kind"] == r["payment_kind"] and p["ref_id"] == r["ref_id"]), None)
            if paid:
                outcome["payment"] = paid
            elif r["status"] == "refused":
                outcome["payment"] = {"error": "Refused: not enough cash. Nothing was paid."}
        outcomes.append(outcome)
    return outcomes


async def boss_follow_up(ticket_id: int, run_id: str, outcomes: list[dict]) -> BossDecision:
    return await run_loop(
        boss_agent, "boss",
        f"Ticket {ticket_id}: the human operator has made these decisions:\n"
        f"{json.dumps(outcomes, indent=2, default=str)}\n"
        f"Finish the ticket with them: have the right workers act on them, make sure any "
        f"customer gets a draft message, and set the ticket's final status.",
        RunDeps(run_id=run_id, ticket_id=ticket_id),
    )


# ============================================================ 7. FastAPI routes

# One ticket at a time: the team shares one cash account, so runs queue up.
TEAM_LOCK = asyncio.Lock()
RUNS: dict[str, dict] = {}                 # run_id -> status record
TASKS: set[asyncio.Task] = set()           # keep background tasks alive


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with shop_server():              # one MCP server process for the app's lifetime
        yield


app = FastAPI(title="Campus Customs backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # The Vite board (frontend/, `npm run dev`) runs at localhost:5173. Any other
    # localhost port is allowed too (Vite picks the next free one if 5173 is taken).
    # No outside website can call the backend.
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _tool(name: str, **args) -> dict:
    result = await call_tool(name, **args)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return result


def _busy() -> bool:
    return any(r["status"] in {"queued", "running"} for r in RUNS.values())


def _start(kind: str, ticket_id: int, work) -> dict:
    """Queue an agent run in the background and return its status record."""
    run_id = new_run_id()
    record = {"run_id": run_id, "kind": kind, "ticket_id": ticket_id, "status": "queued",
              "queued_at": _now(), "finished_at": None, "decision": None, "error": None}
    RUNS[run_id] = record

    async def job():
        async with TEAM_LOCK:
            record["status"] = "running"
            try:
                audit_append(event="run_started", run_id=run_id, agent="api",
                             ticket_id=ticket_id, prompt=f"{kind} for ticket {ticket_id}")
                decision = await work(run_id)
                record.update(status="finished", decision=decision.model_dump(mode="json"))
                audit_append(event="run_finished", run_id=run_id, agent="api",
                             ticket_id=ticket_id, output={"ticket_status": decision.ticket_status})
            except Exception as exc:
                record.update(status="failed", error=f"{type(exc).__name__}: {exc}")
                try:
                    audit_append(event="run_failed", run_id=run_id, agent="api",
                                 ticket_id=ticket_id, error=record["error"])
                except Exception as audit_exc:      # never leave a run stuck on "running"
                    record["error"] += f" (and the failure couldn't be logged: {audit_exc})"
            finally:
                record["finished_at"] = _now()

    task = asyncio.create_task(job())
    TASKS.add(task)
    task.add_done_callback(TASKS.discard)
    return record


def _summarize(e: dict) -> str:
    """One line on what the agent said or did, for the board."""
    out = e.get("output") or {}
    ev = e["event"]
    if ev == "loop_started":
        return f"{e['agent']} was asked: {e.get('prompt')}"
    if ev == "agent_step":
        tools = ", ".join(c["tool"] for c in e.get("tool_calls", []))
        said = f'"{out}" ' if isinstance(out, str) and out else ""
        return f"{e['agent']} {said}→ calling {tools}" if tools else f"{e['agent']} says {said}"
    if ev == "loop_finished" and isinstance(out, dict):
        said = out.get("message_to_human") or out.get("summary") or ""
        return f"{e['agent']} finished ({len(e.get('tool_calls', []))} tool calls): {said}"
    if ev == "loop_failed":
        return f"{e['agent']} failed: {e.get('error')}"
    if ev == "human_instruction":
        return f"Doug told the boss: {e.get('prompt')}"
    if ev == "human_decision" and isinstance(out, dict):
        return f"{out.get('decided_by')} {out.get('status')} request #{out.get('request_id')}"
    if ev == "payment_executed" and isinstance(out, dict):
        return f"Paid ${out.get('amount'):,.2f}; checking now ${out.get('checking_balance_after'):,.2f}"
    if ev == "payment_refused" and isinstance(out, dict):
        return f"Payment refused: {out.get('error')}"
    return ev.replace("_", " ")


# ---------------------------------------------------------------- tickets

@app.get("/tickets")
async def list_tickets():
    """Every ticket with its status and whether it's open or resolved."""
    data = await _tool("list_tickets")
    return {
        "shop_today": data["shop_today"],
        "tickets": [
            {"id": t["id"], "type": t["type"], "requester": t["requester"], "subject": t["subject"],
             "status": t["status"], "state": t["state"]}
            for t in data["tickets"]
        ],
    }


@app.get("/tickets/{ticket_id}")
async def ticket_detail(ticket_id: int):
    """One ticket with its case notes, approval requests, and message drafts."""
    return {
        "ticket": await _tool("get_ticket", ticket_id=ticket_id),
        "approval_requests": (await _tool("list_approval_requests", ticket_id=ticket_id))["requests"],
        "drafts": (await _tool("list_customer_drafts", ticket_id=ticket_id))["drafts"],
    }


# ---------------------------------------------------------------- run the team

class RunRequest(BaseModel):
    instructions: str = ""       # optional words from Doug to the boss (e.g. an answer to its question)
    approver: str = "Doug"


@app.post("/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int, body: RunRequest | None = None):
    """Doug starts the agent team on one ticket (boss first pass), optionally with
    instructions for the boss. Poll /events or /runs/{run_id}."""
    body = body or RunRequest()
    await _tool("get_ticket", ticket_id=ticket_id)          # 400 if the ticket doesn't exist
    if body.instructions.strip():
        audit_append(event="human_instruction", run_id="human", agent=f"human:{body.approver}",
                     ticket_id=ticket_id, prompt=body.instructions.strip())
    return _start("first_pass", ticket_id, lambda run_id: boss_first_pass(ticket_id, run_id, body.instructions))


@app.get("/runs")
async def list_runs():
    """Every run started since the server came up, newest first."""
    return {"runs": sorted(RUNS.values(), key=lambda r: r["queued_at"], reverse=True), "busy": _busy()}


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Status of one run (queued, running, finished, failed) and the boss's decision."""
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail="Unknown run id (runs are kept in memory).")
    return RUNS[run_id]


# ---------------------------------------------------------------- agent events

@app.get("/events")
async def events(after: int = 0, ticket_id: int | None = None, run_id: str | None = None, limit: int = 200):
    """Audit-trail events after sequence number `after`: what each agent was asked,
    said, and did, and every tool it called. Poll with the last `seq` you saw."""
    entries = []
    if AUDIT_PATH.exists():
        raw = AUDIT_PATH.read_bytes()
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError:            # cut-off file: show every complete entry anyway
            entries, _ = _complete_prefix(raw)
    picked = [
        {**e, "summary": _summarize(e)}
        for e in entries
        if e["seq"] > after
        and (ticket_id is None or e.get("ticket_id") == ticket_id)
        and (run_id is None or e.get("run_id") == run_id)
    ][:limit]
    return {"events": picked, "last_seq": picked[-1]["seq"] if picked else after,
            "total": len(entries), "busy": _busy(), "model": MODEL_NAME}


# ---------------------------------------------------------------- human approvals

class Decision(BaseModel):
    decision: Literal["approve", "reject"]
    approver: str = "Doug"
    note: str = ""
    # Off by default: Doug starts every agent run himself (POST /tickets/{id}/follow_up).
    follow_up: bool = False


@app.get("/approvals")
async def list_approvals(status: str | None = "pending", ticket_id: int | None = None):
    """Payment and price-override requests waiting on the human. Use status=all for every request."""
    if status in ("", "all"):
        status = None
    args = {k: v for k, v in {"status": status, "ticket_id": ticket_id}.items() if v is not None}
    return await _tool("list_approval_requests", **args)


@app.post("/approvals/{request_id}")
async def decide_request(request_id: int, body: Decision):
    """The human's click: approve or reject a request. Approved payments are paid
    immediately (refused if cash is short). This does NOT start any agents; the
    human starts the boss follow-up with POST /tickets/{id}/follow_up."""
    outcome = await decide(request_id, body.decision, body.approver, body.note, run_id=new_run_id())
    if "error" in outcome:
        raise HTTPException(status_code=400, detail=outcome["error"])
    if "error" in outcome["decision"]:
        raise HTTPException(status_code=400, detail=outcome["decision"])

    ticket_id = outcome["request"]["ticket_id"]
    still_pending = (await call_tool("list_approval_requests", ticket_id=ticket_id, status="pending"))["requests"]
    follow_up = _start_follow_up(ticket_id) if body.follow_up and not still_pending else None
    return {**outcome, "still_pending": [r["id"] for r in still_pending], "follow_up_run": follow_up}


def _start_follow_up(ticket_id: int) -> dict:
    async def work(run_id: str):
        return await boss_follow_up(ticket_id, run_id, await decided_outcomes(ticket_id))
    return _start("follow_up", ticket_id, work)


@app.post("/tickets/{ticket_id}/follow_up", status_code=202)
async def follow_up_ticket(ticket_id: int):
    """Human-started: the boss finishes the ticket using every decision Doug made on it
    (read from the database, so it works even after a server restart)."""
    await _tool("get_ticket", ticket_id=ticket_id)
    pending = (await call_tool("list_approval_requests", ticket_id=ticket_id, status="pending"))["requests"]
    if pending:
        raise HTTPException(status_code=409, detail=f"Decide request(s) {[r['id'] for r in pending]} first.")
    if not await decided_outcomes(ticket_id):
        raise HTTPException(status_code=409, detail="No decisions on this ticket yet. Use Run agent team.")
    return _start_follow_up(ticket_id)


# ---------------------------------------------------------------- balance and reset

@app.get("/balance")
async def balance():
    """Current checking balance plus everything competing for it."""
    return await _tool("get_cash_position")


@app.post("/reset")
async def reset():
    """Restore the database to the original values for a fresh run. The audit trail is kept."""
    if _busy():
        raise HTTPException(status_code=409, detail="Agents are running; wait for them to finish.")
    return {"reset": reset_database(), "balance": (await _tool("get_cash_position"))["checking"]}


@app.get("/")
async def root():
    return {"service": "Campus Customs backend", "model": MODEL_NAME, "docs": "/docs"}


# ============================================================ 8. terminal CLI

def _show_request(req: dict) -> None:
    print(f"\n  Request #{req['id']} ({req['kind']}) for ticket {req['ticket_id']}")
    if req["kind"] == "payment":
        print(f"    Pay {req['payment_kind']} {req['ref_id']}: ${req['amount']:,.2f}")
    else:
        print(f"    {req['qty']} x {req['sku']} {req['size']} at ${req['unit_price']:,.2f} (total ${req['amount']:,.2f})")
    print(f"    Requested by {req['requested_by']}: {req['reason']}")


async def terminal_review(ticket_id: int, run_id: str, approver: str) -> list[dict]:
    """Ask the human, in the terminal, to decide every pending request on a ticket."""
    pending = (await call_tool("list_approval_requests", ticket_id=ticket_id, status="pending"))["requests"]
    if not pending:
        return []
    cash = await call_tool("get_cash_position")
    print(f"\n== Human approval needed ({approver}) ==  checking: ${cash['checking']['balance']:,.2f}, "
          f"in flight: ${cash['in_flight_total']:,.2f}")
    outcomes = []
    for req in pending:
        _show_request(req)
        answer = input("    Approve? [y = approve / n = reject / anything else = leave pending]: ").strip().lower()
        if answer not in {"y", "n"}:
            continue
        note = input("    Note (optional): ").strip()
        outcome = await decide(req["id"], "approve" if answer == "y" else "reject", approver, note, run_id)
        if paid := outcome.get("payment"):
            print(f"    -> {paid.get('error') or 'Paid. Checking now $%0.2f' % paid['checking_balance_after']}")
        outcomes.append(outcome)
    return outcomes


def _print_decision(d: BossDecision) -> None:
    print(f"\n== Boss on ticket {d.ticket_id}: {d.ticket_status} ==\n{d.summary}\n\nTo you: {d.message_to_human}")
    for a in d.approvals_needed:
        print(f"  needs approval: #{a.request_id} {a.kind} ${a.amount:,.2f} — {a.why}")


async def work_ticket(ticket_id: int, run_id: str, approvals: str, approver: str) -> BossDecision:
    decision = await boss_first_pass(ticket_id, run_id)
    _print_decision(decision)
    if approvals == "ask" and sys.stdin.isatty():
        outcomes = await terminal_review(ticket_id, run_id, approver)
        if outcomes:
            decision = await boss_follow_up(ticket_id, run_id, outcomes)
            _print_decision(decision)
    return decision


async def _cli_main(args: argparse.Namespace) -> None:
    if args.verify_audit:
        print(audit_verify())
        return
    if args.reset:
        print(f"Reset {reset_database()} from {ORIGINAL_DB.name}.")
        return
    run_id = new_run_id()
    if args.all:
        print(f"Reset {reset_database(run_id)}")
    audit_append(event="run_started", run_id=run_id, agent="runner",
                 prompt=f"tickets={'all' if args.all else args.ticket} approvals={args.approvals}")
    async with shop_server():
        ids = [t["id"] for t in (await call_tool("list_open_tickets"))["tickets"]] if args.all else [args.ticket]
        results = {}
        for tid in ids:
            results[tid] = (await work_ticket(tid, run_id, args.approvals, args.approver)).ticket_status
    audit_append(event="run_finished", run_id=run_id, agent="runner", output=results)


def cli() -> None:
    p = argparse.ArgumentParser(description="Campus Customs agent team (terminal).")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ticket", type=int, help="Work one ticket by id.")
    g.add_argument("--all", action="store_true", help="Reset the DB, then work every open ticket.")
    g.add_argument("--reset", action="store_true", help="Copy the original DB over the working copy and exit.")
    g.add_argument("--verify-audit", action="store_true", help="Check the audit trail's hash chain.")
    p.add_argument("--approvals", choices=["ask", "skip"], default="ask",
                   help="ask = prompt the human in this terminal; skip = leave requests pending.")
    p.add_argument("--approver", default="Doug", help="Name of the human approving requests.")
    asyncio.run(_cli_main(p.parse_args()))


if __name__ == "__main__":
    cli()
