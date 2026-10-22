"""Typed, bounded MuJoCo workcell editing; all writes rebuild the native model."""
from copy import deepcopy
import math

from .schemas import RoboticsConfig


def _property(key, path, label, value, minimum=None, maximum=None, *,
              unit='', meaning='', dependency='', effect='', data_type='number',
              choices=(), editable=True, step=None):
    return {'key': key, 'path': path, 'label': label, 'value': value,
            'minimum': minimum, 'maximum': maximum, 'step': step,
            'unit': unit, 'meaning': meaning, 'data_type': data_type,
            'choices': list(choices), 'editable': editable,
            'requires_reset': True, 'dependency': dependency,
            'physics_effect': effect}


def _axes(prefix, path, values, label, limits, effect, *, unit='m'):
    return [_property(f'{prefix}_{axis}', [*path, i], f'{label} {axis.upper()}',
                      values[i], limits[i][0], limits[i][1], unit=unit,
                      meaning=f'{label} along the world {axis.upper()} axis.',
                      dependency='Rebuilds the MuJoCo collision model and invalidates prior plans.',
                      effect=effect, step=.001)
            for i, axis in enumerate('xyz')]


def _supported(world):
    c = world['config']
    return (world['backend'] == 'mujoco' and c.get('task') == 'pick_place'
            and c.get('scene_profile') == 'workcell')


