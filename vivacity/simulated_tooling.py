"""Visible, bounded simulated tooling; no adhesion or attachment constraints.

These are engineering fixtures, not manufacturer-approved robot hardware.
Their mass, inertia, collision surfaces and finger actuators enter the same
MuJoCo model as the robot. A model-matched mobility policy is still required.
"""
import xml.etree.ElementTree as ET

from pydantic import BaseModel, ConfigDict, Field


class ParallelGripperConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    finger_force_n: float = Field(default=40., ge=1., le=60.)
    sliding_friction: float = Field(default=.8, ge=.001, le=1.5)
    position_stiffness_n_m: float = Field(default=800., ge=200., le=4000.)


def append_parallel_gripper(root, parent, name, config: ParallelGripperConfig, *,
                            position=(0., 0., 0.)):
    if root.find(f".//*[@name='{name}_tool']") is not None:
        raise ValueError('tool identity already exists')
    tool = ET.SubElement(parent, 'body', name=name+'_tool', pos=' '.join(map(str, position)))
    common = dict(type='box', contype='1', conaffinity='1', condim='6',
                  friction=f'{config.sliding_friction} .002 .0001', priority='3',
                  solref='.004 1', margin='0', group='0')
    ET.SubElement(tool, 'geom', name=name+'_palm', size='.045 .115 .025', mass='.25',
                  rgba='.24 .28 .29 1', **common)
    ET.SubElement(tool, 'site', name=name+'_tcp', pos='0 0 -.085', size='.003', rgba='0 0 0 0')
    actuator = root.find('actuator')
    if actuator is None:
        actuator = ET.SubElement(root, 'actuator')
    for side, sign in (('positive', 1), ('negative', -1)):
        identity = f'{name}_{side}'
        finger = ET.SubElement(tool, 'body', name=identity+'_finger', pos=f'0 {sign*.005} -.085')
        ET.SubElement(finger, 'joint', name=identity+'_slide', type='slide', axis=f'0 {sign} 0',
            limited='true', range='0 .105', damping='1', armature='.002',
            actuatorfrclimited='true', actuatorfrcrange=f'-{config.finger_force_n} {config.finger_force_n}')
        ET.SubElement(finger, 'geom', name=identity+'_pad', size='.040 .005 .060', mass='.12',
                      rgba='.73 .53 .25 1', **common)
        ET.SubElement(actuator, 'position', name=identity+'_drive', joint=identity+'_slide',
            kp=str(config.position_stiffness_n_m), kv='10', ctrllimited='true', ctrlrange='0 .105',
            forcelimited='true', forcerange=f'-{config.finger_force_n} {config.finger_force_n}')
    return tool


def tooling_manifest(model, name, config):
    return {'schema_version':'vivacity.simulated-parallel-gripper/1',
        'identity':name, 'hardware_validation':False,
        'scope':'Visible custom simulated tooling; not a manufacturer hardware specification.',
        'parameters':config.model_dump(),
        'mount':{'parent_body':model.body(int(model.body(name+'_tool').parentid[0])).name,
            'position_m':model.body(name+'_tool').pos.tolist(),
            'quaternion_wxyz':model.body(name+'_tool').quat.tolist()},
        'tcp_site':name+'_tcp', 'opening_range_m':[0., .21],
        'actuators':[{ 'name':f'{name}_{side}_drive',
            'command_unit':'m',
            'command_range':model.actuator(f'{name}_{side}_drive').ctrlrange.tolist(),
            'position_stiffness_n_m':float(model.actuator(f'{name}_{side}_drive').gainprm[0]),
            'force_range_n':model.actuator(f'{name}_{side}_drive').forcerange.tolist()}
            for side in ('positive', 'negative')],
        'tool_mass_kg':sum(float(model.body(body).mass[0]) for body in (
            name+'_tool',name+'_positive_finger',name+'_negative_finger'))}
