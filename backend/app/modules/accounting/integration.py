"""Public interface for business modules to emit accounting events.

Business modules import ONLY from this file — never from accounting.service or
accounting.models directly.  This is the EventPublisher: the sync-now /
async-later seam.

  Current: EventPublisher.publish() calls PostingService in the SAME database
           transaction as the business operation (atomic by design).

  Future:  Replace the body of publish() with a broker enqueue.  Business
           modules remain unchanged.

Isolation invariant (enforced by AST contract test):
  • accounting.service  imports NOTHING from sales / purchasing / inventory.
  • This file also imports NOTHING from those modules.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from app.modules.accounting.service import (
    EntryType,
    PostingEvent,
    PostingResult,
    SourceModule,
    find_and_reverse_je,
    get_default_accounts,
    get_or_create_settings,
    posting_service,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class EventPublisher:
    """Thin synchronous dispatch layer between business modules and the engine.

    Checks ``enable_auto_posting`` on ``AccountingSettings`` before every call:
      • False (default) → silently skip.  Existing companies without accounting
        configured continue to operate; no journal entries are created.
      • True  → posting is ATOMIC with the business operation.  Any failure
        (closed period, missing account, unbalanced template) propagates as an
        exception and rolls back the caller's transaction.
    """

    def publish(self, db: Session, event: PostingEvent) -> PostingResult | None:
        """Post a business event synchronously.

        Returns None when auto-posting is disabled.
        Raises on any posting failure so the caller's transaction rolls back.
        """
        settings = get_or_create_settings(db, event.company_id)
        if not settings.enable_auto_posting:
            return None
        return posting_service.post(db, event)

    def reverse_document(
        self,
        db: Session,
        idempotency_key: str,
        reversal_date: datetime.date,
        company_id: int,
        actor_id: int | None,
    ) -> object | None:
        """Find a POSTED JE by idempotency key and reverse it atomically.

        Returns None when:
          • auto-posting is disabled for this company, OR
          • no POSTED JE exists for the key (original posting was skipped or
            already reversed — safe to call unconditionally on every cancel path).
        """
        settings = get_or_create_settings(db, company_id)
        if not settings.enable_auto_posting:
            return None
        return find_and_reverse_je(db, idempotency_key, reversal_date, company_id, actor_id)


event_publisher = EventPublisher()

__all__ = [
    "EntryType",
    "EventPublisher",
    "PostingEvent",
    "PostingResult",
    "SourceModule",
    "event_publisher",
    "get_default_accounts",
]
