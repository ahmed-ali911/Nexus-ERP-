from __future__ import annotations

import datetime
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApprovalRequired, BusinessRuleViolation, NotFoundError
from app.modules.shared.models import ApprovalRequest, ApprovalRequestType, ApprovalStatus


def _find_approval(
    db: Session,
    request_type: ApprovalRequestType,
    reference_type: str,
    reference_id: int,
    status: ApprovalStatus | None = None,
) -> ApprovalRequest | None:
    stmt = select(ApprovalRequest).where(
        ApprovalRequest.request_type == request_type,
        ApprovalRequest.reference_type == reference_type,
        ApprovalRequest.reference_id == reference_id,
    )
    if status is not None:
        stmt = stmt.where(ApprovalRequest.status == status)
    return db.scalars(stmt.order_by(ApprovalRequest.id.desc())).first()


def _require_approval(
    db: Session,
    company_id: int,
    request_type: ApprovalRequestType,
    reference_type: str,
    reference_id: int,
    requested_by: int | None,
    detail: str,
    metadata: dict | None = None,
) -> None:
    """Check for APPROVED approval; if not found, create PENDING and raise."""
    approved = _find_approval(
        db, request_type, reference_type, reference_id, ApprovalStatus.APPROVED
    )
    if approved is not None:
        return

    rejected = _find_approval(
        db, request_type, reference_type, reference_id, ApprovalStatus.REJECTED
    )
    if rejected is not None:
        raise BusinessRuleViolation(
            f"Approval #{rejected.id} for this operation was rejected"
        )

    pending = _find_approval(
        db, request_type, reference_type, reference_id, ApprovalStatus.PENDING
    )
    if pending is not None:
        raise ApprovalRequired(pending.id, f"Approval #{pending.id} is pending: {detail}")

    req = ApprovalRequest(
        company_id=company_id,
        request_type=request_type,
        reference_type=reference_type,
        reference_id=reference_id,
        requested_by=requested_by,
        approval_metadata=json.dumps(metadata) if metadata else None,
    )
    db.add(req)
    db.flush()
    raise ApprovalRequired(req.id, f"Approval #{req.id} created: {detail}")


def approve_request(
    db: Session,
    approval_id: int,
    company_id: int,
    actor_id: int,
) -> ApprovalRequest:
    req = db.get(ApprovalRequest, approval_id)
    if req is None or req.company_id != company_id:
        raise NotFoundError(f"ApprovalRequest {approval_id} not found")
    if req.status != ApprovalStatus.PENDING:
        raise BusinessRuleViolation(f"ApprovalRequest {approval_id} is already {req.status}")
    if req.requested_by == actor_id:
        raise BusinessRuleViolation("The requester cannot approve their own request (maker-checker)")
    req.status = ApprovalStatus.APPROVED
    req.approved_by = actor_id
    req.decided_at = datetime.datetime.now(datetime.UTC)
    db.flush()
    return req


def reject_request(
    db: Session,
    approval_id: int,
    company_id: int,
    actor_id: int,
    reason: str,
) -> ApprovalRequest:
    req = db.get(ApprovalRequest, approval_id)
    if req is None or req.company_id != company_id:
        raise NotFoundError(f"ApprovalRequest {approval_id} not found")
    if req.status != ApprovalStatus.PENDING:
        raise BusinessRuleViolation(f"ApprovalRequest {approval_id} is already {req.status}")
    if req.requested_by == actor_id:
        raise BusinessRuleViolation("The requester cannot reject their own request (maker-checker)")
    req.status = ApprovalStatus.REJECTED
    req.approved_by = actor_id
    req.reason = reason
    req.decided_at = datetime.datetime.now(datetime.UTC)
    db.flush()
    return req


def get_approval_request(
    db: Session, approval_id: int, company_id: int
) -> ApprovalRequest:
    req = db.get(ApprovalRequest, approval_id)
    if req is None or req.company_id != company_id:
        raise NotFoundError(f"ApprovalRequest {approval_id} not found")
    return req


def list_approval_requests(
    db: Session,
    company_id: int,
    status: ApprovalStatus | None = None,
    reference_type: str | None = None,
) -> list[ApprovalRequest]:
    stmt = select(ApprovalRequest).where(ApprovalRequest.company_id == company_id)
    if status is not None:
        stmt = stmt.where(ApprovalRequest.status == status)
    if reference_type is not None:
        stmt = stmt.where(ApprovalRequest.reference_type == reference_type)
    return list(db.scalars(stmt.order_by(ApprovalRequest.id.desc())))
