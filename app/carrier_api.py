"""
Mock carrier system-of-record API.

In production this would be an external HTTPS call to the carrier's case-management
system. For v0 we log the payload with rich formatting and persist it locally.
"""
from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty

from app import database as db
from app.audit import get_timeline
from app.models import CarrierPayload, WorkflowState

console = Console()


async def push_to_carrier(wf: WorkflowState) -> CarrierPayload:
    timeline = await get_timeline(wf.id)

    payload = CarrierPayload(
        quote_id=wf.quote_id,
        document_type=wf.document_type,
        status=wf.status.value,
        timestamp=datetime.utcnow(),
        extracted_fields={},
        audit_events=timeline,
    )

    payload_dict = payload.model_dump(mode="json")
    await db.log_carrier_write(payload_dict)
    await db.add_audit_event(
        wf.id,
        db.AuditEventType.CARRIER_WRITE,
        db.Actor.SYSTEM,
        {"quote_id": wf.quote_id},
    )

    console.print()
    console.print(Panel(
        Pretty(payload_dict),
        title="[bold green]✓ Carrier System Write[/]",
        subtitle=f"quote_id={wf.quote_id}",
        border_style="green",
        expand=False,
    ))
    console.print()

    return payload
