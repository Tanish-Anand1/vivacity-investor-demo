"""Investor-facing scenario catalog. Availability is a server-side contract.

Worlds are simplified, physical workcells, not validated factory digital twins.
References for unsupported hardware/tasks cannot create a runnable world.
"""
from copy import deepcopy
from typing import Literal
from pydantic import Field
from .schemas import Schema, CreateWorld


class TemplateOption(Schema):
    id: str
    name: str
    status: Literal['available','experimental','reference']
    technical: str
    business: str
    scope: str


class TemplateCatalog(Schema):
    schema_version: Literal['vivacity.templates/1.0'] = 'vivacity.templates/1.0'
    arms: list[TemplateOption]
    worlds: list[TemplateOption]
    tasks: list[TemplateOption]
    contract: list[str]


class TemplateSelection(Schema):
    arm: Literal['panda', 'ur5e', 'iiwa', 'scara', 'dual_arm'] = 'panda'
    world: Literal['manufacturing', 'warehouse', 'inspection', 'cluttered', 'textile'] = 'manufacturing'
    task: Literal['pick_place', 'obstacle_transfer', 'cloth_fold', 'machine_tending', 'assembly'] = 'pick_place'
    seed: int = Field(7, ge=0, le=2**32-1)


def option(id, name, status, technical, business, scope):
    return dict(id=id, name=name, status=status, technical=technical, business=business, scope=scope)


CATALOG = {
    'schema_version': 'vivacity.templates/1.0',
    'arms': [
        option('panda', 'Franka Panda', 'available', '7 joint actuators + parallel fingers', 'Flexible manipulation for automation integrators.', 'Menagerie MJCF; MuJoCo joint dynamics and contact.'),
        option('ur5e', 'UR5e collaborative arm', 'reference', '6-axis arm', 'Shared workstations and machine loading.', 'Requires a robot model, gripper and tested controller adapter.'),
        option('iiwa', 'KUKA iiwa', 'reference', '7-axis industrial arm', 'Flexible industrial cells and assembly research.', 'Requires a robot model, gripper and tested controller adapter.'),
        option('scara', 'SCARA arm', 'reference', 'Planar assembly arm', 'Repeated handling on electronics production lines.', 'Requires a SCARA dynamics model and task controller.'),
        option('dual_arm', 'Dual-arm system', 'reference', 'Two coordinated manipulators', 'Two-handed handling and garment automation.', 'Requires two-arm collision planning and coordinated control.'),
    ],
    'worlds': [
        option('manufacturing', 'Industrial workstation', 'available', 'Rigid table, dynamic part, gravity and friction', 'Evaluate part transfer before a physical cell trial.', 'Simplified workbench, not a complete factory digital twin.'),
        option('warehouse', 'Warehouse packing station', 'available', 'Light parcel surrogate on a fixed packing bench', 'Compare handling alternatives for fulfillment automation.', 'Fixed bench; no moving conveyor, bins or warehouse traffic.'),
        option('inspection', 'Inspection bench', 'available', 'Small, light component with measured final placement', 'Test part presentation for inspection integrators.', 'Physical handling only; no camera inspection or defect detection.'),
        option('cluttered', 'Constrained industrial cell', 'available', 'Fixed collision fixture beside the handling area', 'Test path feasibility around existing equipment.', 'A rectangular equipment surrogate; real collision geometry.'),
        option('textile', 'Textile folding station', 'experimental', 'Panda folding fixture, 7×7 MuJoCo flex sheet', 'Explore fixture-based folding for textile automation.', 'Pre-attached bar and fixed hinge; no autonomous garment grasp.'),
    ],
    'tasks': [
        option('pick_place', 'Pick & place', 'available', 'Grasp → lift → transport → release → settle', 'Measure placement feasibility and execution duration.', 'Success requires actual finger contacts, retention and supported placement.'),
        option('obstacle_transfer', 'Obstacle-aware transfer', 'available', 'Pose IK, joint-space RRT and contact validation', 'Compare routes around equipment before moving hardware.', 'Uses the same physical pickup controller with an enabled collision fixture.'),
        option('cloth_fold', 'Cloth folding', 'experimental', 'Joint-actuated fixture motion, flex contact and release', 'Evaluate folding-fixture alternatives.', 'Constrained single fold; autonomous cloth pickup is not implemented.'),
        option('machine_tending', 'Machine tending', 'reference', 'Load, unload and synchronize with a machine', 'Potential application for production automation.', 'Needs a machine model, interlocks and a task controller.'),
        option('assembly', 'Precision assembly', 'reference', 'Contact-guided alignment and insertion', 'Potential application for assembly integrators.', 'Needs insertion geometry, force control and assembly validation.'),
    ],
    'contract': ['Observe', 'Snapshot', 'Fork', 'Apply action', 'Simulate', 'Evaluate', 'Commit', 'Replay'],
}


def catalog():
    result=deepcopy(CATALOG)
    for arm in result['arms']:
        arm['status']='available'
        arm['scope']='Actuated MuJoCo model, modeled parallel gripper, independent state and measured dynamics. Dual Panda uses its primary arm; SCARA is an analytical educational model.'
    for task in result['tasks']:
        if task['id'] in ('machine_tending','assembly'):
            task['status']='available'
            task['scope']='Single-part fixture seating or loading a modeled bay with an actuated door. No fastening, production machining or hardware interlocks.'
    return result


def resolve(selection: TemplateSelection) -> CreateWorld:
    if selection.task == 'cloth_fold':
        if selection.arm!='panda':raise ValueError('The textile fixture currently uses Panda.')
        if selection.world != 'textile':
            raise ValueError('Cloth folding requires the textile folding fixture.')
        return CreateWorld(backend='cloth', seed=selection.seed, config={'side_length': .4, 'mass': .08, 'friction': .6})
    if selection.world == 'textile':
        raise ValueError('The textile station currently supports the constrained cloth fold only.')
    config = dict(task='pick_place', robot_model=selection.arm,
                  physical_operation=selection.task if selection.task in ('assembly','machine_tending') else 'pick_place',obstacle_enabled=False,
                  obstacle_position=[.75, -.4, .22])
    presets = {
        'manufacturing': {},
        'warehouse': dict(cube_mass=.04, cube_friction=.9),
        'inspection': dict(cube_mass=.02, cube_friction=1.2, cube_half_size=.022,
                           cube_position=[.5, -.15, .023], placement_position=[.5, .18, .023]),
        'cluttered': dict(obstacle_enabled=True, obstacle_position=[.75, -.4, .18],
                          obstacle_size=[.04, .08, .18], cube_position=[.5, -.18, .026],
                          placement_position=[.5, .24, .026]),
    }
    config.update(presets[selection.world])
    if selection.task == 'obstacle_transfer':
        config.update(obstacle_enabled=True, obstacle_position=[.75, -.4, .22], obstacle_size=[.055, .13, .22])
    return CreateWorld(backend='mujoco', seed=selection.seed, config=config)
