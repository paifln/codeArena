"""Replace only the marked demo and explicitly named groups; keep student credentials."""
import argparse
import time

from sqlalchemy import delete, func, select

from .db import SessionLocal, lock_write
from .demo import DEMO_KEY, _create_demo
from .models import (
    Announcement, AuditLog, Clarification, Contest, ContestGroup,
    ContestParticipant, ContestProblem, Group, GroupMember, Problem,
    Submission, SubmissionTestResult, SystemSetting, TestCase, User,
)
from .security import owned


def replace_demo(db, author_id, group_ids, start=False):
    lock_write(db)
    owner = db.get(User, author_id)
    if not owner or not owner.active or owner.role not in ("ADMIN", "TEACHER"):
        raise ValueError("Active administrator or teacher required")
    marker = db.get(SystemSetting, DEMO_KEY)
    if not marker:
        raise ValueError("No marked demo exists")
    old_id = marker.value["contest_id"]
    owned(db.get(Contest, old_id), owner)
    groups = [owned(db.get(Group, gid), owner) for gid in set(group_ids)]
    if not groups:
        raise ValueError("Choose explicit demo groups to replace")
    linked = set(db.scalars(select(ContestGroup.group_id).where(ContestGroup.contest_id == old_id)))
    if not linked.issubset(set(group_ids)):
        raise ValueError("Include all groups linked to the old demo")
    if db.scalar(select(ContestGroup.contest_id).where(
        ContestGroup.group_id.in_(group_ids), ContestGroup.contest_id != old_id
    )) is not None:
        raise ValueError("A selected group belongs to another contest")
    members = set(db.scalars(select(GroupMember.user_id).where(GroupMember.group_id.in_(group_ids))))
    members.update(db.scalars(select(ContestParticipant.user_id).where(ContestParticipant.contest_id == old_id)))
    # New identifiers keep browser drafts and links separate from the old demo.
    next_group = (db.scalar(select(func.max(Group.id))) or 0) + 1
    next_contest = (db.scalar(select(func.max(Contest.id))) or 0) + 1
    problems = list(db.scalars(select(ContestProblem.problem_id).where(ContestProblem.contest_id == old_id)))
    submission_ids = select(Submission.id).where(Submission.contest_id == old_id)
    db.execute(delete(SubmissionTestResult).where(SubmissionTestResult.submission_id.in_(submission_ids)))
    db.execute(delete(Submission).where(Submission.contest_id == old_id))
    for model in (Clarification, Announcement, ContestProblem, ContestParticipant, ContestGroup):
        db.execute(delete(model).where(model.contest_id == old_id))
    db.execute(delete(Contest).where(Contest.id == old_id))
    for pid in problems:
        problem = db.get(Problem, pid)
        # Shared problems or problems not created by the demo stay untouched.
        if not problem or not problem.slug.startswith(f"demo-{old_id}-"):
            continue
        referenced = any(db.scalar(select(model.problem_id).where(model.problem_id == pid).limit(1)) is not None
                         for model in (ContestProblem, Submission, Clarification))
        if not referenced:
            db.execute(delete(TestCase).where(TestCase.problem_id == pid))
            db.delete(problem)
    db.execute(delete(GroupMember).where(GroupMember.group_id.in_(group_ids)))
    for group in groups:
        db.delete(group)
    db.delete(marker)
    db.flush()
    cid, _ = _create_demo(db, author_id, next_group, next_contest)
    for uid in members:
        student = db.get(User, uid)
        if student and student.active and student.role == "STUDENT":
            db.add(GroupMember(group_id=next_group, user_id=uid))
    if start:
        contest = db.get(Contest, cid)
        contest.status = "RUNNING"
        contest.start_time = time.time()
        contest.end_time = contest.start_time + 5400
    db.add(AuditLog(user_id=owner.id, action="demo.replace", entity_id=cid,
                    detail={"old_contest_id": old_id, "old_group_ids": sorted(group_ids),
                            "new_group_id": next_group}))
    db.commit()
    return cid, next_group


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author-id", type=int, required=True)
    parser.add_argument("--group-ids", type=int, nargs="+", required=True)
    parser.add_argument("--start", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        cid, gid = replace_demo(db, args.author_id, args.group_ids, args.start)
        print(f"New demo contest: {cid}; group: {gid}")


if __name__ == "__main__":
    main()
