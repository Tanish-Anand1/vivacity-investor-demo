"""Stationary G1 pickup with measured contact and an explicit grasp fixture.

MuJoCo integrates every joint, contact, and rigid parcel motion. The hand model
cannot sustain a friction-only grasp in this task, so a disabled weld is armed
only after sustained force-bearing contacts on *both* hands. Its relative pose
is measured at activation, avoiding a pose jump. This models a rigid grasp
fixture, not dexterous finger manipulation or onboard visual perception.
"""

from __future__ import annotations

from copy import deepcopy
import time

import mujoco as mj
import numpy as np

from .humanoids import (
    STATE, HumanoidTrialRequest, _actuator_target, _frame, _solve_position_ik,
    compiled_model, configured_digest, initial_data,
)


ARM_NAMES = {
    side: [f'{side}_{part}_joint' for part in (
        'shoulder_pitch', 'shoulder_roll', 'shoulder_yaw', 'elbow',
        'wrist_roll', 'wrist_pitch', 'wrist_yaw')]
    for side in ('left', 'right')
}
PHASE_DURATIONS = {'approach': 1.7, 'lift': 1.2, 'transfer': 1.5, 'lower': 1.2}


def _plan(model, targets, qpos=None):
    scratch = initial_data(model)
    if qpos is not None:
        scratch.qpos[:] = qpos
        mj.mj_forward(model, scratch)
    result = {}
    errors = {}
    for side, point in targets.items():
        target, error = _solve_position_ik(
            model, scratch, np.asarray(point), ARM_NAMES[side],
            model.body(f'{side}_hand_middle_0_link').id, geom=False)
        result.update(target)
        errors[side] = float(error)
    return result, errors


def _control_vector(model, data, home, joints):
    result = home.copy()
    for index in range(model.nu):
        _, joint_id = _actuator_target(model, data, index)
        if joint_id in joints:
            result[index] = joints[joint_id]
    return result


def _contact_measurements(model, data):
    """Read solved normal forces and prohibited/support contact identities."""
    forces = {'left': 0., 'right': 0.}
    support = False
    floor_drop = False
    violations = set()
    parcel_geom = model.geom('parcel_box').id
    destination_geom = model.geom('placement_stand').id
    floor_geom = model.geom('floor').id
    for index, contact in enumerate(data.contact[:data.ncon]):
        if contact.dist > 0:
            continue
        geoms = (int(contact.geom1), int(contact.geom2))
        if parcel_geom in geoms:
            other = geoms[1] if geoms[0] == parcel_geom else geoms[0]
            if other == destination_geom:
                support = True
            if other == floor_geom:
                floor_drop = True
            body = mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY,
                                 int(model.geom_bodyid[other])) or ''
            normal = np.zeros(6)
            mj.mj_contactForce(model, data, index, normal)
            for side in forces:
                if body.startswith(f'{side}_hand'):
                    forces[side] += max(0., float(normal[0]))
        for geom in geoms:
            other = geoms[1] if geom == geoms[0] else geoms[0]
            name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, geom) or ''
            body = mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY,
                                 int(model.geom_bodyid[other])) or ''
            if name in ('pickup_stand', 'placement_stand') and body not in ('world', 'parcel'):
                if not body.startswith(('left_hand', 'right_hand')):
                    violations.add(f'robot_fixture:{body}')
            if name == 'floor' and body not in ('world', 'parcel'):
                if not any(part in body for part in ('ankle', 'foot')):
                    violations.add(f'nonfoot_floor:{body}')
    return forces, support, floor_drop, violations


def _activate_grasp(model, data):
    wrist = model.body('right_wrist_yaw_link').id
    parcel = model.body('parcel').id
    wrist_q = np.asarray(data.xquat[wrist]).copy()
    parcel_q = np.asarray(data.xquat[parcel]).copy()
    relative_q = np.zeros(4)
    mj.mju_mulQuat(relative_q, wrist_q * np.array([1, -1, -1, -1]), parcel_q)
    relative_p = np.asarray(data.xmat[wrist]).reshape(3, 3).T @ (
        data.xpos[parcel] - data.xpos[wrist])
    model.eq_data[model.equality('parcel_grasp').id, 3:10] = np.r_[relative_p, relative_q]
    before = np.asarray(data.xpos[parcel]).copy()
    data.eq_active[model.equality('parcel_grasp').id] = 1
    mj.mj_forward(model, data)
    jump = float(np.linalg.norm(data.xpos[parcel] - before))
    return np.r_[relative_p, relative_q].tolist(), jump


