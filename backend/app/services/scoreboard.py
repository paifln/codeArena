"""Standings policy. Runs and post-contest practice never affect official results."""
import time
from fastapi import HTTPException
from sqlalchemy import select
from ..models import Submission, User, Team
from .access import contest_status, manager, participant_ids, problem_pairs
from .common import iso

PENALIZED = {'WRONG_ANSWER', 'TIME_LIMIT_EXCEEDED', 'MEMORY_LIMIT_EXCEEDED', 'RUNTIME_ERROR', 'OUTPUT_LIMIT_EXCEEDED'}


def empty_cell():
    return {'attempts': 0, 'solved': False, 'minutes': None, 'penalty': 0,
            'time_minutes': 0, 'penalty_minutes': 0, 'score': 0, 'pending': 0, 'accepted_at': 0}


def scoreboard(db, c, u):
    privileged = manager(c, u)
    if not privileged and (not c.scoreboard_enabled or contest_status(c) in ('DRAFT', 'SCHEDULED')):
        raise HTTPException(403, 'Scoreboard is unavailable')
    problems = [{'id': p.id, 'title': p.title, 'letter': chr(65+cp.ordinal)} for p, cp in problem_pairs(db, c)]
    members = participant_ids(db, c)
    subs = db.scalars(select(Submission).where(Submission.contest_id == c.id,
        Submission.kind == 'SUBMIT', Submission.is_practice.is_(False)).order_by(Submission.created_at, Submission.id)).all()
    frozen = c.freeze_at is not None and not privileged
    partial = c.scoring == 'PARTIAL'
    training = c.scoring == 'EDUCATIONAL'
    cells = {}
    for s in subs:
        identity = s.team_id if c.mode == 'TEAM' else s.user_id
        if identity is None:
            continue  # Teacher test submissions do not represent a team.
        cell = cells.setdefault((identity, s.problem_id), empty_cell())
        if frozen and s.created_at >= c.freeze_at:
            if not cell['solved']:
                cell['pending'] += 1
            continue
        verdict, score = s.status, s.score
        if frozen and (not s.finished_at or s.finished_at >= c.freeze_at):
            prior = [h for h in (s.history or []) if h.get('finished_at') and h['finished_at'] < c.freeze_at]
            if not prior:
                if not cell['solved']: cell['pending'] += 1
                continue
            verdict, score = prior[-1]['status'], prior[-1].get('score', 100 if prior[-1]['status'] == 'ACCEPTED' else 0)
        if verdict in ('QUEUED', 'RUNNING'):
            if not cell['solved']: cell['pending'] += 1
            continue
        if cell['solved']:
            continue
        if partial:
            if verdict != 'SYSTEM_ERROR':
                cell['score'] = max(cell['score'], score)
            if verdict == 'ACCEPTED':
                cell['solved'] = True
                cell['score'] = 100
            continue
        if verdict == 'ACCEPTED':
            minutes = int(s.contest_elapsed // 60)
            cell.update(solved=True, minutes=minutes, accepted_at=s.contest_elapsed, score=100,
                time_minutes=0 if training else minutes,
                penalty_minutes=0 if training else 20*cell['attempts'])
            cell['penalty'] = cell['time_minutes'] + cell['penalty_minutes']
        elif verdict in PENALIZED:
            cell['attempts'] += 1
    identities = (db.scalars(select(Team).where(Team.contest_id == c.id)).all() if c.mode == 'TEAM'
                  else db.scalars(select(User).where(User.id.in_(members))).all())
    rows = []
    for entity in identities:
        row_cells = [dict(cells.get((entity.id,p['id']), empty_cell()), problem_id=p['id'], letter=p['letter']) for p in problems]
        rows.append({'user_id': entity.id if c.mode != 'TEAM' else None,
                     'team_id': entity.id if c.mode == 'TEAM' else None,
                     'name': entity.name, 'username': getattr(entity, 'username', entity.name),
                     'solved': sum(x['solved'] for x in row_cells), 'penalty': sum(x['penalty'] for x in row_cells),
                     'score': round(sum(x['score'] for x in row_cells), 2),
                     'last_accepted': max((x['accepted_at'] for x in row_cells), default=0), 'cells': row_cells})
    def rank_key(row):
        if partial: return (-row['score'],)
        if training: return (-row['solved'],)
        return (-row['solved'], row['penalty'], row['last_accepted'])
    rows.sort(key=lambda row: (*rank_key(row), row['name'].casefold(), row['username']))
    previous, rank = None, 0
    for index, row in enumerate(rows, 1):
        key = rank_key(row)
        if key != previous: rank = index
        row['rank'], previous = rank, key
    return {'rows': rows, 'problems': problems, 'frozen': frozen, 'mode': c.mode,
            'scoring': c.scoring, 'server_time': iso(time.time())}
