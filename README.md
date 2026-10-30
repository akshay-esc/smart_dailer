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
# SmartDialer

A lightweight SmartDialer prototype built with FastAPI and React, featuring progressive and predictive dialing, safety controls, agent allocation, mock telecom providers, and call-state management.

## 1. Project Overview

SmartDialer is an outbound calling system designed to manage automated calls between borrowers and available agents.

The system supports two dialing strategies:

- **Progressive Dialing:** Initiates calls based on the number of currently available agents.
- **Predictive Dialing:** Uses estimated answer rates and agent availability to determine how many calls should be initiated.

A Safety Controller validates every dialing request before calls are allocated. The system also manages agent and call lifecycles, handles provider events, prevents duplicate event processing, and supports recovery of stale reservations.

The project is implemented as a prototype using FastAPI, SQLAlchemy, SQLite, and React.

## 2. Key Features

### 2.1 Progressive Dialing

- Initiates outbound calls based on available agents.
- Ensures that the number of reserved calls does not exceed available agent capacity.
- Allocates agents and borrowers before initiating calls.
- Uses atomic database updates to reduce the risk of duplicate reservations.
- Releases agent and borrower reservations when call initiation fails.

### 2.2 Predictive Dialing

- Estimates the answer rate using historical call outcomes.
- Considers available agents and queued borrowers.
- Calculates a proposed dialing volume.
- Uses a Safety Controller to validate the proposed volume.
- Prevents the pacing engine from directly initiating calls.

### 2.3 Safety Controller

The Safety Controller acts as an independent validation layer between the Predictive Pacing Engine and the call allocation process.

It checks:

- Available agent capacity.
- Number of queued borrowers.
- Requested dialing volume.
- Provider health.
- Whether the proposed dialing volume is safe.

The controller can approve, reduce, or reject a dialing request.

### 2.4 Agent Lifecycle Management

The system maintains explicit agent states:

| Agent State | Description |
|---|---|
| OFFLINE | Agent is not logged in or available. |
| AVAILABLE | Agent is ready to receive a call. |
| RESERVED | Agent has been reserved for an outbound call. |
| DIALING | An outbound call is being initiated or is ringing. |
| CONNECTED | Agent is connected to a borrower. |
| WRAP_UP | Agent has completed a call and is performing post-call work. |
| PAUSED | Agent is temporarily unavailable. |

An agent in WRAP_UP state must complete the wrap-up process before becoming available for another call.

### 2.5 Call Lifecycle Management

The system manages calls using explicit states:

| Call State | Description |
|---|---|
| QUEUED | Call is waiting to be processed. |
| RESERVED | An agent and borrower have been allocated. |
| INITIATED | The provider has accepted the call initiation request. |
| RINGING | The borrower's phone is ringing. |
| ANSWERED | The borrower has answered the call. |
| CONNECTED | The call is connected to an agent. |
| COMPLETED | The call has finished successfully. |
| FAILED | The call could not be completed. |
| CANCELLED | The call was cancelled. |

Allowed state transitions are validated to prevent invalid or backward transitions.

### 2.6 Mock Telecom Providers

Two mock providers are implemented:

- **Fast Provider:** Simulates a provider with normal call initiation behavior.
- **Flaky Provider:** Simulates provider failures and less reliable behavior.

Provider health is tracked, and unhealthy providers are prevented from receiving new dialing requests.

### 2.7 Provider Event Processing

The system supports provider events such as:

- RINGING
- ANSWERED
- CONNECTED
- COMPLETED
- FAILED
- CANCELLED

Provider events update the call and agent states.

Duplicate provider events are detected using provider event IDs. Invalid state transitions and provider mismatches are rejected.

### 2.8 Stale Reservation Recovery

The maintenance endpoint identifies reservations that remain in the RESERVED state beyond a configured timeout.

It marks stale reservations as failed and releases the associated agent and borrower when their reservation references still match the call.

### 2.9 Monitoring and Metrics

The `/metrics` endpoint provides information about:

- Total agents.
- Available agents.
- Reserved agents.
- Dialing agents.
- Connected agents.
- Agents in wrap-up.
- Paused and offline agents.
- Total calls.
- Initiated calls.
- Ringing calls.
- Answered calls.
- Connected calls.
- Completed calls.
- Failed and cancelled calls.
- Queued borrowers.
- Provider health.
- Agent occupancy percentage.
- Active-call utilization percentage.

These metrics provide a basic view of the current system state.

## 3. Project Structure

smartdialer/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── dialer.py
│   ├── providers.py
│   ├── state_machine.py
│   └── simulate.py
│
├── tests/
│   ├── conftest.py
│   ├── test_dialer.py
│   └── test_events.py
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.js
│
├── docs/
│   ├── architecture.md
│   ├── architecture-decisions.md
│   └── state-machines.md
│
├── requirements.txt
├── README.md
└── .gitignore

