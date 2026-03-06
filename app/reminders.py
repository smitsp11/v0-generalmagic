"""Background task that sends reminders for stale awaiting_doc workflows."""
from __future__ import annotations

import asyncio

from rich.console import Console

from app import database as db
from app import state_machine
from app.config import REMINDER_INTERVAL_SECONDS
from app.sms_handler import DOC_TYPE_LABELS, send_sms

console = Console()


async def reminder_loop() -> None:
    console.log(
        f"[bold]Reminder loop started[/] "
        f"(interval={REMINDER_INTERVAL_SECONDS}s)"
    )
    while True:
        await asyncio.sleep(REMINDER_INTERVAL_SECONDS)
        try:
            stale = await db.get_stale_workflows(REMINDER_INTERVAL_SECONDS)
            for wf in stale:
                label = DOC_TYPE_LABELS.get(wf.document_type, wf.document_type)
                body = (
                    f"Friendly reminder: I still need your {label} to move "
                    f"quote {wf.quote_id} forward. Send it as a PDF or photo "
                    f"whenever you're ready!"
                )
                send_sms(wf.phone, body)
                await state_machine.log_reminder(wf)
        except Exception as exc:
            console.log(f"[red]Reminder loop error:[/] {exc}")
