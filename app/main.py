"""FastAPI application — Document Chase Autopilot v0."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from rich.console import Console

from app import database as db
from app.reminders import reminder_loop
from app.routes import carrier, demo, webhook, workflows

console = Console()


@asynccontextmanager
async def lifespan(app: FastAPI):
    console.print("[bold green]Document Chase Autopilot v0[/] starting…")
    await db.get_db()
    task = asyncio.create_task(reminder_loop())
    yield
    task.cancel()
    await db.close_db()
    console.print("[bold red]Shutting down.[/]")


app = FastAPI(
    title="Document Chase Autopilot",
    version="0.1.0",
    description="Stateful, interruption-proof SMS document-chase workflow engine.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)
app.include_router(workflows.router)
app.include_router(carrier.router)
app.include_router(demo.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "document-chase-autopilot"}
