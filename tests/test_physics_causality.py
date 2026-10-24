"""Independent MuJoCo mechanism checks with explicit analytical references.

These scenes isolate physical causes; passing them does not validate a robot
controller, material calibration, or a warehouse task.
"""

import math

import mujoco as mj
import numpy as np
import pytest


def _step(xml: str, count: int, configure=None):
    model = mj.MjModel.from_xml_string(xml)
    data = mj.MjData(model)
    if configure is not None:
        configure(model, data)
    mj.mj_forward(model, data)
    for _ in range(count):
        mj.mj_step(model, data)
    mj.mj_forward(model, data)
    return model, data


@pytest.mark.parametrize('gravity', [4., 12.])
def test_gravity_changes_free_fall_by_analytical_amount(gravity):
    xml = f'''<mujoco><option timestep=".001" gravity="0 0 -{gravity}" integrator="RK4"/>
    <worldbody><body pos="0 0 2"><freejoint/><geom type="sphere" size=".05" mass="1"/></body></worldbody></mujoco>'''
    _, data = _step(xml, 200)
    assert data.qpos[2] == pytest.approx(2 - gravity * .2**2 / 2, abs=1e-7)
    assert data.qvel[2] == pytest.approx(-gravity * .2, abs=1e-7)


@pytest.mark.parametrize('mass', [.5, 2.])
def test_identical_force_accelerates_inverse_to_mass(mass):
    xml = f'''<mujoco><option timestep=".001" gravity="0 0 0" integrator="RK4"/>
    <worldbody><body name="sample"><freejoint/><geom type="sphere" size=".05" mass="{mass}"/></body></worldbody></mujoco>'''
    model, data = _step(xml, 200, lambda m, d: d.xfrc_applied.__setitem__((m.body('sample').id, 0), 2.))
    assert model.body('sample').mass[0] == pytest.approx(mass)
    assert data.qvel[0] == pytest.approx(2. * .2 / mass, abs=1e-5)


@pytest.mark.parametrize('half_size', [.04, .09])
def test_box_dimensions_change_collision_height_and_compiled_inertia(half_size):
    xml = f'''<mujoco><option timestep=".001"/><worldbody>
    <geom name="floor" type="plane" size="2 2 .1"/>
    <body name="sample" pos="0 0 {half_size + .001}"><freejoint/>
      <geom name="box" type="box" size="{half_size} {half_size} {half_size}" mass="1"/>
    </body></worldbody></mujoco>'''
    model, data = _step(xml, 500)
    assert model.geom('box').size[0] == pytest.approx(half_size)
    assert model.body('sample').inertia[0] == pytest.approx(2 * half_size**2 / 3, rel=1e-5)
    floor_box = [c for c in data.contact[:data.ncon]
                 if {int(c.geom1), int(c.geom2)} == {model.geom('floor').id, model.geom('box').id}]
    assert floor_box
    assert data.body('sample').xpos[2] == pytest.approx(half_size, abs=.003)
    assert data.body('sample').xpos[2] - floor_box[0].pos[2] == pytest.approx(half_size, abs=.003)


@pytest.mark.parametrize('inertia', [.1, .25])
def test_identical_torque_accelerates_inverse_to_inertia(inertia):
    xml = f'''<mujoco><option timestep=".001" gravity="0 0 0" integrator="RK4"/>
    <worldbody><body name="rotor"><joint name="hinge" type="hinge" axis="0 0 1" damping="0"/>
      <inertial pos="0 0 0" mass="1" diaginertia=".2 .2 {inertia}"/>
      <geom type="sphere" size=".01" contype="0" conaffinity="0"/>
    </body></worldbody></mujoco>'''
    model, data = _step(xml, 100, lambda m, d: d.qfrc_applied.__setitem__(m.joint('hinge').id, 1.))
    assert model.body('rotor').inertia[2] == pytest.approx(inertia)
    assert data.qvel[0] == pytest.approx(.1 / inertia, abs=1e-5)


def _incline(sliding_friction):
    angle = math.radians(18)
    sine, cosine = math.sin(angle), math.cos(angle)
    rotation = f'{math.cos(angle / 2)} 0 {math.sin(angle / 2)} 0'
    half = .05
    start = np.array([sine * (half + .001), 0, cosine * (half + .001)])
    xml = f'''<mujoco><option timestep=".001"/><worldbody>
    <geom name="incline" type="plane" quat="{rotation}" size="2 2 .1"
      friction="{sliding_friction} .005 .0001" priority="1"/>
    <body name="sample" pos="{start[0]} 0 {start[2]}" quat="{rotation}"><freejoint/>
      <geom name="box" type="box" size="{half} {half} {half}" mass="1" friction="1 .005 .0001"/>
    </body></worldbody></mujoco>'''
    model, data = _step(xml, 1000)
    downhill = np.array([-cosine, 0, sine])
    distance = float((data.body('sample').xpos - start) @ downhill)
    contacts = [float(c.friction[0]) for c in data.contact[:data.ncon]
                if model.geom('incline').id in (int(c.geom1), int(c.geom2))]
    return distance, contacts


def test_incline_contact_sticks_at_high_friction_and_slides_at_low_friction():
    low_distance, low_contacts = _incline(.05)
    high_distance, high_contacts = _incline(1.)
    assert low_contacts and high_contacts
    assert all(mu == pytest.approx(.05) for mu in low_contacts)
    assert all(mu == pytest.approx(1.) for mu in high_contacts)
    assert low_distance < high_distance - .05
    assert abs(high_distance) < .02
