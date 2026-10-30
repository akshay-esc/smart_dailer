# SmartDialer — Hiring 2026 Technical Assignment

A backend-first SmartDialer prototype demonstrating progressive dialing, predictive pacing, a separate Safety Controller, atomic reservations, mock telecom providers, event deduplication, and failure-oriented tests.

> This is a local simulation. It does not place real telephone calls or contact real borrowers.

## Features

- FastAPI REST API for agents, borrowers, campaigns, dialing, and provider events.
- SQLAlchemy + SQLite for easy local setup. SQLite is convenient for a prototype; use PostgreSQL row locking/transactions for a multi-worker production deployment.
- Progressive dialer: one new agent-bound call per successfully reserved available agent.
- Predictive pacing engine: proposes a batch size using recent answer rate, provider health, and available capacity.
- Safety Controller: independently caps the proposed batch by atomically reservable agents and queued borrowers. The pacing engine never calls the provider directly.
- Atomic agent/borrower reservation with conditional updates.
- Two mock providers:
  - `fast`: quick, mostly reliable, events in order.
  - `flaky`: slower, can time out, duplicate events, and emit out-of-order events.
- Idempotent provider event ingestion and terminal-state protection.
- Basic simulation, tests, and architecture/state-machine documentation.

## Quick start

Python 3.10+ recommended.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive API documentation.

The database file `smartdialer.db` is created in the working directory on startup.

## Run tests

```bash
pytest -q
```

## Run the simulation

With the server running in another terminal:

```bash
python -m app.simulate
```

The simulator uses the API and prints a small summary. For a clean run, stop the server and delete `smartdialer.db` first, or use a fresh working directory.

## Example workflow

1. Create agents:
```bash
curl -X POST http://127.0.0.1:8000/agents/bulk \
  -H 'Content-Type: application/json' \
  -d '{"count": 3}'
```

2. Create borrowers:
```bash
curl -X POST http://127.0.0.1:8000/borrowers/bulk \
  -H 'Content-Type: application/json' \
  -d '{"count": 10}'
```

3. Initiate progressive calls:
```bash
curl -X POST http://127.0.0.1:8000/dial/progressive \
  -H 'Content-Type: application/json' \
  -d '{"campaign_id":"default","provider":"fast","max_calls":3}'
```

4. Check status:
```bash
curl http://127.0.0.1:8000/metrics
curl http://127.0.0.1:8000/calls
```

5. Run predictive pacing:
```bash
curl -X POST http://127.0.0.1:8000/dial/predictive \
  -H 'Content-Type: application/json' \
  -d '{"campaign_id":"default","provider":"fast","max_requested":10}'
```

6. Simulate a provider event (replace `CALL_ID` with a call ID from `/calls`):
```bash
curl -X POST http://127.0.0.1:8000/provider-events \
  -H 'Content-Type: application/json' \
  -d '{"provider":"fast","event_id":"evt-001","call_id":"CALL_ID","status":"ANSWERED"}'
```

Supported event statuses: `RINGING`, `ANSWERED`, `CONNECTED`, `COMPLETED`, `FAILED`, `CANCELLED`.

## API overview

- `GET /health`
- `POST /agents`, `POST /agents/bulk`, `GET /agents`
- `POST /borrowers`, `POST /borrowers/bulk`, `GET /borrowers`
- `POST /dial/progressive`
- `POST /dial/predictive`
- `GET /calls`, `GET /calls/{call_id}`
- `POST /provider-events`
- `POST /providers/{provider}/health` — set mock provider health (`healthy` or `unhealthy`)
- `GET /metrics`

## Important design notes / limitations

- The Safety Controller approves a proposed number; each actual allocation still uses atomic conditional database updates. This is necessary because capacity may change between a read and a reservation.
- Agent and borrower reservation is performed in one database transaction. If either reservation fails, the transaction is rolled back.
- Provider calls are initiated only after the call intent and reservations are persisted. In a real distributed system, use a transactional outbox and idempotency keys to close the database/provider dual-write gap.
- The mock provider returns an initiation result; provider events can be delivered separately to test duplicate/out-of-order processing.
- The prototype uses SQLite. SQLite serializes writes and is suitable for local demonstration, but PostgreSQL is preferable for concurrent workers at scale.
- The prototype deliberately does not include authentication, borrower PII, a real telecom integration, or production compliance controls.

## Project structure

```text
app/
  database.py       SQLAlchemy engine/session and schema
  models.py         Agent, Borrower, Call, ProviderEvent models
  schemas.py        API request/response schemas
  providers.py      Provider interface and two mock providers
  state_machine.py  Valid event/state transition logic
  dialer.py         Progressive dialer, predictive pacing, Safety Controller
  main.py           FastAPI routes
  simulate.py       Small API-based simulation
tests/
  conftest.py
  test_dialer.py
  test_events.py
docs/
  architecture.md
  state-machines.md
  architecture-decisions.md
```
