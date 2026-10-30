# Architecture Decision Record (ADR)

## Decision 1: Python + FastAPI
**Choice:** Python and FastAPI.

**Why:** Fast to build, clear API contracts, automatic OpenAPI docs, and easy automated testing.

**Trade-off:** A synchronous SQLAlchemy prototype is not intended to demonstrate maximum throughput.

## Decision 2: SQLite for the runnable prototype
**Choice:** SQLite by default, configurable with `DATABASE_URL`.

**Why:** Minimal setup means reviewers can run the project locally without provisioning a database.

**Trade-off:** SQLite is not the preferred choice for many concurrent production workers. PostgreSQL is the next step for row locking and stronger multi-worker behaviour.

## Decision 3: Separate pacing and safety
**Choice:** Pacing only proposes a batch; Safety Controller independently caps it.

**Why:** Predictions can be wrong. Safety must not depend on the model being accurate.

**Trade-off:** Conservative capacity limits can reduce utilization.

## Decision 4: Mock providers behind an interface
**Choice:** `fast` and `flaky` implement a common provider interface.

**Why:** The dialer is isolated from provider-specific behaviour and can be tested under failures.

**Trade-off:** Real provider integrations need webhook verification, request idempotency, status reconciliation, and provider-specific error handling.

## Decision 5: Persist call intent before initiation
**Choice:** Reserve resources and persist a call record before calling the provider.

**Why:** This reduces the chance that an initiated call has no local record.

**Trade-off:** A crash between database commit and provider request can leave an uncertain operation. Production should use a transactional outbox and provider idempotency keys.

## Decision 6: Event deduplication and monotonic state
**Choice:** Unique provider event IDs and terminal-state protection.

**Why:** Webhooks can be retried or delivered out of order.

**Trade-off:** Real systems may need richer reconciliation when two conflicting terminal events are received.
