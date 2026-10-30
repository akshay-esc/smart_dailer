def _make_call(client):
    client.post("/agents/bulk", json={"count": 1})
    client.post("/borrowers/bulk", json={"count": 1})
    result = client.post("/dial/progressive", json={"max_calls": 1, "provider": "fast"}).json()
    return result["calls"][0]["call_id"]

def test_duplicate_provider_event_is_idempotent(client):
    call_id = _make_call(client)
    event = {"provider": "fast", "event_id": "evt-1", "call_id": call_id, "status": "RINGING"}
    first = client.post("/provider-events", json=event).json()
    second = client.post("/provider-events", json=event).json()
    assert first["duplicate"] is False
    assert second["duplicate"] is True

def test_terminal_call_does_not_regress_on_late_event(client):
    call_id = _make_call(client)
    completed = {"provider": "fast", "event_id": "evt-complete", "call_id": call_id, "status": "COMPLETED"}
    late = {"provider": "fast", "event_id": "evt-ring", "call_id": call_id, "status": "RINGING"}
    client.post("/provider-events", json=completed)
    response = client.post("/provider-events", json=late).json()
    assert response["call_status"] == "COMPLETED"
def test_invalid_provider_event_is_rejected(client):
    call_id = _make_call(client)

    event = {
        "provider": "fast",
        "event_id": "evt-invalid",
        "call_id": call_id,
        "status": "RINGING",
    }

    first = client.post("/provider-events", json=event)
    assert first.status_code == 200

    # The API schema rejects unsupported event values.
    invalid = {
        "provider": "fast",
        "event_id": "evt-invalid-2",
        "call_id": call_id,
        "status": "UNKNOWN",
    }

    response = client.post("/provider-events", json=invalid)
    assert response.status_code == 422


def test_provider_mismatch_is_rejected(client):
    call_id = _make_call(client)

    event = {
        "provider": "flaky",
        "event_id": "evt-mismatch",
        "call_id": call_id,
        "status": "RINGING",
    }

    response = client.post("/provider-events", json=event)

    assert response.status_code == 200
    assert response.json()["accepted"] is False
    assert response.json()["reason"] == "provider_mismatch"


def test_call_state_does_not_move_backwards(client):
    call_id = _make_call(client)

    connected = {
        "provider": "fast",
        "event_id": "evt-connected",
        "call_id": call_id,
        "status": "CONNECTED",
    }

    client.post("/provider-events", json=connected)

    late_ringing = {
        "provider": "fast",
        "event_id": "evt-late-ringing",
        "call_id": call_id,
        "status": "RINGING",
    }

    response = client.post("/provider-events", json=late_ringing)

    assert response.status_code == 200
    assert response.json()["call_status"] == "CONNECTED"
    assert response.json()["changed"] is False