// Thin client for every backend route from Problem 7.
import type {
  ApprovalRequest, CashPosition, DecisionResponse, EventsResponse, RunRecord, TicketDetail, TicketsResponse,
} from "./types";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(`Can't reach the backend at ${API_URL}. Is uvicorn running?`);
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = (body as { detail?: unknown }).detail;
    const msg = typeof d === "string" ? d : (d as { error?: string })?.error ?? JSON.stringify(d);
    throw new ApiError(msg || `${res.status} ${res.statusText}`);
  }
  return body as T;
}

export const api = {
  tickets: () => req<TicketsResponse>("/tickets"),
  ticket: (id: number) => req<TicketDetail>(`/tickets/${id}`),
  runTicket: (id: number, instructions = "") =>
    req<RunRecord>(`/tickets/${id}/run`, { method: "POST", body: JSON.stringify({ instructions }) }),
  followUp: (id: number) => req<RunRecord>(`/tickets/${id}/follow_up`, { method: "POST" }),
  runs: () => req<{ runs: RunRecord[]; busy: boolean }>("/runs"),
  run: (runId: string) => req<RunRecord>(`/runs/${runId}`),
  events: (after: number) => req<EventsResponse>(`/events?after=${after}&limit=5000`),
  approvals: () => req<{ requests: ApprovalRequest[] }>("/approvals?status=pending"),
  decide: (id: number, decision: "approve" | "reject", approver: string, note: string) =>
    req<DecisionResponse>(`/approvals/${id}`, {
      method: "POST",
      body: JSON.stringify({ decision, approver, note }),
    }),
  balance: () => req<CashPosition>("/balance"),
  reset: () => req<{ reset: string; balance: CashPosition["checking"] }>("/reset", { method: "POST" }),
};
