import json
import mujoco as mj
import numpy as np
import pytest
from vivacity.robotics import STATE_SPEC
from vivacity.schemas import CreateWorld, RoboticsConfig, ExperimentRequest
from vivacity.runtime import Conflict


def test_model_loading_and_actual_transforms(robot):
    b, w = robot
    assert w.model.nq == 9 and w.model.nu == 8
    obs = b.observe(w)
    assert len(obs['body_transforms']) >= 12
    assert obs['time'] == 0
    assert not obs['contacts']
    assert w.model.geom('cube').rgba[2] > w.model.geom('cube').rgba[0]


def test_pose_ik_accuracy(robot):
    b, w = robot
    q, info = b.ik(w)
    assert info['converged']
    assert info['position_error_m'] < 0.001
    assert info['orientation_error_rad'] < 0.01
    assert np.all(q >= w.model.jnt_range[:7, 0])
    assert np.all(q <= w.model.jnt_range[:7, 1])


def test_control_physics_and_full_snapshot_restore(robot):
    b, original = robot
    w = b.fork(b.snapshot(original))
    w.data.ctrl[0] = 0.15
    w.data.qfrc_applied[1] = 0.7
    w.data.xfrc_applied[2, 0] = 0.2
    for _ in range(100):
        mj.mj_step(w.model, w.data)
    assert w.data.time == pytest.approx(0.2)
    assert w.data.qpos[0] > 0.02
    state = json.loads(json.dumps(b.snapshot(w)))
    assert len(state['integration_state']) == mj.mj_stateSize(w.model, STATE_SPEC)
    restored = b.fork(state)
    np.testing.assert_array_equal(b.snapshot(restored)['integration_state'], state['integration_state'])
    for _ in range(20):
        mj.mj_step(w.model, w.data); mj.mj_step(restored.model, restored.data)
    np.testing.assert_array_equal(b.snapshot(w)['integration_state'], b.snapshot(restored)['integration_state'])


def test_fork_independence_including_configuration(robot):
    b, w = robot
    snap = b.snapshot(w)
    a, c = b.fork(snap), b.fork(snap)
    a.data.qpos[0] = 1
    a.data.ctrl[0] = 1
    a.config['target_position'][0] = 0.3
    assert c.data.qpos[0] == w.data.qpos[0] == 0
    assert c.data.ctrl[0] == 0
    assert c.config['target_position'][0] == snap['config']['target_position'][0] == 0.55
    assert a.model is not c.model and a.data is not c.data


def test_snapshot_rejects_different_geometry(robot):
    b, w = robot
    changed = b.create_world(RoboticsConfig(obstacle_position=[0.7, -0.3, 0.22]).model_dump(), 7)
    with pytest.raises(ValueError, match='mismatch'):
        b.restore(changed, b.snapshot(w))


def test_prohibited_obstacle_contact(robot):
    b, w = robot
    f = b.fork(b.snapshot(w))
    f.data.qpos[:7] = b.ik(f)[0]
    # Move obstacle onto the actual end effector using independent model geometry.
    mj.mj_forward(f.model, f.data)
    f.model.body('obstacle').pos[:] = f.data.site('pregrasp').xpos
    mj.mj_forward(f.model, f.data)
    violations = b.contacts(f)
    assert violations
    assert all(v['category'] == 'environment_collision' for v in violations)


def test_success_failure_replay_and_commit(runtime):
    w = runtime.create_world(CreateWorld(backend='mujoco'))
    initial = runtime.snapshot(w['id'])
    e = runtime.wait(runtime.submit(w['id'], ExperimentRequest())['id'])
    assert e['status'] == 'completed' and e['selected_branch_id']
    branches = runtime.store.branches(e['id'])
    assert len(branches) == 3
    assert any(b['evaluation']['status'] == 'collision_failure' for b in branches)
    selected = next(b for b in branches if b['id'] == e['selected_branch_id'])
    assert selected['evaluation']['planning_feasible']
    assert selected['evaluation']['success']
    assert selected['evaluation']['goal_error_m'] < 0.02
    assert runtime.snapshot(w['id']) == initial  # simulation never implicitly commits
    backend = runtime.backends['mujoco']
    replayed = backend.fork(selected['initial_state'])
    backend.apply_action(replayed, selected['action'])
    result = backend.simulate(replayed, e['request'])
    np.testing.assert_array_equal(backend.snapshot(replayed)['integration_state'], selected['final_state']['integration_state'])
    assert result['trace'] == selected['trace']
    assert runtime.replay(e['id'])['branches'][2]['source'] == 'measured_mujoco_trace'
    committed = runtime.commit(w['id'], e['id'], selected['id'])
    assert committed['revision'] == 1
    assert committed['state'] == selected['final_state']
    with pytest.raises(Conflict):
        runtime.commit(w['id'], e['id'], selected['id'])


def test_all_paths_fail_and_geometry_invalidates(runtime):
    w = runtime.create_world(CreateWorld(backend='mujoco', config=RoboticsConfig(obstacle_position=[0.5, 0.1, 0.3], obstacle_size=[0.35, 0.35, 0.3])))
    e = runtime.wait(runtime.submit(w['id'], ExperimentRequest(planner_iterations=100))['id'])
    assert e['status'] == 'completed'
    assert e['selected_branch_id'] is None
    assert all(not b['evaluation']['success'] for b in runtime.store.branches(e['id']))
    assert e['performance']['branch_failure_rate'] == 1
    runtime.environment(w['id'], RoboticsConfig(obstacle_position=[0.75, -0.4, 0.2]))
    assert runtime.get_experiment(e['id'])['stale']
    e2 = runtime.wait(runtime.submit(w['id'], ExperimentRequest(planner_iterations=100))['id'])
    assert e2['selected_branch_id']
    selected = e2['selected_branch_id']
    runtime.environment(w['id'], RoboticsConfig())
    with pytest.raises(Conflict, match='stale'):
        runtime.commit(w['id'], e2['id'], selected)


def test_timeout_is_not_success(robot):
    b, w = robot
    f = b.fork(b.snapshot(w))
    action = b.candidates(f, 2, 100)[0][0]
    b.apply_action(f, action)
    result = b.simulate(f, {'max_simulation_seconds': 0.1})
    assert b.evaluate(f, result)['status'] == 'timeout'


def test_joint_limit_and_controller_failures(robot):
    b, w = robot
    f = b.fork(b.snapshot(w))
    f.data.qpos[0] = 3.2
    assert b.step(f, 0, {'max_simulation_seconds': 25})[0] == 'joint_limit_failure'
    f = b.fork(b.snapshot(w))
    f.data.qvel[0] = 1000
    assert b.step(f, 0, {'max_simulation_seconds': 25})[0] == 'controller_failure'


def test_self_collision_classification(robot):
    b, w = robot
    f = b.fork(b.snapshot(w)); rng = np.random.default_rng(41)
    for _ in range(200):
        f.data.qpos[:7] = rng.uniform(f.model.jnt_range[:7, 0], f.model.jnt_range[:7, 1])
        mj.mj_forward(f.model, f.data)
        if any(v['category'] == 'self_collision' for v in b.contacts(f)):
            return
    pytest.fail('no measured self-contact encountered in seeded configurations')
