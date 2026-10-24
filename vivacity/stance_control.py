"""Development whole-body standing controller for complete embodiments.

This controller does not implement locomotion. Its contact wrenches are solver
predictions; native force sensors, root pose and slip must independently decide
whether a trial remained stable. No root pose or applied support force is set.
"""
from copy import deepcopy

import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation

from .humanoid_embodiments import FEET, ROOTS
from .wrench_dynamics import WrenchInverseDynamics


class StanceController:
    version = 'vivacity.complete-humanoid-stance/1-experimental'

    def __init__(self, model, identity, *, reference_weight=None):
        self.model, self.identity = model, identity
        self.solver = WrenchInverseDynamics(model)
        self.reference_weight = float(reference_weight if reference_weight is not None
                                      else {'h1':.2, 'apollo':10., 'g1':10.}[identity])
        self.steps = 0
        self.commands = model.key_ctrl[0].copy()
        self.target = model.key_qpos[0].copy()
        self.joints = model.actuator_trnid[:, 0]
        self.qadr = model.jnt_qposadr[self.joints]
        self.dofs = model.jnt_dofadr[self.joints]
        self.root = model.body(ROOTS[identity]).id
        scratch = mj.MjData(model)
        mj.mj_resetDataKeyframe(model, scratch, 0)
        mj.mj_forward(model, scratch)
        self.feet = {name:{'position':scratch.body(name).xpos.tolist(),
                           'rotation':scratch.body(name).xmat.reshape(3, 3).tolist()} for name in FEET[identity]}
        self.center = scratch.subtree_com[self.root].copy()
        self.center[:2] = np.mean([value['position'][:2] for value in self.feet.values()], axis=0)

    def compute(self, data, target_qpos=None, *, site_targets=None):
        if self.steps % 5 == 0:
            model = self.model
            target = self.target if target_qpos is None else np.asarray(target_qpos)
            tasks, limits = [], []
            for name, reference in self.feet.items():
                body = model.body(name).id
                jp, jr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
                dp, dr = np.zeros_like(jp), np.zeros_like(jr)
                mj.mj_jacBody(model, data, jp, jr, body)
                mj.mj_jacDot(model, data, dp, dr, data.xpos[body], body)
                jac = np.vstack((jp, .2*jr))
                rotation = Rotation.from_matrix(np.asarray(reference['rotation']) @ data.xmat[body].reshape(3, 3).T).as_rotvec()
                error = np.r_[np.asarray(reference['position'])-data.xpos[body], .2*rotation]
                acceleration = 80.*error-18.*(jac @ data.qvel)-np.vstack((dp, .2*dr)) @ data.qvel
                tasks.append((jac, acceleration, 500.))
                if data.time > .15:
                    limits.append((jac, acceleration-2., acceleration+2.))
            jc = np.zeros((3, model.nv))
            mj.mj_jacSubtreeCom(model, data, jc, self.root)
            tasks.append((jc, 80.*(self.center-data.subtree_com[self.root])-18.*(jc @ data.qvel), 300.))
            jr = np.zeros((3, model.nv))
            mj.mj_jacBody(model, data, None, jr, self.root)
            angular_error = Rotation.from_matrix(data.xmat[self.root].reshape(3, 3).T).as_rotvec()
            tasks.append((jr, 100.*angular_error-20.*(jr @ data.qvel), 300.))
            for name, pose in (site_targets or {}).items():
                site = model.site(name).id
                jp, jr = np.zeros((3,model.nv)), np.zeros((3,model.nv))
                mj.mj_jacSite(model, data, jp, jr, site)
                jac = np.vstack((jp,.2*jr))
                angular = Rotation.from_matrix(np.asarray(pose['rotation']) @ data.site_xmat[site].reshape(3,3).T).as_rotvec()
                error = np.r_[np.asarray(pose['position'])-data.site_xpos[site],.2*angular]
                weight = float(pose.get('weight', 300.))
                if not np.isfinite(weight) or not 1. <= weight <= 10000.:
                    raise ValueError('site tracking weight must be finite and bounded')
                tasks.append((jac,150.*error-25.*(jac @ data.qvel),weight))
            native_bias = (model.actuator_biasprm[:, 0]+model.actuator_biasprm[:, 1]*data.actuator_length
                           +model.actuator_biasprm[:, 2]*data.actuator_velocity)
            servo = model.actuator_biastype == mj.mjtBias.mjBIAS_AFFINE
            pd = 100.*(target[self.qadr]-data.qpos[self.qadr])-4.*data.qvel[self.dofs]
            force_reference = np.where(servo, model.actuator_gainprm[:, 0]*target[self.qadr]+native_bias, pd)
            solution = self.solver.compute(data, target, torque_reference=force_reference,
                torque_weight=self.reference_weight, extra_tasks=tasks, acceleration_limits=limits)
            self.commands = solution.commands
        self.steps += 1
        return self.commands.copy()

    def snapshot(self):
        return {'identity':self.identity, 'steps':self.steps, 'reference_weight':self.reference_weight,
                'commands':self.commands.tolist(),
                'target':self.target.tolist(), 'feet':deepcopy(self.feet),
                'center':self.center.tolist(), 'solver':self.solver.snapshot()}

    def restore(self, state):
        if state['identity'] != self.identity:
            raise ValueError('stance embodiment changed')
        for key, shape in (('commands',(self.model.nu,)), ('target',(self.model.nq,)), ('center',(3,))):
            value = np.asarray(state[key], dtype=float)
            if value.shape != shape or not np.isfinite(value).all():
                raise ValueError('invalid stance checkpoint')
            setattr(self, key, value.copy())
        self.steps = int(state['steps'])
        self.reference_weight = float(state['reference_weight'])
        self.feet = deepcopy(state['feet'])
        self.solver.restore(state['solver'])
