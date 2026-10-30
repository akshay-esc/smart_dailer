from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from app.models import Agent, Borrower, Call, ProviderEvent
from app.providers import registry
from app.state_machine import (
    apply_call_event,
    TERMINAL_CALL_STATES,
    ALLOWED_EVENTS,
)


@dataclass
class SafetyDecision:
    requested: int
    approved: int
    reason: str


class SafetyController:
    """Independent safety boundary for call allocation."""

    def decide(
        self,
        db: Session,
        requested: int,
        provider_name: str,
    ) -> SafetyDecision:
        if requested < 0:
            return SafetyDecision(requested, 0, "invalid_request")
        if requested == 0:
            return SafetyDecision(requested, 0, "no_calls_proposed")
        try:
            provider = registry.get(provider_name)
        except ValueError:
            return SafetyDecision(requested, 0, "unknown_provider")

        if not provider.healthy:
            return SafetyDecision(requested, 0, "provider_unhealthy")

        available_agents = (
            db.scalar(
                select(func.count())
                .select_from(Agent)
                .where(Agent.status == "AVAILABLE")
            )
            or 0
        )

        queued_borrowers = (
            db.scalar(
                select(func.count())
                .select_from(Borrower)
                .where(Borrower.status == "QUEUED")
            )
            or 0
        )

        approved = max(
            0,
            min(requested, available_agents, queued_borrowers),
        )

        reason = (
            "approved"
            if approved == requested
            else "reduced_to_current_capacity"
        )

        return SafetyDecision(requested, approved, reason)


class PredictivePacingEngine:
    """Proposes a dialing quantity without allocating or initiating calls."""

    def propose(
        self,
        db: Session,
        max_requested: int,
        provider_name: str,
    ) -> tuple[int, dict]:
        provider = registry.get(provider_name)

        available = (
            db.scalar(
                select(func.count())
                .select_from(Agent)
                .where(Agent.status == "AVAILABLE")
            )
            or 0
        )

        queued = (
            db.scalar(
                select(func.count())
                .select_from(Borrower)
                .where(Borrower.status == "QUEUED")
            )
            or 0
        )

        recent_calls = list(
            db.scalars(
                select(Call)
                .order_by(Call.created_at.desc())
                .limit(50)
            )
        )

        observed_calls = [
            call
            for call in recent_calls
            if call.status in TERMINAL_CALL_STATES
        ]

        answered_calls = [
            call
            for call in observed_calls
            if call.status == "COMPLETED"
        ]

        if observed_calls:
            answer_rate = len(answered_calls) / len(observed_calls)
        else:
            answer_rate = 0.35

        answer_rate = min(0.9, max(0.1, answer_rate))

        if provider_name == "flaky":
            answer_rate *= 0.75

        proposed = min(
            max_requested,
            queued,
            max(0, int(available / max(answer_rate, 0.1))),
        )

        if not provider.healthy:
            proposed = 0

        explanation = {
            "available_agents": available,
            "queued_borrowers": queued,
            "estimated_answer_rate": round(answer_rate, 3),
            "recent_calls_sampled": len(recent_calls),
            "provider_healthy": provider.healthy,
            "proposed_calls": proposed,
        }

        return proposed, explanation


