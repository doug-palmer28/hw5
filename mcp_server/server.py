"""Campus Customs MCP server.

This is the shop's single tools layer. Every agent on the team (boss,
inventory, accounting, facilities, customer service) reads and changes shop
data only through the tools here, backed by data/campus_customs_new.db.

Tools only report what is in the database; they never make up values. If a
lookup finds nothing, the tool says so instead of guessing. The simulation
rules every agent must follow live here (SIMULATION_RULES), are served as the
`rules://simulation` resource, and are appended to every agent's prompt.

Run modes:
    python mcp_server/server.py           # serve over stdio (the backend does this for you)
    python mcp_server/server.py --smoke   # call tools over MCP, write output/mcp_smoke.json

Safety design (see SIMULATION_RULES):
- Agents can only *request* payments and price overrides. Requests land in
  `approval_requests` as `pending`.
- Only the human-only tools (prefixed `human_`) can approve a request or move
  money. No agent is given those tools, and they refuse agent names as the
  approver.
- `human_execute_payment` refuses rather than let a balance go negative.
- Customer messages are saved as drafts only. There is no tool that sends
  anything outside the simulation.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("CAMPUS_CUSTOMS_DB", ROOT / "data" / "campus_customs_new.db"))

SIMULATION_RULES = """# Campus Customs Simulation Rules

These rules apply to every agent (boss, inventory, accounting, facilities, customer service) and to every developer tool working on this project. They are not optional.

## 1. Today is `desk.date_today`
The shop's "today" is the `date_today` value in the `desk` table (currently `2026-08-31`). Use it for every due date, overdue count, and delivery estimate. Never use the real computer clock.

## 2. Vendors do not ship until they are paid
Each vendor's lead time is `vendors.lead_days`. That countdown only starts once the vendor's invoice is paid. An unpaid vendor ships nothing, so you cannot promise a delivery date while the invoice is unpaid.

## 3. Every payment needs human approval ⚠️ MOST IMPORTANT
No money moves without explicit approval from the human operator (Doug). This includes rent, vendor invoices, and any other payment.
- No agent can approve a payment. That includes the boss.
- An agent may *recommend* a payment, then it must stop and wait for the human's decision.
- Every row in `payments.approved_by` must name the human who approved it, never an agent.
- Going ahead with a payment without human approval is a serious failure of the exercise.

## 4. No negative balances
If an account doesn't have enough cash for a payment, the payment tool must **refuse** and change nothing. A balance can never go below $0. This applies even when a human has approved the payment.

## 5. Money only goes out
In this simulation no money comes in: no customer payments, deposits, or refunds to the shop. Cash only goes down. Plan around the balance as it is now.

## 6. Reset before every full run
Before a full run to resolve the tickets, reset the working database to the original values:

Press **Reset shop** on the board (`POST /reset`), or run `python backend/main.py --reset` with the backend stopped. Both copy `data/campus_customs.db` (the untouched original) over `data/campus_customs_new.db`.

## 7. No outside contact. This is a simulation.
Do not email customers, call or message real vendors or landlords, or contact anyone in any way. The only person agents talk to is the human operator (Doug). "Contacting" a customer or vendor means writing a draft or a record inside the simulation, never actually sending it.

## 8. Don't invent data
Only use facts that are in the database or that the human gives you. If something isn't known, say so. Don't guess prices, stock, dates, or names.
"""

AGENT_ROLES = {"boss", "inventory", "accounting", "facilities", "customer_service"}
TICKET_STATUSES = {
    "open", "in_progress", "waiting_on_human", "waiting_on_vendor", "resolved", "declined",
}
CLOSED_STATUSES = {"resolved", "declined"}

# Tables the original database doesn't have. Created on demand so they come
# back automatically after a reset restores the original file.
EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS case_notes (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    author TEXT NOT NULL,
    note TEXT NOT NULL,
    shop_date TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
CREATE TABLE IF NOT EXISTS approval_requests (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- 'payment' or 'price_override'
    ticket_id INTEGER NOT NULL,
    payment_kind TEXT,               -- 'vendor_invoice' or 'rent' (payments only)
    ref_id INTEGER,                  -- invoice id or lease id (payments only)
    sku TEXT,                        -- price overrides only
    size TEXT,
    qty INTEGER,
    unit_price REAL,
    amount REAL NOT NULL,            -- payment amount, or override order total
    requested_by TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,            -- pending, approved, rejected, paid, refused
    decided_by TEXT,
    decision_note TEXT,
    shop_date TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
CREATE TABLE IF NOT EXISTS customer_drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    author TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft_not_sent',
    shop_date TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
CREATE TABLE IF NOT EXISTS stock_reservations (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    reserved_by TEXT NOT NULL,
    shop_date TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
"""

