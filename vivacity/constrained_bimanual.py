"""Versioned experimental G1 carton task using bounded contact-wrench control.

This is separate from the accepted native-servo baseline. Passing that baseline
does not qualify this model/controller combination. No pose writes drive a step.
"""
from copy import deepcopy
import hashlib
from pathlib import Path

import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation

from .bimanual import BimanualConfig, BimanualTask, SOURCE_HASHES
from .contact_evidence import descendants
from .execution_checkpoint import ImmutableModelArtifact, restore
from .whole_body_contact import WholeBodyContactController
from .wrench_dynamics import WrenchInverseDynamics


CONTROLLER_HASHES = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                     for name in ('constrained_bimanual.py', 'wrench_dynamics.py')}


class ConstrainedCartonController(WholeBodyContactController):
    version = 'vivacity.g1-wrench-carton/1-experimental'

    def __init__(self, model):
        self.model = model
        self.joints = model.actuator_trnid[:, 0]
        self.qadrs = model.jnt_qposadr[self.joints]
        self.home_qpos = model.key_qpos[0].copy()
        self.stiffness = model.actuator_gainprm[:, 0].copy()
        scratch = mj.MjData(model)
        scratch.qpos[:] = self.home_qpos
        mj.mj_forward(model, scratch)
        self.feet = {side: {'position': scratch.body(f'{side}_ankle_roll_link').xpos.tolist(),
                           'rotation': scratch.body(f'{side}_ankle_roll_link').xmat.reshape(3, 3).tolist()}
                     for side in ('left', 'right')}
        self.commands = np.zeros(model.nu)
        self.steps = 0
        self.solver = WrenchInverseDynamics(model)
        self.groups = {side: descendants(model, f'{side}_wrist_yaw_link') for side in ('left', 'right')}
        self.parcel = model.body('parcel').id
        fixtures = [model.geom(name).id for name in ('floor', 'bimanual_table', 'bimanual_table_leg')]
        self.clearance_pairs = []
        for geom in range(model.ngeom):
            body = int(model.geom_bodyid[geom])
            if body in (0, self.parcel) or not (model.geom_contype[geom] or model.geom_conaffinity[geom]):
                continue
            for fixture in fixtures:
                if fixture == fixtures[0] and 'ankle' in model.body(body).name:
                    continue
                # Hand/table contact is allowed by the benchmark during release.
                if fixture != fixtures[0] and any(body in group for group in self.groups.values()):
                    continue
                self.clearance_pairs.append((geom, fixture, .005))
        self.maximum_compute_s = 0.
        self.total_compute_s = 0.

    def compute(self, targets, *, data, hand_targets=None):
        if self.steps % 5 == 0:
            qtarget = self.home_qpos.copy()
            qtarget[self.qadrs] = targets
            tasks, limits = [], []
            for side in ('left', 'right'):
                poses = [('ankle_roll_link', self.feet[side], 1000.)]
                if hand_targets and side in hand_targets:
                    poses.append(('wrist_yaw_link', hand_targets[side], 100.))
                for part, target, weight in poses:
                    body = self.model.body(f'{side}_{part}').id
                    jp, jr = np.zeros((3, self.model.nv)), np.zeros((3, self.model.nv))
                    djp, djr = np.zeros_like(jp), np.zeros_like(jr)
                    mj.mj_jacBody(self.model, data, jp, jr, body)
                    mj.mj_jacDot(self.model, data, djp, djr, data.xpos[body], body)
                    jac = np.vstack((jp, .2*jr))
                    bias = np.vstack((djp, .2*djr)) @ data.qvel
                    angular = Rotation.from_matrix(np.asarray(target['rotation']) @ data.xmat[body].reshape(3, 3).T).as_rotvec()
                    error = np.r_[np.asarray(target['position'])-data.xpos[body], .2*angular]
                    acceleration = 200.*error-30.*(jac @ data.qvel)-bias
                    tasks.append((jac, acceleration, weight))
                    if part == 'ankle_roll_link' and data.time > .15:
                        # Compliant support permits bounded corrective acceleration;
                        # it is not an invisible weld or a fixed root constraint.
                        limits.append((jac, acceleration-2., acceleration+2.))
            force_targets = {}
            for side, group in self.groups.items():
                contacts = [i for i, c in enumerate(data.contact[:data.ncon])
                            if self.parcel in (self.model.geom_bodyid[c.geom1], self.model.geom_bodyid[c.geom2])
                            and (self.model.geom_bodyid[c.geom1] in group or self.model.geom_bodyid[c.geom2] in group)
                            and c.dist <= .001 and c.efc_address >= 0]
                for index in contacts:
                    force_targets[index] = 25./len(contacts)
            reference = (self.stiffness*np.asarray(targets)+self.model.actuator_biasprm[:, 0]
                +self.model.actuator_biasprm[:, 1]*data.actuator_length
                +self.model.actuator_biasprm[:, 2]*data.actuator_velocity)
            solution = self.solver.compute(data, qtarget, torque_reference=reference,
                command_reference=targets, torque_weight=10000.,
                extra_tasks=tasks, acceleration_limits=limits, clearance_pairs=self.clearance_pairs,
                normal_force_targets=force_targets)
            self.commands = solution.commands
            self.maximum_compute_s = max(self.maximum_compute_s, solution.compute_s)
            self.total_compute_s += solution.compute_s
        self.steps += 1
        return self.commands.copy()

