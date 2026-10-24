import gc
from copy import deepcopy

import numpy as np
import pytest

from vivacity.apollo_door import CabinetDoorPrimitive, SOURCE_HASHES


def test_door_primitive_checkpoint_preserves_feedback_and_independent_native_state():
    task=CabinetDoorPrimitive()
    assert task.manifest['cabinet_fixture_profile']=='historical-partial-door'
    assert not task.controller.wide_tooling
    while task.data.time<5.5 and task.state['status']=='running':
        task.step()
    assert task.state['status']=='running',task.state.get('failure_detail')
    assert task.state['phase']=='approach'
    assert max(np.linalg.norm(v) for v in task.controller.integrals.values())>0.
    assert task.frame()['seq']==0
    saved=task.snapshot()
    assert saved.checkpoint.task_state['source_hashes']==SOURCE_HASHES
    assert saved.checkpoint.next_frame_seq==1
    branch=CabinetDoorPrimitive.from_checkpoint(saved)
    for _ in range(40):
        task.step()
        branch.step()
    np.testing.assert_array_equal(task.data.qpos,branch.data.qpos)
    np.testing.assert_array_equal(task.data.qvel,branch.data.qvel)
    assert task.state==branch.state
    assert task.controller.snapshot()==branch.controller.snapshot()
    assert task.frame()==branch.frame()
    # Mutating a branch does not alter the original model or integral memory.
    branch.model.jnt_stiffness[branch.model.joint('service_latch_slide').id]=4000.
    assert task.model.joint('service_latch_slide').stiffness[0]==300.
    branch.controller.integrals['l'][0]=.06
    assert task.controller.integrals['l'][0]!=.06
    with pytest.raises(ValueError,match='immutable model changed'):
        branch.snapshot()
    assert task.model.neq==task.model.nmocap==0
    assert not task.state['cabinet_service_complete']
    saved.checkpoint.task_state['source_hashes']['apollo_door.py']='0'*64
    with pytest.raises(ValueError,match='version changed'):
        CabinetDoorPrimitive.from_checkpoint(saved)
    del branch,task
    gc.collect()


def test_wide_opening_keeps_its_distinct_model_and_never_substitutes_the_partial_goal():
    task=CabinetDoorPrimitive(opening_angle_rad=1.1)
    assert task.manifest['cabinet_fixture_profile']=='wide-opening-development'
    assert task.manifest['identity']=='vivacity.apollo-cabinet-swivel-tool/2-experimental'
    assert task.model.nu==37
    assert task.manifest['cabinet_tooling']['torque_range_nm']==[-3.,3.]
    assert not task.manifest['cabinet_tooling']['hardware_validation']
    assert task.controller.wide_tooling
    assert task.state['opening_angle_rad']==1.1
    np.testing.assert_allclose(task.model.geom('service_latch_button').pos,[-.085,.4,.065])
    task.fail('lost_door_grip')
    task.step()
    assert task.state['opening_angle_rad']==1.1
    assert not task.state['success'] and not task.state['cabinet_service_complete']


def test_invalid_cartesian_integral_state_is_rejected():
    task=CabinetDoorPrimitive()
    state=deepcopy(task.controller.snapshot())
    state['integrals']['l']=[float('nan'),0.,0.]
    with pytest.raises(ValueError,match='integral'):
        task.controller.restore(state)
    state=deepcopy(task.controller.snapshot())
    state['stance']['commands'][0]=float('nan')
    before=task.controller.snapshot()
    with pytest.raises(ValueError,match='stance checkpoint'):
        task.controller.restore(state)
    assert task.controller.snapshot()==before


def test_swivel_embodiment_checkpoint_restores_independent_actuators_and_native_state():
    task=CabinetDoorPrimitive(opening_angle_rad=1.1)
    for _ in range(40):
        task.step()
    saved=task.snapshot()
    branch=CabinetDoorPrimitive.from_checkpoint(saved)
    assert branch.model.nu==37 and branch.controller.wide_tooling
    for _ in range(20):
        task.step()
        branch.step()
    np.testing.assert_array_equal(task.data.qpos,branch.data.qpos)
    np.testing.assert_array_equal(task.data.qvel,branch.data.qvel)
    assert task.controller.snapshot()==branch.controller.snapshot()
    assert task.state==branch.state
    branch.data.ctrl[branch.model.actuator('l_service_swivel_drive').id]=1.
    assert not np.array_equal(task.data.ctrl,branch.data.ctrl)


def test_failed_primitive_freezes_the_measured_state_and_is_not_a_service_success():
    task=CabinetDoorPrimitive()
    task.step()
    task.fail('cancelled')
    task.fail('later_failure_must_not_replace_the_first')
    before=task.data.qpos.copy()
    when=task.data.time
    task.step()
    np.testing.assert_array_equal(before,task.data.qpos)
    assert task.data.time==when
    assert task.state['failure']=='cancelled'
    assert not task.state['success'] and not task.state['cabinet_service_complete']


@pytest.mark.parametrize('force,stiffness,expected',[(40.,300.,None),(1.,300.,'unstable_posture'),
    (40.,4000.,'latch_resistance_or_retention_failure')])
def test_native_door_opening_and_force_limited_failure_cases(force,stiffness,expected):
    from vivacity.cabinet_mechanism import CabinetConfig
    from vivacity.simulated_tooling import ParallelGripperConfig
    task=CabinetDoorPrimitive(CabinetConfig(front_x_m=.75,latch_stiffness_n_m=stiffness),
        ParallelGripperConfig(finger_force_n=force))
    while task.state['status']=='running' and task.data.time<50.:
        task.step()
    assert task.state['failure']==expected,task.state
    assert task.state['peak_gripper_actuator_force_n']<=force+1e-6
    assert not task.state['cabinet_service_complete']
    measured=task.observe()
    if expected is None:
        assert task.state['success'] and task.state['status']=='completed'
        assert measured['door_angle_rad']>.20
        assert measured['latch_retraction_m']>.035
        assert measured['root_speed_m_s']<.03
        assert task.state['peak_tilt_rad']<.20
        assert all(min(loads.values())>2. for loads in measured['grip_forces_n'].values())
        assert [event['to'] for event in task.state['phase_events']]==['approach','insert','grasp','latch','open']
    else:
        assert not task.state['success']
        assert measured['door_angle_rad']<.05
        if expected=='unstable_posture':
            # A one-newton finger drive cannot support even its own 0.12 kg
            # vertical finger. The measured approach fails before grasping.
            assert measured['root_tilt_rad']>.20 or task.data.qpos[2]<.9*task.model.key_qpos[0,2]
        else:
            assert task.state['phase']=='latch'
            assert task.state['failure_detail']['measured_retraction_m']<.025
            assert task.state['failure_detail']['requested_retraction_m']==.05
