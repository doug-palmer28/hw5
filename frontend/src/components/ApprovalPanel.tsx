import { useState } from "react";
import { AGENT_BY_ROLE, isRole, money } from "../agents";
import { product } from "../plain";
import type { ApprovalRequest, Ticket } from "../types";
import { AgentFigure } from "./AgentFigure";

function describe(r: ApprovalRequest): string {
  if (r.kind === "price_override") {
    return `Sell ${r.qty} of ${product(r.sku)} (size ${r.size}) at ${money(r.unit_price)} each`;
  }
  return r.payment_kind === "rent" ? `Pay this month's shop rent (lease #${r.ref_id})` : `Pay the vendor's bill (invoice #${r.ref_id})`;
}

/** The human-in-the-loop: nothing gets paid or discounted until Doug clicks here. */
export function ApprovalPanel({ approvals, balance, selected, approver, setApprover, onDecide, deciding,
  questionTickets, onOpenTicket }: {
  approvals: ApprovalRequest[];
  balance: number | null;
  selected: number | null;
  approver: string;
  setApprover: (s: string) => void;
  onDecide: (r: ApprovalRequest, d: "approve" | "reject", note: string) => void;
  deciding: number | null;
  questionTickets: Ticket[];
  onOpenTicket: (id: number) => void;
}) {
  const needsYou = approvals.length + questionTickets.length;
  const [notes, setNotes] = useState<Record<number, string>>({});
  const sorted = [...approvals].sort((a, b) => Number(b.ticket_id === selected) - Number(a.ticket_id === selected));

  return (
    <section className={`panel approvals ${needsYou ? "approvals-hot" : ""}`} aria-label="Your approvals">
      <div className="approvals-head">
        <AgentFigure who="human" status={needsYou ? "working" : "idle"} size={0.5} />
        <div>
          <h2>{needsYou ? "Needs you" : "Your approvals"}</h2>
          <label className="approver">
            Approving as <input value={approver} onChange={(e) => setApprover(e.target.value)} aria-label="Your name" />
          </label>
        </div>
        {needsYou > 0 && <span className="count-badge">{needsYou}</span>}
      </div>

      {needsYou === 0 && (
        <p className="muted approvals-empty">
          Nothing is waiting on you. When the team wants to pay a bill or give a discount, or the boss
          has a question, it shows up here. No agent can approve anything on its own.
        </p>
      )}

      {questionTickets.map((t) => (
        <article key={`q${t.id}`} className="request request-question">
          <div className="request-top">
            <span className="request-kind">Question from the boss</span>
            <span className="muted">Ticket {t.id}</span>
          </div>
          <div className="request-what">{t.subject}: the boss needs an answer before it can continue.</div>
          <button className="btn btn-primary" onClick={() => onOpenTicket(t.id)}>Open ticket {t.id} to answer</button>
        </article>
      ))}

      {sorted.map((r) => {
        const after = r.kind === "payment" && balance != null ? balance - r.amount : null;
        const short = after != null && after < 0;
        const by = isRole(r.requested_by) ? AGENT_BY_ROLE[r.requested_by].title : r.requested_by;
        return (
          <article key={r.id} className={`request ${r.ticket_id === selected ? "request-here" : ""}`}>
            <div className="request-top">
              <span className="request-kind">{r.kind === "payment" ? "Payment" : "Price override"}</span>
              <span className="muted">Ticket {r.ticket_id} · #{r.id}</span>
            </div>
            <div className="request-amount">{money(r.amount)}</div>
            <div className="request-what">{describe(r)}</div>
            <p className="request-why"><b>{by}:</b> {r.reason}</p>
            {after != null && (
              <div className={`request-impact ${short ? "is-short" : ""}`}>
                {short
                  ? `Not enough cash: checking has ${money(balance)}. The payment will be refused.`
                  : <>Checking goes <b>{money(balance)}</b> → <b>{money(after)}</b></>}
              </div>
            )}
            {r.kind === "price_override" && (
              <div className="request-impact">No money moves. Approving only sets the price the team may offer the customer.</div>
            )}
            <input
              className="note"
              placeholder="Note (optional)"
              value={notes[r.id] ?? ""}
              onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })}
            />
            <div className="request-actions">
              <button className="btn btn-primary" disabled={deciding != null || !approver.trim()}
                onClick={() => onDecide(r, "approve", notes[r.id] ?? "")}>
                {deciding === r.id ? "Working…" : r.kind === "payment" ? "Approve & pay" : "Approve"}
              </button>
              <button className="btn btn-outline" disabled={deciding != null || !approver.trim()}
                onClick={() => onDecide(r, "reject", notes[r.id] ?? "")}>
                Reject
              </button>
            </div>
          </article>
        );
      })}
    </section>
  );
}
