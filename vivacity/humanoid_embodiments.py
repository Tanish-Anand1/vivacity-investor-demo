"""Complete, separately versioned humanoid models for control development.

Adding tooling changes the plant. In particular this full 23-actuator H1 is not
compatible with the existing 10-actuator walking policy. No mobility policy is
assigned by this module and compilation is not a task acceptance certificate.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco as mj
import numpy as np

from .execution_checkpoint import model_bytes
from .simulated_tooling import ParallelGripperConfig, append_parallel_gripper, tooling_manifest


ASSETS = Path(__file__).resolve().parents[1]/'assets'/'menagerie'
SOURCES = {'g1':('unitree_g1', 'g1_with_hands.xml'),
           'apollo':('apptronik_apollo', 'apptronik_apollo.xml'),
           'h1':('unitree_h1', 'h1.xml')}
FEET = {'g1':('left_ankle_roll_link', 'right_ankle_roll_link'),
        'apollo':('l_foot_link', 'r_foot_link'), 'h1':('left_ankle_link', 'right_ankle_link')}
ROOTS = {'g1':'pelvis', 'apollo':'base_link', 'h1':'pelvis'}


def _source_pose(root):
    key = root.find('keyframe/key')
    if key is None:
        return {}
    values = np.fromstring(key.get('qpos', ''), sep=' ')
    result, offset = {}, 0
    for joint in root.find('worldbody').iter():
        if joint.tag not in ('joint', 'freejoint'):
            continue
        kind = joint.get('type', 'free' if joint.tag == 'freejoint' else 'hinge')
        width = {'free':7, 'ball':4}.get(kind, 1)
        if joint.get('name') and offset+width <= len(values):
            result[joint.get('name')] = values[offset:offset+width].copy()
        offset += width
    return result


def embodiment_tree(identity, tooling=None):
    if identity not in SOURCES:
        raise ValueError('unknown humanoid embodiment')
    tooling = ParallelGripperConfig() if tooling is None else tooling
    folder, filename = SOURCES[identity]
    source = ASSETS/folder/filename
    root = ET.parse(source).getroot()
    pose = _source_pose(root)
    root.find('compiler').set('meshdir', str(source.parent/'assets'))
    root.find('compiler').set('texturedir', str(source.parent/'assets'))
    option = root.find('option')
    if option is None:
        option = ET.SubElement(root, 'option')
    option.attrib.update(timestep='.002', integrator='implicitfast', iterations='80', cone='elliptic')
    world = root.find('worldbody')
    ET.SubElement(world, 'geom', name='floor', type='plane', size='5 5 .05',
        rgba='.28 .30 .30 1', contype='1', conaffinity='1', priority='2', friction='.8 .005 .0001')
    ET.SubElement(world, 'light', pos='0 -3 4', diffuse='.9 .9 .9')
    if identity == 'apollo':
        scene = ET.parse(source.parent/'scene.xml').getroot()
        contacts = root.find('contact')
        if contacts is None:
            contacts = ET.SubElement(root, 'contact')
        contacts.extend(deepcopy(list(scene.find('contact'))))
        for pair in contacts.findall('pair'):
            if pair.get('geom2') == 'floor':
                pair.set('friction', '.8 .8 .01 .0001 .0001')
        for geom in root.findall('.//geom'):
            if geom.get('name', '').startswith('collision_'):
                geom.set('contype', '0')
                geom.set('conaffinity', '1')
        for side in ('l', 'r'):
            parent = root.find(f".//body[@name='{side}_wrist_pitch_link']")
            # Keep the source wrist/hand assembly, including its declared inertia.
            # The visible tool is an added adapter beyond its fixed hand geometry.
            append_parallel_gripper(root, parent, side+'_service', tooling, position=(0., 0., -.22))
    elif identity == 'h1':
        for side in ('left', 'right'):
            parent = root.find(f".//body[@name='{side}_elbow_link']")
            append_parallel_gripper(root, parent, side+'_service', tooling, position=(0., 0., -.34))
    keys = root.find('keyframe')
    if keys is not None:
        root.remove(keys)
    ET.SubElement(ET.SubElement(root, 'keyframe'), 'key', name='development_stand')
    return root, pose


def compile_embodiment(identity, tooling=None, *, append_scene=None):
    config = ParallelGripperConfig() if tooling is None else tooling
    root, pose = embodiment_tree(identity, config)
    if append_scene is not None:
        append_scene(root)
    model = mj.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'))
    home = model.qpos0.copy()
    for name, value in pose.items():
        address = int(model.joint(name).qposadr[0])
        home[address:address+len(value)] = value
    if identity == 'h1':
        # Initial stance only, not a locomotion trajectory or transplanted policy.
        home[:7] = [0., 0., 1.04, 1., 0., 0., 0.]
        for side in ('left', 'right'):
            for joint, angle in (('hip_pitch', -.2), ('knee', .4), ('ankle', -.2)):
                home[model.joint(f'{side}_{joint}').qposadr[0]] = angle
            home[model.joint(f'{side}_elbow').qposadr[0]] = .4
            # Added crossbars need an abducted rest posture; the source arm-down
            # pose intersects the hips after tooling is fitted.
            home[model.joint(f'{side}_shoulder_roll').qposadr[0]] = .2 if side == 'left' else -.2
    for index in range(model.njnt):
        name = model.joint(index).name or ''
        if '_service_' in name and name.endswith('_slide'):
            home[model.jnt_qposadr[index]] = .09
    adjustments = []
    for index in range(model.njnt):
        # pybind enum equality with NumPy integers is asymmetric on Linux.
        # Tuple membership calls the enum's comparison first; normalize both.
        if model.jnt_limited[index] and int(model.jnt_type[index]) in (
                int(mj.mjtJoint.mjJNT_HINGE), int(mj.mjtJoint.mjJNT_SLIDE)):
            address = model.jnt_qposadr[index]
            bounded = float(np.clip(home[address], *model.jnt_range[index]))
            if home[address] != bounded:
                adjustments.append({'joint':model.joint(index).name, 'source_value':float(home[address]),
                                    'initial_value':bounded, 'reason':'source keyframe exceeded native joint range'})
                home[address] = bounded
    # Correct source-keyframe sole penetration at initialization only. After
    # reset every root displacement must result from native integration.
    initial = mj.MjData(model)
    initial.qpos[:] = home
    mj.mj_forward(model, initial)
    floor = model.geom('floor').id
    foot_bodies = {model.body(name).id for name in FEET[identity]}
    sole_distance = min(mj.mj_geomDistance(model, initial, floor, geom, .5, None)
        for geom in range(model.ngeom) if model.geom_bodyid[geom] in foot_bodies
        and (model.geom_contype[geom] or model.geom_conaffinity[geom]
             or geom in model.pair_geom1 or geom in model.pair_geom2))
    if abs(sole_distance-.0001) > 1e-8:
        correction = float(-sole_distance+.0001)
        home[2] += correction
        adjustments.append({'joint':model.joint(0).name, 'vertical_offset_m':correction,
                            'reason':'place initial sole surfaces 0.1 mm above floor before physics execution'})
    model.key_qpos[0] = home
    for index, joint in enumerate(model.actuator_trnid[:, 0]):
        # Native torque motors have zero command at reset; affine position
        # servos target the corresponding initial joint position.
        model.key_ctrl[0, index] = (home[model.jnt_qposadr[joint]]
            if model.actuator_biastype[index] == mj.mjtBias.mjBIAS_AFFINE else 0.)
    data = mj.MjData(model)
    mj.mj_resetDataKeyframe(model, data, 0)
    mj.mj_forward(model, data)
    names = ('l_service', 'r_service') if identity == 'apollo' else (
        ('left_service', 'right_service') if identity == 'h1' else ())
    robot = model.body(ROOTS[identity]).id
    robot_bodies = []
    for body in range(1, model.nbody):
        parent = body
        while parent not in (0, robot):
            parent = int(model.body_parentid[parent])
        if parent == robot:
            robot_bodies.append(body)
    manifest = {
        'schema_version':'vivacity.humanoid-embodiment/1',
        'identity':f'vivacity.{identity}-complete/1-experimental', 'robot':identity,
        'compiled_model_sha256':hashlib.sha256(model_bytes(model)).hexdigest(),
        'simulator_version':mj.__version__, 'root_body':ROOTS[identity], 'support_bodies':list(FEET[identity]),
        'mobility_policy':None, 'task_acceptance':False, 'hardware_validation':False,
        'robot_mass_kg':float(model.body_mass[robot_bodies].sum()),
        'world_body_mass_sum_kg':float(model.body_mass.sum()),
        'initial_pose_adjustments':adjustments,
        'initial_qpos':model.key_qpos[0].tolist(),
        'tooling':[tooling_manifest(model, name, config) for name in names],
        'joints':[{ 'name':model.joint(i).name, 'type':int(model.jnt_type[i]),
            'qpos_address':int(model.jnt_qposadr[i]), 'velocity_address':int(model.jnt_dofadr[i]),
            'range':model.jnt_range[i].tolist(), 'limited':bool(model.jnt_limited[i])}
            for i in range(model.njnt)],
        'actuators':[{ 'name':model.actuator(i).name,
            'joint':model.joint(int(model.actuator_trnid[i, 0])).name,
            'gain':model.actuator_gainprm[i].tolist(), 'bias':model.actuator_biasprm[i].tolist(),
            'command_range':model.actuator_ctrlrange[i].tolist(),
            'force_limited':bool(model.actuator_forcelimited[i]), 'force_range':model.actuator_forcerange[i].tolist()}
            for i in range(model.nu)],
    }
    return model, data, manifest
