import json
import threading
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from vivacity.api import create_app
from vivacity.runtime import Busy, Runtime
from vivacity.schemas import SessionRequest, CreateWorld, ExperimentRequest


TOKEN='testcapability'+'a'*32


def wait_session(supervisor, sid, token=TOKEN, timeout=120):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        session=supervisor.get(sid,token)
        if session['status'] not in ('active','stopping'):
            return session
        time.sleep(.03)
    pytest.fail('session did not finish before timeout')


@pytest.mark.parametrize('limit', ['lease_seconds', 'max_wall_seconds'])
def test_expired_session_is_stopped_not_falsely_completed(runtime, monkeypatch, limit):
    monkeypatch.setattr(runtime.supervisor, limit, -1)
    s = runtime.supervisor.create(SessionRequest(backend='cloth',search_candidates=50, max_cycles=2), TOKEN)
    done = wait_session(runtime.supervisor, s['id'])
    assert done['status'] == 'stopped'
    assert done['cycle'] == 0 and done['experiments'] == []


def test_autonomous_cloth_recomputes_new_physical_conditions(runtime):
    s=runtime.supervisor.create(SessionRequest(backend='cloth',search_candidates=50,max_cycles=2),TOKEN)
    assert runtime.supervisor.create(SessionRequest(backend='cloth',search_candidates=50,max_cycles=2),TOKEN)['id']==s['id']
    completed=wait_session(runtime.supervisor,s['id'])
    assert completed['status']=='completed' and completed['cycle']==2,completed
    assert len(set(completed['world_ids']))==2
    assert [c['seed'] for c in completed['conditions']]==[7,8]
    experiments=[runtime.get_experiment(eid) for eid in completed['experiments']]
    assert experiments[0]['selected_branch_id'] and experiments[1]['selected_branch_id']
    winners=[next(b for b in runtime.store.branches(e['id']) if b['id']==e['selected_branch_id']) for e in experiments]
    assert all(w['evaluation']['milestone']=='constrained_single_fold' for w in winners)
    worlds=[runtime.get_world(wid) for wid in completed['world_ids']]
    assert worlds[0]['config']['friction']!=worlds[1]['config']['friction']
    assert all(runtime.observe(w['id'])['observation']['vertices'] for w in worlds)


def test_session_capabilities_cover_rest_and_both_websockets(tmp_path):
    app=create_app(tmp_path/'session-api.sqlite3')
    with TestClient(app) as client:
        headers={'X-Session-Token':TOKEN}
        response=client.post('/v1/sessions',json={'backend':'cloth','max_cycles':1,'search_candidates':50},headers=headers)
        assert response.status_code==201,response.text
        s=response.json();sid=s['id'];wid=s['world_id']
        assert client.get(f'/v1/worlds/{wid}').status_code==403
        assert client.get(f'/v1/worlds/{wid}',headers=headers).status_code==200
        assert client.get(f'/v1/sessions/{sid}',headers={'X-Session-Token':'wrong'+'z'*32}).status_code==403
        completed=wait_session(app.state.runtime.supervisor,sid)
        eid=completed['experiment_id']
        assert client.get(f'/v1/experiments/{eid}').status_code==403
        assert client.get(f'/v1/experiments/{eid}/live',headers=headers).status_code==200
        for endpoint in ('events','live'):
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(f'/v1/experiments/{eid}/{endpoint}') as ws:
                    ws.receive_json()
            with client.websocket_connect(f'/v1/experiments/{eid}/{endpoint}',subprotocols=['vivacity.live','vivacity.token.'+TOKEN]) as ws:
                message=ws.receive_json()
                assert message['schema_version'] in ('1.0','vivacity.live/1.0')
        assert 'token_hash' not in response.text


def test_bounded_sessions_stop_and_restart_recovery(tmp_path):
    r=Runtime(tmp_path/'sessions.sqlite3')
    try:
        started=threading.Event();release=threading.Event()
        backend=r.backends['cloth'];original=backend.simulate
        def delayed(world,limits):
            started.set();release.wait(10);return original(world,limits)
        backend.simulate=delayed
        one=r.supervisor.create(SessionRequest(backend='cloth',search_candidates=50,max_cycles=4),TOKEN)
        assert started.wait(10)
        two=r.supervisor.create(SessionRequest(backend='cloth',search_candidates=50,max_cycles=4),TOKEN+'b')
        with pytest.raises(Busy):r.supervisor.create(SessionRequest(backend='cloth',search_candidates=50),TOKEN+'c')
        r.supervisor.stop(one['id'],TOKEN);r.supervisor.stop(two['id'],TOKEN+'b');release.set()
        assert wait_session(r.supervisor,one['id'])['status']=='stopped'
        assert wait_session(r.supervisor,two['id'],TOKEN+'b')['status']=='stopped'
        assert r.get_experiment(r.supervisor.get(one['id'],TOKEN)['experiment_id'])['status']=='cancelled'
        assert len(r.live_states)<=32
        interrupted=r.store.get('sessions',one['id'])|{'status':'active'}
        r.store.put('sessions',interrupted)
    finally:r.close()
    second=Runtime(tmp_path/'sessions.sqlite3')
    try:assert second.supervisor.get(one['id'],TOKEN)['error']=='supervisor_interrupted_by_restart'
    finally:second.close()


def test_selected_pickup_is_fresh_physics_execution_and_live_state(runtime):
    s=runtime.supervisor.create(SessionRequest(backend='mujoco',max_cycles=1,realtime_execution=False,
        config={'task':'pick_place','obstacle_enabled':False},search_candidates=5000,physics_budget=3),TOKEN)
    done=wait_session(runtime.supervisor,s['id'])
    assert done['status']=='completed',done
    e=runtime.get_experiment(done['experiment_id'])
    assert e['result']['search']['generated']==e['result']['search']['distinct_generated']==5000
    assert e['result']['search']['fully_simulated']==3
    assert e['result']['execution_evaluation']['success'],e
    branches=runtime.store.branches(e['id'])
    assert len(branches)==4
    live=next(b for b in branches if b['id']==e['result']['execution_branch_id'])
    assert live['action']['execution_role']=='authoritative_execution'
    assert live['performance']['simulation_steps']>1000 and live['initial_state']==branches[0]['initial_state']
    latest=runtime.live(e['id'])
    assert latest['stage']=='verified' and latest['sequence']>=len(live['trace'])-2
    assert latest['frame']['time']==live['final_state']['integration_state'][0]
    assert latest['frame']['cube_position']==live['evaluation']['final_cube_position']
    assert runtime.get_world(done['world_id'])['state']==live['final_state']
    assert not e['stale']


def test_two_autonomous_pickups_change_conditions_and_execute(runtime):
    s=runtime.supervisor.create(SessionRequest(backend='mujoco',max_cycles=2,realtime_execution=False,
        config={'task':'pick_place','obstacle_position':[.75,-.4,.22]}),TOKEN)
    done=wait_session(runtime.supervisor,s['id'])
    assert done['status']=='completed' and done['cycle']==2,done
    worlds=[runtime.get_world(wid) for wid in done['world_ids']]
    assert worlds[0]['config']['cube_position']!=worlds[1]['config']['cube_position']
    assert worlds[0]['seed']!=worlds[1]['seed']
    experiments=[runtime.get_experiment(eid) for eid in done['experiments']]
    assert all(e['result']['execution_evaluation']['success'] for e in experiments),experiments
    assert all(not e['stale'] for e in experiments)
    assert all(runtime.replay(e['id'])['stale'] is False for e in experiments)