def describe_world(world, observation=None):
    if not _supported(world):
        return {'schema_version': 'vivacity.world_editor/1.0',
                'world_id': world['id'], 'revision': world['revision'],
                'entities': [], 'scope': 'Physical editing currently supports the MuJoCo pick-and-place workcell only. This model does not implement humanoid transport, packing, or arbitrary imported geometry.'}
    c = world['config']
    half = c.get('cube_half_sizes') or [c.get('cube_half_size', .025)] * 3
    object_properties = (
        _axes('position', ['cube_position'], c['cube_position'], 'Pickup center',
              [(-.27, 1.07), (-.62, .62), (.02, .032)],
              'Moves the free body initial pose; the controller replans from this pose.')[:2]
        + _axes('half_size', ['cube_half_sizes'], half, 'Half-size',
                [(.02, .03)] * 3,
                'Compiles a new collision box and native inertia tensor from mass and dimensions.')
        + [_property('mass', ['cube_mass'], 'Mass', c['cube_mass'], .02,
                     .30 if c.get('physical_operation') == 'assembly' else .15,
                     unit='kg', meaning='Explicit rigid-body mass; editing it clears density mode.',
                     dependency='Clears density mode. MuJoCo recomputes inertia; grasp and payload feasibility change.',
                     effect='Changes gravity, contact response, inertia, and measured grasp outcome.', step=.001),
           _property('density', ['cube_density_kg_m3'], 'Solid density',
                     c.get('cube_density_kg_m3'), 50., 5000., unit='kg/m³',
                     meaning='Optional homogeneous solid-box density. Mass = density × 8 × product of half-sizes.',
                     dependency='Enables density mode; changing dimensions then recomputes mass and inertia. Invalid implied mass is rejected.',
                     effect='Changes native body mass and inertia via the compiled box.', step=1.),
           _property('friction', ['cube_friction'], 'Sliding friction', c['cube_friction'], .05, 1.5,
                     meaning='MuJoCo sliding coefficient for the custom object material.',
                     dependency='Sets material to custom; recalculates contact parameters on reset.',
                     effect='Changes finger and surface contact forces.', step=.01),
           _property('material', ['object_material'], 'Contact preset', c['object_material'],
                     data_type='choice', choices=('custom','steel','aluminium','rubber','wood','plastic','glass','concrete','cardboard'),
                     meaning='Illustrative MuJoCo friction preset. Density and mass remain independent.',
                     dependency='Replaces sliding, torsional and rolling contact coefficients; does not override mass.',
                     effect='Changes native geom friction/contact dimension.'),
           _property('inertia_x', [], 'Measured inertia X',
                     ((observation or {}).get('inspection') or {}).get('object', {}).get('principal_inertia_kg_m2', [None]*3)[0],
                     unit='kg·m²', meaning='Native principal body inertia from the compiled MuJoCo model.',
                     dependency='Computed by MuJoCo from shape and mass.', effect='Dynamics state.', editable=False)]
    )
    obstacle = (
        [_property('enabled', ['obstacle_enabled'], 'Collision enabled', c['obstacle_enabled'],
                   data_type='boolean', meaning='Obstacle participates in MuJoCo contacts when enabled.',
                   dependency='Rebuilds collision masks.', effect='Changes route feasibility.')]
        + _axes('position', ['obstacle_position'], c['obstacle_position'], 'Center',
                [(.15,.8),(-.5,.5),(.05,.6)], 'Moves the collision obstacle and invalidates planned routes.')
        + _axes('half_size', ['obstacle_size'], c['obstacle_size'], 'Half-size',
                [(.01,.4)]*3, 'Rebuilds the obstacle collision box and route clearance.')
    )
    surface = [_property('friction', ['table_friction'], 'Sliding friction', c.get('table_friction', 1.), .05, 2.,
                         meaning='MuJoCo sliding coefficient of the supporting table geom.',
                         dependency='Recompiles the table contact geom.', effect='Changes object/table contact response.', step=.01)]
    robot = [_property('gripper_force', ['physics','gripper_force_scale'], 'Gripper force scale',
                       c['physics']['gripper_force_scale'], .05, 1.,
                       meaning='Scales the native finger actuator force limit.',
                       dependency='Recompiles actuator force range and invalidates grasp outcomes.',
                       effect='Changes contact force and object retention.', step=.01)]
    environment = [_property('gravity', ['physics','gravity_m_s2'], 'Downward gravity',
                             c['physics']['gravity_m_s2'], 0., 20., unit='m/s²',
                             meaning='Magnitude of world gravity along negative Z.',
                             dependency='Recompiles MuJoCo model and resets the initial state.',
                             effect='Changes free-body acceleration, weight, and balance.', step=.01)]
    entities = [
        {'id':'object','name':'Pickup object','kind':'object','properties':object_properties},
        {'id':'obstacle','name':'Route obstacle','kind':'obstacle','properties':obstacle},
        {'id':'surface','name':'Worktable surface','kind':'surface','properties':surface},
        {'id':'robot','name':'Robot and gripper','kind':'robot','properties':robot},
        {'id':'environment','name':'Environment','kind':'environment','properties':environment},
    ]
    for i, geom in enumerate(c.get('scene_geometries', [])):
        path = ['scene_geometries', i]
        size_limits = [(.005, .4)] * 3
        size = _axes('half_size', [*path,'size'], geom['size'], 'Half-size',
                     size_limits, 'Changes the native static collision shape and contact positions.')
        if geom['type'] == 'cylinder':
            size = [size[0], size[1]]
            size[0]['label'] = 'Radius'; size[1]['label'] = 'Half-height'
        q = geom.get('quaternion_wxyz', [1.,0.,0.,0.])
        yaw = math.degrees(math.atan2(2*(q[0]*q[3]+q[1]*q[2]), 1-2*(q[2]*q[2]+q[3]*q[3])))
        properties = (
            [_property('shape', [*path,'type'], 'Collision shape', geom['type'],
                       data_type='choice', choices=('box','cylinder'),
                       meaning='Supported static primitive in the MuJoCo scene.',
                       dependency='Recompiles the geom.', effect='Changes collision shape.')]
            + _axes('position', [*path,'position'], geom['position'], 'Center',
                    [(-.3,1.1),(-.65,.65),(.005,.8)], 'Moves the static collision geom and invalidates routes.')
            + size
            + [_property('yaw_deg', [*path,'quaternion_wxyz'], 'Yaw about Z', yaw, -180., 180., unit='°',
                         meaning='World-Z orientation. Editing yaw replaces other rotation components.',
                         dependency='Compiles a new unit quaternion and invalidates prior plans.',
                         effect='Rotates actual MuJoCo collision geometry.', step=1.),
               _property('friction', [*path,'friction'], 'Sliding friction', geom['friction'], .05, 2.,
                         meaning='MuJoCo sliding coefficient of this static collision geom.',
                         dependency='Recompiles the geom contact parameter.',
                         effect='Changes contacts with the object and robot.', step=.01)]
        )
        entities.append({'id':'geometry:'+geom['name'], 'name':geom['name'],
                         'kind':'obstacle', 'properties':properties})
    return {'schema_version':'vivacity.world_editor/1.0', 'world_id':world['id'],
            'revision':world['revision'], 'entities':entities,
            'scope':'MuJoCo pick-and-place workcell. Static primitives, cube mass/density, table and object friction, gravity and gripper force are executable. Articulated robot topology, independent static/dynamic friction, adhesion, and arbitrary rigid-body creation are unsupported.'}


