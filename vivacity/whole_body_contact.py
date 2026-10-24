"""Experimental constrained G1 stance/manipulation controller.

This is kept separate from the passing native-servo baseline until full task
acceptance passes. Its predicted forces never feed the success evaluator.
"""
from __future__ import annotations

import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation

from .inverse_dynamics import ConstrainedInverseDynamics


class WholeBodyContactController:
    version = 'vivacity.g1-whole-body-contact/1-experimental'

    def __init__(self, model, *, convert_model=False):
        self.model = model
        self.joints = model.actuator_trnid[:, 0]
        self.qadrs = model.jnt_qposadr[self.joints]
        self.home_qpos = model.key_qpos[0].copy()
        self.stiffness = model.actuator_gainprm[:, 0].copy()
        if convert_model:
            damping = -model.actuator_biasprm[:, 2].copy()
            for i, joint in enumerate(self.joints):
                model.dof_damping[model.jnt_dofadr[joint]] += damping[i]
                model.actuator_ctrlrange[i] = model.jnt_actfrcrange[joint]
            model.actuator_gainprm[:] = 0
            model.actuator_gainprm[:, 0] = 1
            model.actuator_biasprm[:] = 0
            model.actuator_biastype[:] = int(mj.mjtBias.mjBIAS_NONE)
            model.actuator_ctrllimited[:] = True
        self.solver = ConstrainedInverseDynamics(model)
        scratch = mj.MjData(model)
        scratch.qpos[:] = self.home_qpos
        mj.mj_forward(model, scratch)
        self.feet = {side: {'position': scratch.body(f'{side}_ankle_roll_link').xpos.tolist(),
                           'rotation': scratch.body(f'{side}_ankle_roll_link').xmat.reshape(3, 3).tolist()}
                     for side in ('left', 'right')}
        self.commands = np.zeros(model.nu)
        self.steps = 0

    def compute(self, targets, *, data, hand_targets=None):
        if self.steps % 5 == 0:
            qtarget = self.home_qpos.copy()
            qtarget[self.qadrs] = targets
            tasks = []
            for side in ('left', 'right'):
                poses = [('ankle_roll_link', self.feet[side], 1000.)]
                if hand_targets and side in hand_targets:
                    poses.append(('wrist_yaw_link', hand_targets[side], 100.))
                for part, target, weight in poses:
                    body = self.model.body(f'{side}_{part}').id
                    jp, jr = np.zeros((3, self.model.nv)), np.zeros((3, self.model.nv))
                    mj.mj_jacBody(self.model, data, jp, jr, body)
                    jac = np.vstack((jp, .2*jr))
                    angular = Rotation.from_matrix(np.asarray(target['rotation']) @ data.xmat[body].reshape(3,3).T).as_rotvec()
                    error = np.r_[np.asarray(target['position'])-data.xpos[body], .2*angular]
                    tasks.append((jac, 200.*error-30.*(jac @ data.qvel), weight))
            reference = self.stiffness*(np.asarray(targets)-data.qpos[self.qadrs])
            self.commands = self.solver.compute(data, qtarget, torque_reference=reference,
                                                torque_weight=.01, base_weight=40., extra_tasks=tasks).commands
        self.steps += 1
        return self.commands.copy()

    def snapshot(self):
        return {'solver': self.solver.snapshot(), 'steps': self.steps,
                'commands': self.commands.tolist(), 'stiffness': self.stiffness.tolist(),
                'feet': self.feet, 'home_qpos': self.home_qpos.tolist()}

    def restore(self, state):
        self.solver.restore(state['solver'])
        self.steps = state['steps']
        self.commands, self.stiffness = np.asarray(state['commands']), np.asarray(state['stiffness'])
        self.home_qpos = np.asarray(state['home_qpos'])
        self.feet = state['feet']
