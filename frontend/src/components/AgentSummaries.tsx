import { AGENTS } from "../agents";
import { shortCall } from "../plain";
import type { AgentView } from "../teamState";
import type { Role } from "../types";
import { AgentFigure } from "./AgentFigure";

/** One card per agent: what it did on this ticket, in plain English. Exact tool names are tucked away. */
export function AgentSummaries({ team }: { team: Record<Role, AgentView> }) {
  return (
    <div className="summaries">
      {AGENTS.map((a) => {
        const v = team[a.role];
        const tools = Object.entries(v.toolCounts);
        const did = new Map<string, number>();
        for (const [t, n] of tools) did.set(shortCall(t), (did.get(shortCall(t)) ?? 0) + n);
        const used = v.loops > 0;
        return (
          <article key={a.role} className={`summary ${used ? "" : "summary-unused"}`} style={{ ["--role" as string]: a.color }}>
            <header>
              <span className="summary-face"><AgentFigure who={a.role} status={used ? "done" : "idle"} size={0.42} /></span>
              <div>
                <h4>{a.title}</h4>
                <span className="muted">
                  {used ? `Worked on this ticket ${v.loops === 1 ? "once" : `${v.loops} times`}` : "Not needed on this ticket"}
                </span>
              </div>
            </header>
            {used && (
              <>
                <p>{v.summary ?? (v.status === "working" ? "Still working…" : "No summary yet.")}</p>
                {did.size > 0 && (
                  <ul className="did-list">
                    {[...did].map(([what, n]) => <li key={what}>{what}{n > 1 ? ` (${n}×)` : ""}</li>)}
                  </ul>
                )}
                {tools.length > 0 && (
                  <details className="tools-used">
                    <summary>Tools used</summary>
                    <div className="chips">
                      {tools.map(([t, n]) => <code key={t} className="chip">{t}{n > 1 ? ` ×${n}` : ""}</code>)}
                    </div>
                  </details>
                )}
              </>
            )}
          </article>
        );
      })}
    </div>
  );
}
