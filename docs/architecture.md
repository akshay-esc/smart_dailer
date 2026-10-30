# Architecture

```text
                  +----------------------+
                  | Campaign / API       |
                  | borrower queue       |
                  +----------+-----------+
                             |
                             v
                  +----------------------+
                  | Pacing Engine        |
                  | proposes N calls    |
                  +----------+-----------+
                             |
                             v
                  +----------------------+
                  | Safety Controller    |
                  | independent cap     |
                  +----------+-----------+
                             |
                             v
                  +----------------------+
                  | Call Allocator       |
                  | atomic reservations |
                  +----------+-----------+
                             |
                             v
                  +----------------------+
                  | Provider Interface   |
                  +----------+-----------+
                         /       \
                        v         v
                   Fast Mock   Flaky Mock

Provider events -> Event deduplication -> Call state machine -> DB state
```

## Main safety invariants

1. An agent with an active reservation is not eligible for another allocation.
2. A borrower with an active reservation is not eligible for another call.
3. A request from the pacing engine is only a proposal; the Safety Controller caps it.
4. Atomic conditional updates are authoritative at reservation time.
5. Terminal call states never regress due to late provider events.
6. Duplicate `(provider, event_id)` events have no repeated side effects.

## Production evolution

- Replace SQLite with PostgreSQL and use row-level locks / `SKIP LOCKED` where appropriate.
- Add a transactional outbox for call-initiation requests.
- Use a durable queue for event delivery and retry work.
- Add provider webhook signature validation, authentication, authorization, audit trails, rate limits, retention policies, and explicit consent/compliance checks.
- Use provider-specific reconciliation APIs for uncertain initiation outcomes.
- Add campaign-level throttles, time windows, opt-out suppression, and jurisdiction-specific calling rules before any real calls.
