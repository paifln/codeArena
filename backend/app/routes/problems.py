import io
import json
import secrets
import zipfile
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from sqlalchemy import select, delete
from sqlalchemy.orm import Session as DBSession
from ..db import get_db, lock_write
from ..models import Contest, ContestProblem, Problem, TestCase
from .. import schemas as S
from ..security import current_user, teacher, owned
from ..services import access_contest, audit, contest_status, problem_public

router = APIRouter()


@router.get("/problems")
def problems(
    q: str = "",
    difficulty: str | None = None,
    tag: str | None = None,
    user=Depends(teacher),
    db: DBSession = Depends(get_db),
):
    query = select(Problem)
    if user.role != "ADMIN":
        query = query.where(Problem.author_id == user.id)
    if q:
        query = query.where(Problem.title.ilike("%" + q[:100] + "%"))
    if difficulty:
        query = query.where(Problem.difficulty == difficulty)
    result = [
        problem_public(db, p, True)
        for p in db.scalars(query.order_by(Problem.created_at.desc()).limit(300))
    ]
    return [p for p in result if not tag or tag in p["tags"]]


def save_problem(db, req, user, p=None):
    data = req.model_dump(exclude={"tests"})
    if p is None:
        p = Problem(**data, author_id=user.id, slug=secrets.token_hex(8))
        db.add(p)
        db.flush()
    else:
        for k, v in data.items():
            setattr(p, k, v)
        p.version += 1
        db.execute(delete(TestCase).where(TestCase.problem_id == p.id))
    for i, t in enumerate(req.tests):
        db.add(TestCase(problem_id=p.id, ordinal=i, **t.model_dump()))
    audit(db, user, "problem.save", p.id, {"version": p.version})
    db.commit()
    return problem_public(db, p, True)


@router.post("/problems", status_code=201)
def create_problem(
    req: S.ProblemIn, user=Depends(teacher), db: DBSession = Depends(get_db)
):
    return save_problem(db, req, user)


@router.get("/problems/{pid}")
def get_problem(
    pid: int,
    contest_id: int | None = None,
    language: str = "ru",
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    p = db.get(Problem, pid)
    if not p:
        raise HTTPException(404, "Problem not found")
    privileged = user.role == "ADMIN" or (
        user.role == "TEACHER" and p.author_id == user.id
    )
    if not privileged:
        if not contest_id:
            raise HTTPException(404, "Problem not found")
        c = access_contest(db, contest_id, user)
        if contest_status(c) not in ("RUNNING", "PAUSED", "FINISHED") or not db.get(
            ContestProblem, (contest_id, pid)
        ):
            raise HTTPException(403, "Problem is unavailable")
    result = problem_public(db, p, privileged, language)
    if not privileged and contest_status(c) == "FINISHED":
        result["editorial"] = p.editorial
    return result


@router.patch("/problems/{pid}")
def edit_problem(
    pid: int, req: S.ProblemIn, user=Depends(teacher), db: DBSession = Depends(get_db)
):
    lock_write(db)
    p = owned(db.get(Problem, pid), user)
    contests = db.scalars(
        select(Contest)
        .join(ContestProblem, ContestProblem.contest_id == Contest.id)
        .where(ContestProblem.problem_id == pid)
    ).all()
    if any(contest_status(c) in ("RUNNING", "PAUSED") for c in contests):
        raise HTTPException(
            409, "Editing is locked during an active contest. Finish it first."
        )
    return save_problem(db, req, user, p)


@router.get("/problems/{pid}/export")
def export_problem(pid: int, user=Depends(teacher), db: DBSession = Depends(get_db)):
    p = owned(db.get(Problem, pid), user)
    data = problem_public(db, p, True)
    manifest = {
        k: data[k]
        for k in S.ProblemIn.model_fields
        if k not in ("tests", "description")
    }
    manifest["tests"] = []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("statement.md", p.description)
        for i, t in enumerate(data["tests"], 1):
            stem = f"tests/{i:02d}"
            z.writestr(stem + ".in", t["input_data"])
            z.writestr(stem + ".out", t["expected"])
            manifest["tests"].append(
                {
                    "input": stem + ".in",
                    "output": stem + ".out",
                    "is_sample": t["is_sample"],
                    "weight": t.get("weight", 1),
                }
            )
        z.writestr("problem.json", json.dumps(manifest, ensure_ascii=False))
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="problem-{pid}.zip"'},
    )


@router.post("/problems/import", status_code=201)
async def import_problem(
    file: UploadFile = File(...), user=Depends(teacher), db: DBSession = Depends(get_db)
):
    blob = await file.read(1_000_001)
    if len(blob) > 1_000_000:
        raise HTTPException(413, "Archive too large")
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            infos = z.infolist()
            if len(infos) > 104 or sum(i.file_size for i in infos) > 1_000_000:
                raise ValueError()
            names = [i.filename for i in infos]
            if len(set(names)) != len(names):
                raise ValueError()
            for i in infos:
                if (
                    i.filename.startswith(("/", "\\"))
                    or "\\" in i.filename
                    or ":" in i.filename
                    or ".." in i.filename.split("/")
                    or i.flag_bits & 1
                    or (i.external_attr >> 16) & 0o170000 == 0o120000
                ):
                    raise ValueError()
                if i.file_size > max(i.compress_size, 1) * 100:
                    raise ValueError()
            data = json.loads(z.read("problem.json"))
            # Count references too: a small archive must not expand into an
            # unbounded list by referring to the same large member repeatedly.
            entries = data.get("tests")
            if not isinstance(entries, list) or not 1 <= len(entries) <= 50:
                raise ValueError()
            by_name = {i.filename: i for i in infos}
            referenced_size = sum(
                by_name[t[key]].file_size
                for t in entries
                for key in ("input", "output")
            )
            if referenced_size > 512_000:
                raise ValueError()
            data["description"] = z.read("statement.md").decode("utf-8")
            data["tests"] = [
                {
                    "input_data": z.read(t["input"]).decode("utf-8"),
                    "expected": z.read(t["output"]).decode("utf-8"),
                    "is_sample": t.get("is_sample", False),
                    "weight": t.get("weight", 1),
                }
                for t in data["tests"]
            ]
            req = S.ProblemIn.model_validate(data)
    except Exception:
        raise HTTPException(400, "Invalid or unsafe problem archive")
    return save_problem(db, req, user)
