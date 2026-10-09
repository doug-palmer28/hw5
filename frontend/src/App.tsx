import { useEffect, useMemo, useState } from "react";
import { api, ApiError, API_URL } from "./api";
import { money } from "./agents";
import { teamView } from "./teamState";
import { useDesk } from "./useDesk";
import type { ApprovalRequest, RunRecord } from "./types";
import { TicketList } from "./components/TicketList";
import { TeamFloor } from "./components/TeamFloor";
import { LiveFeed } from "./components/LiveFeed";
import { AgentSummaries } from "./components/AgentSummaries";
import { ApprovalPanel } from "./components/ApprovalPanel";
import { BalanceCard } from "./components/BalanceCard";
import { Drafts, Ledger } from "./components/SidePanels";
import { NextStep } from "./components/NextStep";
import { product } from "./plain";

type Toast = { id: number; text: string; tone: "info" | "good" | "bad" };

const STATUS_LABEL: Record<string, string> = {
  open: "Open", in_progress: "In progress", waiting_on_human: "Waiting on you",
  waiting_on_vendor: "Waiting on vendor", resolved: "Resolved", declined: "Declined",
};

export default function App() {
  // `?ticket=102` opens the board on that ticket (handy for links and screenshots).
  const [selected, setSelected] = useState<number | null>(() => {
    const t = Number(new URLSearchParams(window.location.search).get("ticket"));
    return Number.isInteger(t) && t > 0 ? t : null;
  });
  const desk = useDesk(selected);
  const [watching, setWatching] = useState<RunRecord | null>(null);
  const [deciding, setDeciding] = useState<number | null>(null);
  const [approver, setApprover] = useState(() => localStorage.getItem("approver") ?? "Doug");
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => localStorage.setItem("approver", approver), [approver]);

  const toast = (text: string, tone: Toast["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, tone }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5200);
  };

  // Default to the first open ticket.
  useEffect(() => {
    if (selected == null && desk.tickets.length) {
      setSelected((desk.tickets.find((t) => t.state === "open") ?? desk.tickets[0]).id);
    }
  }, [desk.tickets, selected]);

  // Follow the run we started via GET /runs/{run_id} until it ends.
  const { refreshNow } = desk;
  useEffect(() => {
    if (!watching || watching.status === "finished" || watching.status === "failed") return;
    const id = window.setInterval(async () => {
      try {
        const r = await api.run(watching.run_id);
        setWatching(r);
        if (r.status === "finished") {
          toast(`Ticket ${r.ticket_id}: boss set it to "${STATUS_LABEL[r.decision?.ticket_status ?? ""] ?? r.decision?.ticket_status}".`, "good");
          refreshNow();
        } else if (r.status === "failed") {
          toast(`Run failed: ${r.error}`, "bad");
          refreshNow();
        }
      } catch { /* keep trying */ }
    }, 1000);
    return () => window.clearInterval(id);
  }, [watching, refreshNow]);

  const ticketEvents = useMemo(() => desk.events.filter((e) => e.ticket_id === selected), [desk.events, selected]);
  const liveRunIds = useMemo(
    () => new Set(desk.runs.filter((r) => r.status === "queued" || r.status === "running").map((r) => r.run_id)),
    [desk.runs],
  );
  const team = useMemo(() => teamView(ticketEvents, liveRunIds), [ticketEvents, liveRunIds]);
  const ticket = desk.tickets.find((t) => t.id === selected) ?? null;
  const detail = desk.detail?.ticket.id === selected ? desk.detail : null;
  const activeRun = desk.runs.find((r) => r.status === "running" || r.status === "queued") ?? null;
  const lastRunHere = desk.runs.find((r) => r.ticket_id === selected) ?? null;
  const paidOut = desk.events
    .filter((e) => e.event === "payment_executed")
    .reduce((s, e) => s + (e.output?.amount ?? 0), 0);

  async function run(instructions = "") {
    if (selected == null) return;
    try {
      const r = await api.runTicket(selected, instructions);
      setWatching(r);
      toast(instructions.trim() ? `Sent your message to the boss on ticket ${selected}.` : `The team is starting on ticket ${selected}.`);
      desk.refreshNow();
    } catch (e) {
      toast((e as ApiError).message, "bad");
    }
  }

  async function finish() {
    if (selected == null) return;
    try {
      const r = await api.followUp(selected);
      setWatching(r);
      toast(`The boss is wrapping up ticket ${selected} with your decision…`);
      desk.refreshNow();
    } catch (e) {
      toast((e as ApiError).message, "bad");
    }
  }

  async function decide(r: ApprovalRequest, d: "approve" | "reject", note: string) {
    setDeciding(r.id);
    try {
      const res = await api.decide(r.id, d, approver.trim(), note);
      if (res.payment?.error) toast(`The payment was refused, so nothing was paid: ${res.payment.error}`, "bad");
      else if (res.payment) toast(`Paid ${money(res.payment.amount)}. Checking is now ${money(res.payment.checking_balance_after)}.`, "good");
      else toast(`You ${res.decision.status} the ${r.kind === "payment" ? "payment" : "discount"}.`, "good");
      if (res.still_pending.length === 0) {
        setSelected(r.ticket_id);
        toast(`Next: press "Finish ticket" on ticket ${r.ticket_id} so the boss can act on your decision.`);
      }
      await desk.refreshNow();
    } catch (e) {
      toast((e as ApiError).message, "bad");
    } finally {
      setDeciding(null);
    }
  }

  async function reset() {
    if (!window.confirm("Reset the shop database to the original values? (The audit trail is kept.)")) return;
    try {
      const r = await api.reset();
      toast(`Fresh start: checking back to ${money(r.balance.balance)}.`, "good");
      setWatching(null);
      await desk.refreshNow();
    } catch (e) {
      toast((e as ApiError).message, "bad");
    }
  }

  const resolved = ticket?.state === "resolved";
  const workingHere = activeRun?.ticket_id === selected;
  const pendingHere = desk.approvals.filter((a) => a.ticket_id === selected);
  // Tickets where the boss asked Doug a question (needs you, but no approval card to click).
  const questionTickets = desk.tickets.filter((t) =>
    t.status === "waiting_on_human" && !desk.approvals.some((a) => a.ticket_id === t.id)
    && activeRun?.ticket_id !== t.id);

  return (
    <>
      <div className="announce">
        <span><b>Campus Customs agent desk</b></span>
        <span>Shop date {desk.shopToday || "…"}</span>
        <span>Model {desk.model}</span>
        <span className={`conn ${desk.online === false ? "conn-off" : ""}`}>
          <i className="live-dot" />{desk.online === false ? `Backend offline (${API_URL})` : desk.busy ? "Agents working" : "Live"}
        </span>
      </div>

      <header className="masthead">
        <div className="brand">
          <div className="wordmark">Campus Customs</div>
          <h1>Agent Desk</h1>
          <p>Pick a ticket, send in the team, and approve anything that costs money.</p>
        </div>
        <BalanceCard cash={desk.cash} paidOut={paidOut} />
        <button className="btn btn-outline reset" onClick={reset} disabled={desk.busy}>Reset shop</button>
      </header>

      {desk.online === false && (
        <div className="offline">
          Can't reach the backend. Start it from <code>Homework 5/backend</code>: <code>uvicorn main:app --reload --port 8000</code>
        </div>
      )}

      <main className="layout">
        <TicketList tickets={desk.tickets} selected={selected} onSelect={setSelected}
          approvals={desk.approvals} runningTicket={activeRun?.ticket_id ?? null} />

        <div className="center">
          {ticket && (
            <section className={`ticket-head ${resolved ? "is-resolved" : ""}`}>
              <div className="ticket-head-num">{ticket.id}</div>
              <div className="ticket-head-body">
                <span className="eyebrow">{ticket.type.replace("_", " ")} · from {ticket.requester}</span>
                <h2>{ticket.subject}</h2>
                {detail?.ticket.notes && <p className="ticket-quote">“{detail.ticket.notes}”</p>}
                <div className="ticket-facts">
                  {detail?.ticket.sku && <span>{detail.ticket.qty} × {product(detail.ticket.sku)}, size {detail.ticket.size}</span>}
                  {detail?.ticket.invoice_id && <span>Linked bill: invoice #{detail.ticket.invoice_id}</span>}
                  {detail?.ticket.lease_id && <span>Linked lease #{detail.ticket.lease_id}</span>}
                  <span className={`pill pill-${ticket.status}`}>{STATUS_LABEL[ticket.status] ?? ticket.status}</span>
                </div>
              </div>
              <div className="ticket-head-cta">
                {resolved ? (
                  <div className="stamp">Resolved ✓</div>
                ) : workingHere ? (
                  <div className="working-tag"><i className="live-dot" />Team at work</div>
                ) : null}
                {lastRunHere && (
                  <span className="run-line">
                    Last {lastRunHere.kind === "follow_up" ? "wrap-up" : "look"}: {
                      { queued: "waiting its turn", running: "in progress", finished: "finished", failed: "stopped with a problem" }[lastRunHere.status]}
                  </span>
                )}
              </div>
            </section>
          )}

          {ticket && (
            <NextStep ticket={ticket} events={ticketEvents} pending={pendingHere} working={workingHere}
              busy={desk.busy} onRun={run} onFinish={finish} />
          )}

          <TeamFloor team={team} />

          <section className="panel">
            <div className="panel-head">
              <h2>Live feed</h2>
              <span className="muted">{ticketEvents.length} events on this ticket</span>
            </div>
            <LiveFeed events={ticketEvents} />
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>What each agent did</h2>
              <span className="muted">summaries and tools used on ticket {selected}</span>
            </div>
            <AgentSummaries team={team} />
          </section>
        </div>

        <aside className="rail">
          <ApprovalPanel approvals={desk.approvals} balance={desk.cash?.checking.balance ?? null}
            selected={selected} approver={approver} setApprover={setApprover}
            onDecide={decide} deciding={deciding}
            questionTickets={questionTickets} onOpenTicket={setSelected} />
          <Ledger events={desk.events} />
          <Drafts drafts={detail?.drafts ?? []} />
        </aside>
      </main>

      <footer className="foot">
        Campus Customs · Homework 5 · Every agent loop is recorded in <code>output/audit_trail.json</code>. Nothing is sent outside this simulation.
      </footer>

      <div className="toasts" role="status">
        {toasts.map((t) => <div key={t.id} className={`toast toast-${t.tone}`}>{t.text}</div>)}
      </div>
    </>
  );
}
