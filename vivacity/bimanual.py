"""Checkpointable G1 frictional manipulation research task.

No equality constraint connects the parcel to either hand. The current native
position-servo controller is a contact baseline, not the completed whole-body
inverse-dynamics release. Keep it distinct from historical fixture trials.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import time
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Literal

import mujoco as mj
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy.spatial.transform import Rotation

from .contact_evidence import body_contact_loads, bilateral_support, descendants
from .execution_checkpoint import capture, restore, ImmutableModelArtifact
from .humanoids import _configured_tree, initial_data, _frame
from .humanoid_pickup import ARM_NAMES
from .physical_parameters import BoxPhysics
from .inverse_dynamics import ControllerInfeasible
from .whole_body_contact import WholeBodyContactController

SOURCE_HASHES = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                 for name in ('bimanual.py', 'contact_evidence.py', 'physical_parameters.py',
                              'inverse_dynamics.py', 'whole_body_contact.py')}


class BimanualConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, frozen=True)
    parcel: BoxPhysics = Field(default_factory=BoxPhysics)
    controller: Literal['native_position', 'inverse_dynamics_experimental'] = 'native_position'
    source_xy_m: tuple[float, float] = (.32, 0.)
    destination_xy_m: tuple[float, float] = (.40, 0.)
    floor_friction: float = Field(default=.8, ge=.1, le=1.5)
    hand_torque_scale: float = Field(default=1., ge=.01, le=1.)
    gravity_m_s2: float = Field(default=9.81, ge=1., le=15.)
    disturbance_n: float = Field(default=0., ge=0, le=150.)
    seed: int = Field(default=7, ge=0, le=2**31-1)
    timeout_s: float = Field(default=22., ge=8., le=30.)

    @model_validator(mode='after')
    def bounded_world(self):
        for point in (self.source_xy_m, self.destination_xy_m):
            if not (.18 <= point[0] <= .7 and -.3 <= point[1] <= .3):
                raise ValueError('positions must remain within the physical table')
        return self


def compile_scene(config: BimanualConfig):
    root, _ = _configured_tree('unitree_g1', config.floor_friction, config.parcel.effective_mass)
    root.remove(root.find('equality'))
    root.find('option').set('gravity', f'0 0 -{config.gravity_m_s2}')
    world = root.find('worldbody')
    for geom in list(world.findall('geom')):
        if geom.get('name') in ('pickup_stand', 'placement_stand'):
            world.remove(geom)
    ET.SubElement(world, 'geom', name='bimanual_table', type='box', pos='.45 0 .72',
                  size='.28 .45 .02', rgba='.4 .4 .4 1', friction='.8 .005 .0001')
    ET.SubElement(world, 'geom', name='bimanual_table_leg', type='box', pos='.62 0 .35',
                  size='.03 .35 .35', rgba='.3 .3 .3 1')
    body = root.find(".//body[@name='parcel']")
    x, y = config.source_xy_m
    body.set('pos', f'{x} {y} {.74+config.parcel.dimensions_m[2]/2}')
    geom = body.find('geom')
    geom.attrib.update(config.parcel.mjcf_geom())
    if config.parcel.mjcf_inertial():
        ET.SubElement(body, 'inertial', **config.parcel.mjcf_inertial())
    for side in ('left', 'right'):
        for joint in root.findall(f".//body[@name='{side}_wrist_yaw_link']//joint"):
            if joint.get('actuatorfrcrange'):
                limits = np.fromstring(joint.get('actuatorfrcrange'), sep=' ')*config.hand_torque_scale
                joint.set('actuatorfrcrange', ' '.join(map(str, limits)))
    model = mj.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'))
    return model


def hand_ik(model, initial_qpos, side, target, rotation=None):
    """6D damped least-squares on independent scratch state, within joint limits."""
    scratch = mj.MjData(model)
    scratch.qpos[:] = initial_qpos
    joints = np.array([model.joint(name).id for name in ARM_NAMES[side]])
    qadr, dofs = model.jnt_qposadr[joints], model.jnt_dofadr[joints]
    body = model.body(f'{side}_wrist_yaw_link').id
    rotation = np.eye(3) if rotation is None else np.asarray(rotation)
    jp, jr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
    for _ in range(250):
        mj.mj_forward(model, scratch)
        error = np.asarray(target)-scratch.xpos[body]
        angular = Rotation.from_matrix(rotation @ scratch.xmat[body].reshape(3, 3).T).as_rotvec()
        residual = np.r_[error, .18*angular]
        if np.linalg.norm(residual) < 1e-4:
            break
        mj.mj_jacBody(model, scratch, jp, jr, body)
        jac = np.vstack((jp[:, dofs], .18*jr[:, dofs]))
        delta = jac.T @ np.linalg.solve(jac @ jac.T+np.eye(6)*.0001, residual)
        scratch.qpos[qadr] = np.clip(scratch.qpos[qadr]+np.clip(delta, -.08, .08),
                                    model.jnt_range[joints, 0]+.005, model.jnt_range[joints, 1]-.005)
    return dict(zip(joints, scratch.qpos[qadr])), float(np.linalg.norm(error)), float(np.linalg.norm(angular))


class NativePositionController:
    version = 'vivacity.g1-native-position-contact/1'

    def __init__(self, model):
        self.model = model
        self.commands = np.zeros(model.nu)

    def compute(self, commands, **_):
        self.commands = np.clip(commands, self.model.actuator_ctrlrange[:, 0], self.model.actuator_ctrlrange[:, 1])
        return self.commands.copy()

    def snapshot(self):
        return {'commands': self.commands.tolist()}

    def restore(self, state):
        values = np.asarray(state['commands'], dtype=float)
        if values.shape != (self.model.nu,) or not np.isfinite(values).all():
            raise ValueError('invalid native servo state')
        self.commands = values.copy()


class BimanualTask:
    version = 'vivacity.g1-frictional-carton/1'
    durations = {'raise': 2., 'above': 2., 'approach': 2., 'grip': 1.5,
                 'lift': 2., 'hold': 1., 'transfer': 2., 'lower': 2., 'release': 1.5, 'settle': 1.}

    def __init__(self, config: BimanualConfig):
        self.config = config
        self.model = compile_scene(config)
        self.data = initial_data(self.model)
        original_ctrl = self.data.ctrl.copy()
        self.controller = (NativePositionController(self.model) if config.controller == 'native_position'
                           else WholeBodyContactController(self.model, convert_model=True))
        if config.controller != 'native_position':
            self.data.ctrl[:] = 0.
            mj.mj_forward(self.model, self.data)
        self.rng = np.random.default_rng(config.seed)
        self.model_artifact = ImmutableModelArtifact(self.model)
        self.world_version = hashlib.sha256((self.model_artifact.sha256+self.version+config.model_dump_json()).encode()).hexdigest()
        self.state = {
            'source_sha256': dict(SOURCE_HASHES),
            'phase': 'raise', 'phase_start_s': 0., 'steps': 0, 'next_frame_seq': 0,
            'status': 'running', 'failure': None, 'events': [],
            'home': original_ctrl.tolist(), 'start': original_ctrl.tolist(), 'goal': [],
            'previous_targets': original_ctrl.tolist(),
            'minimum_base_height_m': float(self.data.qpos[2]), 'maximum_base_tilt_rad': 0.,
            'maximum_parcel_clearance_m': 0., 'maximum_joint_limit_error_rad': 0.,
            'bilateral_hold_samples': 0, 'hold_samples': 0, 'minimum_hold_share': 1.,
            'maximum_hold_force_balance_error_n': 0., 'support_before_release': False,
            'unsupported_transport_samples': 0, 'retained_transport_samples': 0,
            'maximum_transport_force_balance_error_n': 0.,
            'grip_contact_observed': False, 'maximum_grip_slip_m': 0.,
            'release_time_s': None, 'prohibited_contacts': [],
            'last_measurement': {}, 'planning': [],
        }
        self._bind()
        self._enter('raise', {'left': [.04, .24, 1.], 'right': [.04, -.24, 1.]})

    def _bind(self):
        self.parcel_id = self.model.body('parcel').id
        self.parcel_dof = int(self.model.jnt_dofadr[self.model.joint('parcel_free').id])
        self.groups = {side: descendants(self.model, f'{side}_wrist_yaw_link') for side in ('left', 'right')}
        self.limited = np.flatnonzero(self.model.jnt_limited)
        self.actuator_joints = self.model.actuator_trnid[:, 0]

    def _hands(self):
        return {side: self.data.body(f'{side}_wrist_yaw_link').xpos.copy() for side in self.groups}

    def _enter(self, phase, targets=None):
        state = self.state
        state['phase'], state['phase_start_s'] = phase, float(self.data.time)
        state['start'] = list(state['previous_targets'])
        goal = np.asarray(state['previous_targets']).copy()
        state['hand_tasks'] = {}
        for side in self.groups:
            wrist = self.data.body(f'{side}_wrist_yaw_link')
            state['hand_tasks'][side] = {'start_position': wrist.xpos.tolist(),
                'start_rotation': wrist.xmat.reshape(3, 3).tolist(),
                'position': np.asarray(targets[side]).tolist() if targets else wrist.xpos.tolist(),
                'rotation': (wrist.xmat.reshape(3, 3) if not targets or phase == 'release' else np.eye(3)).tolist()}
        if targets is not None:
            goal = np.asarray(state['home']).copy()
            errors = {}
            for side, target in targets.items():
                orientation = self.data.body(f'{side}_wrist_yaw_link').xmat.reshape(3, 3).copy() if phase == 'release' else None
                joints, position, rotation = hand_ik(self.model, self.data.qpos.copy(), side, target, orientation)
                errors[side] = {'position_m': position, 'rotation_rad': rotation}
                for aid, joint in enumerate(self.actuator_joints):
                    if int(joint) in joints:
                        goal[aid] = joints[int(joint)]
            state['planning'].append({'phase': phase, 'errors': errors})
            if any(error['position_m'] > .05 or error['rotation_rad'] > .3 for error in errors.values()):
                self._fail('unreachable_target')
        state['goal'] = goal.tolist()
        state['events'].append({'phase': phase, 'time_s': float(self.data.time),
                                'measurement': deepcopy(state['last_measurement'])})

    def _fail(self, reason):
        self.state['status'], self.state['failure'] = 'failed', reason

    def _measure(self):
        model, data = self.model, self.data
        loads = body_contact_loads(model, data, self.parcel_id, self.groups)
        az = float(data.qacc[self.parcel_dof+2])
        support = bilateral_support(loads, self.config.parcel.effective_mass, self.config.gravity_m_s2, az)
        parcel = data.xpos[self.parcel_id].copy()
        half = model.geom('parcel_box').size
        bottom = float(parcel[2]-np.abs(data.xmat[self.parcel_id].reshape(3, 3)[2]) @ half)
        tilt = float(np.arccos(np.clip(data.body('pelvis').xmat.reshape(3,3)[2, 2], -1, 1)))
        q = data.qpos[model.jnt_qposadr[self.limited]]
        limit_error = float(np.max(np.maximum(np.maximum(model.jnt_range[self.limited, 0]-q,
                                                         q-model.jnt_range[self.limited, 1]), 0.)))
        prohibited = []
        hands = set.union(*self.groups.values())
        floor, table = model.geom('floor').id, model.geom('bimanual_table').id
        for contact in data.contact[:data.ncon]:
            if contact.dist > 0:
                continue
            geoms = (int(contact.geom1), int(contact.geom2))
            for fixture in (floor, table, model.geom('bimanual_table_leg').id):
                if fixture in geoms:
                    other = geoms[1] if geoms[0] == fixture else geoms[0]
                    body = int(model.geom_bodyid[other])
                    name = model.body(body).name
                    if body not in (0, self.parcel_id) and body not in hands:
                        if fixture != floor or 'ankle' not in name:
                            prohibited.append(f'{model.geom(fixture).name}:{name}')
        return {'parcel_position_m': parcel.tolist(), 'parcel_clearance_m': bottom-.74,
                'parcel_speed_m_s': float(np.linalg.norm(data.qvel[self.parcel_dof:self.parcel_dof+3])),
                'base_height_m': float(data.qpos[2]), 'base_tilt_rad': tilt,
                'joint_limit_error_rad': limit_error, 'prohibited_contacts': sorted(set(prohibited)),
                'loads': {name: load.as_dict() for name, load in loads.items()},
                'support': support, 'destination_error_m': float(np.linalg.norm(parcel[:2]-self.config.destination_xy_m))}

    def step(self):
        if self.state['status'] != 'running':
            return
        s = self.state
        phase = s['phase']
        elapsed = float(self.data.time)-s['phase_start_s']
        progress = min(1., elapsed/(self.durations[phase]*.8))
        blend = progress*progress*(3-2*progress)
        commands = np.asarray(s['start'])+(np.asarray(s['goal'])-s['start'])*blend
        hand_targets = None
        if self.config.controller != 'native_position':
            hand_targets = {}
            for side, task in s['hand_tasks'].items():
                initial_rotation = np.asarray(task['start_rotation'])
                delta = Rotation.from_matrix(np.asarray(task['rotation']) @ initial_rotation.T).as_rotvec()
                hand_targets[side] = {'position': np.asarray(task['start_position'])+blend*(np.asarray(task['position'])-task['start_position']),
                                      'rotation': Rotation.from_rotvec(blend*delta).as_matrix() @ initial_rotation}
        try:
            self.data.ctrl[:] = self.controller.compute(commands, data=self.data, hand_targets=hand_targets)
        except ControllerInfeasible as exc:
            s['controller_error'] = str(exc)
            self._fail('controller_infeasible')
            return
        s['previous_targets'] = commands.tolist()
        self.data.xfrc_applied[self.model.body('pelvis').id, 0] = self.config.disturbance_n if 8. <= self.data.time < 8.25 else 0.
        mj.mj_step(self.model, self.data)
        mj.mj_forward(self.model, self.data)
        s['steps'] += 1
        m = self._measure()
        s['last_measurement'] = m
        s['minimum_base_height_m'] = min(s['minimum_base_height_m'], m['base_height_m'])
        s['maximum_base_tilt_rad'] = max(s['maximum_base_tilt_rad'], m['base_tilt_rad'])
        s['maximum_parcel_clearance_m'] = max(s['maximum_parcel_clearance_m'], m['parcel_clearance_m'])
        s['maximum_joint_limit_error_rad'] = max(s['maximum_joint_limit_error_rad'], m['joint_limit_error_rad'])
        s['prohibited_contacts'] = sorted(set(s['prohibited_contacts']+m['prohibited_contacts']))
        if not np.isfinite(self.data.qpos).all():
            self._fail('nonfinite_state')
        elif m['base_height_m'] < .7 or m['base_tilt_rad'] > .25:
            self._fail('unstable_stance')
        elif m['prohibited_contacts']:
            self._fail('prohibited_collision')
        elif m['joint_limit_error_rad'] > .05:
            self._fail('joint_limit_violation')
        elif self.data.time >= self.config.timeout_s:
            self._fail('task_timeout')
        if s['status'] != 'running':
            return
        if phase == 'grip':
            s['grip_contact_observed'] |= min(m['loads'][side]['normal_force_n'] for side in self.groups) >= 1.
            s['maximum_grip_slip_m'] = max(s['maximum_grip_slip_m'], float(np.linalg.norm(
                np.asarray(m['parcel_position_m'][:2])-self.config.source_xy_m)))
        if phase == 'hold' and elapsed >= .3:
            s['hold_samples'] += 1
            support = m['support']
            good = support['bilateral_load'] and support['unsupported_by_environment']
            s['bilateral_hold_samples'] += int(good)
            share = min(support['left_fraction'] or 0., support['right_fraction'] or 0.)
            s['minimum_hold_share'] = min(s['minimum_hold_share'], share)
            s['maximum_hold_force_balance_error_n'] = max(s['maximum_hold_force_balance_error_n'], abs(support['force_balance_error_n']))
        if phase in ('lift', 'hold', 'transfer', 'lower') and m['parcel_clearance_m'] > .015:
            s['unsupported_transport_samples'] += 1
            support = m['support']
            retained = (support['unsupported_by_environment'] and
                        min(m['loads'][side]['normal_force_n'] for side in self.groups) > 1. and
                        min(support['left_vertical_n'], support['right_vertical_n']) > 0.)
            s['retained_transport_samples'] += int(retained)
            s['maximum_transport_force_balance_error_n'] = max(
                s['maximum_transport_force_balance_error_n'], abs(support['force_balance_error_n']))
            if not retained:
                self._fail('retention_lost')
                return
        if elapsed+1e-8 < self.durations[phase]:
            return
        x, y = self.config.source_xy_m
        z = .74+self.config.parcel.dimensions_m[2]/2
        half_width = self.config.parcel.dimensions_m[1]/2+.025
        if phase == 'raise':
            self._enter('above', {'left': [x-.10, y+half_width+.07, z+.16], 'right': [x-.10, y-half_width-.07, z+.16]})
        elif phase == 'above':
            self._enter('approach', {'left': [x-.10, y+half_width+.07, z], 'right': [x-.10, y-half_width-.07, z]})
        elif phase == 'approach':
            self._enter('grip', {'left': [x-.10, y+half_width, z], 'right': [x-.10, y-half_width, z]})
        elif phase == 'grip':
            if min(m['loads'][side]['normal_force_n'] for side in self.groups) < 4.:
                self._fail('grip_slipped' if s['grip_contact_observed'] and s['maximum_grip_slip_m'] > .04
                           else 'insufficient_grip_contact')
            else:
                self._enter('lift', {'left': [x-.10, y+half_width, z+.14], 'right': [x-.10, y-half_width, z+.14]})
        elif phase == 'lift':
            if m['parcel_clearance_m'] < .04 or not m['support']['unsupported_by_environment']:
                self._fail('lift_not_clear')
            else:
                self._enter('hold')
        elif phase == 'hold':
            if not s['hold_samples'] or s['bilateral_hold_samples'] != s['hold_samples']:
                self._fail('bilateral_load_not_sustained')
            else:
                # Use measured object displacement to close the placement loop.
                shift = np.r_[np.asarray(self.config.destination_xy_m)-np.asarray(m['parcel_position_m'][:2]), 0.]
                self._enter('transfer', {side: point+shift for side, point in self._hands().items()})
        elif phase == 'transfer':
            if not m['support']['bilateral_load'] or not m['support']['unsupported_by_environment']:
                self._fail('retention_lost')
            else:
                shift = np.r_[np.asarray(self.config.destination_xy_m)-m['parcel_position_m'][:2], -m['parcel_clearance_m']-.003]
                self._enter('lower', {side: point+shift for side, point in self._hands().items()})
        elif phase == 'lower':
            if m['support']['other_vertical_n'] < .8*self.config.parcel.effective_mass*self.config.gravity_m_s2:
                self._fail('destination_not_supporting_load')
            else:
                s['support_before_release'], s['release_time_s'] = True, float(self.data.time)
                hands = self._hands()
                hands['left'][1] += .09
                hands['right'][1] -= .09
                self._enter('release', hands)
        elif phase == 'release':
            self._enter('settle')
        elif phase == 'settle':
            supported = m['support']['other_vertical_n'] > .8*self.config.parcel.effective_mass*self.config.gravity_m_s2
            released = max(m['loads'][side]['normal_force_n'] for side in self.groups) < .1
            if m['destination_error_m'] > .03:
                self._fail('placement_outside_tolerance')
            elif not supported or not released or m['parcel_speed_m_s'] > .03:
                self._fail('placement_not_settled')
            else:
                s['status'] = 'completed'

    def frame(self):
        frame = _frame(self.model, self.data)
        frame.update(phase=self.state['phase'], measurement=deepcopy(self.state['last_measurement']),
                     grasp_constraint_active=False)
        self.state['next_frame_seq'] += 1
        return frame

    def snapshot(self):
        return capture(self.model, self.data, self.controller, world_version=self.world_version,
                       task_state={'version': self.version, 'config': self.config.model_dump(), 'state': self.state},
                       rng=self.rng, perception_state={'mode': 'simulator_state'}, order_ledger={},
                       next_frame_seq=self.state['next_frame_seq'], steps_completed=self.state['steps'],
                       model_artifact=self.model_artifact)

    @classmethod
    def from_checkpoint(cls, bundle):
        task = cls.__new__(cls)
        state = bundle.checkpoint.task_state
        if state['version'] != cls.version:
            raise ValueError('task version changed')
        if state['state']['source_sha256'] != SOURCE_HASHES:
            raise ValueError('task implementation changed')
        task.config = BimanualConfig.model_validate(state['config'])
        factory = NativePositionController if task.config.controller == 'native_position' else WholeBodyContactController
        task.model, task.data, task.controller, task.rng = restore(bundle, factory)
        task.state = deepcopy(state['state'])
        task.state['next_frame_seq'] = bundle.checkpoint.next_frame_seq
        task.world_version = bundle.checkpoint.world_version
        task.model_artifact = ImmutableModelArtifact(task.model, bundle.model_binary)
        task._bind()
        return task

    def result(self):
        return {'schema_version': self.version, 'controller': self.controller.version,
                'status': self.state['status'], 'task_success': self.state['status'] == 'completed',
                'failure_reason': self.state['failure'], 'parameters': self.config.model_dump(),
                'world_version': self.world_version, 'simulator_version': mj.__version__,
                'model_sha256': self.model_artifact.sha256,
                'source_sha256': dict(self.state['source_sha256']),
                'equality_constraints': self.model.neq, 'measurements': deepcopy(self.state),
                'scope': ('Experimental stationary frictional carton transfer using '+
                          ('native G1 finger and arm servos' if self.config.controller == 'native_position'
                           else 'experimental constrained inverse dynamics')+
                          '. No weld, locomotion, camera perception, or hardware validation.')}


def run_bimanual(config: BimanualConfig, on_frame=None):
    started = time.perf_counter()
    task = BimanualTask(config)
    frames = [task.frame()]
    if on_frame:
        on_frame(frames[-1], task)
    while task.state['status'] == 'running':
        task.step()
        if task.state['steps'] % 25 == 0 or task.state['status'] != 'running':
            frames.append(task.frame())
            if on_frame:
                on_frame(frames[-1], task)
    result = task.result()
    result['compute_wall_s'] = time.perf_counter()-started
    result['frames'] = frames
    return result
