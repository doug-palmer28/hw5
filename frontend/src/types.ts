// Shapes returned by the FastAPI backend (backend/main.py).

export type Role = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  status: string;
  state: "open" | "resolved";
}

export interface TicketsResponse {
  shop_today: string;
  tickets: Ticket[];
}

export interface CaseNote {
  author: string;
  note: string;
  shop_date: string;
}

export interface TicketFull extends Ticket {
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  notes: string | null;
  created_at: string;
  shop_today: string;
  case_notes: CaseNote[];
}

export interface Draft {
  id: number;
  ticket_id: number;
  recipient: string;
  subject: string;
  body: string;
  author: string;
  status: string;
  shop_date: string;
}

export interface ApprovalRequest {
  id: number;
  kind: "payment" | "price_override";
  ticket_id: number;
  payment_kind: "vendor_invoice" | "rent" | null;
  ref_id: number | null;
  sku: string | null;
  size: string | null;
  qty: number | null;
  unit_price: number | null;
  amount: number;
  requested_by: string;
  reason: string;
  status: string;
  decided_by: string | null;
  decision_note: string | null;
  shop_date: string;
}

export interface TicketDetail {
  ticket: TicketFull;
  approval_requests: ApprovalRequest[];
  drafts: Draft[];
}

export interface ToolCall {
  tool: string;
  args: unknown;
  result?: unknown;
}

export interface AuditEvent {
  seq: number;
  logged_at: string;
  event: string;
  run_id: string;
  loop_id: string | null;
  parent_loop_id: string | null;
  agent: string;
  model: string | null;
  ticket_id: number | null;
  prompt: string | null;
  tool_calls: ToolCall[];
  model_requests: number | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  output: any;
  error: string | null;
  summary: string;
}

export interface EventsResponse {
  events: AuditEvent[];
  last_seq: number;
  total: number;
  busy: boolean;
  model: string;
}

export interface CashPosition {
  shop_today: string;
  checking: { name: string; balance: number; date: string };
  money_coming_in: string;
  paid_out_so_far: number;
  unpaid_invoices: { id: number; vendor: string; amount: number; due_date: string; description: string }[];
  rent_still_due: { id: number; space_name: string; landlord: string; monthly_rent: number; next_due: string }[];
  rent_already_paid_this_period: { id: number; monthly_rent: number; next_due: string; paid_at: string }[];
  payment_requests_in_flight: { id: number; ticket_id: number; amount: number; status: string }[];
  in_flight_total: number;
  balance_if_in_flight_paid: number | null;
}

export interface BossDecision {
  ticket_id: number | null;
  summary: string;
  ticket_status: string;
  message_to_human: string;
  next_steps: string[];
}

export interface RunRecord {
  run_id: string;
  kind: "first_pass" | "follow_up";
  ticket_id: number;
  status: "queued" | "running" | "finished" | "failed";
  queued_at: string;
  finished_at: string | null;
  decision: BossDecision | null;
  error: string | null;
}

export interface DecisionResponse {
  request: ApprovalRequest;
  decision: { status?: string; decided_by?: string; error?: string };
  payment?: { amount?: number; checking_balance_after?: number; approved_by?: string; error?: string };
  still_pending: number[];
  follow_up_run: RunRecord | null;
}
