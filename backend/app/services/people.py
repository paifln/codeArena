"""Scoped account lifecycle operations; historical submissions stay intact."""
from fastapi import HTTPException
from sqlalchemy import delete

from ..models import ContestGroup, ContestParticipant, Group, GroupMember, User
from ..security import owned, revoke_sessions
from .common import audit


def managed_student(db, uid, actor):
    student = db.get(User, uid)
    if (not student or not student.active or student.role != "STUDENT"
            or (actor.role != "ADMIN" and student.creator_id != actor.id)):
        raise HTTPException(404, "Student not found")
    return student


def remove_student(db, student, actor):
    # Retain identity referenced by historical results; revoke all future access.
    student.active = False
    # The contest roster is historical. Inactive users are denied authentication.
    revoke_sessions(db, student.id)
    db.execute(delete(GroupMember).where(GroupMember.user_id == student.id))
    db.execute(delete(ContestParticipant).where(ContestParticipant.user_id == student.id))
    audit(db, actor, "student.delete", student.id)


def remove_group(db, gid, actor):
    group = owned(db.get(Group, gid), actor)
    db.execute(delete(ContestGroup).where(ContestGroup.group_id == gid))
    db.execute(delete(GroupMember).where(GroupMember.group_id == gid))
    db.delete(group)
    audit(db, actor, "group.delete", gid)
