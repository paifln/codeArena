"""One execution policy for HTTP admission, contest views and live updates."""

from .access import contest_status
from .judge_health import judge_status


def execution_policy(db, contest, practice=False):
    state = contest_status(contest)
    reason = {
        "DRAFT": "CONTEST_NOT_STARTED",
        "SCHEDULED": "CONTEST_NOT_STARTED",
        "PAUSED": "CONTEST_PAUSED",
        "FINISHED": "CONTEST_FINISHED",
        "ARCHIVED": "CONTEST_FINISHED",
    }.get(state)
    if practice:
        reason = None if state == "FINISHED" and contest.practice_enabled else "PRACTICE_UNAVAILABLE"
    if reason is None and not judge_status(db)["judge_available"]:
        reason = "JUDGE_UNAVAILABLE"
    return {"allowed": reason is None, "reason": reason}
