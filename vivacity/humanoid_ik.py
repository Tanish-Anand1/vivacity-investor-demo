"""Bounded site-pose IK on independent planning data, never live execution."""
from dataclasses import dataclass

import mujoco as mj
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


@dataclass(frozen=True)
class PosePlan:
    qpos: np.ndarray
    position_error_m: float
    angular_error_rad: float
    feasible: bool
    iterations: int


def site_pose(model, initial_qpos, site_name, joint_names, position, rotation, *, iterations=300,
              joint_margin=None):
    """Plan a pose on scratch data, optionally reserving native joint travel.

    The default damped Jacobian solver preserves existing callers. A requested
    margin uses bounded least squares and weak normalized posture centering to
    select among redundant arm configurations. Margins use each joint's native
    unit (radians for hinges, metres for slides). Neither mode certifies collision
    clearance or force feasibility; the controller and native trial must do that.
    """
    position, rotation = np.asarray(position, dtype=float), np.asarray(rotation, dtype=float)
    if (position.shape != (3,) or rotation.shape != (3,3) or not np.isfinite(position).all()
            or not np.isfinite(rotation).all() or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-6)
            or not np.isclose(np.linalg.det(rotation), 1.) or not 1 <= iterations <= 1000):
        raise ValueError('a finite rigid target pose and bounded iteration budget are required')
    scratch = mj.MjData(model)
    scratch.qpos[:] = initial_qpos
    joints = np.array([model.joint(name).id for name in joint_names], dtype=int)
    if not len(joints) or len(set(joints)) != len(joints) or not all(model.jnt_limited[joints]):
        raise ValueError('unique bounded planning joints required')
    if not np.isin(model.jnt_type[joints], [mj.mjtJoint.mjJNT_HINGE, mj.mjtJoint.mjJNT_SLIDE]).all():
        raise ValueError('IK cannot move floating roots')
    qadr, dofs = model.jnt_qposadr[joints], model.jnt_dofadr[joints]
    site = model.site(site_name).id
    if joint_margin is not None:
        span = np.diff(model.jnt_range[joints],axis=1).ravel()
        if (not np.isfinite(joint_margin) or joint_margin < 0.
                or np.any(2.*joint_margin >= span)):
            raise ValueError('joint margin must leave a nonempty bounded joint interval')
        low, high = model.jnt_range[joints,0]+joint_margin, model.jnt_range[joints,1]-joint_margin
        center = model.jnt_range[joints].mean(axis=1)
        def residual(values):
            scratch.qpos[qadr] = values
            mj.mj_forward(model,scratch)
            angular = Rotation.from_matrix(rotation @ scratch.site_xmat[site].reshape(3,3).T).as_rotvec()
            return np.r_[position-scratch.site_xpos[site],.2*angular,.0005*(values-center)/span]
        fitted = least_squares(residual,np.clip(scratch.qpos[qadr],low,high),bounds=(low,high),
            method='trf',max_nfev=iterations,xtol=1e-10,ftol=1e-10,gtol=1e-10)
        scratch.qpos[qadr] = fitted.x
        iteration = fitted.nfev-1
    else:
        iteration = _damped_pose_iterations(model,scratch,site,qadr,dofs,joints,position,rotation,iterations)
    mj.mj_forward(model, scratch)
    position_error = float(np.linalg.norm(position-scratch.site_xpos[site]))
    angular_error = float(np.linalg.norm(Rotation.from_matrix(rotation @ scratch.site_xmat[site].reshape(3,3).T).as_rotvec()))
    return PosePlan(scratch.qpos.copy(),position_error,angular_error,
                    position_error<.005 and angular_error<.03,iteration+1)


def _damped_pose_iterations(model,scratch,site,qadr,dofs,joints,position,rotation,iterations):
    jp, jr = np.zeros((3,model.nv)), np.zeros((3,model.nv))
    for iteration in range(iterations):
        mj.mj_forward(model, scratch)
        linear = position-scratch.site_xpos[site]
        angular = Rotation.from_matrix(rotation @ scratch.site_xmat[site].reshape(3,3).T).as_rotvec()
        if np.linalg.norm(linear) < .0005 and np.linalg.norm(angular) < .005:
            break
        mj.mj_jacSite(model, scratch, jp, jr, site)
        jac = np.vstack((jp[:,dofs], .2*jr[:,dofs]))
        delta = jac.T @ np.linalg.solve(jac @ jac.T+np.eye(6)*.0001, np.r_[linear,.2*angular])
        scratch.qpos[qadr] = np.clip(scratch.qpos[qadr]+np.clip(delta,-.06,.06),
                                    model.jnt_range[joints,0]+.002,model.jnt_range[joints,1]-.002)
    return iteration
