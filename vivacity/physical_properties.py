"""Explicit illustrative material presets and native MuJoCo scene settings.

Mass remains an independent user input. Densities are reference metadata, not
an assertion that a hollow/test object has the density of a solid material.
"""
from copy import deepcopy
import numpy as np
import mujoco as mj

MATERIALS = {
    'steel': dict(name='Steel', density_kg_m3=7850., sliding=.45, torsional=.005, rolling=.0001),
    'aluminium': dict(name='Aluminium', density_kg_m3=2700., sliding=.4, torsional=.004, rolling=.0001),
    'rubber': dict(name='Rubber', density_kg_m3=1100., sliding=1.2, torsional=.02, rolling=.002),
    'wood': dict(name='Wood', density_kg_m3=650., sliding=.6, torsional=.008, rolling=.0005),
    'plastic': dict(name='Plastic', density_kg_m3=1050., sliding=.35, torsional=.004, rolling=.0002),
    'glass': dict(name='Glass', density_kg_m3=2500., sliding=.2, torsional=.003, rolling=.0001),
    'concrete': dict(name='Concrete', density_kg_m3=2400., sliding=.8, torsional=.01, rolling=.001),
    'cardboard': dict(name='Cardboard', density_kg_m3=700., sliding=.55, torsional=.008, rolling=.0005),
}


def registry():
    return {'schema_version': 'vivacity.materials/1.0', 'materials': deepcopy(MATERIALS),
            'scope': 'Illustrative contact presets, not measured/calibrated material pairs. Mass is an independent input. MuJoCo uses one Coulomb sliding coefficient, plus torsional and rolling friction.'}


def configure_xml(root, config):
    """Before compilation/hash; never mutate a shared compiled MjModel."""
    physics = config.get('physics') or {}
    option = root.find('option')
    option.set('gravity', '0 0 '+str(-physics.get('gravity_m_s2', 9.81)))
    option.set('density', str(physics.get('air_density_kg_m3', 0.)))
    option.set('viscosity', str(physics.get('air_viscosity_pa_s', 0.)))
    option.set('wind', ' '.join(map(str, physics.get('wind_velocity_m_s', [0., 0., 0.]))))
    # Air is disabled by default, preserving the previously verified controller.
    if physics.get('air_density_kg_m3', 0.) or physics.get('air_viscosity_pa_s', 0.):
        option.set('integrator', 'implicitfast')
    cube = root.find(".//geom[@name='cube']")
    table = root.find(".//geom[@name='table']")
    if table is not None:
        table_friction = config.get('table_friction', 1.)
        table.set('friction', f"{table_friction} .005 .0001")
        if table_friction != 1.:
            # The pick-place cube has contact priority 1. MuJoCo otherwise
            # ignores the table coefficient entirely in cube/table contacts.
            table.set('priority', '2')
    if cube is not None:
        material = MATERIALS.get(config.get('object_material'))
        if material:
            cube.set('friction', f"{material['sliding']} {material['torsional']} {material['rolling']}")
            cube.set('condim', '6')
        if 'contact_damping_ratio' in physics:
            cube.set('solref', '.004 '+str(physics['contact_damping_ratio']))
        if physics.get('air_density_kg_m3', 0.) or physics.get('air_viscosity_pa_s', 0.):
            cube.set('fluidshape', 'ellipsoid')
            cube.set('fluidcoef', f"{physics.get('blunt_drag_coefficient', .5)} .25 1.5 0 0")
    scale = physics.get('gripper_force_scale', 1.)
    if scale != 1.:
        # Both native and adapted arms use this same tendon actuator fixture.
        for actuator in root.findall('actuator/*'):
            if actuator.get('tendon') == 'split':
                actuator.set('forcelimited', 'true')
                actuator.set('forcerange', f'{-100.*scale} {100.*scale}')


def initialize_inputs(model, data, config):
    if config.get('task') == 'pick_place':
        settings = config.get('physics') or {}
        data.xfrc_applied[model.body('target').id] = [*settings.get('object_force_n', [0., 0., 0.]),
                                                   *settings.get('object_torque_nm', [0., 0., 0.])]


