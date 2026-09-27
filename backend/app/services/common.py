from datetime import datetime, timezone
from ..models import AuditLog
from ..middleware.logging import event


def iso(ts):
    return (
        datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts is not None else None
    )


def audit(db, u, action, eid=None, detail=None, contest_id=None):
    event(action, user_id=u.id if u else None, entity_id=eid)
    db.add(
        AuditLog(
            user_id=u.id if u else None,
            action=action,
            entity_id=eid,
            contest_id=contest_id,
            detail=detail or {},
        )
    )
