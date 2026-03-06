#!/usr/bin/env python3
"""
Demo script — replays the 2-minute Document Chase Autopilot scenario.

Run the FastAPI server first:
    uvicorn app.main:app --reload

Then in another terminal:
    python demo_script.py
"""
from __future__ import annotations

import sys
import time

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

BASE = "http://localhost:8000"
PHONE = "+15550001234"

console = Console()


def step(label: str, wait: float = 1.5):
    console.print()
    console.rule(f"[bold cyan]{label}[/]")
    time.sleep(wait)


def post(path: str, **kwargs):
    try:
        r = httpx.post(f"{BASE}{path}", **kwargs, timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        console.print(f"[red]HTTP error:[/] {e}")
        sys.exit(1)


def get(path: str):
    try:
        r = httpx.get(f"{BASE}{path}", timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        console.print(f"[red]HTTP error:[/] {e}")
        sys.exit(1)


def show_reply(reply: str):
    console.print(Panel(reply, title="[bold green]Agent Reply", border_style="green", expand=False))


def show_user(text: str, attachment: str | None = None):
    label = text
    if attachment:
        label += f"  [dim][Attached: {attachment}][/]"
    console.print(Panel(label, title="[bold blue]Customer SMS", border_style="blue", expand=False))


def main():
    console.print()
    console.print(Panel.fit(
        "[bold]Document Chase Autopilot v0[/]\n"
        "Demo scenario: auto-quote with missing Declarations Page",
        border_style="cyan",
    ))

    # ------------------------------------------------------------------
    # Step 1: Create the workflow
    # ------------------------------------------------------------------
    step("Step 1 — Customer wants to lock in quote, agent creates doc request")

    data = post("/workflows", json={
        "phone": PHONE,
        "quote_id": "Q-12345",
        "document_type": "declarations_page",
    })
    wf_id = data["workflow"]["id"]
    console.print(f"Workflow [bold]{wf_id[:8]}…[/] created (status: {data['workflow']['status']})")

    first_sms = data["audit_events"][0]["metadata"].get("sms_body", "")
    show_reply(first_sms)

    # ------------------------------------------------------------------
    # Step 2: 5-hour gap — customer asks an unrelated question
    # ------------------------------------------------------------------
    step("Step 2 — 5 hours later: customer asks about glass coverage", wait=2)

    show_user("Hey does my auto policy include glass coverage?")
    result = post("/demo/send", data={
        "from_number": PHONE,
        "body": "Hey does my auto policy include glass coverage?",
        "num_media": "0",
    })
    show_reply(result["reply"])

    # ------------------------------------------------------------------
    # Step 3: Next day — customer sends the document
    # ------------------------------------------------------------------
    step("Step 3 — Next day: customer sends a PDF of their Dec page", wait=2)

    # We use a publicly available small PDF for the demo
    SAMPLE_PDF_URL = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    show_user("Here's my dec page", attachment="declarations_page.pdf")
    result = post("/demo/send", data={
        "from_number": PHONE,
        "body": "Here's my dec page",
        "num_media": "1",
        "media_url": SAMPLE_PDF_URL,
        "media_content_type": "application/pdf",
    })
    show_reply(result["reply"])

    # ------------------------------------------------------------------
    # Step 4: Show the audit timeline
    # ------------------------------------------------------------------
    step("Step 4 — Full audit timeline", wait=1)

    timeline = get(f"/workflows/{wf_id}/timeline")
    table = Table(title="Audit Trail", show_lines=True)
    table.add_column("Timestamp", style="dim")
    table.add_column("Event", style="yellow")
    table.add_column("Actor", style="cyan")
    table.add_column("Details")

    for entry in timeline:
        ts = entry["timestamp"][:19].replace("T", " ")
        meta = ""
        if entry.get("metadata"):
            items = entry["metadata"]
            if "sms_body" in items:
                meta = f"sms: {items['sms_body'][:60]}…"
            elif "user_message" in items:
                meta = f"user: {items['user_message'][:40]}…"
            elif "reason" in items:
                meta = items["reason"]
            elif "quote_id" in items:
                meta = f"quote: {items['quote_id']}"
            elif "content_type" in items:
                meta = items["content_type"]
        table.add_row(ts, entry["event_type"], entry["actor"], meta)

    console.print(table)

    # ------------------------------------------------------------------
    # Step 5: Show final workflow state
    # ------------------------------------------------------------------
    step("Step 5 — Final workflow state")

    wf_data = get(f"/workflows/{wf_id}")
    wf = wf_data["workflow"]
    console.print(f"  Status:        [bold green]{wf['status']}[/]")
    console.print(f"  Quote ID:      {wf['quote_id']}")
    console.print(f"  Document Type: {wf['document_type']}")
    console.print(f"  Created:       {wf['created_at']}")
    console.print(f"  Updated:       {wf['updated_at']}")
    console.print()
    console.print("[bold green]Demo complete![/]")


if __name__ == "__main__":
    main()
