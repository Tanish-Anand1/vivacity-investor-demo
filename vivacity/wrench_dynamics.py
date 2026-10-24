"""Experimental inverse dynamics with native contact dimensions and hard limits.

Predicted wrenches are optimization variables, not measured task evidence. This
model uses conservative pyramidal friction bounds and locally linear clearance
constraints. Native MuJoCo remains the independent execution and evaluation
engine. Contact compliance is not replaced by a rigid-contact success claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import time

import clarabel
import mujoco as mj
import numpy as np
from scipy import sparse

from .inverse_dynamics import ControllerInfeasible


@dataclass
class ContactBasis:
    contact_index: int
    start: int
    dim: int
    jacobian: np.ndarray
    friction: np.ndarray
    normal_force_n: float


def contact_basis(model, data):
    """Map each native contact wrench into generalized force, including moments."""
    result, offset = [], 0
    for index, contact in enumerate(data.contact[:data.ncon]):
        if contact.dist > .001 or contact.efc_address < 0:
            continue
        dim = int(contact.dim)
        if dim not in (1, 3, 4, 6):
            raise ValueError('unsupported MuJoCo contact dimension')
        jp1, jp2 = np.zeros((3, model.nv)), np.zeros((3, model.nv))
        jr1, jr2 = np.zeros((3, model.nv)), np.zeros((3, model.nv))
        mj.mj_jac(model, data, jp1, jr1, contact.pos, int(model.geom_bodyid[contact.geom1]))
        mj.mj_jac(model, data, jp2, jr2, contact.pos, int(model.geom_bodyid[contact.geom2]))
        rotation = contact.frame.reshape(3, 3)
        jac = np.vstack((rotation @ (jp2-jp1), rotation @ (jr2-jr1)))[:dim]
        measured = np.zeros(6)
        mj.mj_contactForce(model, data, index, measured)
        result.append(ContactBasis(index, offset, dim, jac, contact.friction[:dim-1].copy(),
                                   float(measured[0])))
        offset += dim
    return result


def friction_facets(coefficients):
    """Conservative sum(abs(component / coefficient)) <= normal.

    Torsional and rolling coefficients carry length units; they must not be
    replaced by the sliding coefficient. Zero coefficients forbid that wrench.
    """
    coefficients = np.asarray(coefficients, dtype=float)
    positive = np.flatnonzero(coefficients > 1e-12)
    rows = []
    for signs in product((-1., 1.), repeat=len(positive)):
        row = np.zeros(len(coefficients)+1)
        row[0] = 1.
        row[positive+1] = np.asarray(signs)/coefficients[positive]
        rows.append(row)
    return np.asarray(rows), np.flatnonzero(coefficients <= 1e-12)+1


@dataclass
class WrenchSolution:
    commands: np.ndarray
    actuator_forces: np.ndarray
    acceleration: np.ndarray
    wrenches: list[list[float]]
    dynamics_residual: float
    constraint_violation: float
    status: str
    compute_s: float


class WrenchInverseDynamics:
    version = 'vivacity.wrench-inverse-dynamics/3-experimental'

    def __init__(self, model):
        self.model = model
        if (not np.all(model.actuator_trntype == mj.mjtTrn.mjTRN_JOINT)
                or not np.all(np.isin(model.actuator_biastype, [mj.mjtBias.mjBIAS_NONE, mj.mjtBias.mjBIAS_AFFINE]))
                or not np.all(model.actuator_dyntype == mj.mjtDyn.mjDYN_NONE)
                or not np.all(model.actuator_gaintype == mj.mjtGain.mjGAIN_FIXED)
                or not np.all(model.actuator_ctrllimited)
                or not np.all(model.actuator_gainprm[:, 0] > 0)
                or not np.all(model.actuator_gear[:, 0] == 1)
                or np.any(model.actuator_gear[:, 1:] != 0)):
            raise ValueError('bounded positive-gain direct joint motors or affine servos are required')
        self.joints = model.actuator_trnid[:, 0]
        self.controlled_joints = set(map(int, self.joints))
        self.dofs = model.jnt_dofadr[self.joints]
        if len(set(self.dofs)) != model.nu:
            raise ValueError('one motor per joint is required')
        self.previous_commands = np.zeros(model.nu)
        self.calls = 0
        self.maximum_residual = 0.
        self.maximum_violation = 0.
        self.last_status = 'not_run'

    def snapshot(self):
        return dict(version=self.version, previous_commands=self.previous_commands.tolist(),
                    calls=self.calls, maximum_residual=self.maximum_residual,
                    maximum_violation=self.maximum_violation, last_status=self.last_status)

    def restore(self, state):
        if state['version'] != self.version:
            raise ValueError('wrench controller version mismatch')
        commands = np.asarray(state['previous_commands'], dtype=float)
        if commands.shape != (self.model.nu,) or not np.isfinite(commands).all():
            raise ValueError('invalid motor memory')
        self.previous_commands = commands.copy()
        self.calls = int(state['calls'])
        self.maximum_residual = float(state['maximum_residual'])
        self.maximum_violation = float(state['maximum_violation'])
        self.last_status = state['last_status']

    def compute(self, data, target_qpos, *, torque_reference=None, command_reference=None, torque_weight=10.,
                extra_tasks=(), acceleration_limits=(), clearance_pairs=(),
                normal_force_targets=None):
        started = time.perf_counter()
        model, nv, nu = self.model, self.model.nv, self.model.nu
        basis = contact_basis(model, data)
        nf = sum(c.dim for c in basis)
        n = nv+nu+nf
        jac = np.vstack([c.jacobian for c in basis]) if basis else np.zeros((0, nv))
        error = np.zeros(nv)
        mj.mj_differentiatePos(model, error, 1., data.qpos, target_qpos)
        desired = np.clip(300.*error-35.*data.qvel, -100., 100.)
        weights = np.full(nv, .001)
        weights[self.dofs] = 1.
        if model.njnt and model.jnt_type[0] == mj.mjtJoint.mjJNT_FREE:
            weights[:6] = 40.
        hessian = np.diag(np.r_[weights, np.full(nu, torque_weight), np.full(nf, .00002)])
        gradient = np.r_[-weights*desired, np.zeros(nu+nf)]
        if torque_reference is not None:
            gradient[nv:nv+nu] -= torque_weight*np.asarray(torque_reference)
        if nf:
            contact_desired = -30.*(jac @ data.qvel)
            for c in basis:
                contact_desired[c.start] -= 600.*min(float(data.contact[c.contact_index].dist), 0.)
            hessian[:nv, :nv] += 4.*jac.T @ jac
            gradient[:nv] -= 4.*jac.T @ contact_desired
        for task_jac, task_acc, weight in extra_tasks:
            hessian[:nv, :nv] += weight*task_jac.T @ task_jac
            gradient[:nv] -= weight*task_jac.T @ task_acc
        for c in basis:
            if normal_force_targets and c.contact_index in normal_force_targets:
                index = nv+nu+c.start
                hessian[index, index] += .2
                gradient[index] -= .2*normal_force_targets[c.contact_index]

        mass = np.zeros((nv, nv))
        mj.mj_fullM(model, data, mass)
        transmission = np.zeros((nv, nu))
        transmission[self.dofs, np.arange(nu)] = model.actuator_gear[:, 0]
        dynamics = np.c_[mass, -transmission, -jac.T]
        rhs = data.qfrc_smooth-data.qfrc_actuator-model.dof_frictionloss*np.tanh(error/.01)
        rows, lower, upper = [dynamics], [rhs], [rhs]

        def bounds(matrix, lo, hi):
            rows.append(matrix)
            lower.append(np.broadcast_to(lo, matrix.shape[0]))
            upper.append(np.broadcast_to(hi, matrix.shape[0]))

        # Optimize total actuator force, including native velocity feedback.
        # Keep servo damping in the actuator; adding it as passive joint damping
        # would bypass the original combined torque limit.
        gain = model.actuator_gainprm[:, 0]
        bias = np.where(model.actuator_biastype == mj.mjtBias.mjBIAS_AFFINE,
            model.actuator_biasprm[:, 0]+model.actuator_biasprm[:, 1]*data.actuator_length
            +model.actuator_biasprm[:, 2]*data.actuator_velocity, 0.)
        force_low = gain*model.actuator_ctrlrange[:, 0]+bias
        force_high = gain*model.actuator_ctrlrange[:, 1]+bias
        actuator_low = np.where(model.actuator_forcelimited, model.actuator_forcerange[:, 0], -np.inf)
        actuator_high = np.where(model.actuator_forcelimited, model.actuator_forcerange[:, 1], np.inf)
        joint_low = np.where(model.jnt_actfrclimited[self.joints], model.jnt_actfrcrange[self.joints, 0], -np.inf)
        joint_high = np.where(model.jnt_actfrclimited[self.joints], model.jnt_actfrcrange[self.joints, 1], np.inf)
        # Native force clipping follows command clipping. If every possible
        # command saturates in one direction, the feasible force is a singleton,
        # not an empty intersection of unclipped and clipped ranges.
        force_low = np.clip(np.clip(force_low, actuator_low, actuator_high), joint_low, joint_high)
        force_high = np.clip(np.clip(force_high, actuator_low, actuator_high), joint_low, joint_high)
        command_rows = np.zeros((nu, n))
        command_rows[:, nv:nv+nu] = np.eye(nu)
        bounds(command_rows, force_low, force_high)
        for jid in range(model.njnt):
            # A passive fixture can decelerate under its own changing spring
            # force. An actuator-style constant-acceleration braking barrier
            # incorrectly declares that valid motion infeasible. Its native
            # stops remain enabled; enforce command viability on driven joints.
            if jid not in self.controlled_joints or not model.jnt_limited[jid] or int(model.jnt_type[jid]) not in (
                    int(mj.mjtJoint.mjJNT_HINGE), int(mj.mjtJoint.mjJNT_SLIDE)):
                continue
            dof, qadr = model.jnt_dofadr[jid], model.jnt_qposadr[jid]
            horizon = .08
            row = np.zeros((1, n))
            row[0, dof] = 1.
            lo, hi = 2.*(model.jnt_range[jid]-data.qpos[qadr]-data.qvel[dof]*horizon)/horizon**2
            bounds(row, max(-300., lo), min(300., hi))
        for c in basis:
            facets, zeros = friction_facets(c.friction)
            block = np.zeros((len(facets), n))
            start = nv+nu+c.start
            block[:, start:start+c.dim] = facets
            bounds(block, 0., np.inf)
            for zero in zeros:
                row = np.zeros((1, n))
                row[0, start+zero] = 1.
                bounds(row, 0., 0.)
        for task_jac, lo, hi in acceleration_limits:
            bounds(np.c_[task_jac, np.zeros((len(task_jac), nu+nf))], lo, hi)
        # Each pair explicitly excludes intended hand/object and sole contacts.
        # The local bound cannot certify a future trajectory; measured collisions
        # independently stop the task even when optimization was feasible.
        for geom1, geom2, margin in clearance_pairs:
            segment = np.zeros(6)
            distance = mj.mj_geomDistance(model, data, geom1, geom2, .5, segment)
            if distance >= .5:
                continue
            if distance <= 0.:
                raise ControllerInfeasible('prohibited geometry is already in contact')
            normal = (segment[3:]-segment[:3])/distance
            jp1, jp2 = np.zeros((3, nv)), np.zeros((3, nv))
            mj.mj_jac(model, data, jp1, None, segment[:3], int(model.geom_bodyid[geom1]))
            mj.mj_jac(model, data, jp2, None, segment[3:], int(model.geom_bodyid[geom2]))
            j = normal @ (jp2-jp1)
            # A damped acceleration barrier starts braking before the small
            # clearance band. A 5 cm look-ahead activated too late for bounded
            # motors in the driven-slider regression.
            rate = 5.
            minimum = -2.*rate*(j @ data.qvel)-rate**2*(distance-margin)
            bounds(np.r_[j, np.zeros(nu+nf)][None], minimum, np.inf)

        matrix, lo, hi = np.vstack(rows), np.concatenate(lower), np.concatenate(upper)
        if np.any(lo > hi) or not np.isfinite(gradient).all():
            raise ControllerInfeasible('invalid or infeasible wrench dynamics bounds')
        equal = np.isfinite(lo) & np.isfinite(hi) & (lo == hi)
        low, high = ~equal & np.isfinite(lo), ~equal & np.isfinite(hi)
        constraints = sparse.csc_matrix(np.vstack((matrix[equal], -matrix[low], matrix[high])))
        values = np.r_[lo[equal], -lo[low], hi[high]]
        settings = clarabel.DefaultSettings()
        settings.verbose = False
        settings.max_iter = 150
        # Simulation time does not advance while this bounded solve runs. A wall
        # deadline here made identical states fail when another process used the
        # CPU. The worker separately enforces a public-job compute budget.
        settings.time_limit = float('inf')
        settings.max_threads = 1
        solver = clarabel.DefaultSolver(sparse.triu(sparse.csc_matrix(hessian)).tocsc(), gradient,
            constraints, values, [clarabel.ZeroConeT(int(equal.sum())),
            clarabel.NonnegativeConeT(int(low.sum()+high.sum()))], settings)
        solved = solver.solve()
        self.calls += 1
        self.last_status = str(solved.status)
        if self.last_status not in ('Solved', 'AlmostSolved'):
            raise ControllerInfeasible(f'wrench dynamics: {self.last_status}')
        x = np.asarray(solved.x)
        residual = float(np.max(np.abs(dynamics @ x-rhs)))
        violation = float(max(np.max(lo-matrix @ x), np.max(matrix @ x-hi), 0.))
        if not np.isfinite(x).all() or residual > .01 or violation > .001:
            raise ControllerInfeasible('wrench dynamics violated physical bounds')
        forces = x[nv:nv+nu].copy()
        commands = np.clip((forces-bias)/gain, model.actuator_ctrlrange[:, 0], model.actuator_ctrlrange[:, 1])
        if command_reference is not None:
            reference_commands = np.clip(np.asarray(command_reference), model.actuator_ctrlrange[:, 0], model.actuator_ctrlrange[:, 1])
            reference_force = np.clip(np.clip(gain*reference_commands+bias, actuator_low, actuator_high), joint_low, joint_high)
            equivalent = np.abs(reference_force-forces) < 1e-6
            # At saturation the inverse is not unique. Preserve an equivalent
            # original target so native damping and force limiting continue to
            # operate during the control interval instead of weakening the grip.
            commands[equivalent] = reference_commands[equivalent]
        realized = np.clip(np.clip(gain*commands+bias, actuator_low, actuator_high), joint_low, joint_high)
        if np.max(np.abs(realized-forces)) > .001:
            raise ControllerInfeasible('actuator command does not realize optimized force')
        self.previous_commands = commands
        self.maximum_residual = max(self.maximum_residual, residual)
        self.maximum_violation = max(self.maximum_violation, violation)
        return WrenchSolution(commands.copy(), forces, x[:nv].copy(),
            [x[nv+nu+c.start:nv+nu+c.start+c.dim].tolist() for c in basis],
            residual, violation, self.last_status, time.perf_counter()-started)
