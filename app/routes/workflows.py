"""Workflow management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import database as db
from app.audit import format_timeline_text, get_timeline
from app.models import (
    AuditEventType,
    Actor,
    CreateWorkflowRequest,
    TimelineEntry,
    WorkflowResponse,
    WorkflowState,
)
from app.sms_handler import DOC_TYPE_LABELS, send_sms

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowResponse)
async def create_workflow(req: CreateWorkflowRequest) -> dict:
    wf = await db.create_workflow(req.phone, req.quote_id, req.document_type)

    label = DOC_TYPE_LABELS.get(wf.document_type, wf.document_type)
    sms_body = (
        f"To finalize quote {wf.quote_id}, please upload your {label} "
        f"(PDF or photo). I'll wait here."
    )

    await db.add_audit_event(
        wf.id,
        AuditEventType.DOC_REQUESTED,
        Actor.AGENT,
        {"sms_body": sms_body},
    )

    send_sms(wf.phone, sms_body)

    events = await db.get_audit_events(wf.id)
    return {"workflow": wf, "audit_events": events}


@router.get("", response_model=list[WorkflowState])
async def list_workflows() -> list[WorkflowState]:
    d = await db.get_db()
    rows = await d.execute_fetchall("SELECT * FROM workflows ORDER BY created_at DESC")
    return [db._row_to_workflow(r) for r in rows]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str) -> dict:
    wf = await db.get_workflow(workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow not found")
    events = await db.get_audit_events(workflow_id)
    return {"workflow": wf, "audit_events": events}


@router.get("/{workflow_id}/timeline", response_model=list[TimelineEntry])
async def get_workflow_timeline(workflow_id: str) -> list[TimelineEntry]:
    wf = await db.get_workflow(workflow_id)
    if wf is None:
        raise HTTPException(404, "Workflow not found")
    return await get_timeline(workflow_id)
