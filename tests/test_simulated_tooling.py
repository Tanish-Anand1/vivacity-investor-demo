"""Actuated bench lift tests for custom tooling, not a humanoid task claim."""
import xml.etree.ElementTree as ET

import mujoco as mj
import numpy as np
import pytest

from vivacity.simulated_tooling import ParallelGripperConfig, append_parallel_gripper, tooling_manifest


def bench(config, piece_mass=.2):
    root = ET.fromstring('''<mujoco><option timestep=".001" integrator="implicitfast" cone="elliptic"/>
    <worldbody><geom name="floor" type="plane" size="2 2 .05"/>
    <body name="bench_carriage" pos="0 0 .155"><joint name="bench_lift" type="slide" axis="0 0 1"
      range="0 .15" damping="5"/><geom type="sphere" size=".005" mass=".02" contype="0" conaffinity="0"/></body>
    <body name="test_piece" pos="0 0 .04"><freejoint/>
    <geom name="test_piece_geom" type="box" size=".03 .03 .04" mass=".2"/></body></worldbody>
    <actuator><position name="bench_lift_drive" joint="bench_lift" kp="2000" kv="30"
      ctrlrange="0 .15" forcerange="-100 100"/></actuator></mujoco>''')
    append_parallel_gripper(root, root.find(".//body[@name='bench_carriage']"), 'test', config)
    root.find(".//geom[@name='test_piece_geom']").set('mass',str(piece_mass))
    model = mj.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'))
    data = mj.MjData(model)
    for side in ('positive', 'negative'):
        data.qpos[model.joint(f'test_{side}_slide').qposadr[0]] = .07
        data.ctrl[model.actuator(f'test_{side}_drive').id] = .07
    mj.mj_forward(model, data)
    assert min((c.dist for c in data.contact[:data.ncon]), default=0.) >= -1e-8
    return model, data


def measured_pad_loads(model, data):
    result = {side:0. for side in ('positive', 'negative')}
    piece = model.geom('test_piece_geom').id
    for index, contact in enumerate(data.contact[:data.ncon]):
        if piece not in (contact.geom1, contact.geom2) or contact.dist > 0:
            continue
        force = np.zeros(6)
        mj.mj_contactForce(model, data, index, force)
        for side in result:
            if model.geom(f'test_{side}_pad').id in (contact.geom1, contact.geom2):
                result[side] += max(0., float(force[0]))
    return result


@pytest.mark.parametrize('friction,force,mass,lifts', [(.8,40.,.2,True), (.001,40.,.2,False),
                                                     (.8,1.,.2,False), (.8,40.,20.,False)])
def test_gripper_lifts_with_measured_contact_and_fails_insufficient_retention(friction,force,mass,lifts):
    config = ParallelGripperConfig(sliding_friction=friction,finger_force_n=force)
    model, data = bench(config,mass)
    assert model.neq == model.nmocap == 0
    for side in ('positive', 'negative'):
        data.ctrl[model.actuator(f'test_{side}_drive').id] = 0.
    for _ in range(600):
        mj.mj_step(model, data)
    assert min(measured_pad_loads(model, data).values()) > .05
    for iteration in range(1200):
        data.ctrl[0] = min(.10, iteration*.00015)
        mj.mj_step(model, data)
        for side in ('positive', 'negative'):
            force = data.actuator_force[model.actuator(f'test_{side}_drive').id]
            assert abs(force) <= config.finger_force_n+1e-8
    mj.mj_forward(model, data)
    assert (data.body('test_piece').xpos[2] > .10) == lifts
    if lifts:
        assert min(measured_pad_loads(model, data).values()) > 1.
        # Release is real: opening the fingers lets gravity drop the free body.
        for side in ('positive', 'negative'):
            data.ctrl[model.actuator(f'test_{side}_drive').id] = .07
        for _ in range(800):
            mj.mj_step(model, data)
        assert data.body('test_piece').xpos[2] == pytest.approx(.04, abs=.001)


def test_tool_manifest_matches_native_mass_commands_and_force_limits():
    config = ParallelGripperConfig(finger_force_n=12.)
    model, data = bench(config)
    manifest = tooling_manifest(model, 'test', config)
    assert manifest['tool_mass_kg'] == pytest.approx(.49)
    assert manifest['hardware_validation'] is False
    for actuator in manifest['actuators']:
        assert actuator['force_range_n'] == [-12., 12.]
        assert actuator['command_range'] == [0., .105]
    assert model.geom('test_positive_pad').friction[0] == .8


def test_finger_stiffness_changes_measured_grip_pressure_without_changing_force_cap():
    loads=[]
    for stiffness in (400.,800.):
        model,data=bench(ParallelGripperConfig(position_stiffness_n_m=stiffness))
        data.ctrl[1:]=0.
        for _ in range(600):
            mj.mj_step(model,data)
            assert np.max(np.abs(data.actuator_force[1:]))<=40.+1e-8
        mj.mj_forward(model,data)
        loads.append(min(measured_pad_loads(model,data).values()))
        assert model.neq==0
    assert loads[0]>5.
    assert 1.8<loads[1]/loads[0]<2.2
