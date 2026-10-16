from copy import deepcopy
import json
import threading
import time

import mujoco as mj
import numpy as np
import pytest
from fastapi.testclient import TestClient

from vivacity.api import create_app
from vivacity.control import PauseControl
from vivacity.native_pick_place import NativePickup
from vivacity.pick_place import PickPlaceBackend
from vivacity.schemas import CreateWorld, ExperimentRequest, RoboticsConfig, SessionRequest
from vivacity.storage import Store

TOKEN='pause-test-'+'p'*40


def until(fn,timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=fn()
        if value:return value
        time.sleep(.02)
    pytest.fail('Timed out waiting for measured worker condition')


@pytest.fixture(scope='module')
def pickup():
    backend=PickPlaceBackend()
    world=backend.create_world(RoboticsConfig(task='pick_place',obstacle_enabled=False).model_dump(),7)
    actions,_=backend.candidates(world,2,1500)
    return backend,world,actions


def test_diagnostic_sensors_preserve_physical_state_and_parent_hash(pickup):
    b,w,_=pickup
    diagnostic=b.create_world(w.config,w.seed,diagnostics=True)
    assert diagnostic.model_hash==w.model_hash
    initial=b.snapshot(w);b.restore(diagnostic,initial)
    regular=b.fork(initial)
    assert b.snapshot(diagnostic)==b.snapshot(regular)
    for _ in range(200):
        mj.mj_step(regular.model,regular.data);mj.mj_step(diagnostic.model,diagnostic.data)
    np.testing.assert_array_equal(b.snapshot(regular)['integration_state'],b.snapshot(diagnostic)['integration_state'])
    assert b.snapshot(w)==initial


def test_native_repeat_exact_full_state_and_independent_trials(pickup):
    b,w,actions=pickup;parent=b.snapshot(w);engine=NativePickup(b,parent)
    first,evaluation,final=engine.simulate(actions[0],{'max_simulation_seconds':40})
    engine.simulate(actions[1],{'max_simulation_seconds':40})
    repeat,repeated,end=engine.simulate(actions[0],{'max_simulation_seconds':40})
    assert evaluation['success'] and evaluation['grasp_established'] and evaluation['retained_during_transport']
    assert first['simulation_steps']>6000 and first['trace']==repeat['trace']
    assert final==end and evaluation==repeated and b.snapshot(w)==parent
    restored=b.fork(final)
    np.testing.assert_array_equal(b.snapshot(restored)['integration_state'],final['integration_state'])


def test_native_collision_is_measured_even_for_screening_rejected_action(pickup):
    b,_,_=pickup
    w=b.create_world(RoboticsConfig(task='pick_place',obstacle_enabled=True,
        obstacle_position=[.5,0,.12],obstacle_size=[.1,.08,.12]).model_dump(),7)
    actions,_=b.candidates(w,2,1500)
    result,evaluation,_=NativePickup(b,b.snapshot(w)).simulate(actions[0],{'max_simulation_seconds':40})
    assert not evaluation['success'] and evaluation['status']=='collision_failure'
    assert result['simulation_steps']>0 and result['contact_violations']


@pytest.mark.parametrize('engine_name',['native','classic'])
def test_pause_freezes_actual_physics_then_resumes_same_state(pickup,engine_name):
    b,w,actions=pickup;control=PauseControl();cancel=threading.Event()
    started=threading.Event();frames=[];out=[]
    def frame(f):
        frames.append(deepcopy(f));started.set()
    limits={'max_simulation_seconds':40,'checkpoint':lambda:control.checkpoint(cancel),
            'pause_seconds':control.elapsed,'on_frame':frame,'realtime':True}
    if engine_name=='native':
        engine=NativePickup(b,b.snapshot(w))
        work=lambda:out.append(engine.simulate(actions[0],limits))
    else:
        branch=b.fork(b.snapshot(w));b.apply_action(branch,actions[0])
        work=lambda:out.append(b.simulate(branch,limits))
    thread=threading.Thread(target=work);thread.start()
    try:
        assert started.wait(10);control.pause()
        until(lambda:control.state()['paused'])
        frozen=deepcopy(frames);time.sleep(.25)
        assert frames==frozen and thread.is_alive()
        control.resume();until(lambda:len(frames)>len(frozen))
        assert frames[len(frozen)]['time']>frozen[-1]['time']
        cancel.set();thread.join(10);assert not thread.is_alive()
        assert control.elapsed()>=.25
    finally:
        cancel.set();control.resume();thread.join(10)


def test_pause_can_expire_or_cancel_without_resuming():
    control=PauseControl();cancel=threading.Event();control.pause()
    assert not control.checkpoint(cancel,lambda:False)
    assert cancel.is_set()
    control.resume();cancel.clear();control.pause()
    timer=threading.Timer(.1,cancel.set);timer.start()
    assert not control.checkpoint(cancel)
    timer.join();assert control.state()['paused']


def test_native_timeout_and_joint_limits_are_measured(pickup):
    b,w,actions=pickup;engine=NativePickup(b,b.snapshot(w))
    result,evaluation,_=engine.simulate(actions[0],{'max_simulation_seconds':.1})
    assert evaluation['status']=='timeout' and 0<result['simulation_steps']<1000
    bad=deepcopy(actions[0]);bad['stages'][0]['goal'][0]=10
    _,evaluation,_=engine.simulate(bad,{'max_simulation_seconds':40})
    assert not evaluation['success'] and evaluation['status'] in ('joint_limit_failure','controller_failure')


def test_paused_cloth_resumes_real_integration(runtime):
    control=PauseControl();control.pause()
    w=runtime.create_world(CreateWorld(backend='cloth'))
    e=runtime.submit(w['id'],ExperimentRequest(search_candidates=50, physics_budget=3),control=control)
    until(lambda:control.state()['paused'])
    before=runtime.get_experiment(e['id']);time.sleep(.1)
    assert runtime.get_experiment(e['id'])==before
    control.resume();done=runtime.wait(e['id'])
    assert done['status']=='completed' and done['selected_branch_id']
    assert all(b['performance']['simulation_steps']>0 for b in runtime.store.branches(e['id']))


def test_trial_cursor_does_not_skip_late_low_candidate_indices(tmp_path):
    store=Store(tmp_path/'cursor.sqlite3')
    store.trial('e',{'candidate_index':99})
    first=store.trials('e');store.trial('e',{'candidate_index':1})
    second=store.trials('e',first['next_after'])
    assert [x['candidate_index'] for x in first['items']+second['items']]==[99,1]
    assert second['completed']==2


def test_every_requested_trial_is_simulated_and_persisted(runtime):
    w=runtime.create_world(CreateWorld(backend='mujoco',config={'task':'pick_place','obstacle_enabled':False}))
    parent=runtime.snapshot(w['id'])
    e=runtime.submit(w['id'],ExperimentRequest(physics_trials=8,search_candidates=8,max_simulation_seconds=40))
    done=runtime.wait(e['id'])
    assert done['status']=='completed',done
    trials=runtime.store.trials(e['id'])
    assert trials['completed']==done['performance']['trial_count']==8
    assert len({x['control_sha256'] for x in trials['items']})==8
    assert all(x['performance']['simulation_steps']>0 for x in trials['items'])
    assert sum(x['performance']['simulation_steps'] for x in trials['items'])==done['performance']['trial_simulation_steps']
    assert runtime.snapshot(w['id'])==parent
    assert 'checkpoint' not in json.dumps(done) and 'pause_seconds' not in json.dumps(done)
    assert runtime.replay(e['id'])['branches']
    runtime.environment(w['id'],RoboticsConfig(task='pick_place',obstacle_enabled=True))
    assert runtime.get_experiment(e['id'])['stale']


def test_full_trial_all_paths_fail_honestly(runtime):
    w=runtime.create_world(CreateWorld(backend='mujoco',config={'task':'pick_place','obstacle_enabled':True,
        'obstacle_position':[.5,0,.12],'obstacle_size':[.1,.08,.12]}))
    e=runtime.submit(w['id'],ExperimentRequest(physics_trials=4,search_candidates=4,max_simulation_seconds=40,execute_selected=True))
    done=runtime.wait(e['id'])
    assert done['status']=='completed' and done['selected_branch_id'] is None,done
    assert done['result']['search']['fully_simulated']==4
    assert all(not t['evaluation']['success'] and t['performance']['simulation_steps']>0 for t in runtime.store.trials(e['id'])['items'])
    assert 'execution_branch_id' not in done['result']


def test_api_pause_resume_authorization_and_measured_continuation(tmp_path):
    app=create_app(tmp_path/'api.sqlite3')
    headers={'X-Session-Token':TOKEN}
    with TestClient(app) as client:
        s=client.post('/v1/sessions',headers=headers,json={'backend':'mujoco','max_cycles':1,
            'physics_trials':16,'search_candidates':16,'realtime_execution':False,
            'config':{'task':'pick_place','obstacle_enabled':False}}).json()
        sid=s['id']
        assert client.post(f'/v1/sessions/{sid}/pause',headers={'X-Session-Token':'wrong-'+'w'*40}).status_code==403
        paused=client.post(f'/v1/sessions/{sid}/pause',headers=headers)
        assert paused.status_code==200 and paused.json()['pause_requested']
        until(lambda:client.get(f'/v1/sessions/{sid}',headers=headers).json()['paused'])
        current=client.get(f'/v1/sessions/{sid}',headers=headers).json()
        # A pause during initialization can precede creation of the experiment.
        eid=current['experiment_id'];before=app.state.runtime.live(eid) if eid else None
        time.sleep(.2)
        assert (app.state.runtime.live(eid) if eid else None)==before
        assert client.post(f'/v1/sessions/{sid}/resume',headers=headers).json()['pause_requested'] is False
        done=until(lambda:(x if (x:=client.get(f'/v1/sessions/{sid}',headers=headers).json())['status']=='completed' else None),timeout=60)
        eid=done['experiment_id']
        assert done['id']==sid and done['world_id']==s['world_id']
        assert client.get(f'/v1/experiments/{eid}/trials').status_code==403
        trials=client.get(f'/v1/experiments/{eid}/trials?limit=2',headers=headers)
        assert trials.status_code==200 and trials.json()['completed']==16 and len(trials.json()['items'])==2
        assert client.get(f'/v1/experiments/{eid}/trials?limit=101',headers=headers).status_code==422
        assert client.post(f'/v1/sessions/{sid}/pause',headers=headers).status_code==409
        assert client.get(f'/v1/sessions/{sid}',headers=headers).json()['paused_seconds']>=.2


def test_stop_while_paused_retains_partial_trials(runtime):
    s=runtime.supervisor.create(SessionRequest(backend='mujoco',max_cycles=1,physics_trials=100,
        search_candidates=100,config={'task':'pick_place','obstacle_enabled':False}),TOKEN)
    until(lambda:(runtime.supervisor.get(s['id'],TOKEN)['experiment_id']))
    runtime.supervisor.set_paused(s['id'],TOKEN,True)
    until(lambda:runtime.supervisor.get(s['id'],TOKEN)['paused'])
    runtime.supervisor.stop(s['id'],TOKEN)
    done=until(lambda:(x if (x:=runtime.supervisor.get(s['id'],TOKEN))['status']=='stopped' else None))
    assert runtime.get_experiment(done['experiment_id'])['status']=='cancelled'


@pytest.mark.parametrize('settings',[{'physics_trials':4,'search_candidates':3},
    {'physics_trials':5001,'search_candidates':5001}])
def test_invalid_trial_counts_rejected(settings):
    with pytest.raises(ValueError):ExperimentRequest(**settings)


def test_unsupported_full_physics_worlds_rejected_before_queue(runtime):
    for backend in ('cloth','mujoco'):
        w=runtime.create_world(CreateWorld(backend=backend))
        with pytest.raises(ValueError):runtime.submit(w['id'],ExperimentRequest(physics_trials=4,search_candidates=4))
    assert not runtime.futures


def test_pre_upgrade_experiment_retry_keeps_original_job(runtime):
    w=runtime.create_world(CreateWorld(backend='cloth'))
    request=ExperimentRequest(search_candidates=50, physics_budget=3);e=runtime.submit(w['id'],request,'legacy-key')
    runtime.wait(e['id'])
    stored=runtime.store.get('experiments',e['id']);stored['request'].pop('physics_trials')
    runtime.store.put('experiments',stored)
    with runtime.store.connect() as db:
        db.execute('UPDATE submissions SET fingerprint=? WHERE experiment_id=?',('pre-upgrade-fingerprint',e['id']))
    assert runtime.submit(w['id'],request,'legacy-key')['id']==e['id']


def test_pre_upgrade_session_retry_keeps_original_session(runtime):
    request=SessionRequest(backend='cloth',max_cycles=1)
    s=runtime.supervisor.create(request,TOKEN)
    runtime.supervisor.stop(s['id'],TOKEN)
    until(lambda:runtime.supervisor.get(s['id'],TOKEN)['status']=='stopped')
    saved=runtime.store.get('sessions',s['id']);saved['request'].pop('physics_trials')
    runtime.store.put('sessions',saved)
    assert runtime.supervisor.create(request,TOKEN)['id']==s['id']
