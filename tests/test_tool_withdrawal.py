"""Native geometry checks for contact-to-free-space withdrawal planning."""
import mujoco as mj
import numpy as np
import pytest

from vivacity.cabinet_route import plan_tool_clearance, route_tool_to_posture
from vivacity.pickup_planning import stage_commands


def scene(blocked=False, moving_obstacle=False):
    obstacle=('<geom name="wall" type="box" pos="-.07 0 1" size=".01 .5 .5"/>'
              if blocked else '')
    if moving_obstacle:
        obstacle='''<body pos="-.13 .3 1"><joint name="mechanism" type="slide"
          axis="0 -1 0" range="0 .3"/><geom name="wall" type="box" size=".02 .025 .1" mass=".1"/></body>'''
    model=mj.MjModel.from_xml_string(f'''<mujoco><compiler angle="radian"/>
      <worldbody><geom name="handle" type="box" pos="0 0 1" size=".04 .025 .015"/>
      {obstacle}<body pos="0 0 1">
        <joint name="x" type="slide" axis="1 0 0" range="-.3 .3"/>
        <joint name="y" type="slide" axis="0 1 0" range="-.2 .2"/>
        <geom name="palm" type="box" pos="-.08 0 0" size=".01 .04 .04" mass=".2"/>
        <site name="tcp"/>
        <body pos="0 0 .02"><joint name="positive" type="slide" axis="0 0 1" range="0 .1"/>
          <geom name="positive_pad" type="box" size=".04 .025 .005" mass=".1"/></body>
        <body pos="0 0 -.02"><joint name="negative" type="slide" axis="0 0 -1" range="0 .1"/>
          <geom name="negative_pad" type="box" size=".04 .025 .005" mass=".1"/></body>
      </body><body pos="1 1 1"><joint name="unplanned" type="slide" axis="1 0 0" range="-.5 .5"/>
        <geom type="sphere" size=".01" mass=".1"/></body></worldbody></mujoco>''')
    data=mj.MjData(model)
    data.joint('unplanned').qpos[0]=.17
    mj.mj_forward(model,data)
    return model,data


def propose(model,data,targets,**kwargs):
    pads=[model.geom(name).id for name in ('positive_pad','negative_pad')]
    fixtures=[model.geom('handle').id]
    if mj.mj_name2id(model,mj.mjtObj.mjOBJ_GEOM,'wall')>=0:
        fixtures.append(model.geom('wall').id)
    return plan_tool_clearance(model,data.qpos,'tcp',['x','y'],['positive','negative'],
        pads+[model.geom('palm').id],fixtures,
        [(pad,model.geom('handle').id) for pad in pads],targets,**kwargs)


def test_withdrawal_is_seed_independent_and_preserves_every_unplanned_coordinate():
    model,data=scene()
    before=data.qpos.copy()
    targets=[[-.12,0.,1.],[-.10,.05,1.]]
    result=propose(model,data,targets)
    assert result['feasible'],result
    assert result==propose(model,data,targets)
    selected=result['selected']
    assert selected['final_grasp_gap_m']>=.01
    assert selected['minimum_sampled_clearance_m']>=.003
    end=np.asarray(selected['qpos'])
    assert end[model.joint('unplanned').qposadr[0]]==.17
    np.testing.assert_array_equal(data.qpos,before)
    # Independently check a denser edge than the planner used, including the
    # original grasp surfaces. No proposed motion passes through the handle.
    scratch=mj.MjData(model)
    for fraction in np.linspace(0.,1.,200):
        scratch.qpos[:]=before+(end-before)*fraction
        mj.mj_forward(model,scratch)
        for pad in ('positive_pad','negative_pad'):
            assert mj.mj_geomDistance(model,scratch,model.geom(pad).id,
                model.geom('handle').id,1.,None)>=-1e-8


def test_blocked_withdrawal_returns_no_candidate_instead_of_crossing_wall():
    model,data=scene(blocked=True)
    before=data.qpos.copy()
    result=propose(model,data,[[-.12,0.,1.]])
    assert not result['feasible'] and result['selected'] is None
    assert result['feasible_candidate_count']==0
    np.testing.assert_array_equal(data.qpos,before)


