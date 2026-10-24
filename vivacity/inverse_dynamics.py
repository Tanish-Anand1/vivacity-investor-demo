"""Bounded whole-model inverse dynamics for contact manipulation research.

The QP optimizes generalized acceleration, actuator torque and contact force.
Its commands are applied only through motor actuators. Contact forces here are
predictions; acceptance uses independent mj_contactForce measurements.
"""
from __future__ import annotations

from dataclasses import dataclass
import time

import mujoco as mj
import numpy as np
import osqp
from scipy import sparse


class ControllerInfeasible(RuntimeError):
    pass


@dataclass
class DynamicsSolution:
    commands: np.ndarray
    acceleration: np.ndarray
    contact_forces: np.ndarray
    status: str
    residual: float
    compute_s: float


class ConstrainedInverseDynamics:
    """Actuator bounds, rigid-body dynamics and pyramidal friction constraints.

    This controller is not a locomotion policy. Contact acceleration is a soft
    objective to tolerate MuJoCo's compliant contact model. Joint position and
    velocity bounds use a short predictive horizon; the task must independently
    detect actual limit/collision violations. No solver output is a success
    certificate. Infeasibility stops the task instead of changing body poses.
    """
    version = 'vivacity.constrained-inverse-dynamics/1'

    def __init__(self, model: mj.MjModel):
        self.model = model
        self.previous_commands = np.zeros(model.nu)
        self.calls = 0
        self.last_status = 'not_run'
        self.actuated_dofs = np.array([model.jnt_dofadr[int(j)]
                                      for j in model.actuator_trnid[:, 0]], dtype=int)
        if not np.all(model.actuator_trntype == mj.mjtTrn.mjTRN_JOINT):
            raise ValueError('inverse dynamics requires direct joint transmissions')
        if not np.all(model.actuator_biastype == mj.mjtBias.mjBIAS_NONE):
            raise ValueError('inverse dynamics requires motor actuators, not position servos')
        if not np.all(model.actuator_ctrllimited):
            raise ValueError('every motor must declare command limits')

    def snapshot(self):
        return {'version': self.version, 'previous_commands': self.previous_commands.tolist(),
                'calls': self.calls, 'last_status': self.last_status}

    def restore(self, state):
        if state['version'] != self.version:
            raise ValueError('controller version mismatch')
        commands = np.asarray(state['previous_commands'], dtype=float)
        if commands.shape != (self.model.nu,) or not np.isfinite(commands).all():
            raise ValueError('invalid controller commands')
        self.previous_commands = commands.copy()
        self.calls, self.last_status = int(state['calls']), state['last_status']

    def compute(self, data: mj.MjData, target_qpos: np.ndarray, *, kp=300., kd=35.,
                posture_weight=1., base_weight=8., extra_tasks=(), torque_reference=None,
                torque_weight=.0001):
        started = time.perf_counter()
        model = self.model
        nv, nu = model.nv, model.nu
        contacts = [c for c in data.contact[:data.ncon] if c.dist <= .001 and c.efc_address >= 0]
        nc = len(contacts)
        n = nv+nu+3*nc
        jac = np.zeros((3*nc, nv))
        friction = []
        jp1, jp2 = np.zeros((3, nv)), np.zeros((3, nv))
        for i, contact in enumerate(contacts):
            mj.mj_jac(model, data, jp1, None, contact.pos, int(model.geom_bodyid[contact.geom1]))
            mj.mj_jac(model, data, jp2, None, contact.pos, int(model.geom_bodyid[contact.geom2]))
            jac[i*3:i*3+3] = contact.frame.reshape(3, 3) @ (jp2-jp1)
            friction.append(max(.0001, min(float(contact.friction[0]), float(contact.friction[1]))))
        error = np.zeros(nv)
        mj.mj_differentiatePos(model, error, 1., data.qpos, target_qpos)
        desired = np.clip(kp*error-kd*data.qvel, -100., 100.)
        weights = np.full(nv, .001)
        weights[self.actuated_dofs] = posture_weight
        if model.njnt and model.jnt_type[0] == mj.mjtJoint.mjJNT_FREE:
            weights[:6] = base_weight
        objective = np.diag(np.r_[weights, np.full(nu, torque_weight), np.full(nc*3, .00002)])
        linear = np.r_[-weights*desired, np.zeros(nu+nc*3)]
        if torque_reference is not None:
            linear[nv:nv+nu] -= torque_weight*np.asarray(torque_reference)
        if nc:
            contact_desired = -30.*(jac @ data.qvel)
            # Penetration correction uses only measured contact distance.
            for i, c in enumerate(contacts):
                contact_desired[3*i] -= 600.*min(float(c.dist), 0.)
            objective[:nv, :nv] += 4.*jac.T @ jac
            linear[:nv] -= 4.*jac.T @ contact_desired
        for task_jac, task_acc, weight in extra_tasks:
            objective[:nv, :nv] += weight*task_jac.T @ task_jac
            linear[:nv] -= weight*task_jac.T @ task_acc

        mass = np.zeros((nv, nv))
        mj.mj_fullM(model, data, mass)
        transmission = np.zeros((nv, nu))
        transmission[self.actuated_dofs, np.arange(nu)] = model.actuator_gear[:, 0]
        equality = np.c_[mass, -transmission, -jac.T]
        # qfrc_smooth contains bias, passive, applied and current actuator force.
        rhs = (data.qfrc_smooth-data.qfrc_actuator).copy()
        # Native joint dry friction is a constraint, not qfrc_passive. Its
        # bounded opposing torque must be overcome to leave a static pose.
        # Smooth the desired direction around zero to avoid sign chatter.
        rhs -= model.dof_frictionloss*np.tanh(error/.01)
        rows, lower, upper = [equality], [rhs], [rhs]
        command_rows = np.zeros((nu, n))
        command_rows[:, nv:nv+nu] = np.eye(nu)
        rows.append(command_rows)
        lower.append(model.actuator_ctrlrange[:, 0])
        upper.append(model.actuator_ctrlrange[:, 1])

        joint_rows, joint_low, joint_high = [], [], []
        for jid in range(model.njnt):
            if not model.jnt_limited[jid] or model.jnt_type[jid] not in (mj.mjtJoint.mjJNT_HINGE, mj.mjtJoint.mjJNT_SLIDE):
                continue
            dof, qadr = int(model.jnt_dofadr[jid]), int(model.jnt_qposadr[jid])
            horizon = .08
            lo, hi = model.jnt_range[jid]
            q, v = data.qpos[qadr], data.qvel[dof]
            row = np.zeros(n)
            row[dof] = 1.
            joint_rows.append(row)
            joint_low.append(max(-300., 2.*(lo-q-v*horizon)/horizon**2))
            joint_high.append(min(300., 2.*(hi-q-v*horizon)/horizon**2))
        if joint_rows:
            rows.append(np.asarray(joint_rows))
            lower.append(np.asarray(joint_low))
            upper.append(np.asarray(joint_high))
        force_rows = []
        for i, mu in enumerate(friction):
            normal = np.zeros(n)
            normal[nv+nu+3*i] = 1.
            force_rows.append(normal)
            for a, b in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                row = normal*mu
                row[nv+nu+3*i+1] = a
                row[nv+nu+3*i+2] = b
                force_rows.append(row)
        if force_rows:
            rows.append(np.asarray(force_rows))
            lower.append(np.zeros(len(force_rows)))
            upper.append(np.full(len(force_rows), np.inf))
        lower, upper = np.concatenate(lower), np.concatenate(upper)
        if np.any(lower > upper):
            raise ControllerInfeasible('joint stopping bound is infeasible')
        solver = osqp.OSQP()
        solver.setup(P=sparse.csc_matrix(objective), q=linear,
                     A=sparse.csc_matrix(np.vstack(rows)), l=lower, u=upper,
                     verbose=False, eps_abs=1e-3, eps_rel=2e-4,
                     max_iter=20000, polishing=True, adaptive_rho=True,
                     adaptive_rho_interval=50, scaling=30, scaled_termination=True)
        result = solver.solve(raise_error=False)
        self.calls += 1
        self.last_status = result.info.status
        if result.info.status_val not in (1, 2) or result.x is None:
            raise ControllerInfeasible(f'contact dynamics QP: {result.info.status}; '
                                       f'primal={result.info.prim_res:.6g}, dual={result.info.dual_res:.6g}, contacts={nc}')
        commands = np.clip(result.x[nv:nv+nu], model.actuator_ctrlrange[:, 0], model.actuator_ctrlrange[:, 1])
        result.x[nv:nv+nu] = commands
        residual = float(np.max(np.abs(equality @ result.x-rhs)))
        if not np.isfinite(result.x).all() or residual > .05:
            raise ControllerInfeasible('contact dynamics residual exceeds tolerance')
        self.previous_commands = commands.copy()
        return DynamicsSolution(commands.copy(), result.x[:nv].copy(),
                                result.x[nv+nu:].reshape(-1, 3).copy(),
                                result.info.status, residual, time.perf_counter()-started)
