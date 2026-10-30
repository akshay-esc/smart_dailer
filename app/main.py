from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.database import get_db, init_db
from app.models import Agent, Borrower, Call, ProviderEvent
from app.schemas import AgentCreate, BulkCreate, BorrowerCreate, DialRequest, PredictiveDialRequest, ProviderEventIn, ProviderHealthUpdate, AgentStatusUpdate
from app.dialer import dialer
from app.providers import registry

app = FastAPI(title="SmartDialer Prototype", version="1.0.0",
              description="Local simulation of safe progressive and predictive dialing.")

@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok", "service": "smartdialer"}

@app.post("/agents")
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    agent = Agent(name=payload.name, status=payload.status)
    db.add(agent); db.commit(); db.refresh(agent)
    return {"id": agent.id, "name": agent.name, "status": agent.status}

@app.post("/agents/bulk")
def create_agents(payload: BulkCreate, db: Session = Depends(get_db)):
    agents = [Agent(name=f"Agent {i+1}") for i in range(payload.count)]
    db.add_all(agents); db.commit()
    return {"created": len(agents)}

@app.get("/agents")
def list_agents(db: Session = Depends(get_db)):
    return [{"id": a.id, "name": a.name, "status": a.status, "reserved_call_id": a.reserved_call_id}
            for a in db.scalars(select(Agent).order_by(Agent.id))]

