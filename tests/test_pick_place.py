from copy import deepcopy
import json

import mujoco as mj
import numpy as np
import pytest

from vivacity.pick_place import PickPlaceBackend
from vivacity.native_pick_place import NativePickup
from vivacity.schemas import RoboticsConfig, CreateWorld, ExperimentRequest


def test_pickup_placement_minimum_distance_accepts_exact_boundary():
    config = RoboticsConfig(task='pick_place', cube_position=[.5, -.15, .026],
                            placement_position=[.5, -.05, .026])
    assert config.placement_position[1] == -.05
    with pytest.raises(ValueError, match='at least 0.1 m apart'):
        RoboticsConfig(task='pick_place', cube_position=[.5, -.15, .026],
                       placement_position=[.5, -.051, .026])


def test_cube_obstacle_contact_is_prohibited_even_without_robot_contact():
    backend = PickPlaceBackend()
    world = backend.create_world(RoboticsConfig(task='pick_place', obstacle_enabled=True,
        obstacle_position=[.5, -.15, .05], obstacle_size=[.05, .05, .05]).model_dump(), 7)
    violations = backend.contacts(world)
    assert any(v['category'] == 'object_environment_collision' and
               set(v['geoms']) == {'cube', 'obstacle_geom'} for v in violations)


@pytest.mark.parametrize('half_size', [.02, .03])
def test_configured_object_size_changes_real_geometry_and_grasp(half_size):
    height = half_size + .001
    config = RoboticsConfig(task='pick_place', obstacle_enabled=False,
                            cube_half_size=half_size,
                            cube_position=[.5, -.15, height],
                            placement_position=[.5, .18, height])
    backend = PickPlaceBackend()
    world = backend.create_world(config.model_dump(), 7)
    assert world.model.geom_size[world.model.geom('cube').id, 0] == pytest.approx(half_size)
    action = backend.candidates(world, 1, 100)[0][0]
    assert action['planning_feasible']
    result, evaluation, final_state = NativePickup(backend, backend.snapshot(world)).simulate(
        action, {'max_simulation_seconds': 40, 'max_wall_seconds': 120})
    assert result['simulation_steps'] > 1000
    assert evaluation['success'], evaluation
    assert evaluation['grasp_established'] and evaluation['lifted'] and evaluation['released']
    assert evaluation['goal_error_m'] < .025
    assert final_state['config']['cube_half_size'] == half_size


def test_older_pickup_snapshot_without_size_retains_default_geometry():
    backend = PickPlaceBackend()
    config = RoboticsConfig(task='pick_place', obstacle_enabled=False).model_dump()
    legacy = dict(config)
    legacy.pop('cube_half_size')
    previous = backend.create_world(legacy, 7)
    current = backend.create_world(config, 7)
    assert previous.model_hash == current.model_hash
    snapshot = backend.snapshot(previous)
    restored = backend.fork(snapshot)
    assert restored.model_hash == previous.model_hash
    assert backend.snapshot(restored) == snapshot


def test_independent_dimensions_mass_and_friction_change_mujoco_model():
    config=RoboticsConfig(task='pick_place',obstacle_enabled=False,
        cube_half_sizes=[.02,.03,.025],cube_mass=.1,cube_friction=.55)
    world=PickPlaceBackend().create_world(config.model_dump(),7)
    cube=world.model.geom('cube').id
    assert world.model.geom_size[cube].tolist()==pytest.approx([.02,.03,.025])
    assert world.model.body_mass[world.model.body('target').id]==pytest.approx(.1)
    assert world.model.geom_friction[cube,0]==pytest.approx(.55)
    for _ in range(50):
        mj.mj_step(world.model,world.data)
    cube_contacts=[c for c in world.data.contact[:world.data.ncon] if cube in (c.geom1,c.geom2)]
    assert cube_contacts
    assert all(c.friction[0]==pytest.approx(.55) for c in cube_contacts)


@pytest.fixture(scope='module')
def pickup():
    backend = PickPlaceBackend()
    world = backend.create_world(RoboticsConfig(task='pick_place', obstacle_enabled=False).model_dump(), 7)
    state = backend.snapshot(world)
    actions, _ = backend.candidates(world, 3, 100)
    branch = backend.fork(state)
    backend.apply_action(branch, actions[0])
    result = backend.simulate(branch, {'max_simulation_seconds':60})
    return backend, world, state, actions, branch, result, backend.evaluate(branch, result)


