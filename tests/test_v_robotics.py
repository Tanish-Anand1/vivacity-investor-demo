"""Executable precision assembly and honest seven-program readiness boundary."""
from copy import deepcopy

import mujoco as mj
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from vivacity.api import create_app
from vivacity.runtime import Runtime
from vivacity.schemas import ExperimentRequest
from vivacity.v_robotics import catalog, experiment_report
from vivacity.workspace import WorkspaceService
from vivacity.workspace_schemas import ExperimentConfiguration


def configuration(**changes):
    payload = catalog().programs[0].default_configuration.model_dump()
    payload.update(changes)
    return ExperimentConfiguration.model_validate(payload)


def test_catalog_has_one_executable_program_and_no_decorative_humanoid_claim():
    programs = catalog().programs
    assert len(programs) == 7
    assert [program.id for program in programs if program.status == 'executable'] == ['precision_assembly']
    assert len([program for program in programs if program.category == 'robotic_arms']) == 4
    assert len([program for program in programs if program.category == 'humanoids']) == 3
    assert all(program.default_configuration is None and program.missing_capability for program in programs[1:])
    for change in ({'robot_id': 'panda'}, {'operation_id': 'pick_place'}, {'environment_id': 'warehouse'},
                   {'object_mass_kg': .31}, {'assembly': {'arm_speed_rad_s': 2}}):
        with pytest.raises(ValidationError):
            configuration(**change)
    with pytest.raises(ValidationError):
        ExperimentConfiguration(name='Too heavy for a generic pickup', environment_id='desktop', object_mass_kg=.2)


def test_precision_model_and_speed_are_physical_and_bounded(tmp_path):
    runtime = Runtime(tmp_path / 'model.sqlite3')
    workspace = WorkspaceService(runtime)
    try:
        slow = workspace.resolve(configuration(), 'x' * 40).world
        world = runtime.backends['mujoco'].create_world(slow.config.model_dump(), slow.seed)
        model = world.model
        assert model.opt.timestep == pytest.approx(.002)
        assert model.body('target').mass == pytest.approx(.15)
        assert len([model.joint(i) for i in range(6)]) == 6
        assert all(model.jnt_limited[:6])
        assert model.geom('task_fixture_source_tray_0_0').size[0] == pytest.approx(.004)
        assert model.geom('task_fixture_0_0').size[0] == pytest.approx(.004)
        assert model.sensor('v_actuator_effort_0').type == mj.mjtSensor.mjSENS_ACTUATORFRC
        backend = runtime.backends['mujoco']
        before = backend.snapshot(world)
        actions, _ = backend.candidates(world, 2, 100)
        assert actions[0]['planning_feasible']
        assert actions[0]['speed_rad_s'] == pytest.approx(.2)
        faster = workspace.resolve(configuration(assembly={**configuration().assembly.model_dump(), 'arm_speed_rad_s': .4}), 'x' * 40).world
        fast_world = backend.create_world(faster.config.model_dump(), faster.seed)
        faster_actions, _ = backend.candidates(fast_world, 2, 100)
        assert faster_actions[0]['speed_rad_s'] == pytest.approx(.4)
        assert sum(stage['duration_s'] for stage in faster_actions[0]['stages']) < sum(stage['duration_s'] for stage in actions[0]['stages'])
        assert backend.snapshot(world) == before
        independent = backend.fork(before)
        independent.data.qpos[0] += .1
        assert world.data.qpos[0] != independent.data.qpos[0]
    finally:
        workspace.close()
        runtime.close()


