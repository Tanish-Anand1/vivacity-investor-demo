"""Physical-model and honest task-readiness regression tests."""

from copy import deepcopy
import json
from pathlib import Path
import time

import mujoco as mj
import pytest
from fastapi.testclient import TestClient

from vivacity.api import create_app
from vivacity.humanoids import ASSETS, MODELS, HumanoidTrialRequest, compiled_model, initial_data, model_info, simulate


TOKEN = {'X-Workspace-Token': 'humanoid-test-owner-' + 'a' * 40}
OTHER = {'X-Workspace-Token': 'humanoid-other-owner-' + 'b' * 40}


@pytest.mark.parametrize('robot_id,minimum_dof,minimum_meshes', [
    ('unitree_g1', 50, 40), ('apptronik_apollo', 35, 40), ('unitree_h1', 16, 20),
])
def test_distinct_full_body_models_and_frontend_geometry(robot_id, minimum_dof, minimum_meshes):
    info = model_info(robot_id)
    model, digest = compiled_model(robot_id)
    assert info['dof'] >= minimum_dof
    assert info['mesh_count'] >= minimum_meshes
    assert model.nbody > 20 and model.nu >= 19 if robot_id != 'unitree_h1' else model.nbody >= 12 and model.nu == 10
    assert all(name in info['joint_names'] for name in (
        ('left_hip_pitch_joint', 'right_shoulder_pitch_joint') if robot_id == 'unitree_g1'
        else ('l_hip_fe', 'r_shoulder_fe') if robot_id == 'apptronik_apollo'
        else ('left_hip_pitch_joint', 'right_hip_pitch_joint')))
    assert ((ASSETS / MODELS[robot_id][1]).parent / 'LICENSE').is_file()
    assert model.geom('floor').id >= 0
    assert info['initial_frame']['contacts'] >= 0
    assert digest == info['model_hash']


@pytest.mark.parametrize('robot_id', ['unitree_g1', 'apptronik_apollo', 'unitree_h1'])
def test_exported_frontend_geometry_matches_compiled_model_when_packaged(robot_id):
    model, digest = compiled_model(robot_id)
    directory = Path(__file__).resolve().parents[1] / 'frontend/public/vivacity/humanoids' / robot_id
    if not directory.is_dir():
        pytest.skip('Frontend visual assets are shipped by the separate web build, not the backend image')
    manifest = json.loads((directory / 'robot-geometry.json').read_text())
    assert manifest['model_hash'] == digest
    assert manifest['simulator_version'] == mj.__version__
    assert len(manifest['bodies']) == model.nbody
    assert len(manifest['meshes']) == model_info(robot_id)['mesh_count']
    assert (directory / 'robot-meshes.bin').stat().st_size > 1_000_000
    assert (directory / 'LICENSE.txt').is_file()


def test_g1_and_apollo_stand_and_move_real_joints_without_false_task_success():
    for robot_id in ('unitree_g1', 'apptronik_apollo'):
        result = simulate(HumanoidTrialRequest(robot_id=robot_id, duration_s=2))
        assert result['status'] == 'completed' and not result['task_success']
        assert result['measurements']['simulation_steps'] >= 400
        assert result['measurements']['peak_joint_delta_rad'] > .05
        assert result['measurements']['minimum_base_height_m'] > .7
        assert result['measurements']['task_contact_samples'] == 0
        assert len(result['frames']) > 20
        assert result['frames'][0] == result['initial_frame']
        assert result['frames'][-1] == result['final_frame']
        assert result['final_integration_state']
        assert result['failure_reason'] in ('parcel_not_transported', 'switch_not_actuated')


def test_apollo_ik_hand_contact_activates_physical_switch_reproducibly():
    model, _ = compiled_model('apptronik_apollo')
    hand = model.geom('collision_r_hand_plate').id
    switch = model.geom('switch_handle').id
    assert model.geom_conaffinity[hand] & model.geom_contype[switch]
    request = HumanoidTrialRequest(robot_id='apptronik_apollo', duration_s=2, movement_scale=1)
    first, second = simulate(request), simulate(request)
    assert first['planning']['feasible']
    assert first['scene_geometry_hash'] == compiled_model('apptronik_apollo')[1]
    assert first['planning']['hand_position_error_m'] < .01
    assert first['task_success'] and first['failure_reason'] is None
    assert first['measurements']['task_contact_samples'] > 0
    assert first['measurements']['maximum_switch_angle_after_hand_contact_rad'] >= .3
    assert 0 < first['measurements']['switch_activation_time_s'] <= 2
    assert first['frames'] == second['frames']
    reduced = simulate(HumanoidTrialRequest(robot_id='apptronik_apollo', duration_s=2, movement_scale=0))
    assert not reduced['task_success']
    assert reduced['measurements']['task_contact_samples'] == 0
    assert reduced['measurements']['switch_activation_time_s'] is None


def test_apollo_machine_service_requires_contact_motor_response_and_retraction():
    request = HumanoidTrialRequest(robot_id='apptronik_apollo', action='service_machine',
                                   movement_scale=1)
    first, second = simulate(request), simulate(request)
    assert first['task_success'] and first['failure_reason'] is None
    assert first['frames'] == second['frames']
    assert first['measurements']['task_contact_samples'] > 0
    assert first['measurements']['maximum_switch_angle_rad'] >= .3
    assert first['measurements']['machine_shaft_travel_rad'] >= .5
    assert first['measurements']['peak_machine_shaft_speed_rad_s'] >= .3
    assert first['measurements']['final_hand_switch_distance_m'] >= .1
    assert first['final_integration_state'] == second['final_integration_state']
    stiff = simulate(HumanoidTrialRequest(robot_id='apptronik_apollo', action='service_machine',
                                          movement_scale=1, switch_stiffness_n_m_rad=16))
    assert not stiff['task_success'] and stiff['failure_reason'] == 'switch_not_actuated'
    assert stiff['measurements']['machine_shaft_travel_rad'] == 0
    shifted = simulate(HumanoidTrialRequest(robot_id='apptronik_apollo', action='service_machine',
                                            movement_scale=1, switch_y_m=-.24))
    assert shifted['model_hash'] != first['model_hash']
    assert shifted['frames'] != first['frames']