mcp = FastMCP("campus-customs")


@contextmanager
def _db():
    """Open the working DB, make sure the extra tables exist, commit, close."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(EXTRA_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _shop_today(conn: sqlite3.Connection) -> str:
    """The shop's own 'today' from the desk table (not the real clock)."""
    return conn.execute("SELECT date_today FROM desk").fetchone()["date_today"]


def _checking_balance(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT name, balance, date FROM cash_accounts WHERE name = 'checking'"
    ).fetchone()
    return dict(row) if row else {"error": "No checking account found."}


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _plus_days(start: str, days: int) -> str:
    return (date.fromisoformat(start) + timedelta(days=days)).isoformat()


def _ticket(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()


def _note(conn: sqlite3.Connection, ticket_id: int, author: str, note: str) -> None:
    conn.execute(
        "INSERT INTO case_notes (ticket_id, author, note, shop_date) VALUES (?, ?, ?, ?)",
        (ticket_id, author, note, _shop_today(conn)),
    )


def _bad_role(role: str) -> dict | None:
    if role not in AGENT_ROLES:
        return {"error": f"Unknown agent role '{role}'. Use one of: {sorted(AGENT_ROLES)}."}
    return None


def _rent_paid(conn: sqlite3.Connection, lease_id: int, next_due: str) -> sqlite3.Row | None:
    """The rent payment covering the period that ends at next_due (the month before it), if any."""
    return conn.execute(
        "SELECT id, amount, paid_at, approved_by FROM payments "
        "WHERE kind = 'rent' AND ref_id = ? AND paid_at >= ? ORDER BY id LIMIT 1",
        (lease_id, _plus_days(next_due, -31)),
    ).fetchone()


def _approved_payment_total(conn: sqlite3.Connection) -> float:
    """Payment requests still in flight (pending or approved, not yet paid)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS t FROM approval_requests "
        "WHERE kind = 'payment' AND status IN ('pending', 'approved')"
    ).fetchone()
    return row["t"]


# ---------------------------------------------------------------- resources

@mcp.resource("rules://simulation")
def simulation_rules() -> str:
    """The Campus Customs simulation rules. Every agent must follow them."""
    return SIMULATION_RULES


# ---------------------------------------------------------------- tickets

@mcp.tool
def list_tickets() -> dict:
    """List every ticket (open and closed) with its status, plus the shop's date.

    Each ticket also gets `state`: 'resolved' if its status is resolved or
    declined, otherwise 'open'.
    """
    with _db() as conn:
        rows = conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
        return {
            "shop_today": _shop_today(conn),
            "tickets": [
                {**dict(r), "state": "resolved" if r["status"] in CLOSED_STATUSES else "open"}
                for r in rows
            ],
        }


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket that is not resolved or declined, with the shop's date.

    Use this to see the whole work queue, including how tickets compete for
    the same cash or stock.
    """
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE status NOT IN ('resolved', 'declined') ORDER BY id"
        ).fetchall()
        return {"shop_today": _shop_today(conn), "tickets": [dict(r) for r in rows]}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Show one ticket with every field (type, requester, sku/size/qty, linked
    lease or invoice, status, notes), the shop's date, and its case notes.
    """
    with _db() as conn:
        t = _ticket(conn, ticket_id)
        if not t:
            return {"ticket_id": ticket_id, "error": "No ticket with this id."}
        notes = conn.execute(
            "SELECT author, note, shop_date FROM case_notes WHERE ticket_id = ? ORDER BY id",
            (ticket_id,),
        ).fetchall()
        return {**dict(t), "shop_today": _shop_today(conn), "case_notes": [dict(n) for n in notes]}


@mcp.tool
def update_ticket_status(ticket_id: int, status: str, note: str, updated_by: str) -> dict:
    """Set a ticket's status and record why as a case note.

    Allowed statuses: open, in_progress, waiting_on_human, waiting_on_vendor,
    resolved, declined. A ticket can't be marked resolved while one of its
    approval requests is still pending a human decision.
    """
    if err := _bad_role(updated_by):
        return err
    if status not in TICKET_STATUSES:
        return {"error": f"Status must be one of {sorted(TICKET_STATUSES)}."}
    with _db() as conn:
        if not _ticket(conn, ticket_id):
            return {"ticket_id": ticket_id, "error": "No ticket with this id."}
        if status == "resolved":
            pending = conn.execute(
                "SELECT id FROM approval_requests WHERE ticket_id = ? AND status = 'pending'",
                (ticket_id,),
            ).fetchall()
            if pending:
                return {
                    "error": "Refused: this ticket still has approval requests waiting on a human.",
                    "pending_request_ids": [r["id"] for r in pending],
                }
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        _note(conn, ticket_id, updated_by, f"Status -> {status}: {note}")
        return {"ticket_id": ticket_id, "status": status}


@mcp.tool
def add_case_note(ticket_id: int, author: str, note: str) -> dict:
    """Add a note to a ticket's shared case file so other agents can see it.

    This is how agents share findings with each other (e.g. inventory notes
    the stock count, accounting notes the cash impact).
    """
    if err := _bad_role(author):
        return err
    with _db() as conn:
        if not _ticket(conn, ticket_id):
            return {"ticket_id": ticket_id, "error": "No ticket with this id."}
        _note(conn, ticket_id, author, note)
        return {"ticket_id": ticket_id, "saved": True}


@mcp.tool
def get_case_notes(ticket_id: int) -> dict:
    """Read every note other agents have left on a ticket, oldest first."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, author, note, shop_date FROM case_notes WHERE ticket_id = ? ORDER BY id",
            (ticket_id,),
        ).fetchall()
        return {"ticket_id": ticket_id, "notes": [dict(r) for r in rows]}


