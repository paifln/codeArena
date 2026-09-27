from test_api import arena, payload, PREFIX
from app.models import Contest, Team, TeamMember, Problem, Submission, User
from app.services import scoreboard
from sqlalchemy import select


def test_team_members_share_submissions_but_outsiders_cannot(arena):
    clients, factory, ids = arena
    with factory() as db:
        contest=db.get(Contest,ids['contest']);contest.mode='TEAM';contest.scoring='EDUCATIONAL'
        other=db.scalar(select(User).where(User.username=='otherstudent'))
        team=Team(contest_id=contest.id,name='Pair');db.add(team);db.flush()
        db.add_all([TeamMember(contest_id=contest.id,team_id=team.id,user_id=uid) for uid in [ids['student'],other.id]])
        db.commit()
    response=clients['student'].post(PREFIX+'/submissions',json=payload(ids))
    assert response.status_code==202,response.text
    sid=response.json()['id']
    assert clients['otherstudent'].get(f'{PREFIX}/submissions/{sid}').status_code==200
    assert clients['outsider'].get(f'{PREFIX}/submissions/{sid}').status_code==404
    with factory() as db:
        item=db.get(Submission,sid);item.status='ACCEPTED';db.commit()
        rows=scoreboard(db,db.get(Contest,ids['contest']),db.get(User,ids['student']))['rows']
        assert len(rows)==1 and rows[0]['name']=='Pair' and rows[0]['solved']==1
        assert rows[0]['penalty']==0


def test_practice_editorial_and_feedback_are_scoped(arena):
    clients, factory, ids=arena
    path=f"{PREFIX}/problems/{ids['problem']}?contest_id={ids['contest']}"
    with factory() as db:
        db.get(Problem,ids['problem']).editorial='Secret editorial'
        db.commit()
    assert 'editorial' not in clients['student'].get(path).json()
    assert clients['student'].post(PREFIX+'/submissions',json=payload(ids,practice=True)).status_code==403
    with factory() as db:
        c=db.get(Contest,ids['contest']);c.status='FINISHED';c.practice_enabled=True;db.commit()
    assert clients['student'].get(path).json()['editorial']=='Secret editorial'
    assert clients['student'].post(PREFIX+'/submissions',json=payload(ids)).status_code==403
    result=clients['student'].post(PREFIX+'/submissions',json=payload(ids,practice=True))
    assert result.status_code==202,result.text
    sid=result.json()['id']
    feedback=f'{PREFIX}/submissions/{sid}/feedback'
    assert clients['outsider'].patch(feedback,json={'feedback':'Unauthorized'}).status_code==404
    assert clients['student'].patch(feedback,json={'feedback':'Unauthorized'}).status_code==403
    assert clients['teacher'].patch(feedback,json={'feedback':'Try a set.'}).status_code==200
    assert clients['student'].get(f'{PREFIX}/submissions/{sid}').json()['feedback']=='Try a set.'
    with factory() as db:
        db.get(Submission,sid).status='ACCEPTED';db.commit()
        rows=scoreboard(db,db.get(Contest,ids['contest']),db.get(User,ids['student']))['rows']
        assert all(row['solved']==0 for row in rows)


def test_operations_admin_only(arena):
    clients,_,_=arena
    assert clients['student'].get(PREFIX+'/operations').status_code==403
    assert clients['teacher'].get(PREFIX+'/operations').status_code==403
    result=clients['admin'].get(PREFIX+'/operations')
    assert result.status_code==200,result.text
    assert 'backup' in result.json()['alerts']


def test_create_team_contest_validates_roster_and_ownership(arena):
    from datetime import datetime,timedelta,timezone
    clients,_,ids=arena
    now=datetime.now(timezone.utc)
    body={'title':'Team cup','start_time':now.isoformat(),'end_time':(now+timedelta(hours=2)).isoformat(),
          'problem_ids':[ids['problem']], 'mode':'TEAM','scoring':'PARTIAL','practice_enabled':True,
          'teams':[{'name':'Team A','user_ids':[ids['student']]}]}
    result=clients['teacher'].post(PREFIX+'/contests',json=body)
    assert result.status_code==201,result.text
    cid=result.json()['id']
    view=clients['student'].get(f'{PREFIX}/contests/{cid}').json()
    assert view['mode']=='TEAM' and view['scoring']=='PARTIAL' and view['teams'][0]['name']=='Team A'
    invalid={**body,'teams':body['teams']+[{'name':'Team B','user_ids':[ids['student']]}]}
    assert clients['teacher'].post(PREFIX+'/contests',json=invalid).status_code==422
    assert clients['outsider'].post(PREFIX+'/contests',json=body).status_code==404


def test_teacher_can_enable_practice_without_changing_official_state(arena):
    clients, factory, ids=arena
    path=f"{PREFIX}/contests/{ids['contest']}/practice"
    assert clients['student'].patch(path,json={'practice_enabled':True}).status_code==403
    assert clients['outsider'].patch(path,json={'practice_enabled':True}).status_code==404
    response=clients['teacher'].patch(path,json={'practice_enabled':True})
    assert response.status_code==200,response.text
    assert response.json()['practice_enabled'] and not response.json()['practice_execution']['allowed']
    with factory() as db:
        assert db.get(Contest,ids['contest']).status != 'FINISHED'