class ConstrainedBimanualTask(BimanualTask):
    version = 'vivacity.g1-constrained-carton/1-experimental'

    def __init__(self, config):
        super().__init__(config.model_copy(update={'controller': 'native_position'}))
        self.config = config.model_copy(update={'controller': 'inverse_dynamics_experimental'})
        self.controller = ConstrainedCartonController(self.model)
        self.world_version = hashlib.sha256((self.model_artifact.sha256+self.version+
            self.config.model_dump_json()+repr(sorted(CONTROLLER_HASHES.items()))).encode()).hexdigest()
        self.state['controller_source_sha256'] = dict(CONTROLLER_HASHES)
        self.state['lower_adjustments'] = 0
        self.state['lift_adjustments'] = 0
        self.state['maximum_actuator_torque_fraction'] = 0.

    def step(self):
        state = self.state
        if (state['status'] == 'running' and state['phase'] == 'lift'
                and self.data.time-state['phase_start_s'] >= self.durations['lift']-1e-8
                and state['last_measurement']['parcel_clearance_m'] < .045
                and state['lift_adjustments'] < 2):
            state['lift_adjustments'] += 1
            correction = min(.05, .06-state['last_measurement']['parcel_clearance_m'])
            targets = {side: np.asarray(task['position'])+[0., 0., correction]
                       for side, task in state['hand_tasks'].items()}
            self._enter('lift', targets)
        if (state['status'] == 'running' and state['phase'] == 'lower'
                and self.data.time-state['phase_start_s'] >= self.durations['lower']-1e-8
                and state['last_measurement']['support']['other_vertical_n']
                < .8*self.config.parcel.effective_mass*self.config.gravity_m_s2
                and state['lower_adjustments'] < 2):
            # Do not release while the hands still carry most of the weight.
            # A bounded downward correction transfers load to the destination;
            # unchanged support thresholds and the global timeout still apply.
            state['lower_adjustments'] += 1
            targets = {side: np.asarray(task['position'])+[0., 0., -.006]
                       for side, task in state['hand_tasks'].items()}
            self._enter('lower', targets)
        super().step()
        force = np.abs(self.data.qfrc_actuator[self.model.jnt_dofadr[self.actuator_joints]])
        limit = np.max(np.abs(self.model.jnt_actfrcrange[self.actuator_joints]), axis=1)
        fraction = float(np.max(force/limit))
        state['maximum_actuator_torque_fraction'] = max(state['maximum_actuator_torque_fraction'], fraction)
        if fraction > 1.00001:
            self._fail('actuator_torque_limit_violation')

    @classmethod
    def from_checkpoint(cls, bundle):
        state = bundle.checkpoint.task_state
        if (state['version'] != cls.version or state['state']['source_sha256'] != SOURCE_HASHES
                or state['state'].get('controller_source_sha256') != CONTROLLER_HASHES):
            raise ValueError('constrained task implementation changed')
        task = cls.__new__(cls)
        task.config = BimanualConfig.model_validate(state['config'])
        task.model, task.data, task.controller, task.rng = restore(bundle, ConstrainedCartonController)
        task.state = deepcopy(state['state'])
        task.state['next_frame_seq'] = bundle.checkpoint.next_frame_seq
        task.world_version = bundle.checkpoint.world_version
        task.model_artifact = ImmutableModelArtifact(task.model, bundle.model_binary)
        task._bind()
        return task

    def result(self):
        result = super().result()
        result['controller_source_sha256'] = dict(CONTROLLER_HASHES)
        result['controller_diagnostics'] = self.controller.solver.snapshot()
        result['controller_diagnostics'].update(maximum_compute_s=self.controller.maximum_compute_s,
                                              total_compute_s=self.controller.total_compute_s,
                                              clearance_pair_count=len(self.controller.clearance_pairs))
        return result
