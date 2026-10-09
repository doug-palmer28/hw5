// Turns the raw audit events into what the board shows for one ticket.
import { AGENTS, isRole } from "./agents";
import { describeCall } from "./plain";
import type { AuditEvent, Role } from "./types";

export type AgentStatus = "idle" | "working" | "done" | "failed";

export interface AgentView {
  status: AgentStatus;
  bubble: string;            // what the agent is saying/doing right now (or last said)
  currentTool: string | null;
  toolCounts: Record<string, number>;
  summary: string | null;    // last finished loop's summary
  message: string | null;    // boss's message to the human
  facts: { source_tool: string; detail: string }[];
  loops: number;
}

const clip = (s: string, n = 150) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

function delegateLine(args: unknown): string {
  const a = (args ?? {}) as { worker?: string; instructions?: string };
  const who = AGENTS.find((x) => x.role === a.worker)?.title ?? a.worker ?? "a teammate";
  return `Asking ${who} to help: ${a.instructions ?? ""}`;
}

export function stepText(e: AuditEvent): string {
  const said = typeof e.output === "string" ? e.output : "";
  if (said) return said;
  const del = e.tool_calls.filter((c) => c.tool === "delegate");
  if (del.length) return del.map((c) => delegateLine(c.args)).join(" · ");
  const parts = e.tool_calls.map((c) => describeCall(c.tool, c.args));
  return parts.length ? `${parts.join(". ")}…` : "Thinking…";
}

/**
 * @param liveRunIds run ids the backend says are queued/running right now. A loop that
 *   started but never finished only counts as "working" if its run is live; otherwise it
 *   was cut off (e.g. the server was stopped) and is shown as interrupted.
 */
export function teamView(events: AuditEvent[], liveRunIds: Set<string>): Record<Role, AgentView> {
  const blank = (): AgentView => ({
    status: "idle", bubble: "", currentTool: null, toolCounts: {}, summary: null,
    message: null, facts: [], loops: 0,
  });
  const view = Object.fromEntries(AGENTS.map((a) => [a.role, blank()])) as Record<Role, AgentView>;
  const open = new Map<string, Role>();
  const runOf = new Map<string, string>();      // loop_id -> run_id

  for (const e of events) {
    if (!isRole(e.agent)) continue;
    const v = view[e.agent];
    if (e.event === "loop_started") {
      open.set(e.loop_id ?? "", e.agent);
      runOf.set(e.loop_id ?? "", e.run_id);
      v.status = "working";
      v.loops += 1;
      v.currentTool = null;
      v.bubble = e.agent === "boss"
        ? clip(e.prompt?.startsWith("Ticket") ? "Got your decision. Wrapping up the ticket…"
          : e.prompt?.includes("Doug (the human operator) says") ? "Got your message. Taking another look…"
          : "Reading the ticket, the bank balance, and the other tickets…")
        : clip(`The boss asked me to: ${e.prompt ?? ""}`);
    } else if (e.event === "agent_step") {
      for (const c of e.tool_calls) v.toolCounts[c.tool] = (v.toolCounts[c.tool] ?? 0) + 1;
      v.currentTool = e.tool_calls.at(-1)?.tool ?? null;
      v.bubble = clip(stepText(e));
    } else if (e.event === "loop_finished" || e.event === "loop_failed") {
      open.delete(e.loop_id ?? "");
      const stillOpen = [...open.values()].includes(e.agent);
      v.currentTool = null;
      if (e.event === "loop_failed") {
        v.status = "failed";
        v.bubble = clip(`Something went wrong: ${e.error ?? ""}`);
        continue;
      }
      const out = (e.output ?? {}) as { summary?: string; message_to_human?: string; facts?: AgentView["facts"] };
      v.summary = out.summary ?? v.summary;
      v.message = out.message_to_human ?? v.message;
      if (out.facts?.length) v.facts = out.facts;
      v.status = stillOpen ? "working" : "done";
      v.bubble = clip(out.summary ?? out.message_to_human ?? "Done.");
    }
  }

  // Loops left open by a run that is no longer live were interrupted, not working.
  for (const [loopId, role] of open) {
    if (liveRunIds.has(runOf.get(loopId) ?? "")) continue;
    const v = view[role];
    const otherLiveLoop = [...open].some(([id, r]) => r === role && liveRunIds.has(runOf.get(id) ?? ""));
    if (otherLiveLoop) continue;
    v.status = v.summary ? "done" : "idle";
    v.currentTool = null;
    v.bubble = "Stopped: this run was interrupted when the server shut down.";
  }
  return view;
}
