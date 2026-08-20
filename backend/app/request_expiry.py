import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import MaterialRequest, RequestAudit, RequestStatus


logger = logging.getLogger(__name__)
REQUEST_RETENTION_DAYS = 7
EXPIRY_CHECK_INTERVAL_SECONDS = 60 * 60


def delete_expired_requests(db: Session, now: datetime | None = None) -> int:
    """Permanently remove unfinished requests seven days after creation."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=REQUEST_RETENTION_DAYS)
    expired_ids = list(
        db.scalars(
            select(MaterialRequest.id).where(
                MaterialRequest.status != RequestStatus.COMPLETED.value,
                MaterialRequest.created_at <= cutoff,
            )
        )
    )
    if not expired_ids:
        return 0

    db.execute(delete(RequestAudit).where(RequestAudit.request_id.in_(expired_ids)))
    db.execute(delete(MaterialRequest).where(MaterialRequest.id.in_(expired_ids)))
    db.commit()
    return len(expired_ids)


async def request_expiry_worker() -> None:
    while True:
        try:
            with SessionLocal() as db:
                deleted = delete_expired_requests(db)
                if deleted:
                    logger.info("Deleted %s expired material requests", deleted)
        except Exception:
            logger.exception("Unable to delete expired material requests")
        await asyncio.sleep(EXPIRY_CHECK_INTERVAL_SECONDS)
