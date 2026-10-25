"""Bench fixtures exercise passive mechanics, not an Apollo service acceptance.

Prescribed test loads are external bench disturbances. Contact rams have native
force-limited actuators. No live step overwrites a cabinet or cartridge pose.
"""
import xml.etree.ElementTree as ET

import mujoco as mj
import numpy as np
import pytest
from pydantic import ValidationError

from vivacity.cabinet_mechanism import CabinetConfig, compile_fixture, fixture_tree, measure


def step(model, data, seconds):
    for _ in range(round(seconds/model.opt.timestep)):
        mj.mj_step(model, data)
    mj.mj_forward(model, data)


def with_ram(config, target):
    root = fixture_tree(config)
    x, y = config.front_x_m, config.center_y_m
    position, axis, force = ((x-.085, y+.09, 1.165), '0 1 0', 30.) if target == 'latch' else (
        (x+.052, y, 1.06), '0 0 -1', 40.)
    body = ET.SubElement(root.find('worldbody'), 'body', name='bench_ram', pos=' '.join(map(str, position)))
    ET.SubElement(body, 'joint', name='bench_slide', type='slide', axis=axis,
                  range='0 .14', damping='2', armature='.01')
    ET.SubElement(body, 'geom', name='bench_ram_tip', type='box', size='.014 .018 .014', mass='.15',
                  friction='.3 .001 .0001', solref='.004 1')
    actuator = ET.SubElement(root, 'actuator')
    ET.SubElement(actuator, 'position', name='bench_drive', joint='bench_slide', kp='1500', kv='20',
                  ctrlrange='0 .14', forcerange=f'-{force} {force}')
    if target == 'latch':
        # The bench finger follows the door's arc instead of blocking it as a
        # stationary obstacle. Both axes move through finite native actuators.
        ET.SubElement(body, 'joint', name='bench_withdraw', type='slide', axis='-1 0 0',
                      range='0 .65', damping='2', armature='.01')
        ET.SubElement(actuator, 'position', name='bench_withdraw_drive', joint='bench_withdraw',
                      kp='1500', kv='20', ctrlrange='0 .65', forcerange='-40 40')
    return mj.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'))


def test_passive_fixture_loads_without_overlap_and_cartridges_settle_on_real_supports():
    config = CabinetConfig()
    model = compile_fixture(config)
    data = mj.MjData(model)
    mj.mj_forward(model, data)
    assert model.nu == model.neq == 0
    assert min((contact.dist for contact in data.contact[:data.ncon]), default=0.) >= -1e-8
    step(model, data, 1.)
    values = measure(model, data, config)
    assert abs(values['door_angle_rad']) < .005
    assert values['latch_retraction_m'] < .001
    assert values['retention_retraction_m'] < .003
    assert values['old_cartridge_position_m'] == pytest.approx([.8, 0., 1.05], abs=1e-4)
    assert values['replacement_position_m'] == pytest.approx([.38, -.45, 1.05], abs=1e-4)
    assert not values['mechanism_ready']
    force = sum(value for pair, value in values['contact_normal_forces_n'].items()
                if 'service_old_shell' in pair)
    assert force == pytest.approx(config.cartridge_mass_kg*9.81, abs=.01)


def test_latched_door_resists_external_pull_through_measured_strike_contact():
    config = CabinetConfig()
    model = compile_fixture(config)
    data = mj.MjData(model)
    data.xfrc_applied[model.body('service_door').id, 5] = -1.
    step(model, data, 1.)
    values = measure(model, data, config)
    assert 0. < values['door_angle_rad'] < .015
    assert values['contact_normal_forces_n']['service_latch_bolt|service_strike'] > 1.


@pytest.mark.parametrize('height', [.75, .89, 1.05])
@pytest.mark.parametrize('changed_side', ['old', 'replacement'])
def test_tray_height_rebuilds_supports_initial_cartridge_and_measured_destination(height, changed_side):
    config = CabinetConfig(**{f'{changed_side}_tray_surface_height_m': height})
    model = compile_fixture(config)
    data = mj.MjData(model)
    mj.mj_forward(model, data)
    assert model.neq == model.nmocap == 0
    for side in ('old', 'replacement'):
        top = height if side == changed_side else .99
        tray = model.geom(f'service_{side}_tray')
        assert data.geom(tray.id).xpos[2]+tray.size[2] == pytest.approx(top)
        pedestal = model.geom(f'service_{side}_tray_pedestal')
        assert data.geom(pedestal.id).xpos[2]-pedestal.size[2] == pytest.approx(0.)
        assert data.geom(pedestal.id).xpos[2]+pedestal.size[2] == pytest.approx(top-.03)
    step(model, data, 1.)
    measured = measure(model, data, config)
    assert measured['replacement_position_m'][2] == pytest.approx(
        config.replacement_tray_surface_height_m+.06, abs=1e-4)
    assert measured['old_cartridge_position_m'][2] == pytest.approx(1.05, abs=1e-4)
    destination = np.array([config.front_x_m-.22, config.center_y_m+.45,
                            config.old_tray_surface_height_m+.06])
    assert measured['old_tray_error_m'] == pytest.approx(
        np.linalg.norm(np.array(measured['old_cartridge_position_m'])-destination))
    support = sum(force for pair, force in measured['contact_normal_forces_n'].items()
                  if 'service_replacement_shell' in pair and 'service_replacement_tray' in pair)
    assert support == pytest.approx(config.cartridge_mass_kg*9.81, abs=.01)


@pytest.mark.parametrize('height', [.749, 1.051, float('nan')])
@pytest.mark.parametrize('side', ['old', 'replacement'])
def test_invalid_tray_height_is_rejected(height, side):
    with pytest.raises(ValidationError):
        CabinetConfig(**{f'{side}_tray_surface_height_m': height})


