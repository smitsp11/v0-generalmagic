"""Demo simulator — chat UI and API endpoint that mirrors the Twilio path."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, JSONResponse

from app.models import InboundMessage
from app.sms_handler import handle_inbound

router = APIRouter(prefix="/demo", tags=["demo"])

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


@router.get("", response_class=HTMLResponse)
async def demo_ui() -> HTMLResponse:
    html_path = STATIC_DIR / "demo.html"
    return HTMLResponse(html_path.read_text())


@router.post("/send")
async def demo_send(
    from_number: str = Form("+15550001234"),
    body: str = Form(""),
    num_media: int = Form(0),
    media_url: str | None = Form(None),
    media_content_type: str | None = Form(None),
) -> JSONResponse:
    msg = InboundMessage(
        from_number=from_number,
        body=body,
        num_media=num_media,
        media_url=media_url,
        media_content_type=media_content_type,
    )
    reply = await handle_inbound(msg)
    return JSONResponse({"reply": reply})