class SmartDialer:
    def __init__(self):
        self.safety = SafetyController()
        self.pacing = PredictivePacingEngine()

    def _reserve_one(
        self,
        db: Session,
        campaign_id: str,
        provider_name: str,
    ):
        """Reserve one available agent and one queued borrower."""

        agent = db.scalar(
            select(Agent)
            .where(Agent.status == "AVAILABLE")
            .order_by(Agent.id)
            .limit(1)
        )

        borrower = db.scalar(
            select(Borrower)
            .where(Borrower.status == "QUEUED")
            .order_by(Borrower.id)
            .limit(1)
        )

        if agent is None or borrower is None:
            return None

        call_id = "CALL-" + uuid4().hex[:12].upper()

        agent_result = db.execute(
            update(Agent)
            .where(
                Agent.id == agent.id,
                Agent.status == "AVAILABLE",
            )
            .values(
                status="RESERVED",
                reserved_call_id=call_id,
            )
        )

        if agent_result.rowcount != 1:
            db.rollback()
            return None

        borrower_result = db.execute(
            update(Borrower)
            .where(
                Borrower.id == borrower.id,
                Borrower.status == "QUEUED",
            )
            .values(
                status="RESERVED",
                reserved_call_id=call_id,
            )
        )

        if borrower_result.rowcount != 1:
            db.rollback()
            return None

        call = Call(
            id=call_id,
            campaign_id=campaign_id,
            agent_id=agent.id,
            borrower_id=borrower.id,
            provider=provider_name,
            status="RESERVED",
        )

        db.add(call)
        db.flush()

        return call

    def dial(
        self,
        db: Session,
        campaign_id: str,
        provider_name: str,
        requested: int,
        mode: str,
    ):
        """Apply safety limits, reserve resources, and initiate calls."""

        decision = self.safety.decide(
            db,
            requested,
            provider_name,
        )

        approved = decision.approved
        created_ids = []

        for _ in range(approved):
            try:
                with db.begin_nested():
                    call = self._reserve_one(
                        db,
                        campaign_id,
                        provider_name,
                    )

                    if call is not None:
                        created_ids.append(call.id)

                db.commit()

            except Exception:
                db.rollback()
                continue

        provider = registry.get(provider_name)
        outcomes = []

        for call_id in created_ids:
            call = db.get(Call, call_id)

            if call is None:
                continue

            borrower = db.get(Borrower, call.borrower_id)
            agent = db.get(Agent, call.agent_id)

            if borrower is None or agent is None:
                self._fail_call(
                    db,
                    call,
                    "reserved_resource_missing",
                )

                outcomes.append({
                    "call_id": call.id,
                    "status": "FAILED",
                    "error": "reserved_resource_missing",
                })
                continue

            if not provider.healthy:
                self._fail_call(
                    db,
                    call,
                    "provider_unhealthy",
                )

                outcomes.append({
                    "call_id": call.id,
                    "status": "FAILED",
                    "error": "provider_unhealthy",
                })
                continue

            try:
                result = provider.initiate_call(
                    call.id,
                    borrower.phone,
                )

            except Exception as exc:
                self._fail_call(
                    db,
                    call,
                    f"provider_exception:{type(exc).__name__}",
                )

                outcomes.append({
                    "call_id": call.id,
                    "status": "FAILED",
                    "error": "provider_exception",
                })
                continue

            if result.accepted:
                call.provider_call_id = result.provider_call_id
                call.status = "INITIATED"
                agent.status = "DIALING"

                db.commit()

                outcomes.append({
                    "call_id": call.id,
                    "status": "INITIATED",
                })

            else:
                error = result.error or "provider_error"

                self._fail_call(db, call, error)

                outcomes.append({
                    "call_id": call.id,
                    "status": "FAILED",
                    "error": error,
                })

        return {
            "mode": mode,
            "requested": requested,
            "safety_approved": approved,
            "safety_reason": decision.reason,
            "created": len(created_ids),
            "calls": outcomes,
        }

    def _fail_call(
        self,
        db: Session,
        call: Call,
        reason: str,
    ):
        """Mark a failed call and release its reserved resources."""

        call.status = "FAILED"
        call.last_error = reason

        agent = db.get(Agent, call.agent_id)
        borrower = db.get(Borrower, call.borrower_id)

        if agent and agent.reserved_call_id == call.id:
            agent.status = "AVAILABLE"
            agent.reserved_call_id = None

        if borrower and borrower.reserved_call_id == call.id:
            borrower.status = "QUEUED"
            borrower.reserved_call_id = None

        db.commit()

    def process_event(
        self,
        db: Session,
        provider_name: str,
        event_id: str,
        call_id: str,
        status: str,
    ):
        """Process provider events and reject invalid or mismatched events."""

        if status not in ALLOWED_EVENTS:
            return {
                "accepted": False,
                "reason": "invalid_event",
            }

        call = db.get(Call, call_id)

        if call is None:
            return {
                "accepted": False,
                "reason": "unknown_call",
            }

        if call.provider != provider_name:
            return {
                "accepted": False,
                "reason": "provider_mismatch",
            }

        existing = db.scalar(
            select(ProviderEvent).where(
                ProviderEvent.provider == provider_name,
                ProviderEvent.event_id == event_id,
            )
        )

        if existing:
            return {
                "accepted": True,
                "duplicate": True,
                "call_status": call.status,
            }

        event = ProviderEvent(
            provider=provider_name,
            event_id=event_id,
            call_id=call_id,
            status=status,
        )

        db.add(event)

        try:
            db.flush()

        except IntegrityError:
            db.rollback()
            current_call = db.get(Call, call_id)

            return {
                "accepted": True,
                "duplicate": True,
                "call_status": (
                    current_call.status if current_call else None
                ),
            }

        new_state, changed = apply_call_event(
            call.status,
            status,
        )

        call.status = new_state

        agent = db.get(Agent, call.agent_id)
        borrower = db.get(Borrower, call.borrower_id)

        if changed and new_state not in TERMINAL_CALL_STATES:
            if agent and agent.reserved_call_id == call.id:
                if new_state == "CONNECTED":
                    agent.status = "CONNECTED"
                elif new_state in {"RINGING", "ANSWERED"}:
                    agent.status = "DIALING"

        if changed and new_state in TERMINAL_CALL_STATES:
            if agent and agent.reserved_call_id == call.id:
                agent.status = (
                    "WRAP_UP"
                    if new_state == "COMPLETED"
                    else "AVAILABLE"
                )
                agent.reserved_call_id = None

            if borrower and borrower.reserved_call_id == call.id:
                borrower.status = (
                    "CALLED"
                    if new_state == "COMPLETED"
                    else "QUEUED"
                )
                borrower.reserved_call_id = None

        db.commit()

        return {
            "accepted": True,
            "duplicate": False,
            "changed": changed,
            "call_status": call.status,
        }
    def recover_stale_reservations(
        self,
        db: Session,
        timeout_seconds: int = 120,
    ):
        """
        Recover calls that remain RESERVED beyond the timeout.

        Only RESERVED calls are recovered. Calls that have already been
        initiated are not automatically failed because the provider may
        already have accepted them.
        """
        from datetime import datetime, timedelta, timezone

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=timeout_seconds
        )

        stale_calls = list(
            db.scalars(
                select(Call).where(
                    Call.status == "RESERVED",
                    Call.created_at < cutoff,
                )
            )
        )

        recovered = []

        try:
            for call in stale_calls:
                # Reload the resources and verify that they still belong
                # to this call before releasing them.
                agent = db.get(Agent, call.agent_id)
                borrower = db.get(Borrower, call.borrower_id)

                call.status = "FAILED"
                call.last_error = "stale_reservation_recovered"

                if agent and agent.reserved_call_id == call.id:
                    agent.status = "AVAILABLE"
                    agent.reserved_call_id = None

                if borrower and borrower.reserved_call_id == call.id:
                    borrower.status = "QUEUED"
                    borrower.reserved_call_id = None

                recovered.append(call.id)

            db.commit()

        except Exception:
            db.rollback()
            raise

        return {
            "recovered_count": len(recovered),
            "recovered_call_ids": recovered,
            "timeout_seconds": timeout_seconds,
        }
    def complete_agent_wrap_up(self, db: Session, agent_id: int):
        # """Return an agent from WRAP_UP to AVAILABLE."""
        agent = db.get(Agent, agent_id)
        if agent is None:
            return {
                "success": False,
                "reason": "agent_not_found",
            }
        if agent.status != "WRAP_UP":
            return {
                "success": False,
                "reason": "agent_not_in_wrap_up",
                "current_status": agent.status,
            }
        agent.status = "AVAILABLE"
        agent.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "success": True,
            "agent_id": agent.id,
            "status": agent.status,
        }

dialer = SmartDialer()