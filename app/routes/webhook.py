"""Twilio inbound SMS webhook."""
from __future__ import annotations

from fastapi import APIRouter, Form
from fastapi.responses import PlainTextResponse

from app.models import InboundMessage
from app.sms_handler import handle_inbound

router = APIRouter(tags=["twilio"])


@router.post("/webhook/sms", response_class=PlainTextResponse)
async def twilio_webhook(
    From: str = Form(...),
    Body: str = Form(""),
    NumMedia: int = Form(0),
    MediaUrl0: str | None = Form(None),
    MediaContentType0: str | None = Form(None),
) -> str:
    msg = InboundMessage(
        from_number=From,
        body=Body,
        num_media=NumMedia,
        media_url=MediaUrl0,
        media_content_type=MediaContentType0,
    )
    reply = await handle_inbound(msg)

    # Return TwiML so Twilio sends the reply as an SMS
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Message>{reply}</Message>"
        "</Response>"
    )
