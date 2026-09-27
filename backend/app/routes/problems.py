import io
import json
import secrets
import zipfile
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from sqlalchemy import select, delete, func
from sqlalchemy.orm import Session as DBSession
from ..db import get_db, lock_write
from ..models import (
    Contest,
    ContestProblem,
    Problem,
    TestCase,
    Submission,
    ProblemDocument,
)
from .. import schemas as S
from ..security import current_user, teacher, owned
from ..services import access_contest, audit, contest_status, problem_public

router = APIRouter()


@router.get("/problems/{pid}/usage")
def problem_usage(pid: int, user=Depends(teacher), db: DBSession = Depends(get_db)):
    owned(db.get(Problem, pid), user)
    query = (
        select(Contest.id, Contest.title, func.count(Submission.id))
        .join(Submission, Submission.contest_id == Contest.id)
        .where(Submission.problem_id == pid)
        .group_by(Contest.id)
    )
    if user.role != "ADMIN":
        query = query.where(Contest.author_id == user.id)
    rows = [
        {"id": cid, "title": title, "count": count}
        for cid, title, count in db.execute(query)
    ]
    return {"count": sum(r["count"] for r in rows), "contests": rows}


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
    from ..services.problem_packages import read_package

    try:
        req = read_package(blob)
    except ValueError:
        raise HTTPException(400, "Invalid or unsafe problem archive") from None
    return save_problem(db, req, user)


def document_owner(db, pid, user):
    p = owned(db.get(Problem, pid), user)
    contests = db.scalars(
        select(Contest)
        .join(ContestProblem, ContestProblem.contest_id == Contest.id)
        .where(ContestProblem.problem_id == pid)
    ).all()
    if any(contest_status(c) in ("RUNNING", "PAUSED") for c in contests):
        raise HTTPException(409, "Documents are locked during an active contest")
    return p


@router.post("/problems/{pid}/documents", status_code=201)
async def upload_document(
    pid: int,
    file: UploadFile = File(...),
    user=Depends(teacher),
    db: DBSession = Depends(get_db),
):
    from ..services.problem_documents import validate_document, MAX_DOCUMENT

    document_owner(db, pid, user)
    blob = await file.read(MAX_DOCUMENT + 1)
    try:
        name, media_type = validate_document(file.filename, blob)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    lock_write(db)
    document_owner(db, pid, user)
    if (
        db.scalar(
            select(func.count())
            .select_from(ProblemDocument)
            .where(ProblemDocument.problem_id == pid)
        )
        >= 3
    ):
        raise HTTPException(409, "Maximum three documents per problem")
    row = ProblemDocument(
        problem_id=pid, name=name, media_type=media_type, size=len(blob), data=blob
    )
    db.add(row)
    db.flush()
    audit(db, user, "problem.document.add", row.id, {"problem_id": pid})
    db.commit()
    return {"id": row.id, "name": row.name, "size": row.size}


@router.get("/problems/{pid}/documents/{did}")
def download_document(
    pid: int,
    did: int,
    contest_id: int | None = None,
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    from urllib.parse import quote

    get_problem(pid, contest_id, "ru", user, db)
    row = db.get(ProblemDocument, did)
    if not row or row.problem_id != pid:
        raise HTTPException(404, "Document not found")
    return Response(
        row.data,
        media_type=row.media_type,
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(row.name),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/problems/{pid}/documents/{did}", status_code=204)
def delete_document(
    pid: int, did: int, user=Depends(teacher), db: DBSession = Depends(get_db)
):
    lock_write(db)
    document_owner(db, pid, user)
    row = db.get(ProblemDocument, did)
    if not row or row.problem_id != pid:
        raise HTTPException(404, "Document not found")
    db.delete(row)
    audit(db, user, "problem.document.delete", did, {"problem_id": pid})
    db.commit()


@router.post("/problems/import-url")
def import_url(req: S.ExternalProblemIn, user=Depends(teacher)):
    from ..services.external_problems import (
        canonical_url,
        fetch_statement,
        parse_statement,
    )

    try:
        url = canonical_url(req.url)
        return parse_statement(
            url, req.html if req.html is not None else fetch_statement(url)
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
