"""Model-matched proprioception and bounded actions, shared by CPU and MJX.

No trained policy is supplied. The actor receives joint encoders, a body IMU
orientation/angular rate, the requested velocity and its previous action. World
positions, scene bodies and evaluator contacts are deliberately not arguments.
The optional array namespace lets the same arithmetic run in NumPy and JAX.
"""
from dataclasses import dataclass
import hashlib
import json

import mujoco as mj
import numpy as np


VERSION = 'vivacity.complete-locomotion-contract/2-experimental'


@dataclass(frozen=True)
class PolicyContract:
    manifest: dict
    qadr: np.ndarray
    dofs: np.ndarray
    home: np.ndarray
    action_scale: np.ndarray
    joint_low: np.ndarray
    joint_high: np.ndarray
    servo: np.ndarray
    kp: np.ndarray
    kd: np.ndarray
    gain: np.ndarray
    control_low: np.ndarray
    control_high: np.ndarray
    force_limit: np.ndarray

    @property
    def action_size(self):
        return len(self.qadr)

    @property
    def observation_size(self):
        return 9 + 3*self.action_size

    @property
    def sha256(self):
        return hashlib.sha256(json.dumps(self.manifest, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def build_contract(model, embodiment):
    joints = model.actuator_trnid[:, 0]
    if (len(set(joints)) != model.nu or not np.all(model.actuator_ctrllimited)
            or np.any(model.actuator_trntype != int(mj.mjtTrn.mjTRN_JOINT))
            or np.any(model.actuator_gear[:, 0] != 1.) or np.any(model.actuator_gear[:, 1:])
            or np.any(model.actuator_dyntype != int(mj.mjtDyn.mjDYN_NONE))
            or np.any(model.actuator_gaintype != int(mj.mjtGain.mjGAIN_FIXED))
            or not np.all(np.isin(model.actuator_biastype,
                [int(mj.mjtBias.mjBIAS_NONE), int(mj.mjtBias.mjBIAS_AFFINE)]))):
        raise ValueError('contract requires bounded direct joint motors or position servos')
    if not np.all(model.jnt_limited[joints]):
        raise ValueError('every action must have native joint limits')
    qadr, dofs = model.jnt_qposadr[joints].copy(), model.jnt_dofadr[joints].copy()
    names = [model.joint(int(j)).name for j in joints]
    servo = model.actuator_biastype == int(mj.mjtBias.mjBIAS_AFFINE)
    gain = model.actuator_gainprm[:, 0].copy()
    if (np.any(gain <= 0) or np.any(model.actuator_biasprm[servo, 0] != 0)
            or np.any(model.actuator_biasprm[servo, 1] != -gain[servo])):
        raise ValueError('unsupported servo transmission')
    home = model.key_qpos[0, qadr].copy()
    low, high = model.jnt_range[joints].T.copy()
    # This is a new action contract, not the ten-actuator H1 policy mapping.
    scale = np.where(model.jnt_type[joints] == int(mj.mjtJoint.mjJNT_SLIDE), .015, .25)
    scale = np.minimum(scale, (high-low)/4.)
    kp = np.array([40. if 'ankle' in name else
                   50. if any(part in name for part in ('shoulder', 'elbow')) else 100.
                   for name in names])
    kd = 2.*np.sqrt(kp)*.15
    force_limit = np.minimum(
        np.where(model.actuator_forcelimited, np.max(np.abs(model.actuator_forcerange), axis=1), np.inf),
        np.where(model.jnt_actfrclimited[joints], np.max(np.abs(model.jnt_actfrcrange[joints]), axis=1), np.inf))
    # A bounded motor command is itself a force cap when no separate clamp exists.
    force_limit = np.where(servo, force_limit,
        np.minimum(force_limit, gain*np.max(np.abs(model.actuator_ctrlrange), axis=1)))
    if not np.isfinite(force_limit).all() or np.any(force_limit <= 0):
        raise ValueError('finite effective actuator force limits are required')
    manifest = {
        'schema_version':VERSION, 'model_sha256':embodiment['compiled_model_sha256'],
        'embodiment':embodiment['identity'], 'simulator_version':mj.__version__,
        'trained_policy':None, 'hardware_validation':False,
        'actor_fields':[
            {'name':'body_angular_velocity_rad_s', 'width':3, 'scale':.25},
            {'name':'projected_gravity_unit_vector', 'width':3, 'scale':1.},
            {'name':'command_vx_vy_yawrate', 'width':3, 'scale':1.},
            {'name':'joint_position_delta', 'width':model.nu, 'scale':1.},
            {'name':'joint_velocity', 'width':model.nu, 'scale':.05},
            {'name':'previous_normalized_action', 'width':model.nu, 'scale':1.}],
        'coordinate_convention':'right-handed body frame; x forward, y left, z up; SI units',
        'action_names':names, 'action_size':model.nu, 'observation_size':9+3*model.nu,
        'action_bounds':[-1.,1.], 'action_offset_scale':scale.tolist(),
        'joint_home':home.tolist(), 'joint_low':low.tolist(), 'joint_high':high.tolist(),
        'native_position_servo':servo.tolist(), 'motor_kp':kp.tolist(), 'motor_kd':kd.tolist(),
        'actuator_gain':gain.tolist(), 'force_limits':force_limit.tolist(),
        'command_ranges':model.actuator_ctrlrange.tolist(),
    }
    arrays = (qadr,dofs,home,scale,low,high,servo,kp,kd,gain,
              model.actuator_ctrlrange[:,0].copy(),model.actuator_ctrlrange[:,1].copy(),force_limit)
    for array in arrays:
        array.setflags(write=False)
    return PolicyContract(manifest,*arrays)


def observation(contract, joint_position, joint_velocity, body_rotation,
                body_angular_velocity, command, previous_action, *, xp=np):
    """Only explicit sensor values cross the actor boundary; no MjData access."""
    gravity = xp.asarray(body_rotation).T @ xp.asarray([0., 0., -1.])
    return xp.concatenate((.25*xp.asarray(body_angular_velocity), gravity,
        xp.asarray(command), xp.asarray(joint_position)-xp.asarray(contract.home),
        .05*xp.asarray(joint_velocity), xp.asarray(previous_action)))


def free_root_velocity(free_joint_velocity, body_rotation, *, xp=np):
    """IMU-frame velocity for a world-parented free root, in native conventions.

    Free-joint angular velocity is already local; its translation is global.
    Do not depend on optional GPU derived-field exports such as ``cvel``.
    The caller must verify that this body owns the root free joint.
    """
    velocity=xp.asarray(free_joint_velocity)
    rotation=xp.asarray(body_rotation).reshape(3,3)
    return velocity[3:6], rotation.T @ velocity[:3]


def commands(contract, normalized_action, joint_position, joint_velocity, *, xp=np):
    action = xp.clip(xp.asarray(normalized_action), -1., 1.)
    target = xp.clip(xp.asarray(contract.home)+xp.asarray(contract.action_scale)*action,
                     xp.asarray(contract.joint_low), xp.asarray(contract.joint_high))
    torque = xp.asarray(contract.kp)*(target-joint_position)-xp.asarray(contract.kd)*joint_velocity
    result = xp.where(xp.asarray(contract.servo), target, torque/xp.asarray(contract.gain))
    return xp.clip(result, xp.asarray(contract.control_low), xp.asarray(contract.control_high))
