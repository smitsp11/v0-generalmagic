"""
Gemini-powered intent classifier.

Classifies each inbound message into one of:
  - document_upload  (user sent or is describing a document attachment)
  - question         (user is asking something unrelated to the upload)
  - confirm_quote    (user wants to proceed with the quote)
  - other            (greetings, acknowledgements, etc.)

When the active workflow is in awaiting_doc, the response always includes a
gentle document reminder so the chase goal is never lost.
"""
from __future__ import annotations

import json
import re

from google import genai

from app.config import GEMINI_API_KEY
from app.models import IntentResult

_client: genai.Client | None = None

SYSTEM_PROMPT = """\
You are a helpful insurance assistant working via SMS. You are currently helping
a customer finalize an insurance quote.

CONTEXT (provided per message):
- The customer's active workflow status and which document is needed.

YOUR JOB:
1. Classify the customer's message intent as exactly one of:
   "document_upload", "question", "confirm_quote", "other".
2. If the intent is "question", write a SHORT, friendly SMS-length answer.
3. If the workflow is awaiting a document and the intent is NOT "document_upload",
   set doc_reminder to true.

RESPOND WITH ONLY valid JSON (no markdown fences):
{
  "intent": "<intent>",
  "response": "<your answer or empty string>",
  "doc_reminder": <true|false>
}
"""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


async def classify(
    message_body: str,
    document_type: str,
    workflow_status: str,
) -> IntentResult:
    if not GEMINI_API_KEY:
        return _mock_classify(message_body)

    client = _get_client()

    user_context = (
        f"Workflow status: {workflow_status}. "
        f"Document needed: {document_type}. "
        f"Customer message: {message_body}"
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=user_context,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return IntentResult(intent="other", response="", doc_reminder=True)

    return IntentResult(
        intent=data.get("intent", "other"),
        response=data.get("response", ""),
        doc_reminder=data.get("doc_reminder", True),
    )


_QUESTION_KEYWORDS = {"?", "does", "can", "will", "how", "what", "when", "is", "do", "why", "which"}
_UPLOAD_KEYWORDS = {"attached", "attaching", "sending", "here's", "here is", "uploaded", "file", "pdf", "photo"}


def _mock_classify(message_body: str) -> IntentResult:
    """Rule-based fallback when no Gemini API key is configured."""
    lower = message_body.lower()
    words = set(lower.split())

    if words & _UPLOAD_KEYWORDS:
        return IntentResult(intent="document_upload", response="", doc_reminder=False)

    if "?" in lower or words & _QUESTION_KEYWORDS:
        return IntentResult(
            intent="question",
            response="Great question! Let me look into that for you.",
            doc_reminder=True,
        )

    return IntentResult(intent="other", response="", doc_reminder=True)