def test_g1_reachable_parcel_contact_moves_object_without_false_transport_claim():
    result = simulate(HumanoidTrialRequest(robot_id='unitree_g1', duration_s=2, movement_scale=1))
    assert result['planning']['feasible']
    assert result['planning']['hand_position_error_m'] < .01
    assert result['measurements']['task_contact_samples'] > 0
    assert result['measurements']['maximum_parcel_height_m'] > .70
    assert result['measurements']['peak_joint_delta_rad'] > .5
    assert not result['task_success']
    assert result['failure_reason'] == 'parcel_not_transported'


def test_h1_matched_policy_walks_stops_and_replays_deterministically():
    request = HumanoidTrialRequest(robot_id='unitree_h1', action='walk_to_goal')
    first, second = simulate(request), simulate(request)
    assert first['task_success'] and first['failure_reason'] is None
    assert not first['measurements']['fallen']
    assert first['measurements']['task_contact_samples'] > 0
    assert first['measurements']['maximum_foot_slip_m_s'] > 0
    assert first['measurements']['p95_support_foot_slip_m_s'] < .8
    assert first['measurements']['goal_error_m'] < .18
    assert first['measurements']['stable_stop_duration_s'] >= 1
    assert first['measurements']['peak_joint_delta_rad'] > .1
    assert len(first['policy_sha256']) == 64
    assert first['frames'] == second['frames']
    assert first['final_integration_state'] == second['final_integration_state']
    no_motion = simulate(HumanoidTrialRequest(robot_id='unitree_h1', action='walk_to_goal', movement_scale=0))
    assert not no_motion['task_success'] and no_motion['failure_reason'] == 'terrain_not_crossed'
    assert no_motion['measurements']['goal_error_m'] > first['measurements']['goal_error_m']


def test_parameter_change_changes_model_and_motion_without_mutating_parent():
    base_model, base_hash = compiled_model('unitree_g1')
    base = initial_data(base_model)
    changed_model, changed_hash = compiled_model('unitree_g1', .4, 1.2)
    assert changed_hash != base_hash
    assert changed_model.body('parcel').mass == pytest.approx(1.2)
    assert changed_model.geom('floor').friction[0] == pytest.approx(.4)
    low = simulate(HumanoidTrialRequest(robot_id='unitree_g1', duration_s=1.5, movement_scale=0))
    high = simulate(HumanoidTrialRequest(robot_id='unitree_g1', duration_s=1.5, movement_scale=1))
    assert high['measurements']['peak_joint_delta_rad'] > low['measurements']['peak_joint_delta_rad'] + .1
    assert high['scene_geometry_hash'] == base_hash
    varied = simulate(HumanoidTrialRequest(robot_id='unitree_g1', duration_s=.5,
                                           movement_scale=0, floor_friction=.4,
                                           parcel_mass_kg=1.2))
    assert varied['model_hash'] == changed_hash
    assert varied['scene_geometry_hash'] == base_hash
    assert base.time == 0 and base.qpos[0] == 0


def test_background_api_owner_isolation_validation_persistence_and_replay(tmp_path):
    database = tmp_path / 'humanoid.sqlite3'
    with TestClient(create_app(database)) as client:
        assert client.get('/v1/robotics/humanoids/models/unitree_g1').status_code == 200
        assert client.get('/v1/robotics/humanoids/models/panda').status_code == 422
        assert client.post('/v1/robotics/humanoids/experiments', headers=TOKEN,
                           json={'robot_id': 'unitree_g1', 'duration_s': 8}).status_code == 422
        assert client.post('/v1/robotics/humanoids/experiments', headers=TOKEN,
                           json={'robot_id': 'unitree_g1', 'fictional_grip_strength': 100}).status_code == 422
        assert client.post('/v1/robotics/humanoids/experiments',
                           json={'robot_id': 'unitree_g1'}).status_code == 422
        submitted = client.post('/v1/robotics/humanoids/experiments', headers=TOKEN,
                                json={'robot_id': 'unitree_g1', 'duration_s': .5})
        assert submitted.status_code == 202
        trial_id = submitted.json()['id']
        assert client.get(f'/v1/robotics/humanoids/experiments/{trial_id}', headers=OTHER).status_code == 404
        for _ in range(100):
            current = client.get(f'/v1/robotics/humanoids/experiments/{trial_id}', headers=TOKEN).json()
            if current['status'] in ('completed', 'failed'):
                break
            time.sleep(.05)
        assert current['status'] == 'completed', current.get('error')
        assert current['result']['measurements']['simulation_steps'] == 250
        assert current['result']['effective_physics']['floor_sliding_friction'] == pytest.approx(.8)
        assert client.get('/v1/robotics/humanoids/experiments?robot_id=unitree_g1', headers=TOKEN).json()[0]['id'] == trial_id
        replay = client.get(f'/v1/robotics/humanoids/experiments/{trial_id}/replay', headers=TOKEN)
        assert replay.status_code == 200
        assert replay.json()['frames'] == current['result']['frames']
        saved = deepcopy(current)
    with TestClient(create_app(database)) as client:
        assert client.get(f'/v1/robotics/humanoids/experiments/{trial_id}', headers=TOKEN).json() == saved
