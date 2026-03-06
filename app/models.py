from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStatus(str, enum.Enum):
    AWAITING_DOC = "awaiting_doc"
    DOC_RECEIVED = "doc_received"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    READY_FOR_REVIEW = "ready_for_review"


class AuditEventType(str, enum.Enum):
    DOC_REQUESTED = "doc_requested"
    REMINDER_SENT = "reminder_sent"
    INTERRUPTION = "interruption"
    DOC_RECEIVED = "doc_received"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FLAGGED = "validation_flagged"
    CARRIER_WRITE = "carrier_write"
    READY_FOR_REVIEW = "ready_for_review"


class Actor(str, enum.Enum):
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"


# ---------------------------------------------------------------------------
# Core domain objects
# ---------------------------------------------------------------------------

class WorkflowState(BaseModel):
    id: str
    phone: str
    quote_id: str
    document_type: str
    status: WorkflowStatus = WorkflowStatus.AWAITING_DOC
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    media_url: str | None = None
    media_content_type: str | None = None
    validation_reason: str | None = None


class AuditEvent(BaseModel):
    id: str | None = None
    workflow_id: str
    event_type: AuditEventType
    actor: Actor
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# API request / response schemas
# ---------------------------------------------------------------------------

class CreateWorkflowRequest(BaseModel):
    phone: str
    quote_id: str
    document_type: str = "declarations_page"


class WorkflowResponse(BaseModel):
    workflow: WorkflowState
    audit_events: list[AuditEvent] = []


class TimelineEntry(BaseModel):
    event_type: str
    actor: str
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntentResult(BaseModel):
    intent: str  # question | document_upload | confirm_quote | other
    response: str = ""
    doc_reminder: bool = False


class CarrierPayload(BaseModel):
    quote_id: str
    document_type: str
    status: str
    timestamp: datetime
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    audit_events: list[TimelineEntry] = []


class InboundMessage(BaseModel):
    """Normalized representation of an inbound SMS (from Twilio or the simulator)."""
    from_number: str
    body: str
    num_media: int = 0
    media_url: str | None = None
    media_content_type: str | None = None
