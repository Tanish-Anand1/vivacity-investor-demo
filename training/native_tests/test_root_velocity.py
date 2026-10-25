"""Sensor-frame mapping checks against native MuJoCo, not duplicated formulas."""
import mujoco as mj
import numpy as np
import pytest

from training.locomotion_contract import free_root_velocity


@pytest.mark.parametrize('seed',range(8))
def test_free_root_sensor_velocity_matches_native_object_velocity(seed):
    model=mj.MjModel.from_xml_string('''<mujoco><compiler alignfree="false"/>
      <worldbody><body name="base" pos="0 0 1"><freejoint/>
        <geom type="box" size=".1 .2 .3" mass="2" pos=".1 .05 0"/>
        <body pos=".2 0 .1"><joint type="hinge" axis="0 1 0"/>
          <geom type="capsule" size=".03 .1" mass=".5"/>
        </body>
      </body></worldbody></mujoco>''')
    rng=np.random.default_rng(seed)
    data=mj.MjData(model)
    quaternion=rng.normal(size=4)
    data.qpos[3:7]=quaternion/np.linalg.norm(quaternion)
    data.qpos[7]=rng.normal()
    data.qvel[:]=rng.normal(size=model.nv)
    mj.mj_forward(model,data)
    expected=np.zeros(6)
    mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_XBODY,model.body('base').id,expected,1)
    angular,linear=free_root_velocity(data.qvel[:6],data.body('base').xmat)
    np.testing.assert_allclose(angular,expected[:3],atol=1e-12)
    np.testing.assert_allclose(linear,expected[3:],atol=1e-12)