def test_out_of_reach_goal_has_no_feasible_proposal():
    model,data=scene()
    result=propose(model,data,[[-1.,0.,1.]])
    assert not result['feasible'] and result['selected'] is None


def test_parking_checks_future_mechanism_motion_on_independent_scratch_state():
    model,data=scene(moving_obstacle=True)
    before=data.qpos.copy()
    targets=[[-.12,0.,1.]]
    assert propose(model,data,targets)['feasible']
    blocked=propose(model,data,targets,mechanism_sweep=('mechanism',.3))
    assert not blocked['feasible']
    safe=propose(model,data,targets,mechanism_sweep=('mechanism',.05))
    assert safe['feasible'] and safe['selected']['sweep_samples']>1
    assert safe['selected']['swept_clearance_m']>=.01
    np.testing.assert_array_equal(data.qpos,before)


@pytest.mark.parametrize('sweep',[('mechanism',.31),('mechanism',float('nan')),('x',0.)])
def test_invalid_mechanism_sweep_cannot_move_a_controlled_joint_or_exceed_bounds(sweep):
    model,data=scene(moving_obstacle=True)
    before=data.qpos.copy()
    with pytest.raises(ValueError,match='mechanism sweep'):
        propose(model,data,[[-.12,0.,1.]],mechanism_sweep=sweep)
    np.testing.assert_array_equal(data.qpos,before)


def test_posture_route_keeps_released_fingers_open_and_avoids_physical_obstacle():
    model,data=scene()
    data.joint('x').qpos[0]=-.15
    data.joint('positive').qpos[0]=.04
    data.joint('negative').qpos[0]=.04
    before=data.qpos.copy()
    goal=before.copy()
    goal[model.joint('x').qposadr[0]]=.18
    # The planner must not inherit this unchecked goal value for the other arm.
    goal[model.joint('unplanned').qposadr[0]]=-.3
    names=['x','y','positive','negative']
    tools=[model.geom(name).id for name in ('palm','positive_pad','negative_pad')]
    result=route_tool_to_posture(model,before,goal,names,tools,[model.geom('handle').id],
        np.random.default_rng(7),opening_joints=['positive','negative'])
    assert result['feasible'] and len(result['waypoints'])>2,result
    np.testing.assert_array_equal(data.qpos,before)
    np.testing.assert_array_equal(np.asarray(result['waypoints'])[:,model.joint('unplanned').qposadr[0]],
        np.full(len(result['waypoints']),.17))
    scratch=mj.MjData(model)
    for pose in stage_commands(result,np.linspace(0,1,400)):
        assert pose[model.joint('unplanned').qposadr[0]]==pytest.approx(.17,abs=1e-14)
        assert all(pose[model.joint(name).qposadr[0]]>=.039 for name in ('positive','negative'))
        scratch.qpos[:]=pose
        mj.mj_forward(model,scratch)
        for tool in tools:
            assert mj.mj_geomDistance(model,scratch,tool,model.geom('handle').id,1.,None)>.009


def test_posture_route_refuses_future_mechanism_intersection():
    model,data=scene(moving_obstacle=True)
    data.joint('x').qpos[0]=-.12
    data.joint('positive').qpos[0]=.04
    data.joint('negative').qpos[0]=.04
    before=data.qpos.copy()
    tools=[model.geom(name).id for name in ('palm','positive_pad','negative_pad')]
    result=route_tool_to_posture(model,before,before,['x','y','positive','negative'],tools,
        [model.geom('handle').id,model.geom('wall').id],np.random.default_rng(7),
        mechanism_sweep=('mechanism',.3))
    assert not result['feasible']
    assert result['failure']=='parked_posture_intersects_mechanism'
    assert not result['waypoints']
    np.testing.assert_array_equal(data.qpos,before)


@pytest.mark.parametrize('targets,settings',[
    ([[float('nan'),0.,1.]],{}),([],{}),([[-.1,0.,1.]],{'opening_m':.2}),
    ([[-.1,0.,1.]],{'minimum_clearance_m':-.001}),
])
def test_invalid_withdrawal_does_not_mutate_native_state(targets,settings):
    model,data=scene()
    before=data.qpos.copy()
    with pytest.raises(ValueError,match='bounded'):
        propose(model,data,targets,**settings)
    np.testing.assert_array_equal(data.qpos,before)
