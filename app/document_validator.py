"""
Lightweight document validator for v0.

Checks:
  1. Media content-type is in the allowed set.
  2. File size is under the configured max.
  3. (PDF only) At least one page is present.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import httpx
from rich.console import Console

from app.config import ALLOWED_MEDIA_TYPES, MAX_FILE_SIZE_BYTES

console = Console()


@dataclass
class ValidationResult:
    passed: bool
    reason: str


async def validate(
    media_url: str | None,
    media_content_type: str | None,
) -> ValidationResult:
    if not media_url or not media_content_type:
        return ValidationResult(passed=False, reason="No media attached")

    if media_content_type not in ALLOWED_MEDIA_TYPES:
        return ValidationResult(
            passed=False,
            reason=f"Unsupported file type: {media_content_type}. "
                   f"Accepted: {', '.join(sorted(ALLOWED_MEDIA_TYPES))}",
        )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(media_url)
            resp.raise_for_status()
            data = resp.content
    except httpx.HTTPError as exc:
        return ValidationResult(passed=False, reason=f"Could not fetch media: {exc}")

    if len(data) > MAX_FILE_SIZE_BYTES:
        mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        return ValidationResult(passed=False, reason=f"File exceeds {mb:.0f} MB limit")

    if media_content_type == "application/pdf":
        return _validate_pdf(data)

    console.log(f"[green]Document validated[/] ({media_content_type}, {len(data)} bytes)")
    return ValidationResult(passed=True, reason="OK")


def _validate_pdf(data: bytes) -> ValidationResult:
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if len(reader.pages) < 1:
            return ValidationResult(passed=False, reason="PDF has no pages")
        console.log(f"[green]PDF validated[/] ({len(reader.pages)} page(s), {len(data)} bytes)")
        return ValidationResult(passed=True, reason=f"OK — {len(reader.pages)} page(s)")
    except Exception as exc:
        return ValidationResult(passed=False, reason=f"PDF parsing error: {exc}")
