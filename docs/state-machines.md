# State machines

## Agent

```text
OFFLINE -> AVAILABLE -> RESERVED -> DIALING -> CONNECTED -> WRAP_UP -> AVAILABLE
                  \-> PAUSED
AVAILABLE -> OFFLINE
AVAILABLE -> PAUSED
```

In this prototype, an agent becomes `RESERVED` during allocation, `DIALING` after provider initiation, `CONNECTED` after a CONNECTED event, and `WRAP_UP` after a completed call. Failed/cancelled calls release the agent to `AVAILABLE`.

## Call

```text
QUEUED -> RESERVED -> INITIATED -> RINGING -> ANSWERED -> CONNECTED -> COMPLETED
                      |             |          |
                      +-------------+----------+----> FAILED / CANCELLED
```

Provider events may skip intermediate states. Duplicate events are deduplicated by provider and event ID. Terminal states (`COMPLETED`, `FAILED`, `CANCELLED`) cannot regress. In a production design, event timestamps/sequence numbers and provider reconciliation would be used to resolve conflicting terminal outcomes.
