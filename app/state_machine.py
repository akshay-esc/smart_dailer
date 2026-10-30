TERMINAL_CALL_STATES = {"COMPLETED", "FAILED", "CANCELLED"}

ALLOWED_EVENTS = {
    "RINGING",
    "ANSWERED",
    "CONNECTED",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
}

# Valid forward transitions for provider events. Providers may skip
# intermediate states, but calls cannot move backward.

ALLOWED_TRANSITIONS = {
    "RESERVED": {
        "RINGING",
        "ANSWERED",
        "CONNECTED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    },
    "INITIATED": {
        "RINGING",
        "ANSWERED",
        "CONNECTED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    },
    "RINGING": {
        "ANSWERED",
        "CONNECTED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    },
    "ANSWERED": {
        "CONNECTED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    },
    "CONNECTED": {
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    },
}

def apply_call_event(current: str, event: str) -> tuple[str, bool]:
    """Apply a provider event and return (new_state, changed).

    Terminal states cannot be reopened. Invalid events and backward
    transitions are ignored; providers may skip intermediate states.
    """
    if event not in ALLOWED_EVENTS:
        return current, False

    if current in TERMINAL_CALL_STATES:
        return current, False

    if event == current:
        return current, False

    allowed = ALLOWED_TRANSITIONS.get(current, set())

    if event in allowed:
        return event, True

    return current, False