# ---------------------------------------------------------------- inventory

@mcp.tool
def check_stock(sku: str) -> dict:
    """Show every size of a product with its quantity on hand, aisle location,
    unit cost, and list price.

    Use for customer orders (can we fill it from stock?) and price overrides
    (how many are on hand, and what is the cost floor for a discount?).
    """
    with _db() as conn:
        sizes = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ?",
            (sku,),
        ).fetchall()
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()

    if not sizes:
        return {"sku": sku, "error": "No inventory rows for this SKU."}

    return {
        "sku": sku,
        "name": sizes[0]["name"],
        "sizes": [
            {"size": r["size"], "qty": r["qty"], "location": r["location"]}
            for r in sizes
        ],
        "total_qty": sum(r["qty"] for r in sizes),
        "unit_cost": price["unit_cost"] if price else None,
        "list_price": price["list_price"] if price else None,
    }


@mcp.tool
def reserve_stock(ticket_id: int, sku: str, size: str, qty: int, reserved_by: str) -> dict:
    """Take units off the shelf for a ticket (lowers inventory.qty).

    Refuses if there isn't enough stock in that size. For a price_override
    ticket, refuses unless a human has approved a price override for it.
    """
    if err := _bad_role(reserved_by):
        return err
    if qty <= 0:
        return {"error": "qty must be positive."}
    with _db() as conn:
        t = _ticket(conn, ticket_id)
        if not t:
            return {"ticket_id": ticket_id, "error": "No ticket with this id."}
        if t["type"] == "price_override":
            ok = conn.execute(
                "SELECT id FROM approval_requests WHERE ticket_id = ? AND kind = 'price_override' "
                "AND status = 'approved'",
                (ticket_id,),
            ).fetchone()
            if not ok:
                return {"error": "Refused: no human-approved price override for this ticket yet."}
        row = conn.execute(
            "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        if not row:
            return {"error": f"No inventory row for {sku} size {size}."}
        if row["qty"] < qty:
            return {
                "error": "Refused: not enough stock.",
                "sku": sku, "size": size, "on_hand": row["qty"], "requested": qty,
            }
        conn.execute(
            "UPDATE inventory SET qty = qty - ? WHERE sku = ? AND size = ?", (qty, sku, size)
        )
        today = _shop_today(conn)
        conn.execute(
            "INSERT INTO stock_reservations (ticket_id, sku, size, qty, reserved_by, shop_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, sku, size, qty, reserved_by, today),
        )
        _note(conn, ticket_id, reserved_by, f"Reserved {qty} x {sku} size {size}.")
        return {"reserved": qty, "sku": sku, "size": size, "on_hand_after": row["qty"] - qty}


@mcp.tool
def list_vendors() -> dict:
    """List every vendor with its specialty and lead time in days.

    Lead time only starts once the vendor is paid (vendors don't ship unpaid).
    """
    with _db() as conn:
        rows = conn.execute("SELECT * FROM vendors ORDER BY id").fetchall()
        return {"vendors": [dict(r) for r in rows]}


# ---------------------------------------------------------------- money (read)

@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Show a vendor invoice with the vendor's name, specialty, and lead time,
    how many days overdue it is as of the shop's date, the earliest arrival
    date if it were paid today, and the current checking balance.

    Use when a ticket is linked to an invoice (for example, a customer order
    waiting on a reprint) or when accounting needs to decide whether to pay it.
    """
    with _db() as conn:
        inv = conn.execute(
            """SELECT i.id, i.amount, i.due_date, i.status, i.description,
                      v.id AS vendor_id, v.name AS vendor_name,
                      v.specialty AS vendor_specialty, v.lead_days AS vendor_lead_days
               FROM invoices i JOIN vendors v ON v.id = i.vendor_id
               WHERE i.id = ?""",
            (invoice_id,),
        ).fetchone()
        if not inv:
            return {"invoice_id": invoice_id, "error": "No invoice with this id."}
        today = _shop_today(conn)
        checking = _checking_balance(conn)

        paid = conn.execute(
            "SELECT id, paid_at, approved_by FROM payments WHERE kind = 'vendor_invoice' AND ref_id = ? "
            "ORDER BY id LIMIT 1", (invoice_id,),
        ).fetchone()

    overdue = _days_between(inv["due_date"], today)
    out = {
        **dict(inv),
        "shop_today": today,
        "days_overdue": max(overdue, 0) if inv["status"] != "paid" else 0,
        "checking": checking,
    }
    if inv["status"] != "paid":
        out["vendor_ships"] = "only after this invoice is paid"
        out["earliest_arrival_if_paid_today"] = _plus_days(today, inv["vendor_lead_days"])
    elif paid:
        out["paid"] = {"payment_id": paid["id"], "paid_at": paid["paid_at"], "approved_by": paid["approved_by"]}
        out["expected_arrival"] = _plus_days(paid["paid_at"], inv["vendor_lead_days"])
        out["arrived"] = today >= out["expected_arrival"]
    return out


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Show a lease's space, landlord, monthly rent, and next due date, how
    many days remain until rent is due as of the shop's date, any rent already
    paid on it, and the current checking balance.

    Use to verify a rent notice against the actual lease before paying it.
    """
    with _db() as conn:
        lease = conn.execute(
            """SELECT id, space_name, landlord, monthly_rent, next_due, notes
               FROM leases WHERE id = ?""",
            (lease_id,),
        ).fetchone()
        if not lease:
            return {"lease_id": lease_id, "error": "No lease with this id."}
        today = _shop_today(conn)
        checking = _checking_balance(conn)
        paid = conn.execute(
            "SELECT * FROM payments WHERE kind = 'rent' AND ref_id = ? ORDER BY id", (lease_id,)
        ).fetchall()

    return {
        **dict(lease),
        "shop_today": today,
        "days_until_due": _days_between(today, lease["next_due"]),
        "rent_payments_recorded": [dict(p) for p in paid],
        "checking": checking,
    }


@mcp.tool
def get_cash_position() -> dict:
    """Show the checking balance next to everything competing for it: unpaid
    vendor invoices, rent that is still unpaid for the current period, and
    payment requests already pending or approved. Rent already paid for the
    period is shown separately so it is never counted as still due. Returns
    what would be left if every pending/approved request were paid.

    Use before recommending any payment, because tickets share one account
    and no money comes in during the simulation.
    """
    with _db() as conn:
        today = _shop_today(conn)
        checking = _checking_balance(conn)
        invoices = conn.execute(
            """SELECT i.id, v.name AS vendor, i.amount, i.due_date, i.description
               FROM invoices i JOIN vendors v ON v.id = i.vendor_id
               WHERE i.status != 'paid' ORDER BY i.due_date"""
        ).fetchall()
        rent_due, rent_paid = [], []
        for lease in conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due FROM leases ORDER BY next_due"
        ).fetchall():
            paid = _rent_paid(conn, lease["id"], lease["next_due"])
            if paid:
                rent_paid.append({**dict(lease), "paid_at": paid["paid_at"], "payment_id": paid["id"],
                                  "approved_by": paid["approved_by"]})
            else:
                rent_due.append(dict(lease))
        requests = conn.execute(
            "SELECT id, ticket_id, payment_kind, ref_id, amount, status FROM approval_requests "
            "WHERE kind = 'payment' AND status IN ('pending', 'approved')"
        ).fetchall()
        committed = _approved_payment_total(conn)
        paid_out = conn.execute("SELECT COALESCE(SUM(amount), 0) AS t FROM payments").fetchone()["t"]

    balance = checking.get("balance")
    return {
        "shop_today": today,
        "checking": checking,
        "money_coming_in": "none (simulation rule: funds only go out)",
        "paid_out_so_far": paid_out,
        "unpaid_invoices": [dict(r) for r in invoices],
        "rent_still_due": rent_due,
        "rent_already_paid_this_period": rent_paid,
        "payment_requests_in_flight": [dict(r) for r in requests],
        "in_flight_total": committed,
        "balance_if_in_flight_paid": None if balance is None else balance - committed,
    }


