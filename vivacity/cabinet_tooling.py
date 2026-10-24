"""Explicit experimental tool swivel, retaining all manufacturer arm limits."""
import xml.etree.ElementTree as ET
import math


SWIVEL_JOINT = 'l_service_swivel'


def append_latch_swivel(root):
    tool=root.find(".//body[@name='l_service_tool']")
    actuator=root.find('actuator')
    if tool is None or actuator is None:
        raise ValueError('left parallel gripper and actuator section required')
    if root.find(f".//*[@name='{SWIVEL_JOINT}']") is not None:
        raise ValueError('cabinet swivel already exists')
    compiler=root.find('compiler')
    angle_limit=1.65 if compiler is not None and compiler.get('angle')=='radian' else math.degrees(1.65)
    # Rotation is about the gripper approach axis; it does not move the TCP.
    # Its visible rotor adds mass/inertia, and both native force clamps apply.
    ET.SubElement(tool,'joint',name=SWIVEL_JOINT,type='hinge',axis='0 0 1',
        limited='true',range=f'{-angle_limit} {angle_limit}',damping='.15',armature='.001',
        actuatorfrclimited='true',actuatorfrcrange='-3 3')
    ET.SubElement(tool,'geom',name='l_service_swivel_rotor',type='cylinder',
        size='.035 .018',pos='0 0 .04',mass='.10',rgba='.58 .60 .59 1',
        contype='1',conaffinity='1',condim='6',friction='.6 .002 .0001',margin='0')
    ET.SubElement(actuator,'position',name='l_service_swivel_drive',joint=SWIVEL_JOINT,
        kp='40',kv='4',ctrllimited='true',ctrlrange='-1.65 1.65',
        forcelimited='true',forcerange='-3 3')


def swivel_manifest(model):
    joint=model.joint(SWIVEL_JOINT)
    return {'identity':'vivacity.cabinet-tool-swivel/1-experimental',
        'hardware_validation':False,'joint':SWIVEL_JOINT,'range_rad':joint.range.tolist(),
        'torque_range_nm':model.jnt_actfrcrange[joint.id].tolist(),
        'rotor_mass_kg':.10,'control':'native force-limited position servo',
        'scope':'Visible custom simulated tooling; no object attachment.'}
