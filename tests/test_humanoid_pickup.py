"""Measured stationary G1 pickup, failure, reproducibility, and API boundary."""

import time

import mujoco as mj
import pytest
from fastapi.testclient import TestClient

from vivacity.api import create_app
from vivacity.humanoids import HumanoidTrialRequest, compiled_model, simulate


TOKEN = {'X-Workspace-Token': 'pickup-owner-' + 'a'*40}
OTHER = {'X-Workspace-Token': 'pickup-other-' + 'b'*40}


def pickup(**settings):
    return simulate(HumanoidTrialRequest(robot_id='unitree_g1', action='pickup_place', **settings))


def test_g1_contact_gated_grasp_lift_place_release_and_replay():
    parent, digest = compiled_model('unitree_g1')
    original_relpose = parent.eq_data.copy()
    first = pickup()
    second = pickup()
    assert digest == first['model_hash'] == second['model_hash']
    assert parent.eq_data.tolist() == original_relpose.tolist()
    assert first['task_success'] and first['failure_reason'] is None
    assert [event['phase'] for event in first['events']] == [
        'lift', 'transfer', 'lower', 'settle_before_release', 'released']
    evidence = first['events'][0]['evidence']
    assert evidence['bilateral_contact_steps'] >= 10
    assert evidence['left_normal_force_n'] >= 2
    assert evidence['right_normal_force_n'] >= 2
    assert evidence['constraint_pose_jump_m'] < 1e-8
    measured = first['measurements']
    assert measured['maximum_parcel_height_m'] > .84
    assert measured['final_support_contact']
    assert measured['support_contact_samples_after_release'] >= 20
    assert not measured['grasp_constraint_active_final']
    assert not measured['floor_drop_contact']
    assert not measured['prohibited_contacts']
    assert measured['minimum_base_height_m'] > .7
    assert measured['maximum_base_tilt_rad'] < .4
    assert measured['maximum_joint_limit_violation_rad'] < .05
    assert measured['destination_error_m'] < .17
    assert measured['final_parcel_speed_m_s'] < .05
    assert first['frames'] == second['frames']
    assert first['initial_integration_state'] == second['initial_integration_state']
    assert first['final_integration_state'] == second['final_integration_state']
    assert first['grasp_constraint_relpose'] == second['grasp_constraint_relpose']
    assert first['frames'][0]['grasp_active'] is False
    assert any(frame['grasp_active'] for frame in first['frames'])
    assert first['frames'][-1]['grasp_active'] is False


def test_missing_grasp_and_unreachable_object_are_honest_failures():
    no_motion = pickup(movement_scale=0)
    assert not no_motion['task_success']
    assert no_motion['failure_reason'] == 'no_supported_bilateral_grasp'
    assert no_motion['grasp_constraint_relpose'] is None
    assert no_motion['measurements']['task_contact_samples'] == 0
    unreachable = pickup(parcel_xy_m=(.95, 0.))
    assert not unreachable['task_success']
    assert unreachable['failure_reason'] == 'unreachable_grasp_target'
    assert not unreachable['planning']['feasible']
    assert unreachable['measurements']['simulation_steps'] == 0
    assert unreachable['frames'][0]['parcel_position_m'][0] == pytest.approx(.95)


def test_mass_destination_and_contact_configuration_change_measured_outcomes():
    light = pickup(parcel_mass_kg=.2)
    heavier = pickup(parcel_mass_kg=1.2)
    assert light['task_success'] and heavier['task_success']
    assert light['model_hash'] != heavier['model_hash']
    assert light['measurements']['final_parcel_position_m'] != heavier['measurements']['final_parcel_position_m']
    moved = pickup(destination_xy_m=(.6, -.5))
    assert moved['task_success']
    assert moved['measurements']['final_parcel_position_m'] != light['measurements']['final_parcel_position_m']
    overloaded = pickup(parcel_mass_kg=2.)
    assert not overloaded['task_success']
    assert overloaded['failure_reason'] in ('prohibited_robot_contact', 'unstable_stance', 'placement_not_stable')
    assert overloaded['measurements']['prohibited_contacts'] or overloaded['measurements']['fallen'] or not overloaded['measurements']['final_support_contact']


def test_pickup_api_validation_owner_persistence_and_replay(tmp_path):
    database = tmp_path / 'pickup.sqlite3'
    with TestClient(create_app(database)) as client:
        assert client.post('/v1/robotics/humanoids/experiments', headers=TOKEN,
                           json={'robot_id': 'unitree_h1', 'action': 'pickup_place'}).status_code == 422
        assert client.post('/v1/robotics/humanoids/experiments', headers=TOKEN,
                           json={'robot_id': 'unitree_g1', 'action': 'pickup_place',
                                 'parcel_xy_m': [20, 0]}).status_code == 422
        submitted = client.post('/v1/robotics/humanoids/experiments', headers=TOKEN,
                                json={'robot_id': 'unitree_g1', 'action': 'pickup_place'})
        assert submitted.status_code == 202
        trial_id = submitted.json()['id']
        assert client.get(f'/v1/robotics/humanoids/experiments/{trial_id}',
                          headers=OTHER).status_code == 404
        deadline = time.monotonic()+30
        while time.monotonic() < deadline:
            current = client.get(f'/v1/robotics/humanoids/experiments/{trial_id}',
                                 headers=TOKEN).json()
            if current['status'] in ('completed', 'failed'):
                break
            time.sleep(.1)
        assert current['status'] == 'completed', current['error']
        assert current['result']['task_success']
        replay = client.get(f'/v1/robotics/humanoids/experiments/{trial_id}/replay',
                            headers=TOKEN)
        assert replay.status_code == 200
        assert replay.json()['frames'] == current['result']['frames']
        assert client.get(f'/v1/robotics/humanoids/experiments/{trial_id}/replay',
                          headers=OTHER).status_code == 404
    with TestClient(create_app(database)) as client:
        restored = client.get(f'/v1/robotics/humanoids/experiments/{trial_id}',
                              headers=TOKEN).json()
        assert restored == current
