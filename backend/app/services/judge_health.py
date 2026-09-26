import time
from .common import iso
from ..models import SystemSetting


def judge_status(db):
    row = db.get(SystemSetting, "judge_heartbeat")
    data = row.value if row else {}
    available = bool(data.get("available")) and time.time() - data.get("time", 0) < 20
    return {
        "judge_available": available,
        "judge_detail": "ready"
        if available
        else "Sandbox unavailable. Start the Docker judge worker.",
        "server_time": iso(time.time()),
    }