## 4. Technology Stack

### Backend
- Python
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
### Frontend
- React
- Vite
- JavaScript
- HTML
- CSS
### Testing
- Pytest
- FastAPI TestClient
### Development Tools
- Visual Studio Code
- Git
- GitHub
- Postman / cURL
## 7. API Endpoints

The SmartDialer backend exposes REST API endpoints through FastAPI. These endpoints support agent management, borrower management, dialing operations, call processing, provider management, monitoring, and maintenance.

### 7.1 Health Check

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Checks whether the backend service is running. |

### 7.2 Agent Management

| Method | Endpoint | Description |
|---|---|---|
| POST | `/agents` | Creates a new agent. |
| POST | `/agents/bulk` | Creates multiple agents. |
| GET | `/agents` | Retrieves agent information. |
| PATCH | `/agents/{agent_id}` | Updates an agent's status. |
| POST | `/agents/{agent_id}/complete-wrap-up` | Changes an agent from WRAP_UP to AVAILABLE. |

### 7.3 Borrower Management

| Method | Endpoint | Description |
|---|---|---|
| POST | `/borrowers` | Creates a new borrower. |
| POST | `/borrowers/bulk` | Creates multiple borrowers. |
| GET | `/borrowers` | Retrieves borrower information. |

### 7.4 Dialing Operations

| Method | Endpoint | Description |
|---|---|---|
| POST | `/dial/progressive` | Initiates progressive dialing based on available agent capacity. |
| POST | `/dial/predictive` | Initiates predictive dialing using the proposed dialing volume from the pacing engine. |

### 7.5 Call Management

| Method | Endpoint | Description |
|---|---|---|
| GET | `/calls` | Retrieves call records. |
| GET | `/calls/{call_id}` | Retrieves details of a specific call. |

### 7.6 Provider Management

| Method | Endpoint | Description |
|---|---|---|
| POST | `/provider-events` | Receives and processes telecom provider events. |
| PATCH | `/providers/{provider_name}/health` | Updates the health status of a provider. |

### 7.7 Monitoring and Maintenance

| Method | Endpoint | Description |
|---|---|---|
| GET | `/metrics` | Retrieves agent, call, borrower, and provider metrics. |
| POST | `/maintenance/recover-stale-reservations` | Identifies and recovers eligible stale reservations. |

### 7.8 API Documentation

FastAPI provides interactive API documentation for testing and exploring the available endpoints.

Open the following URL after starting the backend:

`http://127.0.0.1:8000/docs`
## 13. Current Limitations

SmartDialer is a prototype developed to demonstrate the core concepts of progressive dialing, predictive pacing, agent allocation, safety validation, and call-state management.

The current implementation has the following limitations:

1. **Database:** SQLite is used for data storage. A production system would benefit from PostgreSQL or another database designed for concurrent workloads.

2. **Mock Providers:** The system uses simulated telecom providers instead of integrating with real telephony services.

3. **Basic Predictive Algorithm:** Predictive pacing uses a basic historical answer-rate estimate. It does not yet implement advanced machine learning or sophisticated statistical forecasting.

4. **Basic Simulation:** The current simulation demonstrates the progressive dialing workflow but does not fully implement all the assignment's statistical scenarios, such as different answer rates, call durations, and changing provider conditions.

5. **Current-State Metrics:** Metrics provide a snapshot of system activity. They do not yet provide complete time-based agent utilization or historical campaign analytics.

6. **Reservation Recovery:** Stale reservation recovery handles eligible database reservations, but it does not perform complete reconciliation with an external telecom provider.

7. **Distributed Processing:** Production-grade distributed worker coordination, distributed locking, and transactional outbox processing are not implemented.

8. **Load Testing:** A dedicated load-testing suite for evaluating high-volume concurrent dialing requests is not yet included.

9. **Provider Integration:** Real-world provider authentication, webhooks, retry policies, and advanced failure recovery need further implementation.

10. **Security:** Authentication, authorization, and role-based access control are not yet implemented.

## 14. Future Enhancements

The following improvements can extend the system:

- Integrate real telecom providers.
- Migrate from SQLite to PostgreSQL.
- Introduce Redis for distributed coordination.
- Implement transactional outbox processing.
- Improve predictive pacing using historical campaign data and machine learning.
- Add advanced simulation scenarios with configurable answer rates and call durations.
- Implement provider reconciliation and retry mechanisms.
- Add load testing for concurrent dialing requests.
- Introduce authentication and role-based access control.
- Develop real-time dashboards for agent and campaign monitoring.
- Add historical analytics and time-based utilization reports.
- Implement monitoring and alerting for provider failures.
