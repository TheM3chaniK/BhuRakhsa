from typing import Any, Dict
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.area_officer_assignment import AreaOfficerAssignment
from app.models.enums import NotificationChannel, NotificationStatus, NotificationType
from app.models.notification import Notification


async def handle_case_approved(db: AsyncSession, payload: Dict[str, Any], event_id: uuid.UUID) -> None:
    """Send in-app approval notification to the civilian case owner."""
    user_id = uuid.UUID(str(payload["owner_id"]))
    case_id = uuid.UUID(str(payload["case_id"]))

    notif = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        case_id=case_id,
        event_id=event_id,
        type=NotificationType.CASE_APPROVED,
        title="Property verification completed",
        message="Your property verification case has been approved.",
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.SENT,
        data={"action": "open_case", "case_id": str(case_id)},
    )
    db.add(notif)


async def handle_case_rejected(db: AsyncSession, payload: Dict[str, Any], event_id: uuid.UUID) -> None:
    """Send in-app rejection notification to the civilian case owner."""
    user_id = uuid.UUID(str(payload["owner_id"]))
    case_id = uuid.UUID(str(payload["case_id"]))

    notif = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        case_id=case_id,
        event_id=event_id,
        type=NotificationType.CASE_REJECTED,
        title="Property verification completed",
        message="Your property verification case has been rejected. Please review the case details for the available decision information.",
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.SENT,
        data={"action": "open_case", "case_id": str(case_id)},
    )
    db.add(notif)


async def handle_proof_requested(db: AsyncSession, payload: Dict[str, Any], event_id: uuid.UUID) -> None:
    """Send in-app notification to the civilian when proof is requested."""
    user_id = uuid.UUID(str(payload["requested_from"]))
    case_id = uuid.UUID(str(payload["case_id"]))
    proof_request_id = payload.get("proof_request_id")

    notif = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        case_id=case_id,
        event_id=event_id,
        type=NotificationType.PROOF_REQUESTED,
        title="Additional proof required",
        message="Additional documentation is required for your property verification case.",
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.SENT,
        data={
            "action": "open_proof_request",
            "case_id": str(case_id),
            "proof_request_id": str(proof_request_id) if proof_request_id else None,
        },
    )
    db.add(notif)


async def handle_proof_submitted(db: AsyncSession, payload: Dict[str, Any], event_id: uuid.UUID) -> None:
    """Send in-app notification to Area Officers assigned to the case area."""
    case_id = uuid.UUID(str(payload["case_id"]))
    area_id = uuid.UUID(str(payload["area_id"]))
    proof_request_id = payload.get("proof_request_id")

    # Find active officers in this area
    officers_stmt = select(AreaOfficerAssignment.user_id).where(
        AreaOfficerAssignment.area_id == area_id,
        AreaOfficerAssignment.is_active.is_(True),
    )
    officers_res = await db.execute(officers_stmt)
    officer_ids = list(officers_res.scalars().all())

    for officer_id in officer_ids:
        notif = Notification(
            id=uuid.uuid4(),
            user_id=officer_id,
            case_id=case_id,
            event_id=event_id,
            type=NotificationType.PROOF_SUBMITTED,
            title="New proof submitted",
            message="A civilian has uploaded requested documentation for case verification.",
            channel=NotificationChannel.IN_APP,
            status=NotificationStatus.SENT,
            data={
                "action": "review_proof",
                "case_id": str(case_id),
                "proof_request_id": str(proof_request_id) if proof_request_id else None,
            },
        )
        db.add(notif)


async def handle_proof_accepted(db: AsyncSession, payload: Dict[str, Any], event_id: uuid.UUID) -> None:
    """Send in-app notification to the civilian when proof is accepted."""
    user_id = uuid.UUID(str(payload["requested_from"]))
    case_id = uuid.UUID(str(payload["case_id"]))

    notif = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        case_id=case_id,
        event_id=event_id,
        type=NotificationType.PROOF_ACCEPTED,
        title="Proof reviewed",
        message="The additional document you submitted has been accepted and your case will continue through verification.",
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.SENT,
        data={"action": "open_case", "case_id": str(case_id)},
    )
    db.add(notif)


async def handle_proof_rejected(db: AsyncSession, payload: Dict[str, Any], event_id: uuid.UUID) -> None:
    """Send in-app notification to the civilian when proof is rejected."""
    user_id = uuid.UUID(str(payload["requested_from"]))
    case_id = uuid.UUID(str(payload["case_id"]))

    notif = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        case_id=case_id,
        event_id=event_id,
        type=NotificationType.PROOF_REJECTED,
        title="Proof requires attention",
        message="The additional document submitted for your case was not accepted. Please review the proof request for further information.",
        channel=NotificationChannel.IN_APP,
        status=NotificationStatus.SENT,
        data={"action": "open_case", "case_id": str(case_id)},
    )
    db.add(notif)


HANDLERS = {
    "CaseApprovedEvent": handle_case_approved,
    "CaseRejectedEvent": handle_case_rejected,
    "ProofRequestedEvent": handle_proof_requested,
    "ProofSubmittedEvent": handle_proof_submitted,
    "ProofAcceptedEvent": handle_proof_accepted,
    "ProofRejectedEvent": handle_proof_rejected,
}
