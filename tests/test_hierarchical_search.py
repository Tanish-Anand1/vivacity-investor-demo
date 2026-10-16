import hashlib
import json
from vivacity.schemas import CreateWorld,ExperimentRequest
from vivacity.search import search_reaches


def test_5000_distinct_screened_real_physics_and_top_three(runtime):
    w=runtime.create_world(CreateWorld(backend='mujoco'))
    e=runtime.submit(w['id'],ExperimentRequest(search_candidates=5000,physics_budget=12))
    done=runtime.wait(e['id'],timeout=300)
    assert done['status']=='completed',done
    search=done['result']['search']
    assert search['generated']==search['screened']==5000
    assert search['distinct_generated']==5000
    assert search['rejected']+search['screening_passed']==5000
    branches=runtime.store.branches(e['id'])
    assert search['fully_simulated']==len(branches)<=12
    assert sum(b['performance']['simulation_steps'] for b in branches)>0
    successful=[b for b in branches if b['evaluation']['success']]
    assert search['verified_feasible']==len(successful)>=3
    assert len(done['result']['top_feasible_branch_ids'])==3
    assert any(b['evaluation']['status']=='collision_failure' for b in branches)
    assert runtime.snapshot(w['id'])==w['initial_state']
    assert len({json.dumps(b['action']['waypoints']) for b in branches})==len(branches)
    assert all(b['initial_state']==w['initial_state'] for b in branches)
    events=runtime.store.events(e['id'])
    assert any(ev['details'].get('screened')==5000 for ev in events)


def test_seeded_search_is_reproducible_and_counts_actual_work(robot):
    backend,world=robot
    settings={'search_candidates':100,'physics_budget':4,'planner_iterations':1500}
    first,_,counts=search_reaches(backend,world,settings,lambda _:None)
    second,_,again=search_reaches(backend,world,settings,lambda _:None)
    assert first==second and counts==again
    assert counts['generated']==counts['screened']==100


def test_blocked_search_retains_genuine_failure(runtime):
    w=runtime.create_world(CreateWorld(backend='mujoco',config={'obstacle_position':[.5,.1,.3],'obstacle_size':[.35,.35,.3]}))
    e=runtime.submit(w['id'],ExperimentRequest(search_candidates=100,planner_iterations=100))
    done=runtime.wait(e['id'])
    assert done['selected_branch_id'] is None
    assert done['result']['search']['verified_feasible']==0
    assert done['result']['top_feasible_branch_ids']==[]
    branches=runtime.store.branches(e['id'])
    assert done['result']['search']['fully_simulated']==sum(b['performance']['simulation_steps']>0 for b in branches)
