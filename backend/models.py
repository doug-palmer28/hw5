"""Data types shared by the agent team, the runner, and the audit trail."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentRole = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
WorkerRole = Literal["inventory", "accounting", "facilities", "customer_service"]
TicketStatus = Literal[
    "open", "in_progress", "waiting_on_human", "waiting_on_vendor", "resolved", "declined"
]


@dataclass
class RunDeps:
    """Context passed into every agent loop."""

    run_id: str                       # one id per runner invocation
    ticket_id: int | None             # ticket being worked, if any
    loop_id: str = ""                 # this agent loop's id (set by the loop runner)
    delegations: int = 0              # how many times the boss has delegated in this loop


class Fact(BaseModel):
    """A single fact an agent relied on, tied to the MCP tool that returned it."""

    source_tool: str = Field(description="MCP tool the fact came from, e.g. 'check_stock'.")
    detail: str = Field(description="The fact, with the exact numbers/dates from the tool output.")


class WorkerReport(BaseModel):
    """What a worker agent hands back to the boss."""

    agent: WorkerRole
    ticket_id: int | None
    summary: str = Field(
        description="Two or three plain-English sentences a shop owner can read: what you found and what "
                    "you did. No tool names, field names, or SKU codes (say 'the white Bulldog tee', not "
                    "'CC-TEE-WHITE'; 'checked the shelves', not 'check_stock')."
    )
    facts: list[Fact] = Field(description="Every fact you used, each citing its source tool.")
    actions_taken: list[str] = Field(
        description="Changes you made through tools (notes, requests, drafts, reservations). Empty if none."
    )
    approval_request_ids: list[int] = Field(
        default_factory=list, description="IDs of approval requests you created."
    )
    recommendations: list[str] = Field(description="What you recommend the boss or human do next.")
    open_questions: list[str] = Field(
        default_factory=list, description="Anything you could not answer from the data."
    )
    needs_human: bool = Field(description="True if a human decision is required before this can move on.")


class ApprovalNeeded(BaseModel):
    """A pending request the human must decide on."""

    request_id: int
    kind: Literal["payment", "price_override"]
    amount: float
    why: str = Field(description="Why it's needed and what happens to cash or the order if approved/rejected.")


class BossDecision(BaseModel):
    """The boss's output at the end of a loop on a ticket."""

    ticket_id: int | None
    summary: str = Field(description="Plain-English summary of the ticket and where it stands.")
    delegated_to: list[WorkerRole]
    actions_taken: list[str]
    approvals_needed: list[ApprovalNeeded] = Field(
        description="Pending approval requests for this ticket that need the human."
    )
    ticket_status: TicketStatus
    message_to_human: str = Field(
        description="What the human operator needs to know or decide, including cash impact. Plain English."
    )
    question_for_human: str | None = Field(
        default=None,
        description="A direct question Doug must answer before you can continue (e.g. 'What unit price "
                    "should we offer?'). Leave empty if approval requests cover everything.",
    )
    next_steps: list[str]


class ToolCallRecord(BaseModel):
    tool: str
    args: Any
    result: Any = None


class AuditEntry(BaseModel):
    """One record in output/audit_trail.json. Entries are only ever appended."""

    seq: int
    prev_hash: str
    hash: str = ""
    logged_at: str                       # real wall-clock time the entry was written
    event: Literal["loop_started", "agent_step", "loop_finished", "loop_failed", "human_decision",
                   "payment_executed", "payment_refused", "run_started", "run_finished",
                   "run_failed", "db_reset", "human_instruction", "audit_repaired"]
    run_id: str
    loop_id: str | None = None
    parent_loop_id: str | None = None
    agent: str                           # agent role, 'human:<name>', or 'runner'
    model: str | None = None
    ticket_id: int | None = None
    prompt: str | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    model_requests: int | None = None
    output: Any = None
    error: str | None = None
