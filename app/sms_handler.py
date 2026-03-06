"""
Core message handler — the orchestration layer.

Receives a normalized InboundMessage, resolves the active workflow,
classifies intent, drives state transitions, and returns the reply text.
This module is used by both the Twilio webhook and the demo simulator so
the code path is identical.
"""
from __future__ import annotations

from rich.console import Console

from app import database as db
from app import document_validator, intent_classifier, state_machine
from app.carrier_api import push_to_carrier
from app.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
from app.models import InboundMessage, WorkflowStatus

console = Console()

DOC_TYPE_LABELS: dict[str, str] = {
    "declarations_page": "Declarations Page",
    "driver_abstract": "Driver Abstract",
    "proof_of_address": "Proof of Address",
}


async def handle_inbound(msg: InboundMessage) -> str:
    """Process an inbound message and return the SMS reply body."""
    phone = msg.from_number.strip()
    if not phone.startswith("+") and phone[0:1].isdigit():
        phone = "+" + phone
    wf = await db.get_active_workflow_for_phone(phone)

    if wf is None:
        return (
            "Hi! I don't have an active document request for this number. "
            "If you're expecting one, please contact your agent."
        )

    label = DOC_TYPE_LABELS.get(wf.document_type, wf.document_type)

    # --- Branch 1: user sent media while we're awaiting a document -----------
    if wf.status == WorkflowStatus.AWAITING_DOC and msg.num_media > 0:
        wf = await state_machine.mark_doc_received(
            wf, msg.media_url or "", msg.media_content_type or ""
        )

        result = await document_validator.validate(
            wf.media_url, wf.media_content_type
        )

        if result.passed:
            wf = await state_machine.mark_validated(wf)
            await push_to_carrier(wf)
            wf = await state_machine.mark_ready_for_review(wf)
            return (
                f"Got it — your {label} looks good and has been staged for review. "
                f"Quote {wf.quote_id} is moving forward!"
            )
        else:
            wf = await state_machine.mark_needs_review(wf, result.reason)
            return (
                f"I received your file, but there's an issue: {result.reason}. "
                f"Could you re-send your {label}? (PDF or photo accepted)"
            )

    # --- Branch 2: text-only message while awaiting doc ----------------------
    if wf.status == WorkflowStatus.AWAITING_DOC:
        intent = await intent_classifier.classify(
            msg.body, wf.document_type, wf.status.value
        )

        if intent.intent == "document_upload":
            return (
                f"It looks like you're trying to send a document — please attach "
                f"the file as a photo or PDF so I can process it."
            )

        response_parts: list[str] = []
        if intent.response:
            response_parts.append(intent.response)
        if intent.doc_reminder:
            response_parts.append(
                f"By the way, I still need your {label} to finalize quote "
                f"{wf.quote_id}. You can send it as a PDF or photo anytime."
            )

        reply = " ".join(response_parts) if response_parts else (
            f"Thanks for the message! Just a reminder — I'm still waiting on "
            f"your {label} for quote {wf.quote_id}."
        )

        await state_machine.log_interruption(wf, msg.body, reply)
        return reply

    # --- Branch 3: workflow is in a non-awaiting state -----------------------
    if wf.status == WorkflowStatus.NEEDS_REVIEW:
        if msg.num_media > 0:
            wf.status = WorkflowStatus.AWAITING_DOC
            await db.update_workflow(wf)
            return await handle_inbound(msg)  # re-enter with correct state

        return (
            f"Your previous upload needs attention: {wf.validation_reason}. "
            f"Please re-send your {label} as a PDF or photo."
        )

    return "Your document is already being processed. Sit tight!"


def send_sms(to: str, body: str) -> str | None:
    """Send an outbound SMS via Twilio. Returns the message SID or None in demo mode."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        console.log(f"[dim]SMS (demo mode) → {to}:[/] {body}")
        return None

    from twilio.rest import Client

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=body,
        from_=TWILIO_PHONE_NUMBER,
        to=to,
    )
    console.log(f"[green]SMS sent[/] SID={message.sid} → {to}")
    return message.sid
