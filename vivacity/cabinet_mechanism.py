"""Passive cabinet fixture for the Apollo service task under development.

All joints here are unactuated. The latch and retention bar have physical spring
returns; their collision geometry blocks motion until displaced. Cartridges are
free bodies and keep their identities. This module does not implement a robot
controller or claim that Apollo can complete the service sequence.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import mujoco as mj
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CabinetConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    front_x_m: float = Field(default=.60, ge=.5, le=1.2)
    center_y_m: float = Field(default=0., ge=-.3, le=.3)
    cartridge_dimensions_m: tuple[float, float, float] = (.20, .15, .12)
    cartridge_mass_kg: float = Field(default=.35, ge=.05, le=2.)
    latch_stiffness_n_m: float = Field(default=300., ge=50., le=4000.)
    retention_stiffness_n_m: float = Field(default=500., ge=50., le=4000.)
    contact_friction: float = Field(default=.6, ge=.05, le=1.5)
    old_tray_surface_height_m: float = Field(default=.99, ge=.75, le=1.05)
    replacement_tray_surface_height_m: float = Field(default=.99, ge=.75, le=1.05)

    @model_validator(mode='after')
    def fits_fixed_guides(self):
        x, y, z = self.cartridge_dimensions_m
        if not (.18 <= x <= .205 and .14 <= y <= .151 and .10 <= z <= .125):
            raise ValueError('cartridge dimensions exceed the declared cabinet guide envelope')
        return self


def _values(values):
    return ' '.join(map(str, values))


def _box(parent, name, pos, half, *, mass=None, rgba='.30 .34 .35 1', friction=.6):
    attributes = dict(name=name, type='box', pos=_values(pos), size=_values(half),
        rgba=rgba, contype='1', conaffinity='1', condim='6',
        friction=f'{friction} .002 .0001', solref='.004 1', margin='0')
    if mass is not None:
        attributes['mass'] = str(mass)
    return ET.SubElement(parent, 'geom', **attributes)


def append_cabinet(root: ET.Element, config: CabinetConfig):
    """Append globally named bodies to a scene before compilation.

    The model's default geom/joint classes are deliberately overridden for all
    physical fixture properties, so Apollo's disabled-contact defaults cannot
    silently turn this into visual scenery.
    """
    world = root.find('worldbody')
    if world is None:
        raise ValueError('MJCF worldbody is required')
    if root.find(".//*[@name='service_cabinet']") is not None:
        raise ValueError('cabinet fixture already present')
    x, y = config.front_x_m, config.center_y_m
    cabinet = ET.SubElement(world, 'body', name='service_cabinet', pos=_values((x, y, 1.10)))
    for name, pos, half in (
        ('bottom', (.22, 0, -.31), (.22, .30, .02)),
        ('top', (.22, 0, .31), (.22, .30, .02)),
        ('back', (.43, 0, 0), (.01, .30, .29)),
        ('left', (.22, .29, 0), (.22, .01, .29)),
        # The strike pocket and retention slot are real gaps in the geometry.
        ('right_bottom', (.22, -.29, -.16), (.22, .01, .13)),
        ('right_top', (.22, -.29, .16), (.22, .01, .13)),
        ('right_pocket_back', (.245, -.29, 0), (.195, .01, .03)),
        ('shelf', (.275, 0, -.12), (.145, .25, .01)),
        ('shelf_front_left', (.085, .16, -.12), (.045, .09, .01)),
        ('shelf_front_right', (.085, -.16, -.12), (.045, .09, .01)),
        ('rail_left', (.21, .083, -.035), (.11, .006, .05)),
        ('rail_right', (.21, -.083, -.035), (.11, .006, .05)),
        ('backstop', (.315, 0, -.04), (.005, .077, .06)),
        ('strike', (-.012, -.29, 0), (.012, .022, .018)),
    ):
        _box(cabinet, 'service_'+name, pos, half, friction=config.contact_friction)
    # Visible fixed supports explain the fixture's world anchoring. Their real
    # collision surfaces also prevent treating the space below it as empty.
    for ix,offset_x in enumerate((.06,.38)):
        for iy,offset_y in enumerate((-.24,.24)):
            _box(cabinet,f'service_cabinet_leg_{ix}_{iy}',
                 (offset_x,offset_y,-.715),(.025,.025,.385))

    door = ET.SubElement(cabinet, 'body', name='service_door', pos='0 .28 0')
    ET.SubElement(door, 'joint', name='service_door_hinge', type='hinge', axis='0 0 -1',
        limited='true', range='0 1.7', damping='.4', stiffness='0', armature='.002')
    _box(door, 'service_door_panel', (0, -.25, 0), (.012, .25, .285), mass=1.8)
    _box(door, 'service_door_handle', (-.060, -.46, 0), (.016, .06, .014), mass=.12,
         rgba='.75 .52 .20 1')
    for offset in (-.045, .045):
        _box(door, f'service_handle_mount_{offset}', (-.032, -.46+offset, 0),
             (.028, .010, .014), mass=.025)
    latch = ET.SubElement(door, 'body', name='service_latch', pos='0 -.535 0')
    ET.SubElement(latch, 'joint', name='service_latch_slide', type='slide', axis='0 1 0',
        limited='true', range='0 .055', damping='3', stiffness=str(config.latch_stiffness_n_m),
        springref='0', armature='.005')
    _box(latch, 'service_latch_bolt', (.018, -.02, 0), (.015, .025, .012), mass=.06,
         rgba='.77 .51 .19 1')
    _box(latch, 'service_latch_link', (-.045, 0, .0325), (.010, .010, .0325), mass=.02)
    # A visible rigid crossbar lets the left hand release the latch while the
    # right hand holds the handle. No hidden actuator or logical unlock exists.
    _box(latch, 'service_latch_crossbar', (-.023, .20, .065), (.006, .20, .010), mass=.10)
    for end in (0., .40):
        # The left button stands clear of the broad crossbar so a real finger
        # can surround it without entering that bar during wrist rotation.
        center_x, half_x = (-.054,.037) if end==.40 else (-.034,.017)
        _box(latch, f'service_latch_crossbar_link_{end}', (center_x, end, .065),
             (half_x, .010, .010), mass=.01)
    _box(latch, 'service_latch_button', (-.085, .40, .065), (.018, .018, .018), mass=.04,
         rgba='.77 .51 .19 1')

    retention = ET.SubElement(cabinet, 'body', name='service_retention', pos='.087 0 -.096')
    ET.SubElement(retention, 'joint', name='service_retention_slide', type='slide', axis='0 0 -1',
        limited='true', range='0 .050', damping='3', stiffness=str(config.retention_stiffness_n_m),
        springref='0', armature='.005')
    _box(retention, 'service_retention_bar', (0, 0, 0), (.008, .060, .012), mass=.08,
         rgba='.77 .51 .19 1')
    _box(retention, 'service_retention_button', (-.035, 0, 0), (.027, .022, .010), mass=.03,
         rgba='.77 .51 .19 1')

    for name, center in (('old', (x-.22, y+.45)), ('replacement', (x-.22, y-.45))):
        tray_top = getattr(config, f'{name}_tray_surface_height_m')
        pedestal_half_height = (tray_top-.03)/2
        _box(world,f'service_{name}_tray_pedestal',(*center,pedestal_half_height),
             (.035,.035,pedestal_half_height))
        _box(world,f'service_{name}_tray_foot',(*center,.015),(.15,.13,.015))
        _box(world, f'service_{name}_tray', (*center, tray_top-.015), (.15, .13, .015),
             rgba='.40 .42 .42 1', friction=config.contact_friction)
        # Physical side walls retain a released cartridge, not an invisible region.
        for sign in (-1, 1):
            _box(world, f'service_{name}_tray_wall_{sign}',
                 (center[0], center[1]+sign*.135, tray_top+.03), (.15, .005, .03))
    half = np.asarray(config.cartridge_dimensions_m)/2
    for identity, position in (
        ('old', (x+.20, y, .99+half[2])),
        ('replacement', (x-.22, y-.45, config.replacement_tray_surface_height_m+half[2])),
    ):
        body = ET.SubElement(world, 'body', name=f'service_{identity}_cartridge', pos=_values(position))
        ET.SubElement(body, 'freejoint', name=f'service_{identity}_free')
        _box(body, f'service_{identity}_shell', (0, 0, 0), half,
             mass=config.cartridge_mass_kg, rgba='.50 .38 .21 1' if identity == 'old' else '.28 .52 .57 1',
             friction=config.contact_friction)
    # All fixture and cartridge contact surfaces share the exposed cabinet
    # friction setting. Tool-pad friction is a separate gripper parameter.
    for geom in root.findall('.//geom'):
        if (geom.get('name') or '').startswith('service_'):
            geom.set('friction', f'{config.contact_friction} .002 .0001')
    return cabinet


def fixture_tree(config: CabinetConfig):
    root = ET.Element('mujoco', model='vivacity_passive_cabinet_v1')
    ET.SubElement(root, 'compiler', angle='radian')
    ET.SubElement(root, 'option', timestep='.001', integrator='implicitfast', cone='elliptic',
                  iterations='80', gravity='0 0 -9.81')
    world = ET.SubElement(root, 'worldbody')
    ET.SubElement(world, 'light', pos='0 -2 3')
    ET.SubElement(world, 'geom', name='floor', type='plane', size='3 3 .05', rgba='.22 .24 .24 1')
    append_cabinet(root, config)
    return root


def compile_fixture(config: CabinetConfig):
    return mj.MjModel.from_xml_string(ET.tostring(fixture_tree(config), encoding='unicode'))


def measure(model, data, config: CabinetConfig):
    """Mechanism-only measurements. Robot stability and service history are separate."""
    joint = lambda name: float(data.qpos[int(model.joint(name).qposadr[0])])
    old = data.body('service_old_cartridge').xpos.copy()
    new = data.body('service_replacement_cartridge').xpos.copy()
    seated = np.array([config.front_x_m+.20, config.center_y_m, .99+config.cartridge_dimensions_m[2]/2])
    goal_tray = np.array([config.front_x_m-.22, config.center_y_m+.45,
                         config.old_tray_surface_height_m+config.cartridge_dimensions_m[2]/2])
    rotation = data.body('service_replacement_cartridge').xmat.reshape(3, 3)
    angular_error = float(np.arccos(np.clip((np.trace(rotation)-1)/2, -1, 1)))
    contacts = {}
    for index, contact in enumerate(data.contact[:data.ncon]):
        if contact.dist > 0:
            continue
        names = tuple(sorted((model.geom(contact.geom1).name or '', model.geom(contact.geom2).name or '')))
        if not any(name.startswith('service_') for name in names):
            continue
        force = np.zeros(6)
        mj.mj_contactForce(model, data, index, force)
        contacts['|'.join(names)] = contacts.get('|'.join(names), 0.)+max(0., float(force[0]))
    return {
        'time_s': float(data.time), 'door_angle_rad': joint('service_door_hinge'),
        'door_angular_velocity_rad_s':float(data.joint('service_door_hinge').qvel[0]),
        'latch_retraction_m': joint('service_latch_slide'),
        'retention_retraction_m': joint('service_retention_slide'),
        'old_cartridge_position_m': old.tolist(), 'replacement_position_m': new.tolist(),
        'old_tray_error_m': float(np.linalg.norm(old-goal_tray)),
        'replacement_seating_error_m': float(np.linalg.norm(new-seated)),
        'replacement_orientation_error_rad': angular_error,
        'contact_normal_forces_n': contacts,
        'mechanism_ready': bool(np.linalg.norm(new-seated) < .003 and angular_error < .03
            and joint('service_retention_slide') < .003 and abs(joint('service_door_hinge')) < .025
            and joint('service_latch_slide') < .003),
    }