@mcp.tool
def list_payments() -> dict:
    """List every payment already made, with who approved it."""
    with _db() as conn:
        rows = conn.execute("SELECT * FROM payments ORDER BY id").fetchall()
        return {"payments": [dict(r) for r in rows]}


@mcp.tool
def quote_price(sku: str, qty: int, unit_price: float) -> dict:
    """Work out an order total at a given unit price and compare it to the
    product's unit cost and list price. Does not change anything.

    Use to check whether a proposed discount stays above cost before
    recommending it.
    """
    if qty <= 0:
        return {"error": "qty must be positive."}
    with _db() as conn:
        p = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
    if not p:
        return {"sku": sku, "error": "No pricing for this SKU."}
    return {
        "sku": sku,
        "qty": qty,
        "unit_price": unit_price,
        "unit_cost": p["unit_cost"],
        "list_price": p["list_price"],
        "discount_pct_off_list": round(100 * (1 - unit_price / p["list_price"]), 2),
        "order_total": round(unit_price * qty, 2),
        "order_total_at_list": round(p["list_price"] * qty, 2),
        "margin_per_unit": round(unit_price - p["unit_cost"], 2),
        "below_cost": unit_price < p["unit_cost"],
    }


# ---------------------------------------------------------------- requests (agents)

@mcp.tool
def request_payment(
    ticket_id: int, payment_kind: str, ref_id: int, requested_by: str, reason: str
) -> dict:
    """Ask the human to approve a payment. This does NOT move any money.

    payment_kind is 'vendor_invoice' (ref_id = invoice id) or 'rent'
    (ref_id = lease id). The amount is taken from the invoice or lease in the
    database. Agents cannot set it. Creates a 'pending' approval request and
    shows whether cash would cover it.
    """
    if err := _bad_role(requested_by):
        return err
    with _db() as conn:
        if not _ticket(conn, ticket_id):
            return {"ticket_id": ticket_id, "error": "No ticket with this id."}
        if payment_kind == "vendor_invoice":
            row = conn.execute("SELECT amount, status FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if not row:
                return {"error": f"No invoice {ref_id}."}
            if row["status"] == "paid":
                return {"error": f"Invoice {ref_id} is already paid."}
            amount = row["amount"]
        elif payment_kind == "rent":
            row = conn.execute(
                "SELECT monthly_rent, next_due FROM leases WHERE id = ?", (ref_id,)
            ).fetchone()
            if not row:
                return {"error": f"No lease {ref_id}."}
            # Rent already paid for this period (within the month before next_due)?
            paid = _rent_paid(conn, ref_id, row["next_due"])
            if paid:
                return {"error": f"Rent for lease {ref_id} due {row['next_due']} is already paid "
                                 f"(payment #{paid['id']} on {paid['paid_at']})."}
            amount = row["monthly_rent"]
        else:
            return {"error": "payment_kind must be 'vendor_invoice' or 'rent'."}

        dup = conn.execute(
            "SELECT id, status FROM approval_requests WHERE kind = 'payment' AND payment_kind = ? "
            "AND ref_id = ? AND status IN ('pending', 'approved')",
            (payment_kind, ref_id),
        ).fetchone()
        if dup:
            return {"error": "A request for this payment already exists.", "request_id": dup["id"],
                    "status": dup["status"]}

        balance = _checking_balance(conn).get("balance", 0)
        committed = _approved_payment_total(conn)
        cur = conn.execute(
            "INSERT INTO approval_requests (kind, ticket_id, payment_kind, ref_id, amount, "
            "requested_by, reason, status, shop_date) VALUES ('payment', ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (ticket_id, payment_kind, ref_id, amount, requested_by, reason, _shop_today(conn)),
        )
        _note(conn, ticket_id, requested_by,
              f"Requested human approval for {payment_kind} {ref_id}: ${amount:,.2f}.")
        return {
            "request_id": cur.lastrowid,
            "status": "pending",
            "amount": amount,
            "checking_balance": balance,
            "other_requests_in_flight": committed,
            "balance_if_all_in_flight_paid": balance - committed - amount,
            "covered_by_cash": balance - committed - amount >= 0,
            "next_step": "Wait for a human decision. No agent can approve or pay this.",
        }


@mcp.tool
def request_price_override(
    ticket_id: int, sku: str, size: str, qty: int, unit_price: float,
    requested_by: str, reason: str,
) -> dict:
    """Ask the human to approve a non-list price for an order.

    Refuses outright if unit_price is below the product's unit cost. Creates a
    'pending' approval request; the price is not usable until a human approves.
    """
    if err := _bad_role(requested_by):
        return err
    if qty <= 0:
        return {"error": "qty must be positive."}
    with _db() as conn:
        if not _ticket(conn, ticket_id):
            return {"ticket_id": ticket_id, "error": "No ticket with this id."}
        p = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if not p:
            return {"error": f"No pricing for {sku}."}
        if unit_price < p["unit_cost"]:
            return {"error": f"Refused: ${unit_price:.2f} is below unit cost ${p['unit_cost']:.2f}."}
        if unit_price >= p["list_price"]:
            return {"error": "That's not a discount; list price needs no override."}
        total = round(unit_price * qty, 2)
        cur = conn.execute(
            "INSERT INTO approval_requests (kind, ticket_id, sku, size, qty, unit_price, amount, "
            "requested_by, reason, status, shop_date) "
            "VALUES ('price_override', ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (ticket_id, sku, size, qty, unit_price, total, requested_by, reason, _shop_today(conn)),
        )
        _note(conn, ticket_id, requested_by,
              f"Requested human approval for price override: {qty} x {sku} {size} at ${unit_price:.2f}.")
        return {
            "request_id": cur.lastrowid,
            "status": "pending",
            "order_total": total,
            "order_total_at_list": round(p["list_price"] * qty, 2),
            "next_step": "Wait for a human decision. No agent can approve this.",
        }


@mcp.tool
def list_approval_requests(ticket_id: int | None = None, status: str | None = None) -> dict:
    """List payment and price-override requests, optionally for one ticket or
    one status (pending, approved, rejected, paid, refused).
    """
    sql, args = "SELECT * FROM approval_requests WHERE 1=1", []
    if ticket_id is not None:
        sql, args = sql + " AND ticket_id = ?", args + [ticket_id]
    if status is not None:
        sql, args = sql + " AND status = ?", args + [status]
    with _db() as conn:
        rows = conn.execute(sql + " ORDER BY id", args).fetchall()
        return {"requests": [dict(r) for r in rows]}


@mcp.tool
def draft_customer_message(
    ticket_id: int, recipient: str, subject: str, body: str, author: str
) -> dict:
    """Save a message to a customer, landlord, or vendor as a DRAFT.

    Nothing is ever sent. This is a simulation and there is no send tool.
    The human can read the drafts.
    """
    if err := _bad_role(author):
        return err
    with _db() as conn:
        if not _ticket(conn, ticket_id):
            return {"ticket_id": ticket_id, "error": "No ticket with this id."}
        cur = conn.execute(
            "INSERT INTO customer_drafts (ticket_id, recipient, subject, body, author, shop_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, recipient, subject, body, author, _shop_today(conn)),
        )
        _note(conn, ticket_id, author, f"Drafted message to {recipient} (draft #{cur.lastrowid}, not sent).")
        return {"draft_id": cur.lastrowid, "status": "draft_not_sent"}


@mcp.tool
def list_customer_drafts(ticket_id: int | None = None) -> dict:
    """List saved message drafts (never sent), optionally for one ticket."""
    sql, args = "SELECT * FROM customer_drafts", []
    if ticket_id is not None:
        sql, args = sql + " WHERE ticket_id = ?", [ticket_id]
    with _db() as conn:
        rows = conn.execute(sql + " ORDER BY id", args).fetchall()
        return {"drafts": [dict(r) for r in rows]}


# ---------------------------------------------------------------- human-only

@mcp.tool
def human_record_decision(request_id: int, decision: str, approver: str, note: str = "") -> dict:
    """HUMAN ONLY. Approve or reject a pending payment or price-override request.

    No agent is given this tool. The approver must be a person's name, not an
    agent role. decision is 'approve' or 'reject'.
    """
    name = approver.strip()
    if not name or name.lower().replace(" ", "_") in AGENT_ROLES or "agent" in name.lower():
        return {"error": "Refused: approver must be the human operator, not an agent."}
    if decision not in {"approve", "reject"}:
        return {"error": "decision must be 'approve' or 'reject'."}
    with _db() as conn:
        req = conn.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,)).fetchone()
        if not req:
            return {"error": f"No approval request {request_id}."}
        if req["status"] != "pending":
            return {"error": f"Request {request_id} is already {req['status']}."}
        status = "approved" if decision == "approve" else "rejected"
        conn.execute(
            "UPDATE approval_requests SET status = ?, decided_by = ?, decision_note = ? WHERE id = ?",
            (status, name, note, request_id),
        )
        conn.execute(
            "INSERT INTO case_notes (ticket_id, author, note, shop_date) VALUES (?, ?, ?, ?)",
            (req["ticket_id"], f"human:{name}",
             f"Request {request_id} {status}." + (f" {note}" if note else ""), _shop_today(conn)),
        )
        return {"request_id": request_id, "status": status, "decided_by": name}


