import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from ..db import get_db, lock_write
from ..models import Group, GroupMember, User
from .. import schemas as S
from ..security import teacher, owned, user_public, hash_password
from ..services import audit

router = APIRouter()


@router.get("/users")
def users(user=Depends(teacher), db: DBSession = Depends(get_db)):
    q = select(User)
    if user.role != "ADMIN":
        q = q.where(User.creator_id == user.id)
    return [user_public(u) for u in db.scalars(q.order_by(User.name).limit(1000))]


@router.post("/users", status_code=201)
def create_user(
    req: S.UserCreate, user=Depends(teacher), db: DBSession = Depends(get_db)
):
    if req.role == "TEACHER" and user.role != "ADMIN":
        raise HTTPException(403, "Only an administrator can create teachers")
    u = User(
        username=req.username,
        name=req.name,
        password_hash=hash_password(req.password),
        role=req.role,
        creator_id=user.id,
    )
    db.add(u)
    db.flush()
    audit(db, user, "user.create", u.id, {"role": u.role})
    db.commit()
    return user_public(u)


def group_data(db, g):
    members = db.scalars(
        select(User)
        .join(GroupMember, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == g.id)
    ).all()
    return {
        "id": g.id,
        "name": g.name,
        "author_id": g.author_id,
        "member_count": len(members),
        "members": [user_public(u) for u in members],
    }


@router.get("/groups")
def groups(user=Depends(teacher), db: DBSession = Depends(get_db)):
    q = select(Group)
    if user.role != "ADMIN":
        q = q.where(Group.author_id == user.id)
    return [group_data(db, g) for g in db.scalars(q.order_by(Group.id.desc()))]


@router.post("/groups", status_code=201)
def create_group(
    req: S.GroupCreate, user=Depends(teacher), db: DBSession = Depends(get_db)
):
    g = Group(name=req.name, author_id=user.id)
    db.add(g)
    db.flush()
    audit(db, user, "group.create", g.id)
    db.commit()
    return group_data(db, g)


@router.post("/groups/{gid}/members")
def assign_members(
    gid: int, req: S.Members, user=Depends(teacher), db: DBSession = Depends(get_db)
):
    g = owned(db.get(Group, gid), user)
    for uid in set(req.user_ids):
        u = db.get(User, uid)
        if (
            not u
            or u.role != "STUDENT"
            or (user.role != "ADMIN" and u.creator_id != user.id)
        ):
            raise HTTPException(404, "Student not found")
        if not db.get(GroupMember, (gid, uid)):
            db.add(GroupMember(group_id=gid, user_id=uid))
    audit(db, user, "group.assign", gid, {"user_ids": req.user_ids})
    db.commit()
    return group_data(db, g)


@router.post("/groups/{gid}/students", status_code=201)
def bulk_students(
    gid: int,
    req: S.BulkStudents,
    user=Depends(teacher),
    db: DBSession = Depends(get_db),
):
    # Hash before taking the write lock; insertion is all-or-nothing.
    credentials = [
        {"username": f"{req.prefix}{i:02d}", "password": secrets.token_urlsafe(10)}
        for i in range(1, req.count + 1)
    ]
    hashes = [hash_password(c["password"]) for c in credentials]
    lock_write(db)
    owned(db.get(Group, gid), user)
    for c, h in zip(credentials, hashes):
        u = User(
            username=c["username"],
            name=c["username"],
            password_hash=h,
            role="STUDENT",
            creator_id=user.id,
        )
        db.add(u)
        db.flush()
        db.add(GroupMember(group_id=gid, user_id=u.id))
    audit(db, user, "students.bulk_create", gid, {"count": req.count})
    db.commit()
    return {"credentials": credentials}