def apply_change(config, prop, value):
    data_type = prop['data_type']
    if data_type == 'number':
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('a finite numeric value is required')
        if (prop['minimum'] is not None and value < prop['minimum']) or (prop['maximum'] is not None and value > prop['maximum']):
            raise ValueError(f"{prop['label']} is outside its supported range")
    elif data_type == 'boolean':
        if not isinstance(value, bool):
            raise ValueError('a boolean value is required')
    elif value not in prop['choices']:
        raise ValueError('unsupported property choice')
    changed = deepcopy(config)
    path = prop['path']
    parent = changed
    if prop['key'].startswith('half_size_') and path[0] == 'cube_half_sizes' and parent['cube_half_sizes'] is None:
        parent['cube_half_sizes'] = [parent['cube_half_size']] * 3
    for key in path[:-1]:
        parent = parent[key]
    if prop['key'] == 'yaw_deg':
        angle = math.radians(value) / 2
        value = [math.cos(angle), 0., 0., math.sin(angle)]
    parent[path[-1]] = value
    if path[0] == 'cube_half_sizes':
        z = changed['cube_half_sizes'][2]
        changed['cube_half_size'] = z
        changed['cube_position'][2] = z + .001
        changed['placement_position'][2] = (3*z if changed.get('physical_operation') == 'stacking' else z) + .001
    if path[0] == 'cube_mass':
        changed['cube_density_kg_m3'] = None
    if path[0] == 'cube_friction':
        changed['object_material'] = 'custom'
    return RoboticsConfig.model_validate(changed)


def geometry_action(config, action, entity_id=None, geometry_type='box'):
    changed = deepcopy(config)
    geoms = changed['scene_geometries']
    if action == 'add':
        if len(geoms) >= 24:
            raise ValueError('scene supports at most 24 additional collision geoms')
        names = {g['name'] for g in geoms}
        stem = 'block' if geometry_type == 'box' else 'cylinder'
        index = next(i for i in range(1, 26) if f'{stem}_{i}' not in names)
        name = f'{stem}_{index}'
        geoms.append({'name':name,'type':geometry_type,'position':[.7,0.,.08],
                      'size':[.05,.05,.08], 'quaternion_wxyz':[1.,0.,0.,0.],
                      'rgba':[.46,.53,.50,1.], 'friction':.8})
    else:
        if not entity_id or not entity_id.startswith('geometry:'):
            raise ValueError('select an editable scene primitive')
        name = entity_id.split(':',1)[1]
        source = next((g for g in geoms if g['name'] == name), None)
        if source is None:
            raise ValueError('scene primitive no longer exists')
        if action == 'delete':
            geoms.remove(source)
            return RoboticsConfig.model_validate(changed), None
        if len(geoms) >= 24:
            raise ValueError('scene supports at most 24 additional collision geoms')
        names = {g['name'] for g in geoms}
        suffix = next(i for i in range(1, 26) if f'{name}_{i}' not in names)
        name = f'{name}_{suffix}'
        duplicate = deepcopy(source)
        duplicate['name'] = name
        x = duplicate['position'][0]
        duplicate['position'][0] = x + .12 if x + .12 <= 1.1 else x - .12
        geoms.append(duplicate)
    return RoboticsConfig.model_validate(changed), 'geometry:'+name