@mcp.tool
def human_execute_payment(request_id: int) -> dict:
    """HUMAN ONLY. Pay a request that a human has approved.

    Refuses if the request isn't approved, or if checking doesn't have enough
    cash (the balance can never go negative). On success it writes a payments
    row (approved_by = the human), lowers the checking balance, and marks a
    vendor invoice as paid.
    """
    with _db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        req = conn.execute(
            "SELECT * FROM approval_requests WHERE id = ? AND kind = 'payment'", (request_id,)
        ).fetchone()
        if not req:
            return {"error": f"No payment request {request_id}."}
        if req["status"] != "approved" or not req["decided_by"]:
            return {"error": f"Refused: request {request_id} is '{req['status']}', not human-approved."}
        balance = _checking_balance(conn).get("balance", 0)
        today = _shop_today(conn)
        if balance < req["amount"]:
            conn.execute(
                "UPDATE approval_requests SET status = 'refused', decision_note = "
                "COALESCE(decision_note, '') || ' [refused: insufficient funds]' WHERE id = ?",
                (request_id,),
            )
            conn.execute(
                "INSERT INTO case_notes (ticket_id, author, note, shop_date) VALUES (?, ?, ?, ?)",
                (req["ticket_id"], "system",
                 f"Payment request {request_id} refused: needs ${req['amount']:,.2f}, "
                 f"checking has ${balance:,.2f}.", today),
            )
            return {"error": "Refused: not enough cash. Nothing was paid.",
                    "needed": req["amount"], "checking_balance": balance}

        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES (?, ?, ?, 'checking', ?, ?)",
            (req["payment_kind"], req["ref_id"], req["amount"], today, req["decided_by"]),
        )
        conn.execute(
            "UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = 'checking'",
            (req["amount"], today),
        )
        if req["payment_kind"] == "vendor_invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
        conn.execute("UPDATE approval_requests SET status = 'paid' WHERE id = ?", (request_id,))
        conn.execute(
            "INSERT INTO case_notes (ticket_id, author, note, shop_date) VALUES (?, ?, ?, ?)",
            (req["ticket_id"], "system",
             f"Paid ${req['amount']:,.2f} ({req['payment_kind']} {req['ref_id']}), "
             f"approved by {req['decided_by']}. Payment #{cur.lastrowid}.", today),
        )
        return {
            "payment_id": cur.lastrowid,
            "amount": req["amount"],
            "approved_by": req["decided_by"],
            "paid_at": today,
            "checking_balance_after": balance - req["amount"],
        }


