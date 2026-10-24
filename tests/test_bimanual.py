import mujoco as mj
import numpy as np
import pytest

from vivacity.bimanual import BimanualConfig, BimanualTask, run_bimanual
from vivacity.physical_parameters import BoxPhysics


def test_native_g1_both_hands_carry_and_release_without_attachment():
    result = run_bimanual(BimanualConfig())
    assert result['task_success'], result['failure_reason']
    assert result['equality_constraints'] == 0
    measured = result['measurements']
    assert measured['hold_samples'] >= 250
    assert measured['bilateral_hold_samples'] == measured['hold_samples']
    assert measured['minimum_hold_share'] >= .15
    assert measured['maximum_hold_force_balance_error_n'] < .1
    assert measured['unsupported_transport_samples'] > 1000
    assert measured['retained_transport_samples'] == measured['unsupported_transport_samples']
    assert measured['maximum_transport_force_balance_error_n'] < .1
    assert measured['maximum_parcel_clearance_m'] >= .04
    assert measured['support_before_release']
    assert measured['last_measurement']['destination_error_m'] <= .03
    assert measured['last_measurement']['parcel_speed_m_s'] < .03
    assert not measured['prohibited_contacts']
    assert measured['maximum_base_tilt_rad'] < .25
    assert measured['maximum_joint_limit_error_rad'] < .05
    assert all(not frame['grasp_constraint_active'] for frame in result['frames'])
    assert len(result['model_sha256']) == 64


@pytest.mark.parametrize('config,expected', [
    (BimanualConfig(parcel=BoxPhysics(sliding_friction=.001, torsional_friction_m=0., rolling_friction_m=0.)),
     {'grip_slipped', 'insufficient_grip_contact', 'lift_not_clear', 'bilateral_load_not_sustained', 'retention_lost'}),
    (BimanualConfig(hand_torque_scale=.01),
     {'grip_slipped', 'insufficient_grip_contact', 'lift_not_clear', 'bilateral_load_not_sustained', 'retention_lost'}),
    (BimanualConfig(source_xy_m=(.68, 0.)), {'unreachable_target'}),
])
def test_deliberate_failures_are_measured(config, expected):
    result = run_bimanual(config)
    assert not result['task_success']
    assert result['failure_reason'] in expected
    assert result['equality_constraints'] == 0
    if result['failure_reason'] == 'grip_slipped':
        assert result['measurements']['grip_contact_observed']
        assert result['measurements']['maximum_grip_slip_m'] > .04
    elif result['failure_reason'] == 'insufficient_grip_contact':
        # On the Linux runtime, very low friction can prevent a load-bearing
        # grip before the slip threshold is reached. Require measured evidence
        # for that earlier failure rather than demanding one platform's label.
        measured = result['measurements']
        assert measured['phase'] == 'grip'
        assert min(measured['last_measurement']['loads'][side]['normal_force_n']
                   for side in ('left','right')) < 4.
        assert not (measured['grip_contact_observed'] and measured['maximum_grip_slip_m'] > .04)
        assert measured['maximum_parcel_clearance_m'] < .04


def test_contact_task_checkpoint_repeats_physics_and_controller_decisions():
    task = BimanualTask(BimanualConfig())
    while task.data.time < 7.8 and task.state['status'] == 'running':
        task.step()
    assert task.state['phase'] == 'lift'
    checkpoint = task.snapshot()
    branch = BimanualTask.from_checkpoint(checkpoint)
    for _ in range(120):
        task.step()
        branch.step()
    np.testing.assert_array_equal(task.data.qpos, branch.data.qpos)
    np.testing.assert_array_equal(task.data.qvel, branch.data.qvel)
    assert task.state == branch.state
    assert task.controller.snapshot() == branch.controller.snapshot()
    branch.model.geom_friction[branch.model.geom('parcel_box').id, 0] = .01
    assert task.model.geom('parcel_box').friction[0] == .8
