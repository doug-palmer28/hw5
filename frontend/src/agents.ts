import type { Role } from "./types";

export interface AgentMeta {
  role: Role;
  title: string;        // job title shown on the name plate
  name: string;         // personified first name (Yale landmarks)
  color: string;        // role color, same palette as desk_tickets.html
  outfit: string;       // what they wear, for design.md / tooltips
}

export const AGENTS: AgentMeta[] = [
  { role: "boss", title: "Boss", name: "Eli", color: "#1d1d1d", outfit: "Navy blazer and Yale-blue tie" },
  { role: "inventory", title: "Inventory", name: "Sterling", color: "#00366b", outfit: "Yale cap and hoodie, carrying a stock box" },
  { role: "accounting", title: "Accounting", name: "Penny", color: "#046e82", outfit: "Green visor, glasses, sweater vest, calculator" },
  { role: "facilities", title: "Facilities", name: "Harkness", color: "#286dc0", outfit: "White hard hat and a tool belt with a wrench" },
  { role: "customer_service", title: "Customer Service", name: "Mory", color: "#335e89", outfit: "Headset, Yale polo, and a 'Hi!' name tag" },
];

export const AGENT_BY_ROLE = Object.fromEntries(AGENTS.map((a) => [a.role, a])) as Record<Role, AgentMeta>;

export const HUMAN_COLOR = "#f04f36";

export function isRole(x: string): x is Role {
  return x in AGENT_BY_ROLE;
}

export function money(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function prettyTool(name: string): string {
  return name === "delegate" ? "delegate →" : name;
}
