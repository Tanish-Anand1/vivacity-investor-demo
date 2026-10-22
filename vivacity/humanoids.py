"""Bounded, inspectable humanoid physics trials.

The imported Menagerie models are the source of robot geometry and dynamics.
These controllers are deliberately limited probes, not walking or manipulation
policies. A task is reported successful only when measured task conditions hold.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import uuid
import xml.etree.ElementTree as ET

import mujoco as mj
import numpy as np
from pydantic import BaseModel, Field, model_validator

from .storage import Store, encode


ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'menagerie'
MODELS = {
    'unitree_g1': ('Unitree G1 with hands', 'unitree_g1/g1_with_hands.xml', 'warehouse_logistics'),
    'apptronik_apollo': ('Apptronik Apollo', 'apptronik_apollo/apptronik_apollo.xml', 'industrial_maintenance'),
    'unitree_h1': ('Unitree H1', 'unitree_h1/h1.xml', 'terrain_mobility'),
}
STATE = mj.mjtState.mjSTATE_INTEGRATION


class HumanoidTrialRequest(BaseModel):
    robot_id: str
    action: str = Field(default='attempt_task', pattern='^(attempt_task|hold_stance|pickup_place)$')
    duration_s: float = Field(default=2.0, ge=.5, le=3.0)
    movement_scale: float = Field(default=.6, ge=0, le=1)
    floor_friction: float = Field(default=.8, ge=.2, le=1.5)
    parcel_mass_kg: float = Field(default=.5, ge=.1, le=2)
    parcel_xy_m: tuple[float, float] = (.35, 0.)
    destination_xy_m: tuple[float, float] = (.66, -.47)
    task_timeout_s: float = Field(default=8., ge=6., le=12.)
    perturbation_n: float = Field(default=0, ge=0, le=80)
    seed: int = Field(default=7, ge=0, le=2**31-1)

    @model_validator(mode='after')
    def valid_task_configuration(self):
        if self.action == 'pickup_place' and self.robot_id != 'unitree_g1':
            raise ValueError('Stationary pickup is validated only for Unitree G1 with hands')
        if self.action == 'pickup_place' and 'movement_scale' not in self.model_fields_set:
            self.movement_scale = 1.
        if not (.18 <= self.parcel_xy_m[0] <= 1.0 and -.22 <= self.parcel_xy_m[1] <= .22):
            raise ValueError('Parcel center must be inside the bounded collection workspace')
        if not (.48 <= self.destination_xy_m[0] <= .76 and -.62 <= self.destination_xy_m[1] <= -.32):
            raise ValueError('Destination center must be on the placement stand')
        return self


class HumanoidModelResponse(BaseModel):
    schema_version: str = 'vivacity.humanoid-model/1.0'
    robot_id: str
    name: str
    environment_id: str
    model_hash: str
    simulator_version: str
    dof: int
    actuators: int
    mesh_count: int
    joint_names: list[str]
    initial_frame: dict
    geometry_url: str
    task_scope: str


class HumanoidTrialResponse(BaseModel):
    schema_version: str = 'vivacity.humanoid-job/1.0'
    id: str
    status: str
    request: dict
    created_unix_s: float
    result: dict | None = None
    error: str | None = None


def _add_box(world, name, pos, size, rgba, *, friction='0.8 0.005 0.0001', **other):
    other.setdefault('contype', '1')
    other.setdefault('conaffinity', '1')
    return ET.SubElement(world, 'geom', name=name, type='box', pos=' '.join(map(str, pos)),
                         size=' '.join(map(str, size)), rgba=' '.join(map(str, rgba)),
                         friction=friction, **other)


def _scene(root, robot_id, friction, parcel_mass):
    world = root.find('worldbody')
    if world is None:
        raise ValueError('robot model has no worldbody')
    ET.SubElement(world, 'light', name='lab_key', pos='-2 -3 5', dir='.3 .4 -1', diffuse='0.95 0.95 0.93')
    ET.SubElement(world, 'geom', name='floor', type='plane', size='8 8 0.05',
                  rgba='.31 .34 .34 1', friction=f'{friction} 0.005 0.0001',
                  contype='1', conaffinity='1')
    if robot_id == 'unitree_g1':
        # Keep the approach lane and camera sightline clear; racks are behind
        # the robot and remain genuine collision geometry.
        for side, y in [('rear', 1.55)]:
            for x in (-.4, 1.4):
                _add_box(world, f'{side}_rack_upright_{x}', [x, y, .9], [.05, .06, .9], [.26,.29,.3,1])
            for z in (.35, 1.1, 1.75):
                _add_box(world, f'{side}_rack_shelf_{z}', [.5,y,z],[.95,.32,.04],[.38,.4,.39,1])
        for y in (-.8, .8):
            _add_box(world, f'pallet_{y}', [1.6,y,.08],[.4,.34,.08],[.43,.29,.18,1])
        _add_box(world, 'pickup_stand', [.35,0,.3],[.22,.23,.3],[.36,.37,.36,1])
        # A separate support fixture keeps the robot's starting stance clear.
        _add_box(world, 'placement_stand', [.66,-.47,.3],[.24,.35,.3],[.28,.43,.35,1])
        package = ET.SubElement(world, 'body', name='parcel', pos='.35 0 .68')
        ET.SubElement(package, 'freejoint', name='parcel_free')
        ET.SubElement(package, 'geom', name='parcel_box', type='box', size='.09 .09 .08',
                      mass=str(parcel_mass), rgba='.6 .39 .19 1', friction='0.8 0.005 0.0001')
        # This disabled weld is activated only after measured bilateral hand
        # contact. Its rest pose is set from the live relative transforms.
        equality = root.find('equality')
        if equality is None:
            equality = ET.SubElement(root, 'equality')
        ET.SubElement(equality, 'weld', name='parcel_grasp',
                      body1='right_wrist_yaw_link', body2='parcel', active='false',
                      relpose='0 0 0 1 0 0 0')
        _add_box(world, 'drop_zone', [1.65,0,.055],[.3,.3,.055],[.21,.43,.34,1])
    elif robot_id == 'apptronik_apollo':
        _add_box(world, 'cabinet', [.85,0,.85],[.22,.47,.85],[.23,.29,.31,1])
        _add_box(world, 'cabinet_face', [.615,0,1.05],[.018,.41,.53],[.37,.43,.45,1])
        _add_box(world, 'machine_base', [1.45,-.85,.4],[.45,.4,.4],[.25,.31,.33,1])
        _add_box(world, 'machine_top', [1.45,-.85,.9],[.32,.31,.1],[.43,.46,.44,1])
        switch = ET.SubElement(world, 'body', name='control_switch', pos='.56 -.18 1.12')
        ET.SubElement(switch, 'joint', name='switch_hinge', type='hinge', axis='0 1 0',
                      range='-.65 .65', damping='0.15', stiffness='8', armature='.01')
        ET.SubElement(switch, 'geom', name='switch_handle', type='box', pos='-.055 0 .03',
                      size='.075 .025 .025', mass='.16', rgba='.78 .46 .18 1',
                      contype='1', conaffinity='1')
        _add_box(world, 'switch_label', [.59,-.18,1.23],[.01,.08,.015],[.71,.7,.63,1], contype='0', conaffinity='0')
    else:
        # The start stripe is flush with the ground plane. Keep it visual-only
        # to avoid duplicate coplanar foot contacts from two identical floors.
        _add_box(world, 'track_start', [-.55,0,-.015],[.6,.58,.015],[.42,.44,.42,1], contype='0', conaffinity='0')
        _add_box(world, 'ramp', [1.45,0,.12],[.6,.48,.08],[.43,.42,.38,1], euler='0 -0.22 0')
        for i in range(3):
            _add_box(world, f'step_{i}', [2.3+i*.45,0,.08+i*.08],[.22,.48,.08+i*.08],[.37,.39,.37,1])
        for i, (x,y,z) in enumerate([(3.9,-.22,.06),(4.35,.17,.09),(4.8,-.1,.05)]):
            _add_box(world, f'rough_block_{i}', [x,y,z],[.2,.22,z],[.39,.4,.36,1])
    return world


@lru_cache(maxsize=3)
def _asset_digest(robot_id):
    source = ASSETS / MODELS[robot_id][1]
    digest = hashlib.sha256()
    for asset in sorted((source.parent / 'assets').rglob('*')):
        if asset.is_file():
            digest.update(asset.relative_to(source.parent).as_posix().encode())
            digest.update(asset.read_bytes())
    return digest.digest()


def _configured_tree(robot_id: str, floor_friction: float, parcel_mass_kg: float):
    if robot_id not in MODELS:
        raise ValueError('Unknown humanoid model')
    source = ASSETS / MODELS[robot_id][1]
    if not source.is_file():
        raise FileNotFoundError(f'Humanoid model asset is unavailable: {robot_id}')
    root = ET.parse(source).getroot()
    compiler = root.find('compiler')
    if compiler is None:
        compiler = ET.SubElement(root, 'compiler')
    compiler.set('meshdir', str(source.parent / 'assets'))
    compiler.set('texturedir', str(source.parent / 'assets'))
    if robot_id == 'unitree_h1':
        scene = ET.parse(source.parent / 'scene.xml').getroot()
        keyframe = scene.find('keyframe')
        if keyframe is None:
            raise ValueError('H1 standing keyframe unavailable')
        root.append(deepcopy(keyframe))
    elif robot_id == 'apptronik_apollo':
        scene = ET.parse(source.parent / 'scene.xml').getroot()
        scene_option = scene.find('option')
        if scene_option is not None:
            option = root.find('option')
            if option is None:
                option = ET.SubElement(root, 'option')
            option.attrib.update(scene_option.attrib)
        scene_contacts = scene.find('contact')
        if scene_contacts is not None:
            contacts = root.find('contact')
            if contacts is None:
                contacts = ET.SubElement(root, 'contact')
            contacts.extend(deepcopy(list(scene_contacts)))
        # Apollo's default class disables general contacts. Its named collision
        # geoms may contact world objects (contype 1) without turning on robot
        # self-collision; the original sole-floor pairs remain in place.
        collision_geoms = root.findall(".//geom")
        collision_geoms = [geom for geom in collision_geoms if geom.get('name', '').startswith('collision_')]
        if not any(geom.get('name') == 'collision_r_hand_plate' for geom in collision_geoms):
            raise ValueError('Apollo right-hand collision plate unavailable')
        for geom in collision_geoms:
            geom.set('contype', '0')
            geom.set('conaffinity', '1')
    _scene(root, robot_id, floor_friction, parcel_mass_kg)
    portable = deepcopy(root)
    portable_compiler = portable.find('compiler')
    portable_compiler.set('meshdir', 'assets')
    portable_compiler.set('texturedir', 'assets')
    digest = hashlib.sha256()
    digest.update(ET.tostring(portable, encoding='utf-8'))
    digest.update(_asset_digest(robot_id))
    digest.update(mj.__version__.encode())
    return root, digest.hexdigest()


@lru_cache(maxsize=16)
def configured_digest(robot_id: str, floor_friction: float = .8, parcel_mass_kg: float = .5):
    """Identity of the source MJCF, assets, physics parameters, and MuJoCo version."""
    return _configured_tree(robot_id, floor_friction, parcel_mass_kg)[1]


@lru_cache(maxsize=4)
def _compiled_xml_model(robot_id: str, floor_friction: float, parcel_mass_kg: float):
    root, digest = _configured_tree(robot_id, floor_friction, parcel_mass_kg)
    return mj.MjModel.from_xml_string(ET.tostring(root, encoding='unicode')), digest


@lru_cache(maxsize=3)
def _verified_binary_path(robot_id: str, directory: str):
    """Reject stale or corrupt build artifacts before loading their physics state."""
    location = Path(directory)
    record = json.loads((location / f'{robot_id}.json').read_text(encoding='utf-8'))
    path = location / f'{robot_id}.mjb'
    if record.get('simulator_version') != mj.__version__ or record.get('model_hash') != configured_digest(robot_id):
        raise RuntimeError(f'Precompiled humanoid model does not match source: {robot_id}')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != record.get('binary_sha256'):
        raise RuntimeError(f'Precompiled humanoid model is corrupt: {robot_id}')
    return path


def compiled_model(robot_id: str, floor_friction: float = .8, parcel_mass_kg: float = .5):
    """Load exact MuJoCo dynamics; production binaries avoid XML compile peaks.

    The build step compiles the default Menagerie scene into .mjb. MuJoCo
    preserves its full mesh/contact model in that binary. Each runtime call
    loads an independent MjModel so physical parameter edits and grasp welds
    cannot mutate another trial. Source XML remains the local fallback.
    """
    directory = os.getenv('VIVACITY_HUMANOID_MODEL_DIR')
    if not directory:
        return _compiled_xml_model(robot_id, floor_friction, parcel_mass_kg)
    if robot_id not in MODELS:
        raise ValueError('Unknown humanoid model')
    model = mj.MjModel.from_binary_path(str(_verified_binary_path(robot_id, directory)))
    if floor_friction != .8:
        model.geom_friction[model.geom('floor').id, 0] = floor_friction
    if robot_id == 'unitree_g1' and parcel_mass_kg != .5:
        parcel = model.body('parcel').id
        scale = parcel_mass_kg / .5
        model.body_mass[parcel] *= scale
        model.body_inertia[parcel] *= scale
        mj.mj_setConst(model, mj.MjData(model))
    return model, configured_digest(robot_id, floor_friction, parcel_mass_kg)


def initial_data(model):
    data = mj.MjData(model)
    mj.mj_resetDataKeyframe(model, data, 0)
    mj.mj_forward(model, data)
    return data


def _frame(model, data):
    return {
        'time_s': float(data.time),
        'base_position_m': data.qpos[:3].tolist(),
        'base_quaternion_wxyz': data.qpos[3:7].tolist(),
        'qpos': data.qpos.tolist(),
        'qvel': data.qvel.tolist(),
        'body_transforms': [
            {'name': mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, i),
             'position': data.xpos[i].tolist(), 'quaternion_wxyz': data.xquat[i].tolist()}
            for i in range(model.nbody)
        ],
        'contacts': int(data.ncon),
    }


def model_info(robot_id):
    model, digest = compiled_model(robot_id)
    data = initial_data(model)
    visual_mesh_count = int(model.nmesh)
    directory = os.getenv('VIVACITY_HUMANOID_MODEL_DIR')
    if directory:
        # A headless binary can omit visual-only meshes while the public
        # geometry bundle still contains the source model's visual meshes.
        record = json.loads((Path(directory) / f'{robot_id}.json').read_text(encoding='utf-8'))
        visual_mesh_count = int(record['source_mesh_count'])
    return {'robot_id': robot_id, 'name': MODELS[robot_id][0], 'environment_id': MODELS[robot_id][2],
            'model_hash': digest, 'simulator_version': mj.__version__, 'dof': int(model.nv),
            'actuators': int(model.nu), 'mesh_count': visual_mesh_count,
            'joint_names': [mj.mj_id2name(model, mj.mjtObj.mjOBJ_JOINT, i) or f'joint_{i}' for i in range(model.njnt)],
            'initial_frame': _frame(model, data),
            'geometry_url': f'/vivacity/humanoids/{robot_id}/robot-geometry.json',
            'task_scope': ('Stationary G1 parcel pickup and placement uses measured bilateral contact and an explicit rigid-grasp fixture. Walking and warehouse fulfillment are unvalidated.'
                           if robot_id == 'unitree_g1' else
                           'Physical task probe. Switch actuation and terrain traversal require measured completion; previews alone are not success.')}


def _actuator_target(model, data, index):
    joint_id = int(model.actuator_trnid[index, 0])
    return float(model.key_qpos[0, model.jnt_qposadr[joint_id]]), joint_id


def _solve_position_ik(model, planner, target, joint_names, effector_id, *, geom):
    joints = [model.joint(name).id for name in joint_names]
    q_indices = np.array([model.jnt_qposadr[joint] for joint in joints], dtype=int)
    v_indices = np.array([model.jnt_dofadr[joint] for joint in joints], dtype=int)
    jacobian = np.zeros((3, model.nv))
    residual = float('inf')
    for _ in range(150):
        position = planner.geom_xpos[effector_id] if geom else planner.xpos[effector_id]
        error = target - position
        residual = float(np.linalg.norm(error))
        if residual < .01:
            break
        if geom:
            mj.mj_jacGeom(model, planner, jacobian, None, effector_id)
        else:
            mj.mj_jacBody(model, planner, jacobian, None, effector_id)
        arm_jacobian = jacobian[:, v_indices]
        delta = arm_jacobian.T @ np.linalg.solve(
            arm_jacobian @ arm_jacobian.T + np.eye(3) * .025**2, error)
        for index, joint in enumerate(joints):
            lower, upper = model.jnt_range[joint]
            planner.qpos[q_indices[index]] = np.clip(
                planner.qpos[q_indices[index]] + np.clip(delta[index], -.05, .05),
                lower + .01, upper - .01)
        mj.mj_kinematics(model, planner)
        mj.mj_comPos(model, planner)
    return {joint: float(planner.qpos[q_indices[index]]) for index, joint in enumerate(joints)}, residual


def _reach_plan(model, robot_id):
    """Compute a task hand target from actual scene geometry, not a pose clip."""
    planner = initial_data(model)
    if robot_id == 'apptronik_apollo':
        target = planner.geom_xpos[model.geom('switch_handle').id].copy() + np.array([-.155, 0., .03])
        effector_id = model.geom('collision_r_hand_plate').id
        joint_names = ('r_shoulder_aa', 'r_shoulder_ie', 'r_shoulder_fe',
                       'r_elbow_fe', 'r_wrist_roll', 'r_wrist_yaw', 'r_wrist_pitch')
        use_geom = True
    else:
        target = planner.body('parcel').xpos.copy() + np.array([-.08, -.08, .08])
        effector_id = model.body('right_hand_middle_0_link').id
        joint_names = ('right_shoulder_pitch_joint', 'right_shoulder_roll_joint',
                       'right_shoulder_yaw_joint', 'right_elbow_joint',
                       'right_wrist_roll_joint', 'right_wrist_pitch_joint',
                       'right_wrist_yaw_joint')
        use_geom = False
    targets, residual = _solve_position_ik(model, planner, target, joint_names, effector_id, geom=use_geom)
    return targets, {
        'method': 'damped_least_squares_hand_position',
        'target_position_m': target.tolist(),
        'hand_position_error_m': residual,
        'feasible': bool(residual < .025),
    }


def _control(model, data, request, elapsed, reach_targets=None):
    phase = min(1., max(0., (elapsed-.3)/1.1))
    blend = np.sin(np.pi*phase/2)**2 if request.action == 'attempt_task' else 0.
    for i in range(model.nu):
        home, jid = _actuator_target(model, data, i)
        name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_JOINT, jid) or ''
        target = home
        if request.robot_id in ('unitree_g1', 'apptronik_apollo') and reach_targets and jid in reach_targets:
            reach_duration = 1.5 if request.robot_id == 'unitree_g1' else 1.8
            reach_phase = min(1., max(0., (elapsed - .2) / reach_duration))
            reach_blend = np.sin(np.pi * reach_phase / 2)**2
            target += (reach_targets[jid] - home) * request.movement_scale * reach_blend
        elif request.robot_id == 'unitree_h1':
            gait = np.sin(2*np.pi*1.1*elapsed)
            sign = 1 if name.startswith('left_') else -1
            if 'hip_pitch' in name: target += sign*.16*request.movement_scale*gait*blend
            if 'knee' in name: target += max(0., sign*gait)*.17*request.movement_scale*blend
            if 'shoulder_pitch' in name: target -= sign*.13*request.movement_scale*gait*blend
        if model.jnt_limited[jid]:
            lo, hi = model.jnt_range[jid]
            target = float(np.clip(target, lo+.002, hi-.002))
        if request.robot_id == 'unitree_h1':
            qadr, vadr = int(model.jnt_qposadr[jid]), int(model.jnt_dofadr[jid])
            kp = 105. if any(part in name for part in ('hip', 'knee', 'torso')) else 55. if 'ankle' in name else 28.
            torque = kp*(target-data.qpos[qadr])-2*np.sqrt(kp)*data.qvel[vadr]
            data.ctrl[i] = np.clip(torque, *model.actuator_ctrlrange[i])
        else:
            data.ctrl[i] = target


def _contact_names(model, data):
    for c in data.contact[:data.ncon]:
        if c.dist > 0:
            continue
        def label(geom_id):
            geom_id = int(geom_id)
            geom_name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, geom_id) or ''
            body_name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[geom_id])) or ''
            return f'{geom_name} {body_name}'
        a, b = [label(g) for g in (c.geom1, c.geom2)]
        yield a, b


def _terrain_foot_contacts(model, data):
    """Count grounded H1 contact points and measure tangential point speed."""
    count = 0
    peak_slip = 0.
    jacobian = np.zeros((3, model.nv))
    for contact in data.contact[:data.ncon]:
        if contact.dist > 0:
            continue
        geom_ids = (int(contact.geom1), int(contact.geom2))
        body_ids = [int(model.geom_bodyid[geom_id]) for geom_id in geom_ids]
        body_names = [mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, body_id) or '' for body_id in body_ids]
        foot_side = next((side for side, name in enumerate(body_names)
                          if name in ('left_ankle_link', 'right_ankle_link')), None)
        if foot_side is None:
            continue
        terrain_geom = mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, geom_ids[1-foot_side]) or ''
        if not terrain_geom.startswith(('floor', 'track_start', 'ramp', 'step_', 'rough_block_')):
            continue
        count += 1
        mj.mj_jac(model, data, jacobian, None, contact.pos, body_ids[foot_side])
        point_velocity = jacobian @ data.qvel
        tangents = np.asarray(contact.frame).reshape(3, 3)[1:]
        peak_slip = max(peak_slip, float(np.linalg.norm(tangents @ point_velocity)))
    return count, peak_slip


def simulate(request: HumanoidTrialRequest):
    if request.robot_id not in MODELS:
        raise ValueError('Unknown humanoid model')
    if request.action == 'pickup_place':
        from .humanoid_pickup import simulate_pickup
        return simulate_pickup(request)
    model, digest = compiled_model(request.robot_id, request.floor_friction, request.parcel_mass_kg)
    data = initial_data(model)
    reach_targets, planning = _reach_plan(model, request.robot_id) if request.robot_id in ('unitree_g1', 'apptronik_apollo') and request.action == 'attempt_task' else (None, None)
    initial = _frame(model, data)
    frames = [initial]
    minimum_height = float(data.qpos[2])
    maximum_tilt = 0.
    min_hand_goal_distance = float('inf')
    max_switch_angle = 0.
    max_parcel_height = 0.
    foot_slip_m_s = 0.
    task_contacts = 0
    had_hand_switch_contact = False
    max_switch_angle_after_contact = 0.
    switch_activation_time_s = None
    peak_joint_delta = 0.
    home_qpos = data.qpos.copy()
    base_id = 1
    sample_stride = max(1, round(.05/model.opt.timestep))
    steps = round(request.duration_s/model.opt.timestep)
    start = time.perf_counter()
    for step in range(steps):
        elapsed = float(data.time)
        _control(model, data, request, elapsed, reach_targets)
        data.xfrc_applied[base_id, 0] = request.perturbation_n if .4 <= elapsed <= .65 else 0.
        mj.mj_step(model, data)
        if not np.isfinite(data.qpos).all():
            raise RuntimeError('nonfinite simulator state')
        minimum_height = min(minimum_height, float(data.qpos[2]))
        qw = float(np.clip(abs(data.qpos[3]), 0, 1))
        maximum_tilt = max(maximum_tilt, float(2*np.arccos(qw)))
        peak_joint_delta = max(peak_joint_delta, float(np.max(np.abs(data.qpos[7:7+model.nu]-home_qpos[7:7+model.nu]))))
        pairs = list(_contact_names(model, data))
        if request.robot_id == 'unitree_g1':
            hand = data.body('right_hand_middle_0_link').xpos
            parcel = data.body('parcel').xpos
            min_hand_goal_distance = min(min_hand_goal_distance, float(np.linalg.norm(hand-parcel)))
            max_parcel_height = max(max_parcel_height, float(parcel[2]))
            task_contacts += sum(any('parcel_box' in name for name in pair) and any('hand' in name for name in pair) for pair in pairs)
        elif request.robot_id == 'apptronik_apollo':
            hand = data.geom_xpos[model.geom('collision_r_hand_plate').id]
            handle = data.geom_xpos[model.geom('switch_handle').id]
            min_hand_goal_distance = min(min_hand_goal_distance, float(np.linalg.norm(hand-handle)))
            max_switch_angle = max(max_switch_angle, abs(float(data.qpos[model.jnt_qposadr[model.joint('switch_hinge').id]])))
            contact_count = sum(any('switch_handle' in name for name in pair) and any('collision_r_hand_plate' in name for name in pair) for pair in pairs)
            task_contacts += contact_count
            had_hand_switch_contact |= bool(contact_count)
            if had_hand_switch_contact:
                max_switch_angle_after_contact = max(max_switch_angle_after_contact, abs(float(data.qpos[model.jnt_qposadr[model.joint('switch_hinge').id]])))
                if switch_activation_time_s is None and max_switch_angle_after_contact >= .3:
                    switch_activation_time_s = float(data.time)
        else:
            foot_contacts, contact_slip = _terrain_foot_contacts(model, data)
            task_contacts += foot_contacts
            foot_slip_m_s = max(foot_slip_m_s, contact_slip)
        if (step+1) % sample_stride == 0 or step == steps-1:
            # mj_step integrates qpos after its forward pass. Refresh derived
            # transforms so each replay frame matches its recorded qpos/time.
            mj.mj_forward(model, data)
            frames.append(_frame(model, data))
    fallen = minimum_height < ({'unitree_g1':.48, 'apptronik_apollo':.65, 'unitree_h1':.55}[request.robot_id]) or maximum_tilt > .75
    if request.robot_id == 'unitree_g1':
        success = not fallen and task_contacts > 0 and max_parcel_height > .85 and float(data.body('parcel').xpos[0]) > 1.35
        reason = None if success else 'fall' if fallen else 'parcel_not_transported'
    elif request.robot_id == 'apptronik_apollo':
        success = not fallen and bool(planning and planning['feasible']) and task_contacts > 0 and switch_activation_time_s is not None
        reason = None if success else 'fall' if fallen else 'switch_not_actuated'
    else:
        success = not fallen and float(data.qpos[0]) > 3.5 and foot_slip_m_s < .4
        reason = None if success else 'fall' if fallen else 'terrain_incomplete'
    final_state = np.zeros(mj.mj_stateSize(model, STATE))
    mj.mj_getState(model, data, final_state, STATE)
    scene_geometry_hash = configured_digest(request.robot_id)
    return {'schema_version': 'vivacity.humanoid-trial/1.0', 'robot_id': request.robot_id,
            'environment_id': MODELS[request.robot_id][2], 'action': request.action,
            'parameters': request.model_dump(), 'seed': request.seed,
            'model_hash': digest, 'scene_geometry_hash': scene_geometry_hash,
            'simulator_version': mj.__version__,
            'status': 'completed', 'task_success': bool(success), 'failure_reason': reason,
            'planning': planning,
            'initial_frame': initial, 'frames': frames, 'final_frame': frames[-1],
            'final_integration_state': final_state.tolist(),
            'measurements': {'simulation_steps': steps, 'simulation_duration_s': float(data.time),
                             'compute_wall_s': time.perf_counter()-start,
                             'minimum_base_height_m': minimum_height, 'maximum_base_tilt_rad': maximum_tilt,
                             'peak_joint_delta_rad': peak_joint_delta, 'minimum_hand_goal_distance_m': min_hand_goal_distance if np.isfinite(min_hand_goal_distance) else None,
                             'task_contact_samples': int(task_contacts), 'maximum_parcel_height_m': max_parcel_height if request.robot_id == 'unitree_g1' else None,
                             'maximum_switch_angle_rad': max_switch_angle if request.robot_id == 'apptronik_apollo' else None,
                             'maximum_switch_angle_after_hand_contact_rad': max_switch_angle_after_contact if request.robot_id == 'apptronik_apollo' else None,
                             'switch_activation_time_s': switch_activation_time_s if request.robot_id == 'apptronik_apollo' else None,
                             'maximum_foot_slip_m_s': foot_slip_m_s if request.robot_id == 'unitree_h1' else None,
                             'final_base_position_m': data.qpos[:3].tolist(), 'fallen': bool(fallen)},
            'scope': 'Simulated joint-control probe; task success requires measured contact and completion.'}


class HumanoidTrialService:
    def __init__(self, store: Store):
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='humanoid-physics')
        self.lock = threading.Lock()
        self.active = 0
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS humanoid_trials(id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL)')
            for trial_id, payload in db.execute('SELECT id,payload FROM humanoid_trials'):
                record = json.loads(payload)
                if record['status'] in ('queued', 'running'):
                    record.update(status='failed', error='worker_interrupted_by_restart')
                    db.execute('UPDATE humanoid_trials SET payload=? WHERE id=?', (encode(record), trial_id))

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=False)

    def _save(self, owner, record):
        with self.store.connect() as db:
            db.execute('INSERT INTO humanoid_trials(id,owner,payload) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                       (record['id'], owner, encode(record)))

    def get(self, owner, trial_id):
        with self.store.connect() as db:
            row = db.execute('SELECT payload FROM humanoid_trials WHERE id=? AND owner=?', (trial_id, owner)).fetchone()
        if row is None:
            raise KeyError(trial_id)
        return json.loads(row[0])

    def list(self, owner, robot_id):
        if robot_id not in MODELS:
            raise ValueError('Unknown humanoid model')
        with self.store.connect() as db:
            rows = [json.loads(row[0]) for row in db.execute(
                'SELECT payload FROM humanoid_trials WHERE owner=? ORDER BY rowid DESC LIMIT 30', (owner,))]
        return [row for row in rows if row['request']['robot_id'] == robot_id][:10]

    def submit(self, owner, request):
        if request.robot_id not in MODELS:
            raise ValueError('Unknown humanoid model')
        with self.lock:
            if self.active >= 2:
                raise ValueError('Humanoid compute capacity reached; retry after a trial finishes')
            self.active += 1
        record = {'id': str(uuid.uuid4()), 'status': 'queued', 'request': request.model_dump(),
                  'created_unix_s': time.time(), 'result': None, 'error': None}
        self._save(owner, record)
        self.executor.submit(self._run, owner, record, request)
        return record

    def _run(self, owner, record, request):
        try:
            record['status'] = 'running'
            self._save(owner, record)
            result = simulate(request)
            record.update(status='completed', result=result)
        except Exception as exc:
            record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        finally:
            self._save(owner, record)
            with self.lock:
                self.active -= 1