def test_precision_assembly_api_run_report_replay_and_persistence(tmp_path):
    database = tmp_path / 'api.sqlite3'
    with TestClient(create_app(database)) as client:
        listed = client.get('/v1/robotics/programs')
        assert listed.status_code == 200
        assert listed.json()['coordinate_system'] == 'right_handed_z_up'
        resolved = client.post('/v1/workspace/configurations/resolve', headers={'X-Workspace-Token': 'x' * 40},
                               json=configuration().model_dump())
        assert resolved.status_code == 200, resolved.text
        world = client.post('/v1/worlds', json=resolved.json()['world'])
        assert world.status_code == 201, world.text
        world_id = world.json()['id']
        initial = deepcopy(world.json()['state'])
        submitted = client.post(f'/v1/worlds/{world_id}/experiments', json={'candidates': 3, 'max_simulation_seconds': 40})
        assert submitted.status_code == 202, submitted.text
        experiment_id = submitted.json()['id']
        done = client.app.state.runtime.wait(experiment_id, timeout=180)
        assert done['status'] == 'completed' and done['selected_branch_id']
        branches = client.get(f'/v1/experiments/{experiment_id}/branches').json()
        assert len(branches) == 3
        assert len({branch['id'] for branch in branches}) == 3
        selected = next(branch for branch in branches if branch['id'] == done['selected_branch_id'])
        evaluation = selected['evaluation']
        assert evaluation['success'] and evaluation['grasp_established'] and evaluation['retained_during_transport']
        assert evaluation['released'] and evaluation['seated'] and evaluation['placement_within_tolerance']
        assert evaluation['goal_error_m'] <= evaluation['placement_tolerance_m']
        assert len(evaluation['peak_actuator_scalar']) == 7
        assert max(evaluation['peak_actuator_scalar'].values()) > 0
        assert selected['performance']['simulation_steps'] > 1000
        assert client.get(f'/v1/worlds/{world_id}').json()['state'] == initial
        replay = client.get(f'/v1/experiments/{experiment_id}/replay').json()
        assert any(branch['frames'] == selected['trace'] for branch in replay['branches'])
        report_response = client.get(f'/v1/robotics/experiments/{experiment_id}/report')
        assert report_response.status_code == 200, report_response.text
        report = report_response.json()
        assert report['validation_status'] == 'verified'
        assert report['solver_configuration']['timestep_s'] == pytest.approx(.002)
        assert report['solver_configuration']['state_dtype'] == 'float64'
        assert report['random_seed'] == 7 and report['terminal_state'] == selected['final_state']
        assert report['measurements']['evaluation']['goal_error_m'] == evaluation['goal_error_m']
        assert len(report['branch_ids']) == 3 and report['export_path']
        assert client.get(report['export_path']).status_code == 200
        saved_report = report
    runtime = Runtime(database)
    try:
        reopened = experiment_report(runtime, experiment_id).model_dump()
        assert reopened == saved_report
    finally:
        runtime.close()


@pytest.mark.parametrize('change,reason', [
    ({'destination_position': [1.02, .5, .026]}, 'planning_failure'),
    ({'object_mass_kg': .30, 'object_friction': .05, 'physics': {'gripper_force_scale': .05}}, 'dropped_object'),
    ({'assembly': {'arm_speed_rad_s': .2, 'grasp_yaw_rad': 0., 'placement_tolerance_m': .001,
                   'orientation_tolerance_rad': .01}}, 'operation_goal_failure'),
])
def test_measured_failures_remain_inspectable(tmp_path, change, reason):
    if 'physics' in change:
        change = change | {'physics': configuration().physics.model_dump() | change['physics']}
    runtime = Runtime(tmp_path / 'failure.sqlite3')
    workspace = WorkspaceService(runtime)
    try:
        world = runtime.create_world(workspace.resolve(configuration(**change), 'x' * 40).world)
        done = runtime.wait(runtime.submit(world['id'], ExperimentRequest(candidates=2, max_simulation_seconds=40))['id'], timeout=180)
        assert done['status'] == 'completed' and done['selected_branch_id'] is None
        branches = runtime.store.branches(done['id'])
        assert branches and all(not branch['evaluation']['success'] for branch in branches)
        assert all(branch['evaluation']['status'] == reason for branch in branches)
        report = experiment_report(runtime, done['id'])
        assert report.validation_status == 'failed' and report.termination_reason == reason
        assert report.selected_branch_id is None and report.terminal_state is None
        assert len(report.measurements['candidate_evaluations']) == 2
    finally:
        workspace.close()
        runtime.close()
