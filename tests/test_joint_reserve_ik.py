"""Native kinematic checks, not a force or collision acceptance claim."""
import mujoco as mj
import numpy as np
import pytest

from vivacity.humanoid_ik import site_pose


def redundant_chain():
    model=mj.MjModel.from_xml_string('''<mujoco><worldbody>
      <body name="base" pos="0 0 2"><freejoint/><geom type="sphere" size=".1" mass="1"/>
        <body><joint name="first" type="slide" axis="1 0 0" range="0 1"/>
          <geom type="sphere" size=".02" mass=".1"/>
          <body><joint name="second" type="slide" axis="1 0 0" range="0 1"/>
            <geom type="sphere" size=".02" mass=".1"/><site name="tip"/>
          </body>
        </body>
      </body></worldbody></mujoco>''')
    data=mj.MjData(model)
    data.qpos[7:]=[.99,.01]
    mj.mj_forward(model,data)
    return model,data


def test_redundant_pose_preserves_accuracy_and_reserves_joint_travel_without_mutating_live_state():
    model,data=redundant_chain()
    before=data.qpos.copy()
    default=site_pose(model,data.qpos,'tip',['first','second'],[1.,0.,2.],np.eye(3))
    planned=site_pose(model,data.qpos,'tip',['first','second'],[1.,0.,2.],np.eye(3),joint_margin=.1)
    assert default.feasible and min(default.qpos[7:])<.02
    assert planned.feasible and planned.position_error_m<1e-5
    assert planned.angular_error_rad<1e-5
    np.testing.assert_allclose(planned.qpos[7:],[.5,.5],atol=1e-4)
    np.testing.assert_array_equal(planned.qpos[:7],before[:7])
    np.testing.assert_array_equal(data.qpos,before)
    assert 1<=planned.iterations<=300
    repeated=site_pose(model,data.qpos,'tip',['first','second'],[1.,0.,2.],np.eye(3),joint_margin=.1)
    np.testing.assert_array_equal(repeated.qpos,planned.qpos)
    impossible=site_pose(model,data.qpos,'tip',['first','second'],[3.,0.,2.],np.eye(3),joint_margin=.1)
    assert not impossible.feasible
    assert all(.1-1e-9<=q<=.9+1e-9 for q in impossible.qpos[7:])


@pytest.mark.parametrize('margin',[-.1,.5,float('nan'),float('inf')])
def test_invalid_joint_reserve_does_not_change_live_state(margin):
    model,data=redundant_chain()
    before=data.qpos.copy()
    with pytest.raises(ValueError,match='joint margin'):
        site_pose(model,data.qpos,'tip',['first','second'],[1.,0.,2.],np.eye(3),joint_margin=margin)
    np.testing.assert_array_equal(data.qpos,before)
