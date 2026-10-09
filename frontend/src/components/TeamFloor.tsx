import { AGENTS } from "../agents";
import type { AgentView } from "../teamState";
import type { Role } from "../types";
import { AgentFigure } from "./AgentFigure";

const STATUS_TEXT = { idle: "Off the clock", working: "Working…", done: "Done", failed: "Hit a problem" };

/** The five agents standing on the shop floor, each with a speech bubble. */
export function TeamFloor({ team }: { team: Record<Role, AgentView> }) {
  return (
    <section className="floor" aria-label="The agent team">
      {AGENTS.map((a) => {
        const v = team[a.role];
        return (
          <div key={a.role} className={`desk desk-${v.status}`} style={{ ["--role" as string]: a.color }}>
            <div className={`bubble ${v.bubble ? "" : "bubble-empty"}`} aria-live="polite">
              {v.bubble || (a.role === "boss" ? "Pick a ticket and press Run agent team." : "Waiting for the boss to ask for help…")}
              {v.status === "working" && <span className="typing"><i /><i /><i /></span>}
            </div>
            <AgentFigure who={a.role} status={v.status} size={0.9} />
            <div className="plate" title={a.outfit}>
              <strong>{a.title}</strong>
              <span>{a.name}</span>
            </div>
            <div className="desk-status">{STATUS_TEXT[v.status]}</div>
          </div>
        );
      })}
    </section>
  );
}
