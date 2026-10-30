def test_progressive_never_exceeds_available_agents(client):
    client.post("/agents/bulk", json={"count": 2})
    client.post("/borrowers/bulk", json={"count": 10})
    response = client.post("/dial/progressive", json={"max_calls": 10, "provider": "fast"})
    assert response.status_code == 200
    data = response.json()
    assert data["created"] <= 2
    assert data["safety_approved"] == 2

def test_safety_controller_reduces_request(client):
    client.post("/agents/bulk", json={"count": 1})
    client.post("/borrowers/bulk", json={"count": 5})
    response = client.post("/dial/predictive", json={"max_requested": 5, "provider": "fast"})
    assert response.status_code == 200
    assert response.json()["created"] <= 1

def test_unhealthy_provider_blocks_new_calls(client):
    client.post("/agents/bulk", json={"count": 2})
    client.post("/borrowers/bulk", json={"count": 2})
    client.post("/providers/fast/health", json={"health": "unhealthy"})
    response = client.post("/dial/progressive", json={"max_calls": 2, "provider": "fast"})
    assert response.json()["created"] == 0
def test_failed_provider_releases_agent_and_borrower(client):
    client.post("/agents/bulk", json={"count": 1})
    client.post("/borrowers/bulk", json={"count": 1})

    # Mark the provider unhealthy so initiation cannot proceed.
    client.post(
        "/providers/fast/health",
        json={"health": "unhealthy"},
    )

    response = client.post(
        "/dial/progressive",
        json={"max_calls": 1, "provider": "fast"},
    )

    assert response.status_code == 200
    assert response.json()["created"] == 0

    agents = client.get("/agents").json()
    borrowers = client.get("/borrowers").json()

    assert agents[0]["status"] == "AVAILABLE"
    assert borrowers[0]["status"] == "QUEUED"
from app.providers import registry, InitiationResult


def test_provider_initiation_failure_releases_resources(client, monkeypatch):
    client.post("/agents/bulk", json={"count": 1})
    client.post("/borrowers/bulk", json={"count": 1})

    provider = registry.get("fast")
    monkeypatch.setattr(
        provider,
        "initiate_call",
        lambda call_id, phone: InitiationResult(
            accepted=False,
            provider_call_id=None,
            error="simulated_failure",
        ),
    )

    response = client.post(
        "/dial/progressive",
        json={"max_calls": 1, "provider": "fast"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["created"] == 1
    assert data["calls"][0]["status"] == "FAILED"

    agents = client.get("/agents").json()
    borrowers = client.get("/borrowers").json()

    assert agents[0]["status"] == "AVAILABLE"
    assert borrowers[0]["status"] == "QUEUED"
from concurrent.futures import ThreadPoolExecutor


def test_concurrent_dialing_does_not_reuse_agent(client):
    client.post("/agents/bulk", json={"count": 2})
    client.post("/borrowers/bulk", json={"count": 10})

    def make_request():
        return client.post(
            "/dial/progressive",
            json={"max_calls": 2, "provider": "fast"},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(make_request)
            for _ in range(2)
        ]
        responses = [future.result() for future in futures]

    assert all(response.status_code == 200 for response in responses)

    calls = client.get("/calls").json()

    active_calls = [
        call for call in calls
        if call["status"] in {
            "RESERVED", "INITIATED", "RINGING",
            "ANSWERED", "CONNECTED",
        }
    ]

    active_agent_ids = [call["agent_id"] for call in active_calls]

    assert len(active_agent_ids) == len(set(active_agent_ids))
    assert len(active_calls) <= 2

from datetime import datetime, timedelta, timezone
from app.models import Agent, Borrower, Call
def test_stale_reservation_recovery(client, test_session_factory):
    from datetime import datetime, timedelta, timezone
    from app.models import Call, Agent, Borrower

    client.post("/agents/bulk", json={"count": 1})
    client.post("/borrowers/bulk", json={"count": 1})

    response = client.post(
        "/dial/progressive",
        json={"max_calls": 1, "provider": "fast"},
    )

    assert response.status_code == 200
    call_id = response.json()["calls"][0]["call_id"]

    # Access the same in-memory database used by the API.
    with test_session_factory() as db:
        call = db.get(Call, call_id)
        assert call is not None

        call.status = "RESERVED"
        call.created_at = datetime.now(timezone.utc) - timedelta(
            seconds=300
        )

        agent = db.get(Agent, call.agent_id)
        borrower = db.get(Borrower, call.borrower_id)

        agent.status = "RESERVED"
        agent.reserved_call_id = call.id

        borrower.status = "RESERVED"
        borrower.reserved_call_id = call.id

        db.commit()

    recovery = client.post(
        "/maintenance/recover-stale-reservations?timeout_seconds=120"
    )

    assert recovery.status_code == 200
    assert recovery.json()["recovered_count"] == 1

    calls = client.get("/calls").json()
    recovered_call = next(
        call for call in calls if call["id"] == call_id
    )

    assert recovered_call["status"] == "FAILED"

    agents = client.get("/agents").json()
    borrowers = client.get("/borrowers").json()

    assert agents[0]["status"] == "AVAILABLE"
    assert borrowers[0]["status"] == "QUEUED"