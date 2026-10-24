"""Bounded site-pose IK on independent planning data, never live execution."""
from dataclasses import dataclass

import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation


@dataclass(frozen=True)
class PosePlan:
    qpos: np.ndarray
    position_error_m: float
    angular_error_rad: float
    feasible: bool
    iterations: int


def site_pose(model, initial_qpos, site_name, joint_names, position, rotation, *, iterations=300):
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
    mj.mj_forward(model, scratch)
    position_error = float(np.linalg.norm(position-scratch.site_xpos[site]))
    angular_error = float(np.linalg.norm(Rotation.from_matrix(rotation @ scratch.site_xmat[site].reshape(3,3).T).as_rotvec()))
    return PosePlan(scratch.qpos.copy(),position_error,angular_error,
                    position_error<.005 and angular_error<.03,iteration+1)
