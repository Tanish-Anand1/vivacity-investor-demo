"""Real MuJoCo geometric-sensor checks for movable tabletop objects."""

import pytest

from vivacity.perception import scan_cube
from vivacity.pick_place import PickPlaceBackend
from vivacity.native_pick_place import NativePickup
from vivacity.schemas import RoboticsConfig, CreateWorld
from vivacity.runtime import Runtime


@pytest.mark.parametrize('x,y', [(0.5, -0.15), (0.2, 0.4), (0.74, -0.4), (-.27, .5), (1.07, -.5)])
def test_overhead_rays_localize_moved_cube(x, y):
    config = RoboticsConfig(task='pick_place', obstacle_enabled=False,
                            cube_position=[x, y, 0.026], placement_position=[0.5, 0.18, 0.026])
    world = PickPlaceBackend().create_world(config.model_dump(), 7)
    scan = scan_cube(world)
    assert scan['method'] == 'mujoco_overhead_semantic_depth_rays'
    assert scan['detected']
    assert scan['visible_cube_rays'] >= 4
    assert scan['localization_error_m'] < 0.015
    assert abs(scan['estimated_xy_m'][0] - x) < 0.015
    assert abs(scan['estimated_xy_m'][1] - y) < 0.015


def test_real_occlusion_is_reported_as_not_visible():
    config = RoboticsConfig(task='pick_place', obstacle_enabled=True,
                            obstacle_position=[0.5, -0.15, 0.22],
                            obstacle_size=[0.08, 0.08, 0.2])
    world = PickPlaceBackend().create_world(config.model_dump(), 7)
    scan = scan_cube(world)
    assert not scan['detected']
    assert scan['estimated_xy_m'] is None
    assert scan['visible_cube_rays'] == 0
    actions, _ = PickPlaceBackend().candidates(world, 2, 100)
    assert all(a['screening_rejection'] == 'object_not_visible' for a in actions)
    assert all(not a['planning_feasible'] and not a['stages'] for a in actions)
    branch = PickPlaceBackend().fork(PickPlaceBackend().snapshot(world))
    PickPlaceBackend().apply_action(branch, actions[0])
    result = PickPlaceBackend().simulate(branch, {'max_simulation_seconds': 1})
    assert result['failure'] == 'planning_failure'
    assert result['simulation_steps'] == 0
    native_result, native_evaluation, _ = NativePickup(PickPlaceBackend(), PickPlaceBackend().snapshot(world)).simulate(
        actions[0], {'max_simulation_seconds': 1})
    assert native_result['simulation_steps'] == 0
    assert native_evaluation['status'] == 'planning_failure'


def test_planner_uses_ray_estimate_instead_of_true_cube_xy():
    config = RoboticsConfig(task='pick_place', obstacle_enabled=False,
                            cube_position=[0.74, -0.4, 0.026])
    backend = PickPlaceBackend()
    world = backend.create_world(config.model_dump(), 7)
    actions, _ = backend.candidates(world, 2, 100)
    measured = actions[0]['object_localization']
    assert measured['detected']
    assert actions[0]['stages'][0]['tool_position'][:2] == measured['estimated_xy_m']
    assert measured['localization_error_m'] < 0.015


def test_relocated_cube_reaches_real_grasp_and_placement():
    backend = PickPlaceBackend()
    config = RoboticsConfig(task='pick_place', obstacle_enabled=False,
                            cube_position=[0.2, 0.4, 0.026])
    world = backend.create_world(config.model_dump(), 7)
    actions, _ = backend.candidates(world, 1, 100)
    assert actions[0]['planning_feasible']
    branch = backend.fork(backend.snapshot(world))
    backend.apply_action(branch, actions[0])
    result = backend.simulate(branch, {'max_simulation_seconds': 40})
    evaluation = backend.evaluate(branch, result)
    assert result['simulation_steps'] > 1000
    assert evaluation['success'], evaluation
    assert evaluation['grasp_established']
    assert evaluation['goal_error_m'] < 0.025


def test_moving_object_recomputes_sensor_result_and_world_revision(tmp_path):
    runtime = Runtime(tmp_path / 'perception.sqlite3')
    try:
        initial = RoboticsConfig(task='pick_place', obstacle_enabled=False)
        world = runtime.create_world(CreateWorld(backend='mujoco', config=initial))
        first = runtime.observe(world['id'])['observation']['perception']
        assert first['detected']
        moved = initial.model_copy(update={'cube_position': [0.74, -0.4, 0.026]})
        changed = runtime.environment(world['id'], moved)
        second = runtime.observe(world['id'])['observation']['perception']
        assert changed['revision'] == world['revision'] + 1
        assert second['detected']
        assert abs(second['estimated_xy_m'][0] - first['estimated_xy_m'][0]) > 0.2
        assert abs(second['estimated_xy_m'][1] - first['estimated_xy_m'][1]) > 0.2
    finally:
        runtime.close()


def test_supported_table_bounds_reject_outside_points():
    RoboticsConfig(task='pick_place', cube_position=[-0.27, 0.62, 0.026])
    RoboticsConfig(task='pick_place', cube_position=[1.07, -0.62, 0.026])
    with pytest.raises(ValueError, match='supported table workspace'):
        RoboticsConfig(task='pick_place', cube_position=[1.08, 0, 0.026])
    with pytest.raises(ValueError, match='supported table workspace'):
        RoboticsConfig(task='pick_place', cube_position=[-.28, 0, 0.026])


def test_mount_overlap_reports_occlusion_without_inventing_a_pick():
    backend=PickPlaceBackend()
    world=backend.create_world(RoboticsConfig(task='pick_place',obstacle_enabled=False,
        cube_position=[0,0,.026]).model_dump(),7)
    scan=scan_cube(world)
    assert not scan['detected']
    actions,_=backend.candidates(world,2,100)
    assert all(action['screening_rejection']=='object_not_visible' for action in actions)
