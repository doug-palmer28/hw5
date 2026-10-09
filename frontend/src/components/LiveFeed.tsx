import { useEffect, useRef } from "react";
import { AGENT_BY_ROLE, HUMAN_COLOR, isRole, money } from "../agents";
import { statusWords } from "../plain";
import { stepText } from "../teamState";
import type { AuditEvent } from "../types";

const SHOWN = new Set([
  "loop_started", "agent_step", "loop_finished", "loop_failed", "human_instruction",
  "human_decision", "payment_executed", "payment_refused", "run_started",
]);

function who(e: AuditEvent): { label: string; color: string } {
  if (isRole(e.agent)) return { label: AGENT_BY_ROLE[e.agent].title, color: AGENT_BY_ROLE[e.agent].color };
  if (e.agent.startsWith("human:")) return { label: "You", color: HUMAN_COLOR };
  return { label: "Desk", color: "#949494" };
}

function line(e: AuditEvent): string {
  const out = e.output ?? {};
  switch (e.event) {
    case "loop_started":
      if (e.agent !== "boss") return `Picked up a task from the boss: "${e.prompt ?? ""}"`;
      if (e.prompt?.startsWith("Ticket")) return "Picked the ticket back up to act on your decision.";
      if (e.prompt?.includes("Doug (the human operator) says")) return "Picked the ticket back up with your message.";
      return "Picked up the ticket.";
    case "agent_step":
      return stepText(e);
    case "loop_finished":
      if (e.agent === "boss") {
        const q = out.question_for_human ? ` Question for you: ${out.question_for_human}` : "";
        return `${out.message_to_human ?? out.summary ?? "Finished."}${q} (Ticket is now ${statusWords(out.ticket_status ?? "")}.)`;
      }
      return out.summary ?? "Finished.";
    case "loop_failed":
      return `Ran into a problem and stopped: ${e.error}`;
    case "human_instruction":
      return `You told the boss: "${e.prompt}"`;
    case "human_decision":
      return `You ${out.status === "approved" ? "approved" : "rejected"} request #${out.request_id}.`;
    case "payment_executed":
      return `${money(out.amount)} left the checking account. Balance is now ${money(out.checking_balance_after)}.`;
    case "payment_refused":
      return `The payment was refused, so nothing was paid: ${out.error}`;
    case "run_started":
      return e.prompt?.startsWith("follow_up") ? "Wrapping up with your decisions" : "Team started on this ticket";
    default:
      return e.summary;
  }
}

/** The ticket's story in plain English, in order. Technical details are tucked away. */
export function LiveFeed({ events }: { events: AuditEvent[] }) {
  const items = events.filter((e) => SHOWN.has(e.event));
  // Keep the newest event in view by scrolling the feed box only (never the page).
  const box = useRef<HTMLOListElement>(null);
  useEffect(() => {
    box.current?.scrollTo({ top: box.current.scrollHeight, behavior: "smooth" });
  }, [items.length]);

  if (!items.length) {
    return <div className="feed feed-empty">Nothing yet. When you press <b>Run agent team</b>, the conversation shows up here as it happens.</div>;
  }
  return (
    <ol className="feed" ref={box}>
      {items.map((e) => {
        const w = who(e);
        const kind = e.event === "run_started" ? "divider" : e.event;
        const calls = e.event === "loop_finished" || e.event === "agent_step" ? e.tool_calls : [];
        return (
          <li key={e.seq} className={`feed-item feed-${kind}`} style={{ ["--role" as string]: w.color }}>
            <span className="feed-who">{w.label}</span>
            <span className="feed-text">{line(e)}</span>
            {calls.length > 0 && (
              <details className="feed-details">
                <summary>Details</summary>
                {calls.map((c, i) => (
                  <div key={i} className="call">
                    <code className="chip">{c.tool}</code>
                    <pre>{JSON.stringify(c.args)}</pre>
                    {c.result !== undefined && <pre className="call-result">{JSON.stringify(c.result, null, 1)}</pre>}
                  </div>
                ))}
              </details>
            )}
            <time className="feed-time">{new Date(e.logged_at).toLocaleTimeString()}</time>
          </li>
        );
      })}
    </ol>
  );
}
