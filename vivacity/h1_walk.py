"""Bounded H1 walking experiment driven by Unitree's recurrent state policy."""

from __future__ import annotations

import time

import mujoco as mj
import numpy as np

from .h1_policy import ACTION_SCALE, DEFAULT_ANGLES, H1Policy, KD, KP, SOURCE_COMMIT, observation, policy_hash
from .humanoids import (STATE, HumanoidTrialRequest, _frame, _terrain_foot_contacts,
                        compiled_model, configured_digest, initial_data)


def _integration_state(model, data):
    state = np.zeros(mj.mj_stateSize(model, STATE))
    mj.mj_getState(model, data, state, STATE)
    return state.tolist()


def simulate_walk(request: HumanoidTrialRequest, *, on_frame=None, checkpoint=None):
    """Integrate real MuJoCo contacts and 50 Hz recurrent feedback until stop."""
    model, digest = compiled_model('unitree_h1', request.floor_friction)
    data = initial_data(model)
    policy = H1Policy()
    action = np.zeros(10, dtype=np.float32)
    target = DEFAULT_ANGLES.copy()
    initial = _frame(model, data)
    initial['phase'] = 'balance' if request.action == 'hold_stance' else 'walk'
    frames = [initial]
    if on_frame:
        on_frame(initial, 0)
    initial_state = _integration_state(model, data)
    goal = 0. if request.action == 'hold_stance' else request.goal_distance_m
    minimum_height = float(data.qpos[2])
    maximum_tilt = 0.
    peak_slip = 0.
    support_slip_samples = []
    foot_samples = 0
    threshold_contact_samples = 0
    peak_joint_delta = 0.
    achieved_at = None
    failure = None
    sample_stride = max(1, round(.05/model.opt.timestep))
    max_steps = round(request.task_timeout_s/model.opt.timestep)
    threshold_geom = model.geom('low_threshold').id
    started = time.perf_counter()
    step_count = 0
    for step in range(max_steps):
        if checkpoint:
            checkpoint()
        if step % 10 == 0:
            remaining = goal - float(data.qpos[0])
            if request.action == 'hold_stance' or remaining < .12:
                forward = 0.
            else:
                forward = float(np.clip(1.15*remaining, .12, .5))*request.movement_scale
            lateral = float(np.clip(-.65*data.qpos[1], -.16, .16))
            command = (forward, lateral, 0.)
            action = policy.act(observation(data, command, action))
            target = DEFAULT_ANGLES + ACTION_SCALE*action
        torque = KP*(target-data.qpos[7:17]) - KD*data.qvel[6:16]
        data.ctrl[:] = torque
        data.xfrc_applied[1, 0] = request.perturbation_n if .4 <= data.time <= .65 else 0.
        mj.mj_step(model, data)
        step_count += 1
        if not np.isfinite(data.qpos).all():
            failure = 'nonfinite_simulator_state'
            break
        height = float(data.qpos[2])
        tilt = float(2*np.arccos(np.clip(abs(data.qpos[3]), 0, 1)))
        minimum_height = min(minimum_height, height)
        maximum_tilt = max(maximum_tilt, tilt)
        peak_joint_delta = max(peak_joint_delta, float(np.max(np.abs(data.qpos[7:17]-initial['qpos'][7:17]))))
        foot_contacts, slip = _terrain_foot_contacts(model, data, min_normal_force_n=30.)
        foot_samples += foot_contacts
        threshold_contact_samples += sum(
            contact.dist <= 0 and threshold_geom in (int(contact.geom1), int(contact.geom2))
            and any((mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY,
                    int(model.geom_bodyid[geom_id])) or '') in ('left_ankle_link', 'right_ankle_link')
                    for geom_id in (int(contact.geom1), int(contact.geom2)))
            for contact in data.contact[:data.ncon])
        peak_slip = max(peak_slip, slip)
        if foot_contacts:
            support_slip_samples.append(slip)
        distance = float(np.linalg.norm(data.qpos[:2]-[goal, 0.]))
        if request.action == 'hold_stance':
            phase = 'balance'
        elif distance < .18:
            if achieved_at is None:
                achieved_at = float(data.time)
            phase = 'settle'
        else:
            achieved_at = None
            phase = 'walk'
        if step_count % sample_stride == 0 or step_count == max_steps:
            mj.mj_forward(model, data)
            frame = _frame(model, data)
            frame['phase'] = phase
            frames.append(frame)
            if on_frame:
                on_frame(frame, step_count)
        if height < .7 or tilt > .65:
            failure = 'fall'
            break
        if request.action != 'hold_stance' and achieved_at is not None and data.time-achieved_at >= 1.0:
            break
    if frames[-1]['time_s'] != float(data.time):
        mj.mj_forward(model, data)
        frame = _frame(model, data)
        frame['phase'] = 'stopped' if achieved_at is not None else 'walk'
        frames.append(frame)
        if on_frame:
            on_frame(frame, step_count)
    final_error = float(np.linalg.norm(data.qpos[:2]-[goal, 0.]))
    p95_slip = float(np.percentile(support_slip_samples, 95)) if support_slip_samples else float('inf')
    upright = minimum_height >= .7 and maximum_tilt <= .65
    stable_stop = request.action == 'hold_stance' or (
        achieved_at is not None and data.time-achieved_at >= 1.0)
    crossed_threshold = goal < .8 or threshold_contact_samples > 0
    success = (failure is None and upright and foot_samples > 0 and crossed_threshold and p95_slip <= .8 and
               stable_stop and (request.action == 'hold_stance' or final_error <= .18))
    if failure is None and not success:
        failure = ('terrain_not_crossed' if not crossed_threshold else
                   'excessive_foot_slip' if p95_slip > .8 else
                   'goal_not_reached_or_stable' if request.action != 'hold_stance' else
                   'unstable_stance')
    return {
        'schema_version': 'vivacity.humanoid-trial/1.0', 'robot_id': 'unitree_h1',
        'environment_id': 'terrain_mobility', 'action': request.action,
        'parameters': request.model_dump(), 'seed': request.seed,
        'model_hash': digest, 'scene_geometry_hash': configured_digest('unitree_h1'),
        'policy_sha256': policy_hash(), 'policy_source_commit': SOURCE_COMMIT,
        'controller': 'unitree_recurrent_policy_numpy_pd',
        'simulator_version': mj.__version__, 'status': 'completed',
        'task_success': bool(success), 'failure_reason': None if success else failure,
        'planning': {'method': 'body_frame_goal_velocity_feedback',
                     'target_position_m': [goal, 0., 0.], 'feasible': bool(request.movement_scale > 0 or goal == 0)},
        'initial_frame': initial, 'frames': frames, 'final_frame': frames[-1],
        'initial_integration_state': initial_state,
        'final_integration_state': _integration_state(model, data),
        'measurements': {
            'simulation_steps': step_count, 'simulation_duration_s': float(data.time),
            'compute_wall_s': time.perf_counter()-started,
            'minimum_base_height_m': minimum_height,
            'maximum_base_tilt_rad': maximum_tilt,
            'peak_joint_delta_rad': peak_joint_delta,
            'minimum_hand_goal_distance_m': None, 'task_contact_samples': foot_samples,
            'maximum_parcel_height_m': None, 'maximum_switch_angle_rad': None,
            'maximum_switch_angle_after_hand_contact_rad': None,
            'switch_activation_time_s': None,
            'maximum_foot_slip_m_s': peak_slip,
            'p95_support_foot_slip_m_s': p95_slip if np.isfinite(p95_slip) else None,
            'threshold_contact_samples': threshold_contact_samples,
            'final_base_position_m': data.qpos[:3].tolist(),
            'goal_error_m': final_error, 'stable_stop_duration_s':
                max(0., float(data.time-achieved_at)) if achieved_at is not None else 0.,
            'fallen': not upright,
        },
        'scope': 'Unitree matched H1 model and recurrent policy in bounded MuJoCo mobility test; '
                 'no general terrain or hardware claim.',
    }
