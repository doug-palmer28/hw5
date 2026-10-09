import { useState } from "react";
import { money } from "../agents";
import { statusWords } from "../plain";
import type { ApprovalRequest, AuditEvent, Ticket } from "../types";

export interface BossWords {
  message: string | null;
  question: string | null;
}

/** The boss's most recent report and question on a ticket, from the audit events. */
export function lastBossWords(events: AuditEvent[]): BossWords & { seq: number } {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.agent === "boss" && e.event === "loop_finished") {
      return { message: e.output?.message_to_human ?? null, question: e.output?.question_for_human ?? null, seq: e.seq };
    }
  }
  return { message: null, question: null, seq: 0 };
}

export type Step = "working" | "approve" | "finish" | "answer" | "start" | "resting" | "done";

/** Work out, in plain terms, where the ticket is and what (if anything) Doug should do. */
export function nextStep(ticket: Ticket, events: AuditEvent[], pending: ApprovalRequest[], working: boolean): Step {
  if (working) return "working";
  if (ticket.state === "resolved") return "done";
  if (pending.length) return "approve";
  const boss = lastBossWords(events);
  const lastDecision = Math.max(0, ...events.filter((e) => e.event === "human_decision").map((e) => e.seq));
  if (lastDecision > boss.seq) return "finish";                       // decided since the boss last looked
  if (!events.some((e) => e.agent === "boss")) return "start";
  if (ticket.status === "waiting_on_human") return "answer";          // the boss asked something
  return "resting";                                                   // waiting on vendor / customer
}

const STEP_TITLE: Record<Step, string> = {
  working: "The team is on it",
  approve: "Your decision is needed",
  finish: "Ready to wrap up",
  answer: "The boss has a question for you",
  start: "Not started yet",
  resting: "Nothing for you to do right now",
  done: "All done",
};

export function NextStep({ ticket, events, pending, working, busy, onRun, onFinish }: {
  ticket: Ticket;
  events: AuditEvent[];
  pending: ApprovalRequest[];
  working: boolean;
  busy: boolean;
  onRun: (instructions: string) => void;
  onFinish: () => void;
}) {
  const [text, setText] = useState("");
  const step = nextStep(ticket, events, pending, working);
  const boss = lastBossWords(events);
  const send = () => { onRun(text); setText(""); };

  let explain: string;
  switch (step) {
    case "working":
      explain = "The boss and the team are working on this ticket now. Watch them on the floor below. Anything that costs money will come to you for approval.";
      break;
    case "approve":
      explain = `The team is asking for your OK on ${pending.length === 1 ? "one request" : `${pending.length} requests`} `
        + `(${pending.map((r) => `${r.kind === "payment" ? "a payment of" : "a discount totaling"} ${money(r.amount)}`).join(", ")}). `
        + "Approve or reject it in the coral panel on the right. Nothing is paid until you approve.";
      break;
    case "finish":
      explain = "You've made your decision. Press Finish ticket so the boss can act on it: update the customer, set aside stock, and close out what it can.";
      break;
    case "answer":
      explain = "The boss stopped because it needs an answer from you before it can go on. Type your answer below and send it to the boss.";
      break;
    case "start":
      explain = "No one has looked at this ticket yet. Press Run agent team. If you want, tell the boss anything first.";
      break;
    case "resting":
      explain = ticket.status === "waiting_on_vendor"
        ? "This ticket is waiting on a vendor shipment that has already been paid. In this simulation the date stays on Aug 31, so the delivery never arrives and the ticket rests here. That's the correct ending; there's nothing more to do."
        : `This ticket is ${statusWords(ticket.status)}. The boss isn't waiting on you. You can still send the boss a message if you want something changed.`;
      break;
    default:
      explain = "This ticket is closed.";
  }

  const showBox = step === "answer" || step === "start" || step === "resting";
  return (
    <section className={`next next-${step}`} aria-live="polite">
      <div className="next-head">
        <span className="next-tag">What's happening</span>
        <h3>{STEP_TITLE[step]}</h3>
      </div>
      <p className="next-explain">{explain}</p>

      {boss.message && step !== "start" && (
        <blockquote className="boss-says">
          <span>The boss's latest report</span>
          {boss.message}
        </blockquote>
      )}
      {boss.question && step === "answer" && (
        <div className="boss-question"><span>The boss asks</span>{boss.question}</div>
      )}

      {step === "finish" && (
        <button className="btn btn-primary btn-big" onClick={onFinish} disabled={busy}>
          {busy ? "Team busy on another ticket…" : "Finish ticket"}
        </button>
      )}

      {showBox && (
        <div className="talk">
          <label htmlFor="talk-box">
            {step === "answer" ? "Your answer to the boss" : step === "start" ? "Anything the boss should know? (optional)" : "Message the boss (optional)"}
          </label>
          <textarea
            id="talk-box"
            rows={2}
            value={text}
            placeholder={step === "answer" ? "e.g. Offer them 10% off on the 8 we have in size M." : "e.g. Keep $500 in checking if you can."}
            onChange={(e) => setText(e.target.value)}
          />
          <button className="btn btn-primary" disabled={busy || (step === "answer" && !text.trim())} onClick={send}>
            {busy ? "Team busy on another ticket…" : step === "start" ? "Run agent team" : "Send to the boss"}
          </button>
        </div>
      )}
    </section>
  );
}
