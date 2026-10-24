import mujoco as mj
import numpy as np

from vivacity.cabinet_route import route_approach
from vivacity.pickup_planning import stage_commands


def scene():
    model=mj.MjModel.from_xml_string('''<mujoco><compiler angle="radian"/>
    <worldbody><geom name="service_tray_obstacle" type="box" pos="0 0 1" size=".05 .12 .04"/>
    <body pos="0 0 1"><joint name="x" type="slide" axis="1 0 0" range="-.4 .4"/>
    <joint name="y" type="slide" axis="0 1 0" range="-.4 .4"/>
    <geom name="r_service_palm" type="sphere" size=".02" mass=".1"/></body>
    </worldbody></mujoco>''')
    data=mj.MjData(model)
    data.qpos[:]=[-.2,0.]
    mj.mj_forward(model,data)
    return model,data


def test_seeded_native_route_goes_around_obstacle_and_preserves_live_state():
    model,data=scene()
    before=data.qpos.copy()
    goal=np.array([.2,0.])
    route=route_approach(model,data.qpos,goal,['x','y'],np.random.default_rng(7),iterations=500)
    assert route['feasible'] and len(route['waypoints'])>2
    repeated=route_approach(model,data.qpos,goal,['x','y'],np.random.default_rng(7),iterations=500)
    assert route==repeated
    np.testing.assert_array_equal(data.qpos,before)
    scratch=mj.MjData(model)
    for q in stage_commands(route,np.linspace(0,1,400)):
        scratch.qpos[:]=q
        mj.mj_forward(model,scratch)
        distance=mj.mj_geomDistance(model,scratch,model.geom('r_service_palm').id,
                                   model.geom('service_tray_obstacle').id,1.,None)
        assert distance>=.0295


def test_collision_at_goal_returns_honest_failure_without_waypoints():
    model,data=scene()
    result=route_approach(model,data.qpos,np.zeros(2),['x','y'],np.random.default_rng(7),iterations=500)
    assert not result['feasible'] and not result['waypoints']
    np.testing.assert_array_equal(data.qpos,[-.2,0.])
