// Plain-English descriptions of what an agent is doing, so the board talks like a
// shop manager instead of a programmer. Tool names stay available under "Details".
import { AGENTS, money } from "./agents";

const PRODUCTS: Record<string, string> = {
  "CC-TEE-WHITE": "the white Bulldog tee",
  "CC-HOOD-NAVY": "the navy Yale hoodie",
  "CC-HAT-BLUE": "the Yale cap",
  "CC-MUG-CREST": "the crest mug",
};
export const product = (sku?: unknown) => PRODUCTS[String(sku)] ?? (sku ? String(sku) : "the item");

const STATUS_WORDS: Record<string, string> = {
  open: "open", in_progress: "in progress", waiting_on_human: "waiting on you",
  waiting_on_vendor: "waiting on the vendor", resolved: "resolved", declined: "declined",
};
export const statusWords = (s: string) => STATUS_WORDS[s] ?? s.replaceAll("_", " ");

type Args = Record<string, unknown>;

const PHRASES: Record<string, (a: Args) => string> = {
  list_tickets: () => "Looking over all the tickets",
  list_open_tickets: () => "Looking at the other open tickets",
  get_ticket: (a) => `Reading ticket ${a.ticket_id ?? ""}`.trim(),
  get_case_notes: () => "Reading the team's notes on this ticket",
  add_case_note: () => "Leaving a note for the team",
  update_ticket_status: (a) => `Marking the ticket "${statusWords(String(a.status ?? ""))}"`,
  check_stock: (a) => `Checking the shelves for ${product(a.sku)}`,
  reserve_stock: (a) => `Setting aside ${a.qty} of ${product(a.sku)} (size ${a.size})`,
  list_vendors: () => "Checking which vendors can restock it",
  get_invoice: (a) => `Looking up invoice #${a.invoice_id}`,
  get_lease: () => "Pulling up the shop's lease",
  get_cash_position: () => "Checking the bank balance and the bills",
  list_payments: () => "Checking what has already been paid",
  quote_price: (a) => `Pricing ${a.qty} at ${money(Number(a.unit_price))} each`,
  request_payment: (a) =>
    a.payment_kind === "rent" ? "Asking you to approve paying the rent"
      : `Asking you to approve paying invoice #${a.ref_id}`,
  request_price_override: (a) =>
    `Asking you to approve ${a.qty} of ${product(a.sku)} at ${money(Number(a.unit_price))} each`,
  list_approval_requests: () => "Checking what's waiting on your approval",
  draft_customer_message: (a) => `Writing a message to ${a.recipient ?? "the customer"} (a draft, not sent)`,
  list_customer_drafts: () => "Reading earlier message drafts",
  delegate: (a) => {
    const who = AGENTS.find((x) => x.role === a.worker)?.title ?? String(a.worker ?? "a teammate");
    return `Handing this to ${who}: "${a.instructions ?? ""}"`;
  },
};

export function describeCall(tool: string, args: unknown): string {
  const f = PHRASES[tool];
  return f ? f((args ?? {}) as Args) : tool.replaceAll("_", " ");
}

/** Short version for counting in summaries ("Checked the shelves" ×2). */
export function shortCall(tool: string): string {
  const map: Record<string, string> = {
    list_tickets: "Reviewed the ticket list", list_open_tickets: "Reviewed the other open tickets",
    get_ticket: "Read the ticket", get_case_notes: "Read the team's notes", add_case_note: "Left a note for the team",
    update_ticket_status: "Updated the ticket status", check_stock: "Checked the shelves",
    reserve_stock: "Set stock aside", list_vendors: "Checked vendors", get_invoice: "Looked up the invoice",
    get_lease: "Checked the lease", get_cash_position: "Checked the bank balance", list_payments: "Checked past payments",
    quote_price: "Priced options", request_payment: "Asked you to approve a payment",
    request_price_override: "Asked you to approve a discount", list_approval_requests: "Checked your approvals",
    draft_customer_message: "Wrote a message draft", list_customer_drafts: "Read message drafts",
    delegate: "Handed work to a teammate",
  };
  return map[tool] ?? tool.replaceAll("_", " ");
}
