import { money } from "../agents";
import type { AuditEvent, Draft } from "../types";

/** Messages customer service wrote. They're drafts and are never sent. */
export function Drafts({ drafts }: { drafts: Draft[] }) {
  return (
    <section className="panel drafts" aria-label="Message drafts">
      <div className="panel-head"><h2>Drafts</h2><span className="muted">never sent</span></div>
      {drafts.length === 0 && <p className="muted">No messages drafted for this ticket yet.</p>}
      {drafts.map((d) => (
        <article key={d.id} className="draft">
          <span className="draft-stamp">Draft · not sent</span>
          <div className="draft-to">To: <b>{d.recipient}</b></div>
          <div className="draft-subject">{d.subject}</div>
          <p>{d.body}</p>
        </article>
      ))}
    </section>
  );
}

/** Money that has actually left the account since the last reset. */
export function Ledger({ events }: { events: AuditEvent[] }) {
  const rows = events.filter((e) => e.event === "payment_executed" || e.event === "payment_refused");
  return (
    <section className="panel ledger" aria-label="Ledger">
      <div className="panel-head"><h2>Ledger</h2><span className="muted">money out</span></div>
      {rows.length === 0 && <p className="muted">No money has gone out yet.</p>}
      <ul>
        {rows.map((e) => {
          const o = e.output ?? {};
          const refused = e.event === "payment_refused";
          return (
            <li key={e.seq} className={refused ? "ledger-refused" : ""}>
              <span>Ticket {e.ticket_id}{!refused && <span className="muted"> · approved by {o.approved_by}</span>}</span>
              <b>{refused ? "Refused" : `−${money(o.amount)}`}</b>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
