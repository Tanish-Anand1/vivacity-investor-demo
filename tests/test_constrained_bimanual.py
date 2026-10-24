import numpy as np
import pytest

from vivacity.bimanual import BimanualConfig, compile_scene
from vivacity.constrained_bimanual import ConstrainedBimanualTask
from vivacity.execution_checkpoint import ImmutableModelArtifact
from vivacity.physical_parameters import BoxPhysics


def finish(task):
    while task.state['status'] == 'running':
        task.step()
    return task.result()


def test_constrained_task_preserves_the_original_native_actuator_and_damping_model():
    task = ConstrainedBimanualTask(BimanualConfig())
    original = compile_scene(BimanualConfig())
    assert task.model_artifact.sha256 == ImmutableModelArtifact(original).sha256
    np.testing.assert_array_equal(task.model.dof_damping, original.dof_damping)
    np.testing.assert_array_equal(task.model.actuator_biasprm, original.actuator_biasprm)
    np.testing.assert_array_equal(task.model.jnt_actfrcrange, original.jnt_actfrcrange)


def test_constrained_g1_uses_measured_bilateral_support_and_settled_release():
    result = finish(ConstrainedBimanualTask(BimanualConfig()))
    assert result['task_success'], (result['failure_reason'], result['measurements'].get('controller_error'))
    m = result['measurements']
    assert result['equality_constraints'] == 0
    assert m['minimum_hold_share'] >= .15
    assert m['bilateral_hold_samples'] == m['hold_samples'] > 250
    assert m['retained_transport_samples'] == m['unsupported_transport_samples'] > 1000
    assert m['maximum_parcel_clearance_m'] > .04
    assert m['support_before_release']
    assert m['last_measurement']['destination_error_m'] < .03
    assert m['last_measurement']['parcel_speed_m_s'] < .03
    assert m['maximum_base_tilt_rad'] < .25
    assert m['maximum_actuator_torque_fraction'] <= 1.00001
    assert result['controller_diagnostics']['maximum_violation'] < .001


def test_constrained_controller_checkpoint_repeats_commands_and_physics():
    task = ConstrainedBimanualTask(BimanualConfig())
    while task.data.time < 3.8:
        task.step()
        assert task.state['status'] == 'running'
    task.frame()
    branch = ConstrainedBimanualTask.from_checkpoint(task.snapshot())
    for _ in range(100):
        task.step()
        branch.step()
    np.testing.assert_array_equal(task.data.qpos, branch.data.qpos)
    np.testing.assert_array_equal(task.data.ctrl, branch.data.ctrl)
    assert task.controller.snapshot() == branch.controller.snapshot()
    assert task.state == branch.state
    branch.state['goal'][0] += .1
    assert task.state['goal'][0] != branch.state['goal'][0]


@pytest.mark.parametrize('config', [
    BimanualConfig(parcel=BoxPhysics(sliding_friction=.001, torsional_friction_m=0., rolling_friction_m=0.)),
    BimanualConfig(hand_torque_scale=.01),
])
def test_constrained_controller_does_not_invent_grip_when_hardware_cannot_retain(config):
    result = finish(ConstrainedBimanualTask(config))
    assert not result['task_success']
    assert result['failure_reason'] in {'grip_slipped', 'insufficient_grip_contact', 'lift_not_clear',
        'bilateral_load_not_sustained', 'retention_lost', 'controller_infeasible'}
    assert result['equality_constraints'] == 0
