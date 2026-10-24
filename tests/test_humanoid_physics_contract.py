"""Check edited humanoid settings at the executed MuJoCo contact boundary."""

import mujoco as mj
import pytest
from pydantic import ValidationError

from vivacity.humanoids import (
    HumanoidTrialRequest, compiled_model, effective_physics,
    floor_contact_friction, initial_data, simulate,
)


@pytest.mark.parametrize('robot_id', ['unitree_g1', 'apptronik_apollo', 'unitree_h1'])
def test_floor_setting_reaches_actual_sole_contact_solver(robot_id):
    observations = {}
    for coefficient in (.2, .8):
        model, digest = compiled_model(robot_id, floor_friction=coefficient)
        data = initial_data(model)
        seen = []
        for _ in range(400):
            mj.mj_step(model, data)
            if data.ncon:
                seen.extend(floor_contact_friction(model, data))
        assert seen, robot_id
        assert all(value == pytest.approx(coefficient) for value in seen)
        assert effective_physics(model, robot_id)['floor_sliding_friction'] == coefficient
        observations[coefficient] = digest
    assert observations[.2] != observations[.8]


def test_apollo_switch_intervention_changes_live_model_without_mutating_baseline():
    baseline, baseline_hash = compiled_model('apptronik_apollo')
    original_switch_y = float(baseline.body('control_switch').pos[1])
    original_stiffness = float(baseline.joint('switch_hinge').stiffness[0])
    changed, changed_hash = compiled_model('apptronik_apollo', switch_y_m=-.24,
                                           switch_stiffness_n_m_rad=14.)
    assert changed_hash != baseline_hash
    assert effective_physics(changed, 'apptronik_apollo')['switch_y_m'] == pytest.approx(-.24)
    assert effective_physics(changed, 'apptronik_apollo')['switch_stiffness_n_m_rad'] == pytest.approx(14.)
    assert baseline.body('control_switch').pos[1] == pytest.approx(original_switch_y)
    assert baseline.joint('switch_hinge').stiffness[0] == pytest.approx(original_stiffness)


def test_g1_payload_mass_and_inertia_are_linked_in_compiled_model():
    light, light_hash = compiled_model('unitree_g1', parcel_mass_kg=.2)
    heavy, heavy_hash = compiled_model('unitree_g1', parcel_mass_kg=1.2)
    first, second = effective_physics(light, 'unitree_g1'), effective_physics(heavy, 'unitree_g1')
    assert light_hash != heavy_hash
    assert first['parcel_mass_kg'] == pytest.approx(.2)
    assert second['parcel_mass_kg'] == pytest.approx(1.2)
    assert all(value > 0 for value in first['parcel_principal_inertia_kg_m2'])
    assert second['parcel_principal_inertia_kg_m2'][0] / first['parcel_principal_inertia_kg_m2'][0] == pytest.approx(6.)
    assert first['parcel_collision_size_m'] == second['parcel_collision_size_m']


def test_low_friction_changes_h1_measured_outcome_and_reports_effective_value():
    nominal = simulate(HumanoidTrialRequest(robot_id='unitree_h1', action='walk_to_goal',
                                            floor_friction=.8))
    low = simulate(HumanoidTrialRequest(robot_id='unitree_h1', action='walk_to_goal',
                                        floor_friction=.2))
    assert nominal['task_success']
    assert not low['task_success']
    assert nominal['frames'] != low['frames']
    assert nominal['effective_physics']['floor_sliding_friction'] == pytest.approx(.8)
    assert low['effective_physics']['floor_sliding_friction'] == pytest.approx(.2)
    assert nominal['measurements']['observed_floor_sliding_friction_range'] == pytest.approx([.8, .8])
    assert low['measurements']['observed_floor_sliding_friction_range'] == pytest.approx([.2, .2])


def test_g1_payload_changes_measured_loading_and_exposes_fixture_limit():
    light = simulate(HumanoidTrialRequest(robot_id='unitree_g1', action='pickup_place',
                                          parcel_mass_kg=.2))
    heavy = simulate(HumanoidTrialRequest(robot_id='unitree_g1', action='pickup_place',
                                          parcel_mass_kg=1.2))
    assert light['effective_physics']['parcel_mass_kg'] == pytest.approx(.2)
    assert heavy['effective_physics']['parcel_mass_kg'] == pytest.approx(1.2)
    assert light['task_success'] and heavy['task_success']
    assert heavy['measurements']['contact_force_peak_n']['right'] > (
        light['measurements']['contact_force_peak_n']['right'] + 50.)
    assert heavy['effective_physics']['grasp_model'] == 'contact_gated_single_wrist_weld'
    assert heavy['frames'] != light['frames']
    overloaded = simulate(HumanoidTrialRequest(robot_id='unitree_g1', action='pickup_place',
                                               parcel_mass_kg=2.))
    assert not overloaded['task_success']
    assert overloaded['failure_reason'] == 'prohibited_robot_contact'
    assert overloaded['measurements']['prohibited_contacts']


def test_unknown_and_nonfinite_physics_settings_are_rejected():
    for change in ({'fictional_grip_strength': 100}, {'floor_friction': float('nan')},
                   {'parcel_mass_kg': float('inf')}, {'switch_y_m': -5.}):
        with pytest.raises(ValidationError):
            HumanoidTrialRequest(robot_id='unitree_g1', action='pickup_place', **change)