# ---------------------------------------------------------------- smoke test (Problem 4)

# Each test: the plain-English prompt a coder or agent would give, and the tool
# call it should lead to. Arguments come from the open tickets in the DB.
SMOKE_TESTS = [
    {"prompt": "Ticket 101: Tauhid Zaman wants one Classic Bulldog Tee in size S. Do we have it in stock?",
     "tool": "check_stock", "arguments": {"sku": "CC-TEE-WHITE"}},
    {"prompt": "Ticket 103: Yale AI Club wants 20 Basic Hoodies in size M at a bulk discount. How many do we have, and what do they cost us?",
     "tool": "check_stock", "arguments": {"sku": "CC-HOOD-NAVY"}},
    {"prompt": "Ticket 101 is linked to invoice 501. What is that invoice, who is the vendor, and is it overdue?",
     "tool": "get_invoice", "arguments": {"invoice_id": 501}},
    {"prompt": "Ticket 102: Elm City Properties says rent is due in 2 days. Check lease 1 and confirm the amount and due date.",
     "tool": "get_lease", "arguments": {"lease_id": 1}},
    {"prompt": "Check stock for SKU CC-FAKE-123.", "tool": "check_stock", "arguments": {"sku": "CC-FAKE-123"},
     "note": "Negative test: an unknown SKU should return an error, not made-up data."},
]


