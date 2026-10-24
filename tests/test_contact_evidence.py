"""Force sign/frame/moment checks use actual solved MuJoCo contacts."""
import mujoco as mj
import numpy as np
import pytest

from vivacity.contact_evidence import body_contact_loads, bilateral_support


def clamp_scene(friction=.8, force=15., mass=.5):
    # Two independently actuated horizontal jaws. The free parcel is never
    # attached. This isolates load measurement from a humanoid controller.
    xml = f'''<mujoco><option timestep=".001" integrator="implicitfast"/>
    <worldbody>
      <body name="left" pos="0 .081 1"><joint name="left" type="slide" axis="0 -1 0" damping="4"/>
        <geom type="box" size=".06 .02 .08" mass="1" friction="{friction} .001 .0001" priority="2"/></body>
      <body name="right" pos="0 -.081 1"><joint name="right" type="slide" axis="0 1 0" damping="4"/>
        <geom type="box" size=".06 .02 .08" mass="1" friction="{friction} .001 .0001" priority="2"/></body>
      <body name="parcel" pos="0 0 1"><freejoint/>
        <geom type="box" size=".05 .06 .05" mass="{mass}"/></body>
    </worldbody><actuator><motor joint="left"/><motor joint="right"/></actuator></mujoco>'''
    model = mj.MjModel.from_xml_string(xml)
    data = mj.MjData(model)
    data.ctrl[:] = force
    for _ in range(600):
        mj.mj_step(model, data)
    mj.mj_forward(model, data)
    groups = {side: {model.body(side).id} for side in ('left', 'right')}
    loads = body_contact_loads(model, data, model.body('parcel').id, groups)
    return model, data, loads


def test_independent_jaws_carry_weight_without_attachment():
    model, data, loads = clamp_scene()
    assert model.neq == 0
    assert data.body('parcel').xpos[2] > .98
    assert loads['left'].normal_force_n == pytest.approx(15., abs=.05)
    assert loads['right'].normal_force_n == pytest.approx(15., abs=.05)
    assert loads['left'].force_world_n[1] < 0
    assert loads['right'].force_world_n[1] > 0
    assert loads['left'].force_world_n[2] == pytest.approx(.5*9.81/2, abs=.05)
    assert loads['right'].force_world_n[2] == pytest.approx(.5*9.81/2, abs=.05)
    evidence = bilateral_support(loads, .5, 9.81, float(data.qacc[4]))
    assert evidence['bilateral_load']
    assert evidence['unsupported_by_environment']
    assert abs(evidence['force_balance_error_n']) < .05
    np.testing.assert_allclose(sum((v.torque_world_nm for v in loads.values())), 0, atol=.01)


@pytest.mark.parametrize('friction,force,mass', [(.001, 15., .5), (.8, .2, .5), (.8, 15., 8.)])
def test_low_friction_weak_grip_and_overload_drop(friction, force, mass):
    model, data, loads = clamp_scene(friction, force, mass)
    assert model.neq == 0
    assert data.body('parcel').xpos[2] < .6
    assert not bilateral_support(loads, mass, 9.81, 0)['bilateral_load']


def test_contact_group_overlap_is_rejected():
    model, data, _ = clamp_scene()
    with pytest.raises(ValueError, match='overlap'):
        body_contact_loads(model, data, model.body('parcel').id,
                           {'left': {1}, 'right': {1}})
