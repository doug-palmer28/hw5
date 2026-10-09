import type { ApprovalRequest, Ticket } from "../types";

const STATUS_LABEL: Record<string, string> = {
  open: "Open",
  in_progress: "In progress",
  waiting_on_human: "Needs you",
  waiting_on_vendor: "Waiting on vendor",
  resolved: "Resolved",
  declined: "Declined",
};

const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price override",
};

export function TicketList({ tickets, selected, onSelect, approvals, runningTicket }: {
  tickets: Ticket[];
  selected: number | null;
  onSelect: (id: number) => void;
  approvals: ApprovalRequest[];
  runningTicket: number | null;
}) {
  const open = tickets.filter((t) => t.state === "open").length;
  return (
    <section className="panel tickets" aria-label="Tickets">
      <div className="panel-head">
        <h2>Tickets</h2>
        <span className="muted">{open} open · {tickets.length - open} resolved</span>
      </div>
      <ul className="ticket-list">
        {tickets.map((t) => {
          const needsYou = approvals.some((a) => a.ticket_id === t.id);
          const running = runningTicket === t.id;
          return (
            <li key={t.id}>
              <button
                className={`ticket ${selected === t.id ? "is-selected" : ""} ${t.state === "resolved" ? "is-resolved" : ""}`}
                onClick={() => onSelect(t.id)}
                aria-pressed={selected === t.id}
              >
                <span className="ticket-num">{t.id}</span>
                <span className="ticket-main">
                  <span className="ticket-type">{TYPE_LABEL[t.type] ?? t.type}</span>
                  <strong>{t.subject}</strong>
                  <span className="muted">{t.requester}</span>
                  <span className="ticket-tags">
                    <span className={`pill pill-${t.status}`}>{STATUS_LABEL[t.status] ?? t.status}</span>
                    {running && <span className="pill pill-live"><i className="live-dot" />Agents working</span>}
                    {needsYou && t.status !== "waiting_on_human" && <span className="pill pill-waiting_on_human">Needs you</span>}
                  </span>
                </span>
                {t.state === "resolved" && <span className="ticket-check" aria-label="Resolved">✓</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
