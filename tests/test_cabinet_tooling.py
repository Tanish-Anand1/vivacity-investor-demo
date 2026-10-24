import xml.etree.ElementTree as ET

import mujoco as mj
import numpy as np
import pytest

from vivacity.cabinet_tooling import SWIVEL_JOINT, append_latch_swivel, swivel_manifest
from vivacity.simulated_tooling import ParallelGripperConfig, append_parallel_gripper


def bench(angle='degree'):
    root=ET.fromstring('''<mujoco><option timestep=".001" integrator="implicitfast"/>
    <worldbody><body name="fixed_test_mount" pos="0 0 1"/></worldbody></mujoco>''')
    ET.SubElement(root,'compiler',angle=angle)
    append_parallel_gripper(root,root.find('.//body'), 'l_service',ParallelGripperConfig())
    append_latch_swivel(root)
    return root,mj.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))


@pytest.mark.parametrize('angle',['degree','radian'])
def test_native_swivel_rotates_the_visible_tool_without_moving_tcp_or_exceeding_torque(angle):
    root,model=bench(angle)
    data=mj.MjData(model)
    mj.mj_forward(model,data)
    before=data.site('l_service_tcp').xpos.copy()
    initial_rotation=data.site('l_service_tcp').xmat.copy()
    drive=model.actuator('l_service_swivel_drive').id
    data.ctrl[drive]=1.5
    for _ in range(4000):
        mj.mj_step(model,data)
        assert abs(data.actuator_force[drive])<=3.+1e-8
    mj.mj_forward(model,data)
    assert data.joint(SWIVEL_JOINT).qpos[0]==pytest.approx(1.5,abs=.01)
    np.testing.assert_allclose(data.site('l_service_tcp').xpos,before,atol=1e-12)
    assert not np.allclose(data.site('l_service_tcp').xmat,initial_rotation)
    assert model.neq==model.nmocap==0
    assert model.body('l_service_tool').mass[0]==pytest.approx(.35)
    manifest=swivel_manifest(model)
    assert manifest['torque_range_nm']==[-3.,3.]
    np.testing.assert_allclose(manifest['range_rad'],[-1.65,1.65])
    assert not manifest['hardware_validation']
    with pytest.raises(ValueError,match='already exists'):
        append_latch_swivel(root)


def test_swivel_overload_stalls_in_real_physics_instead_of_following_commanded_rotation():
    _,model=bench()
    data=mj.MjData(model)
    drive=model.actuator('l_service_swivel_drive').id
    dof=model.joint(SWIVEL_JOINT).dofadr[0]
    # Bench actuator-load fixture only; not external support in a robot task.
    data.qfrc_applied[dof]=-4.
    data.ctrl[drive]=1.5
    for _ in range(2000):
        mj.mj_step(model,data)
    assert data.joint(SWIVEL_JOINT).qpos[0]<0.
    assert abs(data.actuator_force[drive])<=3.+1e-8


def test_swivel_requires_explicit_tooling():
    with pytest.raises(ValueError,match='gripper'):
        append_latch_swivel(ET.fromstring('<mujoco><worldbody/></mujoco>'))