def test_free_cube_real_grasp_lift_transport_release_placement(pickup):
    b, w, state, actions, branch, result, evaluation = pickup
    assert w.model.nq == 16 and w.model.nv == 15 and w.model.nu == 8 and w.model.nmocap == 0
    assert w.model.jnt_type[w.model.joint('cube_free').id] == mj.mjtJoint.mjJNT_FREE
    assert w.model.neq == 1  # Only the Menagerie finger symmetry constraint; no object attachment.
    assert evaluation['success'], evaluation
    assert evaluation['grasp_established'] and evaluation['lifted'] and evaluation['retained_during_transport']
    assert evaluation['released'] and evaluation['table_supported'] and evaluation['goal_error_m'] < .025
    assert result['simulation_steps'] > 1000
    lifted = [f for f in result['trace'] if f['phase'] == 'transport']
    assert lifted and all(f['cube_position'][2] > .07 and f['grasp']['bilateral_grasp'] for f in lifted)
    assert np.linalg.norm(np.asarray(branch.data.body('target').xpos)-w.config['cube_position']) > .1
    assert b.snapshot(w) == state
    assert len({json.dumps(a['stages']) for a in actions}) == 3
    json.dumps(evaluation, allow_nan=False)


def test_full_state_fork_and_exact_physics_reexecution(pickup):
    b, w, state, actions, branch, result, evaluation = pickup
    restored = b.fork(state)
    assert restored.data is not w.data and restored.model is not w.model
    b.apply_action(restored, actions[0])
    repeat = b.simulate(restored, {'max_simulation_seconds':60})
    assert repeat['trace'] == result['trace']
    assert b.snapshot(restored) == b.snapshot(branch)
    assert b.evaluate(restored, repeat) == evaluation


@pytest.mark.parametrize('mode,expected', [('open', 'grasp_failure'), ('drop', 'dropped_object'), ('timeout','timeout')])
def test_real_failure_cases(pickup, mode, expected):
    b, _, state, actions, *_ = pickup
    branch = b.fork(state); action = deepcopy(actions[0])
    if mode == 'open':
        action['stages'][2]['gripper'] = 255
    if mode == 'drop':
        action['stages'][4]['gripper'] = 255
    b.apply_action(branch, action)
    result = b.simulate(branch, {'max_simulation_seconds': .05 if mode == 'timeout' else 60})
    evaluation = b.evaluate(branch, result)
    assert not evaluation['success'] and evaluation['status'] == expected, evaluation


def test_collision_screen_and_action_parent_validation(pickup):
    b, _, _, actions, *_ = pickup
    blocked = b.create_world(RoboticsConfig(task='pick_place', obstacle_position=[.5,0,.2],
                                          obstacle_size=[.3,.3,.2]).model_dump(), 7)
    candidates, _ = b.candidates(blocked, 3, 100)
    # The overhead sensor rejects this fully occluded cube before collision
    # screening can propose a route through the blocker.
    assert all(not a['planning_feasible'] and a['screening_rejection'] == 'object_not_visible' for a in candidates)
    with pytest.raises(ValueError, match='parent'):
        action = deepcopy(actions[0]); action['stages'][0]['start'][0] += .1
        b.apply_action(blocked, action)


def test_runtime_pickup_persistence_exports_and_geometry_invalidation(runtime):
    w = runtime.create_world(CreateWorld(backend='mujoco', config=RoboticsConfig(task='pick_place', obstacle_enabled=False)))
    e = runtime.wait(runtime.submit(w['id'], ExperimentRequest(candidates=2, max_simulation_seconds=40))['id'], timeout=300)
    assert e['status'] == 'completed' and e['selected_branch_id'], e
    assert e['result']['milestone'] == 'physical_pick_and_place'
    exported = runtime.export_branch(e['id'], e['selected_branch_id'])
    assert exported['evaluation']['grasp_established'] and exported['success']
    assert exported['recorded_frames'][-1]['cube_position'] == exported['evaluation']['final_cube_position']
    resized = runtime.environment(w['id'], RoboticsConfig(task='pick_place', obstacle_enabled=False,
        cube_half_size=.03, cube_position=[.5,-.15,.031], placement_position=[.5,.18,.031]))
    assert resized['state']['model_hash'] != w['state']['model_hash']
    assert runtime.get_experiment(e['id'])['stale']
    changed = runtime.environment(w['id'], RoboticsConfig(task='pick_place', obstacle_position=[.5,0,.2],obstacle_size=[.3,.3,.2]))
    assert changed['state']['model_hash'] != w['state']['model_hash']
    assert runtime.get_experiment(e['id'])['stale']
    failed = runtime.wait(runtime.submit(w['id'], ExperimentRequest(candidates=2, planner_iterations=100))['id'])
    assert failed['selected_branch_id'] is None
    assert all(not b['evaluation']['success'] for b in runtime.store.branches(failed['id']))
