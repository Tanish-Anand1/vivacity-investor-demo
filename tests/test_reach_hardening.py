from copy import deepcopy
import numpy as np
import pytest
from vivacity.schemas import CreateWorld,RoboticsConfig,ExperimentRequest


def test_action_is_owned_and_must_start_at_parent(robot):
    backend,world=robot
    branch=backend.fork(backend.snapshot(world))
    action=backend.candidates(branch,2,100)[0][0]
    backend.apply_action(branch,action)
    original=deepcopy(branch.action)
    action['waypoints'][0][0]+=.1
    assert branch.action==original
    with pytest.raises(ValueError,match='parent'):
        backend.apply_action(branch,action)
    with pytest.raises(ValueError,match='unsupported'):
        backend.apply_action(branch,original|{'kind':'attach_object'})


def test_target_change_invalidates_and_recomputes_reach(runtime):
    world=runtime.create_world(CreateWorld(backend='mujoco',config=RoboticsConfig(obstacle_position=[.75,-.4,.2])))
    first=runtime.wait(runtime.submit(world['id'],ExperimentRequest(planner_iterations=100))['id'])
    assert first['selected_branch_id']
    changed=runtime.environment(world['id'],RoboticsConfig(obstacle_position=[.75,-.4,.2],target_position=[.56,.26,.22]))
    assert changed['state']['model_hash']!=world['state']['model_hash']
    assert runtime.get_experiment(first['id'])['stale']
    second=runtime.wait(runtime.submit(world['id'],ExperimentRequest(planner_iterations=100))['id'])
    assert second['selected_branch_id']
    winner=next(b for b in runtime.store.branches(second['id']) if b['id']==second['selected_branch_id'])
    assert winner['evaluation']['milestone']=='collision_free_reach'
    assert winner['evaluation']['goal_error_m']<.02
    assert winner['initial_state']['config']['target_position']==[.56,.26,.22]