def inspect(world, arm_dof):
    """Bounded real measurements. Force solutions precede integration by one dt.

    Kinematics/computation of velocities does not alter integration state or
    warmstart. Never run mj_forward merely to produce a UI frame.
    """
    m, d = world.model, world.data
    mj.mj_comPos(m, d)
    mj.mj_comVel(m, d)
    bid = m.body('target').id
    velocity = np.zeros(6)
    mj.mj_objectVelocity(m, d, mj.mjtObj.mjOBJ_BODY, bid, velocity, 0)
    contacts = []
    for i, contact in enumerate(d.contact[:d.ncon]):
        if contact.dist > .001:
            continue
        force = np.zeros(6)
        mj.mj_contactForce(m, d, i, force)
        # Contact frame axes are rows. Vector is force on geom2, world axes.
        contacts.append({'position_m': contact.pos.tolist(),
                         'force_on_geom2_n': (contact.frame.reshape(3, 3).T @ force[:3]).tolist(),
                         'normal_force_n': float(force[0]),
                         'geoms': [m.geom(int(g)).name or f'geom_{g}' for g in (contact.geom1, contact.geom2)]})
    cube = m.geom('cube').id
    angular_local = d.ximat[bid].reshape(3,3).T @ velocity[:3]
    kinetic = .5*float(m.body_mass[bid])*float(velocity[3:] @ velocity[3:]) + .5*float(angular_local @ (m.body_inertia[bid]*angular_local))
    potential = -float(m.body_mass[bid])*float(m.opt.gravity @ d.xipos[bid])
    return {'schema_version': 'vivacity.inspection/1.0', 'state_time_s': float(d.time),
            'force_solution_time_s': max(0., float(d.time)-float(m.opt.timestep)),
            'object': {'position_m': d.xpos[bid].tolist(), 'center_of_mass_m': d.xipos[bid].tolist(),
                       'mass_kg': float(m.body_mass[bid]), 'principal_inertia_kg_m2': m.body_inertia[bid].tolist(),
                       'principal_inertia_rotation_matrix': d.ximat[bid].reshape(3, 3).tolist(),
                       'linear_velocity_m_s': velocity[3:].tolist(), 'angular_velocity_rad_s': velocity[:3].tolist(),
                       'applied_force_n': d.xfrc_applied[bid, :3].tolist(), 'applied_torque_nm': d.xfrc_applied[bid, 3:].tolist(),
                       'friction': m.geom_friction[cube].tolist(), 'contact_dimension': int(m.geom_condim[cube]),
                       'material': world.config.get('object_material', 'custom'),
                       'kinetic_energy_j': kinetic, 'gravitational_potential_energy_j': potential,
                       'energy_scope': 'Object mechanical energy; potential datum is world origin. Not robot motor energy or conserved energy in contact/air/actuated motion.',
                       'projected_box_areas_m2': [float(4*m.geom_size[cube, j]*m.geom_size[cube, k]) for j, k in ((1,2),(0,2),(0,1))]},
            'robot': {'joint_positions': d.qpos[:arm_dof].tolist(), 'joint_velocities': d.qvel[:arm_dof].tolist(),
                      'actuator_generalized_force': d.qfrc_actuator[:arm_dof].tolist(),
                      'gravity_compensation': 'native body gravcomp=1 in pickup adapters'},
            'environment': {'gravity_m_s2': m.opt.gravity.tolist(), 'air_density_kg_m3': float(m.opt.density),
                            'wind_velocity_m_s': m.opt.wind.tolist(), 'solver_iterations': int(m.opt.iterations),
                            'timestep_s': float(m.opt.timestep), 'engine_version': mj.__version__},
            'contacts': contacts[:48], 'contacts_total': len(contacts), 'contacts_truncated': len(contacts)>48,
            'scope': 'Current MuJoCo kinematics; force/contact solution is from the preceding integrated step. Native ellipsoid air model is not CFD. No electrical energy or real-world calibration.'}
