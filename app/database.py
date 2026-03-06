from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import aiosqlite

from app.config import DATABASE_PATH
from app.models import AuditEvent, AuditEventType, Actor, WorkflowState, WorkflowStatus

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DATABASE_PATH)
        _db.row_factory = aiosqlite.Row
        await _init_tables(_db)
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def _init_tables(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            phone TEXT NOT NULL,
            quote_id TEXT NOT NULL,
            document_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'awaiting_doc',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            media_url TEXT,
            media_content_type TEXT,
            validation_reason TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        );

        CREATE INDEX IF NOT EXISTS idx_workflows_phone ON workflows(phone);
        CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);
        CREATE INDEX IF NOT EXISTS idx_audit_workflow ON audit_events(workflow_id);
        """
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------

async def create_workflow(phone: str, quote_id: str, document_type: str) -> WorkflowState:
    db = await get_db()
    wf = WorkflowState(
        id=str(uuid.uuid4()),
        phone=phone,
        quote_id=quote_id,
        document_type=document_type,
        status=WorkflowStatus.AWAITING_DOC,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await db.execute(
        """INSERT INTO workflows (id, phone, quote_id, document_type, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (wf.id, wf.phone, wf.quote_id, wf.document_type, wf.status.value,
         wf.created_at.isoformat(), wf.updated_at.isoformat()),
    )
    await db.commit()
    return wf


async def get_workflow(workflow_id: str) -> WorkflowState | None:
    db = await get_db()
    row = await db.execute_fetchall(
        "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
    )
    if not row:
        return None
    return _row_to_workflow(row[0])


async def get_active_workflow_for_phone(phone: str) -> WorkflowState | None:
    """Return the most recent non-terminal workflow for a phone number."""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT * FROM workflows
           WHERE phone = ? AND status != 'ready_for_review'
           ORDER BY created_at DESC LIMIT 1""",
        (phone,),
    )
    if not rows:
        return None
    return _row_to_workflow(rows[0])


async def update_workflow(wf: WorkflowState) -> None:
    db = await get_db()
    wf.updated_at = datetime.utcnow()
    await db.execute(
        """UPDATE workflows
           SET status = ?, updated_at = ?, media_url = ?,
               media_content_type = ?, validation_reason = ?
           WHERE id = ?""",
        (wf.status.value, wf.updated_at.isoformat(), wf.media_url,
         wf.media_content_type, wf.validation_reason, wf.id),
    )
    await db.commit()


async def get_stale_workflows(threshold_seconds: int) -> list[WorkflowState]:
    """Return awaiting_doc workflows whose last update exceeds the threshold."""
    db = await get_db()
    cutoff = datetime.utcnow().timestamp() - threshold_seconds
    cutoff_iso = datetime.utcfromtimestamp(cutoff).isoformat()
    rows = await db.execute_fetchall(
        """SELECT * FROM workflows
           WHERE status = 'awaiting_doc' AND updated_at < ?""",
        (cutoff_iso,),
    )
    return [_row_to_workflow(r) for r in rows]


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

async def add_audit_event(
    workflow_id: str,
    event_type: AuditEventType,
    actor: Actor,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    db = await get_db()
    evt = AuditEvent(
        id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        event_type=event_type,
        actor=actor,
        timestamp=datetime.utcnow(),
        metadata=metadata or {},
    )
    await db.execute(
        """INSERT INTO audit_events (id, workflow_id, event_type, actor, timestamp, metadata)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (evt.id, evt.workflow_id, evt.event_type.value, evt.actor.value,
         evt.timestamp.isoformat(), json.dumps(evt.metadata)),
    )
    await db.commit()
    return evt


async def get_audit_events(workflow_id: str) -> list[AuditEvent]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM audit_events WHERE workflow_id = ? ORDER BY timestamp ASC",
        (workflow_id,),
    )
    return [_row_to_audit_event(r) for r in rows]


# ---------------------------------------------------------------------------
# Carrier writes (logged to the same DB for persistence)
# ---------------------------------------------------------------------------

async def log_carrier_write(payload: dict[str, Any]) -> None:
    """Persist carrier API payloads for demo inspection."""
    db = await get_db()
    await db.executescript(
        """CREATE TABLE IF NOT EXISTS carrier_writes (
               id TEXT PRIMARY KEY,
               payload TEXT NOT NULL,
               created_at TEXT NOT NULL
           );"""
    )
    await db.execute(
        "INSERT INTO carrier_writes (id, payload, created_at) VALUES (?, ?, ?)",
        (str(uuid.uuid4()), json.dumps(payload), datetime.utcnow().isoformat()),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Row mappers
# ---------------------------------------------------------------------------

def _row_to_workflow(row: aiosqlite.Row) -> WorkflowState:
    return WorkflowState(
        id=row["id"],
        phone=row["phone"],
        quote_id=row["quote_id"],
        document_type=row["document_type"],
        status=WorkflowStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        media_url=row["media_url"],
        media_content_type=row["media_content_type"],
        validation_reason=row["validation_reason"],
    )


def _row_to_audit_event(row: aiosqlite.Row) -> AuditEvent:
    return AuditEvent(
        id=row["id"],
        workflow_id=row["workflow_id"],
        event_type=AuditEventType(row["event_type"]),
        actor=Actor(row["actor"]),
        timestamp=datetime.fromisoformat(row["timestamp"]),
        metadata=json.loads(row["metadata"]),
    )