def _integration_state(model, data):
    state = np.zeros(mj.mj_stateSize(model, STATE))
    mj.mj_getState(model, data, state, STATE)
    return state.tolist()


def simulate_pickup(request: HumanoidTrialRequest):
    """Run one bounded, independently restored G1 MuJoCo experiment."""
    if request.robot_id != 'unitree_g1' or request.action != 'pickup_place':
        raise ValueError('Pickup controller requires Unitree G1 and pickup_place')
    started = time.perf_counter()
    # Each job receives its own MjModel because the weld rest pose changes at
    # the measured grasp. The cached parent model and other jobs stay untouched.
    template, digest = compiled_model('unitree_g1', request.floor_friction,
                                      request.parcel_mass_kg)
    model = deepcopy(template)
    data = initial_data(model)
    free_joint = model.joint('parcel_free').id
    qadr = int(model.jnt_qposadr[free_joint])
    data.qpos[qadr:qadr+2] = request.parcel_xy_m
    mj.mj_forward(model, data)
    initial = _frame(model, data)
    initial['phase'] = 'approach'
    initial['parcel_position_m'] = data.body('parcel').xpos.tolist()
    initial['grasp_active'] = False
    initial_state = _integration_state(model, data)
    frames = [initial]
    events = []
    phase = 'approach'
    failure = None
    step_count = 0
    source = np.asarray(data.body('parcel').xpos).copy()
    destination = np.asarray(request.destination_xy_m)
    target_points = {
        'left': source + np.array([-.08, .10, .08]),
        'right': source + np.array([-.08, -.10, .08]),
    }
    joints, approach_errors = _plan(model, target_points, data.qpos.copy())
    planning = {
        'method': 'damped_least_squares_bilateral_hand_position',
        'target_positions_m': {k: v.tolist() for k, v in target_points.items()},
        'hand_position_errors_m': approach_errors,
        'feasible': all(error < .025 for error in approach_errors.values()),
        'stage_ik_errors_m': {},
    }
    home = np.array([_actuator_target(model, data, i)[0] for i in range(model.nu)])
    start_control = home.copy()
    end_control = home + (_control_vector(model, data, home, joints)-home)*request.movement_scale
    phase_start = 0.
    bilateral_steps = 0
    grasp_relpose = None
    constraint_jump_m = None
    peak_height = float(source[2])
    minimum_base_height = float(data.qpos[2])
    maximum_tilt = 0.
    peak_joint_delta = 0.
    peak_contact = {'left': 0., 'right': 0.}
    contact_samples = 0
    prohibited_contacts = set()
    limited_joints = np.flatnonzero(model.jnt_limited)
    joint_qadrs = model.jnt_qposadr[limited_joints]
    lower_limits = model.jnt_range[limited_joints, 0]
    upper_limits = model.jnt_range[limited_joints, 1]
    max_joint_violation = 0.
    saw_floor_drop = False
    support_samples_after_release = 0
    released_at = None
    sample_stride = max(1, round(.05/model.opt.timestep))
    max_steps = round(request.task_timeout_s/model.opt.timestep)

    if not planning['feasible']:
        failure = 'unreachable_grasp_target'
    elif not (.22 <= source[0] <= .48 and -.14 <= source[1] <= .14):
        failure = 'parcel_outside_source_fixture'
    elif request.movement_scale == 0:
        # Still run the physical trial; it must fail through absent contacts.
        pass

    def enter(next_phase, targets, *, measured):
        nonlocal phase, phase_start, start_control, end_control
        phase = next_phase
        phase_start = float(data.time)
        start_control = np.asarray(data.ctrl).copy()
        end_control = targets.copy()
        events.append({'phase': next_phase, 'time_s': phase_start,
                       'evidence': measured})

    for step in range(max_steps if failure is None else 0):
        elapsed = float(data.time)
        duration = PHASE_DURATIONS.get(phase, .5)
        progress = float(np.clip((elapsed-phase_start)/duration, 0, 1))
        smooth = float(np.sin(np.pi*progress/2)**2)
        data.ctrl[:] = start_control+(end_control-start_control)*smooth
        data.xfrc_applied[1, 0] = request.perturbation_n if .4 <= elapsed <= .65 else 0.
        mj.mj_step(model, data)
        mj.mj_forward(model, data)
        step_count += 1
        if not np.isfinite(data.qpos).all():
            failure = 'nonfinite_simulator_state'
            break
        parcel = np.asarray(data.body('parcel').xpos).copy()
        peak_height = max(peak_height, float(parcel[2]))
        minimum_base_height = min(minimum_base_height, float(data.qpos[2]))
        maximum_tilt = max(maximum_tilt, float(2*np.arccos(np.clip(abs(data.qpos[3]), 0, 1))))
        peak_joint_delta = max(peak_joint_delta, float(np.max(np.abs(data.qpos[7:7+model.nu]-initial['qpos'][7:7+model.nu]))))
        joint_positions = data.qpos[joint_qadrs]
        max_joint_violation = max(max_joint_violation, float(np.max(np.maximum(
            np.maximum(lower_limits-joint_positions, joint_positions-upper_limits), 0.))))
        forces, supported, floor_drop, violations = _contact_measurements(model, data)
        for side in peak_contact:
            peak_contact[side] = max(peak_contact[side], forces[side])
        contact_samples += int(min(forces.values()) > 0)
        prohibited_contacts.update(violations)
        saw_floor_drop |= floor_drop
        if (step+1) % sample_stride == 0 or step == max_steps-1:
            frame = _frame(model, data)
            frame['phase'] = phase
            frame['parcel_position_m'] = parcel.tolist()
            frame['grasp_active'] = bool(data.eq_active[0])
            frames.append(frame)

        if minimum_base_height < .7 or maximum_tilt > .4:
            failure = 'unstable_stance'
            break
        if violations:
            failure = 'prohibited_robot_contact'
            break
        if max_joint_violation > .05:
            failure = 'joint_limit_violation'
            break
        if phase == 'approach':
            bilateral_steps = bilateral_steps+1 if min(forces.values()) >= 2 else 0
            if bilateral_steps >= 10:
                grasp_relpose, constraint_jump_m = _activate_grasp(model, data)
                point = np.asarray(data.body('right_hand_middle_0_link').xpos)+np.array([0,0,.18])
                lift_joints, errors = _plan(model, {'right': point}, data.qpos.copy())
                planning['stage_ik_errors_m']['lift'] = errors
                enter('lift', _control_vector(model, data, home, lift_joints),
                      measured={'bilateral_contact_steps': bilateral_steps,
                                'left_normal_force_n': forces['left'],
                                'right_normal_force_n': forces['right'],
                                'parcel_position_m': parcel.tolist(),
                                'constraint_pose_jump_m': constraint_jump_m})
            elif elapsed >= 2.8:
                failure = 'no_supported_bilateral_grasp'
        elif phase == 'lift' and elapsed-phase_start >= 1.2:
            if parcel[2] < .84:
                failure = 'lift_height_not_reached'
            else:
                # The hand displacement is derived from the requested destination.
                shift = np.array([.5*(destination[0]-source[0]),
                                  .25*(destination[1]-source[1]), 0.])
                point = np.asarray(data.body('right_hand_middle_0_link').xpos)+shift
                transfer_joints, errors = _plan(model, {'right': point}, data.qpos.copy())
                planning['stage_ik_errors_m']['transfer'] = errors
                enter('transfer', _control_vector(model, data, home, transfer_joints),
                      measured={'parcel_height_m': float(parcel[2]),
                                'destination_xy_m': destination.tolist()})
        elif phase == 'transfer' and elapsed-phase_start >= 1.5:
            if float(np.linalg.norm(parcel[:2]-destination)) > .55:
                failure = 'parcel_not_transferred'
            else:
                point = np.asarray(data.body('right_hand_middle_0_link').xpos)+np.array([0,0,-.17])
                lower_joints, errors = _plan(model, {'right': point}, data.qpos.copy())
                planning['stage_ik_errors_m']['lower'] = errors
                enter('lower', _control_vector(model, data, home, lower_joints),
                      measured={'parcel_position_m': parcel.tolist()})
        elif phase == 'lower' and elapsed-phase_start >= 1.2:
            if parcel[2] > .82:
                failure = 'lowering_height_not_reached'
            else:
                enter('settle_before_release', end_control,
                      measured={'parcel_position_m': parcel.tolist()})
        elif phase == 'settle_before_release' and elapsed-phase_start >= .5:
            if np.linalg.norm(parcel[:2]-destination) > .34:
                failure = 'parcel_outside_destination_before_release'
            else:
                data.eq_active[model.equality('parcel_grasp').id] = 0
                mj.mj_forward(model, data)
                released_at = float(data.time)
                enter('released', end_control,
                      measured={'parcel_position_m': parcel.tolist(),
                                'weld_deactivated': True})
        elif phase == 'released' and supported:
            support_samples_after_release += 1

        if failure:
            break

    if frames[-1]['time_s'] != float(data.time):
        frame = _frame(model, data)
        frame['phase'] = phase
        frame['parcel_position_m'] = data.body('parcel').xpos.tolist()
        frame['grasp_active'] = bool(data.eq_active[0])
        frames.append(frame)
    parcel_final = np.asarray(data.body('parcel').xpos).copy()
    final_forces, final_support, final_floor, _ = _contact_measurements(model, data)
    parcel_velocity = np.asarray(data.qvel[model.jnt_dofadr[free_joint]:model.jnt_dofadr[free_joint]+6])
    destination_error = float(np.linalg.norm(parcel_final[:2]-destination))
    success = (failure is None and released_at is not None and
               support_samples_after_release >= 20 and final_support and
               not final_floor and not saw_floor_drop and
               peak_height >= .84 and destination_error <= .17 and
               .66 <= parcel_final[2] <= .72 and
               float(np.linalg.norm(parcel_velocity[:3])) <= .05 and
               minimum_base_height >= .7 and maximum_tilt <= .4 and
               not prohibited_contacts and not bool(data.eq_active[0]))
    if failure is None and not success:
        failure = ('placement_not_stable' if released_at is not None
                   else 'task_timeout')
    return {
        'schema_version': 'vivacity.humanoid-trial/1.0',
        'robot_id': 'unitree_g1', 'environment_id': 'warehouse_logistics',
        'action': 'pickup_place', 'parameters': request.model_dump(),
        'seed': request.seed, 'model_hash': digest,
        'scene_geometry_hash': configured_digest('unitree_g1'),
        'simulator_version': mj.__version__, 'status': 'completed',
        'task_success': bool(success), 'failure_reason': None if success else failure,
        'planning': planning, 'initial_frame': initial, 'frames': frames,
        'final_frame': frames[-1], 'initial_integration_state': initial_state,
        'final_integration_state': _integration_state(model, data),
        'grasp_constraint_relpose': grasp_relpose, 'events': events,
        'measurements': {
            'simulation_steps': step_count, 'simulation_duration_s': float(data.time),
            'compute_wall_s': time.perf_counter()-started,
            'minimum_base_height_m': minimum_base_height,
            'maximum_base_tilt_rad': maximum_tilt,
            'peak_joint_delta_rad': peak_joint_delta,
            'minimum_hand_goal_distance_m': None,
            'task_contact_samples': contact_samples,
            'maximum_parcel_height_m': peak_height,
            'maximum_switch_angle_rad': None,
            'maximum_switch_angle_after_hand_contact_rad': None,
            'switch_activation_time_s': None,
            'maximum_foot_slip_m_s': None,
            'final_base_position_m': data.qpos[:3].tolist(),
            'fallen': minimum_base_height < .7 or maximum_tilt > .4,
            'contact_force_peak_n': peak_contact,
            'grasp_constraint_pose_jump_m': constraint_jump_m,
            'release_time_s': released_at,
            'support_contact_samples_after_release': support_samples_after_release,
            'final_support_contact': bool(final_support),
            'floor_drop_contact': bool(saw_floor_drop or final_floor),
            'prohibited_contacts': sorted(prohibited_contacts),
            'maximum_joint_limit_violation_rad': max_joint_violation,
            'final_parcel_position_m': parcel_final.tolist(),
            'final_parcel_speed_m_s': float(np.linalg.norm(parcel_velocity[:3])),
            'destination_error_m': destination_error,
            'grasp_constraint_active_final': bool(data.eq_active[0]),
        },
        'scope': 'Stationary MuJoCo G1 pickup; privileged simulator object pose; '
                 'bilateral force-gated rigid weld approximates a supported grasp. '
                 'No dexterous-grasp, vision, walking, or hardware claim.',
    }