async def _smoke() -> None:
    """Start this server as a real MCP subprocess, call tools over the protocol,
    and save the prompt, tool name, arguments, and output to output/mcp_smoke.json."""
    import json
    import sys
    from datetime import datetime, timezone

    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    env = {k: os.environ[k] for k in ("CAMPUS_CUSTOMS_DB",) if k in os.environ}
    transport = StdioTransport(command=sys.executable, args=[str(Path(__file__).resolve())],
                               cwd=str(ROOT), env=env or None)
    async with Client(transport) as client:
        tools = [t.name for t in await client.list_tools()]
        resources = [str(r.uri) for r in await client.list_resources()]
        results = []
        for test in SMOKE_TESTS:
            res = await client.call_tool(test["tool"], test["arguments"], raise_on_error=False)
            results.append({**test, "is_error": res.is_error,
                            "output": res.structured_content if res.structured_content is not None
                            else [c.text for c in res.content]})
        rules = await client.read_resource("rules://simulation")
        results.append({"prompt": "What are the simulation rules every agent must follow?",
                        "resource": "rules://simulation",
                        "output_first_line": rules[0].text.splitlines()[0],
                        "output_chars": len(rules[0].text)})

    out = ROOT / "output" / "mcp_smoke.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "server": "campus-customs (launched over stdio by `python mcp_server/server.py --smoke`)",
        "tools_listed": tools,
        "resources_listed": resources,
        "tests": results,
    }, indent=2))
    print(f"Saved {len(results)} results to output/mcp_smoke.json ({len(tools)} tools listed).")


if __name__ == "__main__":
    import sys

    if "--smoke" in sys.argv:
        import asyncio
        asyncio.run(_smoke())
    else:
        mcp.run(show_banner=False)