@pytest.mark.parametrize('stiffness,opens', [(300., True), (4000., False)])
def test_contact_ram_releases_latch_but_excessive_spring_resistance_prevents_release(stiffness, opens):
    config = CabinetConfig(latch_stiffness_n_m=stiffness)
    model = with_ram(config, 'latch')
    data = mj.MjData(model)
    data.ctrl[0] = .09
    # The protruding button also applies opening torque. This explicit bench
    # load holds the door against its native closed stop while measuring latch
    # actuation, then becomes the opening pull below. It is not robot support.
    data.xfrc_applied[model.body('service_door').id, 5] = 2.
    step(model, data, .8)
    before = measure(model, data, config)
    assert before['contact_normal_forces_n']['bench_ram_tip|service_latch_button'] > 0.
    assert abs(data.actuator_force[0]) <= 30.+1e-8
    assert (before['latch_retraction_m'] > .035) == opens
    data.xfrc_applied[model.body('service_door').id, 5] = -8.
    for _ in range(1500):
        door = data.body('service_door')
        button = door.xpos+door.xmat.reshape(3, 3) @ np.array([-.085, -.085, .065])
        data.ctrl[0] = np.clip(button[1]-.036+.015-(config.center_y_m+.09), 0., .14)
        data.ctrl[1] = np.clip(config.front_x_m-.085-button[0], 0., .65)
        mj.mj_step(model, data)
    mj.mj_forward(model, data)
    after = measure(model, data, config)
    assert (after['door_angle_rad'] > .5) == opens


@pytest.mark.parametrize('press_retention,extracts', [(False, False), (True, True)])
def test_free_cartridge_extraction_requires_contact_release_of_retention(press_retention, extracts):
    config = CabinetConfig()
    model = with_ram(config, 'retention')
    data = mj.MjData(model)
    # An already-open door is the initial condition of this isolated fixture test.
    data.qpos[model.joint('service_door_hinge').qposadr[0]] = 1.4
    if press_retention:
        data.ctrl[0] = .10
    step(model, data, .8)
    before = measure(model, data, config)
    if press_retention:
        assert before['retention_retraction_m'] > .03
        assert before['contact_normal_forces_n']['bench_ram_tip|service_retention_button'] > 0.
    data.xfrc_applied[model.body('service_old_cartridge').id, 0] = -4.
    step(model, data, .3)
    after = measure(model, data, config)
    displacement = before['old_cartridge_position_m'][0]-after['old_cartridge_position_m'][0]
    assert (displacement > .03) == extracts
    if not extracts:
        assert after['contact_normal_forces_n']['service_old_shell|service_retention_bar'] > 0.
    assert model.neq == 0
    assert model.nmocap == 0


def test_dimensions_mass_and_spring_resistance_reach_compiled_model_and_invalid_changes_are_rejected():
    config = CabinetConfig(cartridge_dimensions_m=(.19, .145, .11), cartridge_mass_kg=.8,
                           latch_stiffness_n_m=800., retention_stiffness_n_m=900.)
    model = compile_fixture(config)
    assert model.body('service_old_cartridge').mass[0] == pytest.approx(.8)
    np.testing.assert_allclose(model.geom('service_old_shell').size, [.095, .0725, .055])
    assert model.joint('service_latch_slide').stiffness[0] == 800.
    assert model.joint('service_retention_slide').stiffness[0] == 900.
    for values in ({'cartridge_dimensions_m':(.3, .15, .12)},
                   {'cartridge_dimensions_m':(.2, float('nan'), .12)},
                   {'latch_stiffness_n_m':-1.}, {'imaginary_restitution':.9}):
        with pytest.raises(ValidationError):
            CabinetConfig(**values)
    assert model.body('service_old_cartridge').mass[0] == pytest.approx(.8)


def test_cabinet_contact_friction_reaches_every_native_service_surface_and_contact():
    observed = []
    for friction in (.15, 1.3):
        model = compile_fixture(CabinetConfig(contact_friction=friction))
        data = mj.MjData(model)
        surfaces = [model.geom(index) for index in range(model.ngeom)
                    if (model.geom(index).name or '').startswith('service_')]
        assert len(surfaces) > 30
        assert all(geom.friction[0] == pytest.approx(friction) for geom in surfaces)
        step(model, data, .2)
        contacts = [contact for contact in data.contact[:data.ncon]
                    if {'service_old_shell', 'service_shelf'} ==
                    {model.geom(contact.geom1).name, model.geom(contact.geom2).name}]
        assert contacts
        observed.append(float(contacts[0].friction[0]))
    assert observed[0] == pytest.approx(.15)
    assert observed[1] == pytest.approx(1.3)


def test_full_native_fixture_state_restores_independently_with_contact_forces():
    config = CabinetConfig()
    model = with_ram(config, 'latch')
    data = mj.MjData(model)
    data.ctrl[0] = .09
    step(model, data, .2)
    state_type = mj.mjtState.mjSTATE_INTEGRATION
    state = np.empty(mj.mj_stateSize(model, state_type))
    mj.mj_getState(model, data, state, state_type)
    fork_model = with_ram(config, 'latch')
    fork = mj.MjData(fork_model)
    mj.mj_setState(fork_model, fork, state, state_type)
    mj.mj_forward(fork_model, fork)
    step(model, data, .1)
    step(fork_model, fork, .1)
    np.testing.assert_array_equal(data.qpos, fork.qpos)
    assert measure(model, data, config) == measure(fork_model, fork, config)
    fork.ctrl[0] = 0.
    step(fork_model, fork, .1)
    assert data.ctrl[0] == .09
    assert not np.array_equal(data.qpos, fork.qpos)
