"""
Workflow state machine for the Document Chase Autopilot.

Each public method represents a valid transition. Every transition persists
the new state and emits an audit event atomically.
"""
from __future__ import annotations

from rich.console import Console

from app.database import add_audit_event, update_workflow
from app.models import (
    Actor,
    AuditEventType,
    WorkflowState,
    WorkflowStatus,
)

console = Console()

VALID_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.AWAITING_DOC: {
        WorkflowStatus.AWAITING_DOC,  # interruption / reminder (no state change)
        WorkflowStatus.DOC_RECEIVED,
    },
    WorkflowStatus.DOC_RECEIVED: {
        WorkflowStatus.VALIDATED,
        WorkflowStatus.NEEDS_REVIEW,
    },
    WorkflowStatus.VALIDATED: {
        WorkflowStatus.READY_FOR_REVIEW,
    },
    WorkflowStatus.NEEDS_REVIEW: {
        WorkflowStatus.READY_FOR_REVIEW,
        WorkflowStatus.AWAITING_DOC,  # re-request after failed review
    },
    WorkflowStatus.READY_FOR_REVIEW: set(),  # terminal
}


class InvalidTransition(Exception):
    pass


async def _transition(
    wf: WorkflowState,
    target: WorkflowStatus,
    event_type: AuditEventType,
    actor: Actor,
    metadata: dict | None = None,
) -> WorkflowState:
    if target not in VALID_TRANSITIONS.get(wf.status, set()):
        raise InvalidTransition(f"Cannot go from {wf.status.value} → {target.value}")
    wf.status = target
    await update_workflow(wf)
    await add_audit_event(wf.id, event_type, actor, metadata)
    console.log(
        f"[bold cyan]Workflow {wf.id[:8]}…[/] "
        f"[yellow]{event_type.value}[/] → [green]{target.value}[/]"
    )
    return wf


async def mark_doc_received(
    wf: WorkflowState,
    media_url: str,
    media_content_type: str,
) -> WorkflowState:
    wf.media_url = media_url
    wf.media_content_type = media_content_type
    return await _transition(
        wf,
        WorkflowStatus.DOC_RECEIVED,
        AuditEventType.DOC_RECEIVED,
        Actor.USER,
        {"media_url": media_url, "content_type": media_content_type},
    )


async def mark_validated(wf: WorkflowState) -> WorkflowState:
    wf.validation_reason = None
    return await _transition(
        wf,
        WorkflowStatus.VALIDATED,
        AuditEventType.VALIDATION_PASSED,
        Actor.SYSTEM,
    )


async def mark_needs_review(wf: WorkflowState, reason: str) -> WorkflowState:
    wf.validation_reason = reason
    return await _transition(
        wf,
        WorkflowStatus.NEEDS_REVIEW,
        AuditEventType.VALIDATION_FLAGGED,
        Actor.SYSTEM,
        {"reason": reason},
    )


async def mark_ready_for_review(wf: WorkflowState) -> WorkflowState:
    return await _transition(
        wf,
        WorkflowStatus.READY_FOR_REVIEW,
        AuditEventType.READY_FOR_REVIEW,
        Actor.SYSTEM,
    )


async def log_interruption(wf: WorkflowState, user_message: str, agent_response: str) -> None:
    """Record an interruption without changing state."""
    await add_audit_event(
        wf.id,
        AuditEventType.INTERRUPTION,
        Actor.USER,
        {"user_message": user_message, "agent_response": agent_response},
    )
    # Touch the workflow so the reminder timer resets
    await update_workflow(wf)
    console.log(
        f"[bold cyan]Workflow {wf.id[:8]}…[/] "
        f"[yellow]interruption[/] (state unchanged: {wf.status.value})"
    )


async def log_reminder(wf: WorkflowState) -> None:
    """Record that a reminder was sent."""
    await add_audit_event(
        wf.id,
        AuditEventType.REMINDER_SENT,
        Actor.AGENT,
        {"message": "Automated reminder sent"},
    )
    await update_workflow(wf)
    console.log(
        f"[bold cyan]Workflow {wf.id[:8]}…[/] "
        f"[yellow]reminder_sent[/]"
    )
