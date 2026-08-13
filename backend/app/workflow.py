from sqlalchemy.orm import Session
from .models import MaterialRequest, RequestAudit, User


def transition(db: Session, req: MaterialRequest, actor: User, action: str, to_status: str, note: str | None = None):
    before = req.status
    req.status = to_status
    req.returned_reason = note if "RETURN" in action else None
    db.add(RequestAudit(request_id=req.id, actor_id=actor.id, action=action, from_status=before, to_status=to_status, note=note))
    db.commit(); db.refresh(req)
    return req
