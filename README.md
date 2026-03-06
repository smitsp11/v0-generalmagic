# Document Chase Autopilot v0

A stateful, interruption-proof SMS workflow engine that turns "please upload X document" into a tracked, auditable process with a clean "Ready for review" handoff.

Built as a reusable **Doc Request Workflow** primitive: today it chases a Declarations Page, tomorrow you swap a JSON config and it chases a Driver Abstract, proof of address, or signed compliance form.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Inbound                          │
│  Twilio Webhook (/webhook/sms)                      │
│  Simulator UI   (/demo)                             │
└──────────────┬──────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│                  Core Engine                        │
│  Intent Router (Gemini 2.0 Flash)                   │
│  State Machine  (awaiting → received → validated)   │
│  Document Validator (type, size, PDF pages)          │
│  Audit Logger                                       │
└──────────────┬──────────────────────────────────────┘
               │
         ┌─────┴──────┐
         ▼            ▼
   ┌──────────┐  ┌──────────────────────────────┐
   │  SQLite  │  │  Mock Carrier API             │
   │  (state  │  │  /mock/carrier/v1/cases       │
   │   + audit│  │  (system-of-record write)     │
   │   trail) │  └──────────────────────────────┘
   └──────────┘
```

### State Machine

```
[start] → awaiting_doc → doc_received → validated → ready_for_review → [end]
                │                  └──→ needs_review ──┘
                └── (interruption: answer + nudge, state unchanged)
                └── (reminder: auto-nudge after timeout)
```

## Quick Start

### 1. Clone & install

```bash
cd glacis
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set GEMINI_API_KEY
```

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key for intent classification |
| `TWILIO_ACCOUNT_SID` | No* | Twilio credentials (only for real SMS) |
| `TWILIO_AUTH_TOKEN` | No* | Twilio credentials (only for real SMS) |
| `TWILIO_PHONE_NUMBER` | No* | Your Twilio phone number |
| `DATABASE_PATH` | No | SQLite path (default: `./data/chase.db`) |
| `DEMO_MODE` | No | `true` (default) — logs SMS to terminal instead of sending |
| `REMINDER_INTERVAL_SECONDS` | No | Seconds before reminder (default: 30 in demo mode) |
| `BASE_URL` | No | Server URL (default: `http://localhost:8000`) |

*\*Not required when `DEMO_MODE=true` — SMS replies are logged to terminal instead.*

### 3. Run the server

```bash
uvicorn app.main:app --reload
```

### 4. Open the simulator

Visit **http://localhost:8000/demo** in your browser. This is a chat interface that exercises the exact same code path as real Twilio webhooks.

### 5. Run the automated demo

In a second terminal (with the server running):

```bash
python demo_script.py
```

This replays the full 2-minute demo scenario with colored terminal output showing every state transition, carrier write, and audit timeline.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/workflows` | Create a new doc-chase workflow |
| `GET` | `/workflows` | List all workflows |
| `GET` | `/workflows/{id}` | Get workflow + audit events |
| `GET` | `/workflows/{id}/timeline` | Get formatted audit trail |
| `POST` | `/webhook/sms` | Twilio inbound webhook |
| `POST` | `/mock/carrier/v1/cases` | Mock carrier system endpoint |
| `GET` | `/demo` | Simulator chat UI |
| `POST` | `/demo/send` | Simulator message endpoint |
| `GET` | `/health` | Health check |

## Demo Scenario

1. **Agent creates workflow** → SMS sent: *"Please upload your Declarations Page"*
2. **5 hours later** → Customer: *"Does this include glass coverage?"* → Agent answers the question **and** reminds about the Dec page (interruption-proof)
3. **Next day** → Customer sends PDF → Validator checks file → *"Got it — staged for review"*
4. **Carrier write** → Structured JSON pushed to mock system-of-record
5. **Audit trail** → Complete timeline: requested → interruption → reminder → received → validated → carrier write → ready for review

## Tech Stack

- **Python 3.11+** / **FastAPI** — async web framework
- **SQLite** via `aiosqlite` — zero-dependency state store
- **Google Gemini 2.0 Flash** — intent classification & response generation
- **Twilio** — SMS gateway (optional in demo mode)
- **Rich** — terminal formatting for demo output
- **PyPDF2** — PDF validation

## Project Structure

```
glacis/
├── app/
│   ├── main.py                # FastAPI app, lifespan, route registration
│   ├── config.py              # Environment variables
│   ├── database.py            # SQLite schema + async CRUD
│   ├── models.py              # Pydantic schemas
│   ├── state_machine.py       # Workflow transitions + audit emission
│   ├── intent_classifier.py   # Gemini intent classification
│   ├── document_validator.py  # File-type, size, PDF validation
│   ├── sms_handler.py         # Core message orchestration
│   ├── carrier_api.py         # Mock carrier system write
│   ├── audit.py               # Audit trail helpers
│   ├── reminders.py           # Background reminder loop
│   └── routes/
│       ├── webhook.py         # POST /webhook/sms
│       ├── demo.py            # Simulator UI + API
│       ├── workflows.py       # Workflow CRUD
│       └── carrier.py         # Mock carrier endpoint
├── static/
│   └── demo.html              # Chat simulator UI
├── requirements.txt
├── .env.example
├── demo_script.py             # Automated demo replay script
└── README.md
```
