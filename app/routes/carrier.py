"""Mock carrier system-of-record endpoint."""
from __future__ import annotations

from fastapi import APIRouter
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty

from app import database as db
from app.models import CarrierPayload

router = APIRouter(prefix="/mock/carrier/v1", tags=["carrier"])
console = Console()


@router.post("/cases")
async def receive_case(payload: CarrierPayload) -> dict:
    payload_dict = payload.model_dump(mode="json")
    await db.log_carrier_write(payload_dict)

    console.print()
    console.print(Panel(
        Pretty(payload_dict),
        title="[bold green]✓ Mock Carrier — Case Received[/]",
        subtitle=f"quote_id={payload.quote_id}",
        border_style="green",
        expand=False,
    ))
    console.print()

    return {"status": "accepted", "quote_id": payload.quote_id}
