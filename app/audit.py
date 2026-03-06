"""Audit trail helpers — formatting and retrieval."""
from __future__ import annotations

from app import database as db
from app.models import TimelineEntry


async def get_timeline(workflow_id: str) -> list[TimelineEntry]:
    events = await db.get_audit_events(workflow_id)
    return [
        TimelineEntry(
            event_type=e.event_type.value,
            actor=e.actor.value,
            timestamp=e.timestamp,
            metadata=e.metadata,
        )
        for e in events
    ]


def format_timeline_text(entries: list[TimelineEntry]) -> str:
    """Render a timeline as human-readable text for terminal / API display."""
    if not entries:
        return "(no events)"
    lines: list[str] = []
    for e in entries:
        ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        meta = ""
        if e.metadata:
            meta = f"  | {e.metadata}"
        lines.append(f"  [{ts}] {e.event_type:<22} actor={e.actor}{meta}")
    return "\n".join(lines)
