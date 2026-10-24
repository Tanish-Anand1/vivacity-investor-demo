import xml.etree.ElementTree as ET

import mujoco as mj
import numpy as np
import pytest
from pydantic import ValidationError

from vivacity.physical_parameters import BoxPhysics, BOX_PARAMETER_MANIFEST, parameter_manifest


def compile_box(config):
    root = ET.fromstring('<mujoco><worldbody><geom name="floor" type="plane" size="2 2 .1"/></worldbody></mujoco>')
    body = ET.SubElement(root.find('worldbody'), 'body', name='box', pos=f'0 0 {config.dimensions_m[2]/2}')
    ET.SubElement(body, 'freejoint')
    ET.SubElement(body, 'geom', name='box', **config.mjcf_geom())
    if config.mjcf_inertial():
        ET.SubElement(body, 'inertial', **config.mjcf_inertial())
    model = mj.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'))
    data = mj.MjData(model)
    for _ in range(100):
        mj.mj_step(model, data)
    mj.mj_forward(model, data)
    return model, data


def test_every_editable_box_parameter_has_dependency_and_test():
    assert set(BOX_PARAMETER_MANIFEST) == set(BoxPhysics.model_fields)
    for definition in parameter_manifest()['parameters'].values():
        assert definition['dependency'] and definition['schema']
        assert definition['test'] in globals()


def test_box_mass_density_dimensions_and_inertia():
    original = BoxPhysics()
    enlarged = BoxPhysics(dimensions_m=(.36, .18, .16))
    dense = BoxPhysics(dimensions_m=(.36, .18, .16), mass_mode='density',
                       density_kg_m3=original.effective_mass/np.prod(original.dimensions_m))
    for config in (original, enlarged, dense):
        model, _ = compile_box(config)
        assert model.body('box').mass[0] == pytest.approx(config.effective_mass)
        np.testing.assert_allclose(model.geom('box').size, np.array(config.dimensions_m)/2)
        np.testing.assert_allclose(np.sort(model.body('box').inertia), np.sort(np.linalg.eigvalsh(config.inertia_matrix)))
    assert enlarged.effective_mass == original.effective_mass
    assert dense.effective_mass == pytest.approx(2*original.effective_mass)
    assert enlarged.inertia_matrix[1, 1] > original.inertia_matrix[1, 1]


def test_custom_inertia_validation_and_native_value():
    config = BoxPhysics(custom_inertia_kg_m2=(.002, .0021, .0025, .0001, .0002, .0001))
    model, _ = compile_box(config)
    np.testing.assert_allclose(np.sort(model.body('box').inertia), np.linalg.eigvalsh(config.inertia_matrix))
    for invalid in [(-.1, .1, .1, 0, 0, 0), (.1, .1, 1., 0, 0, 0),
                    (.1, .1, .1, .2, 0, 0), (.02, .03, .04, .002, .001, .003),
                    (float('nan'), .1, .1, 0, 0, 0)]:
        with pytest.raises(ValidationError):
            BoxPhysics(custom_inertia_kg_m2=invalid)


@pytest.mark.parametrize('values', [
    dict(sliding_friction=.2, torsional_friction_m=.002, rolling_friction_m=.0003,
         contact_time_constant_s=.01, contact_damping_ratio=.7),
    dict(sliding_friction=1.2, torsional_friction_m=.02, rolling_friction_m=.003,
         contact_time_constant_s=.04, contact_damping_ratio=1.5),
])
def test_native_contact_parameters(values):
    config = BoxPhysics(**values)
    model, data = compile_box(config)
    assert data.ncon > 0
    expected = [config.sliding_friction, config.sliding_friction,
                config.torsional_friction_m, config.rolling_friction_m, config.rolling_friction_m]
    for contact in data.contact[:data.ncon]:
        np.testing.assert_allclose(contact.friction, expected)
        np.testing.assert_allclose(contact.solref, [config.contact_time_constant_s, config.contact_damping_ratio])


def test_invalid_edit_leaves_prior_configuration_and_model_intact():
    original = BoxPhysics()
    model, _ = compile_box(original)
    mass = model.body_mass.copy()
    with pytest.raises(ValidationError):
        BoxPhysics.model_validate(original.model_dump() | {'dimensions_m': [-1, .2, .2]})
    assert original.dimensions_m == (.18, .18, .16)
    np.testing.assert_array_equal(model.body_mass, mass)


def _spin(axis, torsion, rolling):
    model = mj.MjModel.from_xml_string(f'''<mujoco><option timestep=".001"/>
      <worldbody><geom type="plane" size="2 2 .1"/>
      <body pos="0 0 .1"><freejoint/><geom type="sphere" size=".1" mass="1"
        priority="3" condim="6" friction=".001 {torsion} {rolling}"/></body>
      </worldbody></mujoco>''')
    data = mj.MjData(model)
    data.qvel[3+axis] = 5.
    for _ in range(400):
        mj.mj_step(model, data)
    return abs(data.qvel[3+axis])


def test_torsional_and_rolling_friction_change_angular_decay():
    spin_free = _spin(2, 0., 0.)
    spin_resisted = _spin(2, .02, 0.)
    roll_free = _spin(0, 0., 0.)
    roll_resisted = _spin(0, 0., .01)
    assert spin_free > 4. and spin_resisted < .2
    assert roll_free > 4. and roll_resisted < .2


def _impact(time_constant, damping):
    config = BoxPhysics(contact_time_constant_s=time_constant, contact_damping_ratio=damping)
    root = ET.fromstring('<mujoco><option timestep=".001"/><worldbody><geom type="plane" size="2 2 .1"/></worldbody></mujoco>')
    body = ET.SubElement(root.find('worldbody'), 'body', pos='0 0 .35')
    ET.SubElement(body, 'freejoint')
    ET.SubElement(body, 'geom', **config.mjcf_geom())
    model = mj.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'))
    data = mj.MjData(model)
    penetration, rebound = 0., 0.
    touched = False
    for _ in range(600):
        mj.mj_step(model, data)
        if data.ncon:
            touched = True
        penetration = max(penetration, .08-float(data.qpos[2]))
        if touched:
            rebound = max(rebound, float(data.qvel[2]))
    return penetration, rebound


def test_compliance_and_damping_change_measured_impact():
    stiff, _ = _impact(.004, 1.)
    soft, _ = _impact(.06, 1.)
    _, low_damping = _impact(.02, .2)
    _, high_damping = _impact(.02, 2.)
    assert soft > stiff*2
    assert low_damping > high_damping+.2