@app.patch("/agents/{agent_id}")
def update_agent(agent_id: int, payload: AgentStatusUpdate, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if agent.status in {"RESERVED", "DIALING", "CONNECTED"} and payload.status in {"AVAILABLE", "OFFLINE", "PAUSED"}:
        raise HTTPException(409, "Cannot manually change an agent with an active call reservation")
    agent.status = payload.status; db.commit()
    return {"id": agent.id, "status": agent.status}
@app.post("/agents/{agent_id}/complete-wrap-up")
def complete_agent_wrap_up(
    agent_id: int,
    db: Session = Depends(get_db),
):
    result = dialer.complete_agent_wrap_up(db, agent_id)

    if not result["success"]:
        if result["reason"] == "agent_not_found":
            raise HTTPException(status_code=404, detail=result["reason"])

        raise HTTPException(status_code=409, detail=result)

    return result

@app.post("/borrowers")
def create_borrower(payload: BorrowerCreate, db: Session = Depends(get_db)):
    borrower = Borrower(name=payload.name, phone=payload.phone)
    db.add(borrower); db.commit(); db.refresh(borrower)
    return {"id": borrower.id, "name": borrower.name, "status": borrower.status}

@app.post("/borrowers/bulk")
def create_borrowers(payload: BulkCreate, db: Session = Depends(get_db)):
    borrowers = [Borrower(name=f"Borrower {i+1}", phone=f"+1555000{i:04d}") for i in range(payload.count)]
    db.add_all(borrowers); db.commit()
    return {"created": len(borrowers)}

@app.get("/borrowers")
def list_borrowers(db: Session = Depends(get_db)):
    return [{"id": b.id, "name": b.name, "status": b.status, "reserved_call_id": b.reserved_call_id}
            for b in db.scalars(select(Borrower).order_by(Borrower.id))]

@app.post("/dial/progressive")
def progressive(payload: DialRequest, db: Session = Depends(get_db)):
    return dialer.dial(db, payload.campaign_id, payload.provider, payload.max_calls, "progressive")

@app.post("/dial/predictive")
def predictive(payload: PredictiveDialRequest, db: Session = Depends(get_db)):
    proposed, explanation = dialer.pacing.propose(db, payload.max_requested, payload.provider)
    result = dialer.dial(db, payload.campaign_id, payload.provider, proposed, "predictive")
    result["pacing"] = explanation
    return result

@app.get("/calls")
def list_calls(db: Session = Depends(get_db)):
    calls = db.scalars(select(Call).order_by(Call.created_at.desc())).all()
    return [{"id": c.id, "campaign_id": c.campaign_id, "agent_id": c.agent_id,
             "borrower_id": c.borrower_id, "provider": c.provider, "status": c.status,
             "provider_call_id": c.provider_call_id, "last_error": c.last_error} for c in calls]

@app.get("/calls/{call_id}")
def get_call(call_id: str, db: Session = Depends(get_db)):
    c = db.get(Call, call_id)
    if not c:
        raise HTTPException(404, "Call not found")
    return {"id": c.id, "campaign_id": c.campaign_id, "agent_id": c.agent_id,
            "borrower_id": c.borrower_id, "provider": c.provider, "status": c.status,
            "provider_call_id": c.provider_call_id, "last_error": c.last_error}
@app.post("/maintenance/recover-stale-reservations")
def recover_stale_reservations(
    timeout_seconds: int = 120,
    db: Session = Depends(get_db),
):
    try:
        return dialer.recover_stale_reservations(
            db,
            timeout_seconds=timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/provider-events")
def provider_event(payload: ProviderEventIn, db: Session = Depends(get_db)):
    return dialer.process_event(db, payload.provider, payload.event_id, payload.call_id, payload.status)

@app.post("/providers/{provider_name}/health")
def set_provider_health(provider_name: str, payload: ProviderHealthUpdate):
    try:
        provider = registry.get(provider_name)
    except ValueError:
        raise HTTPException(404, "Unknown provider")
    provider.set_health(payload.health == "healthy")
    return {"provider": provider_name, "health": payload.health}

@app.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    def count(model, condition=None):
        stmt = select(func.count()).select_from(model)

        if condition is not None:
            stmt = stmt.where(condition)

        return db.scalar(stmt) or 0

    total_agents = count(Agent)

    available = count(Agent, Agent.status == "AVAILABLE")
    reserved = count(Agent, Agent.status == "RESERVED")
    dialing = count(Agent, Agent.status == "DIALING")
    connected = count(Agent, Agent.status == "CONNECTED")
    wrap_up = count(Agent, Agent.status == "WRAP_UP")
    paused = count(Agent, Agent.status == "PAUSED")
    offline = count(Agent, Agent.status == "OFFLINE")

    total_calls = count(Call)

    initiated = count(
        Call,
        Call.status.in_([
            "INITIATED",
            "RINGING",
            "ANSWERED",
            "CONNECTED",
            "COMPLETED",
        ]),
    )

    ringing = count(Call, Call.status == "RINGING")
    answered = count(Call, Call.status == "ANSWERED")
    connected_calls = count(Call, Call.status == "CONNECTED")
    completed = count(Call, Call.status == "COMPLETED")
    failed = count(Call, Call.status == "FAILED")
    cancelled = count(Call, Call.status == "CANCELLED")

    queued = count(Borrower, Borrower.status == "QUEUED")

    occupancy_pct = (
        round((total_agents - available) / total_agents * 100, 2)
        if total_agents
        else 0
    )

    active_call_utilization_pct = (
        round(connected / total_agents * 100, 2)
        if total_agents
        else 0
    )

    return {
        "agents_total": total_agents,
        "agents_available": available,
        "agents_reserved": reserved,
        "agents_dialing": dialing,
        "agents_connected": connected,
        "agents_wrap_up": wrap_up,
        "agents_paused": paused,
        "agents_offline": offline,
        "agent_occupancy_pct": occupancy_pct,
        "active_call_utilization_pct": active_call_utilization_pct,
        "calls_total": total_calls,
        "calls_initiated_or_beyond": initiated,
        "calls_ringing": ringing,
        "calls_answered": answered,
        "calls_connected": connected_calls,
        "calls_completed": completed,
        "calls_failed": failed,
        "calls_cancelled": cancelled,
        "borrowers_queued": queued,
        "provider_health": {
            name: ("healthy" if provider.healthy else "unhealthy")
            for name, provider in registry.providers.items()
        },
    }
