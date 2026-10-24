"""Apollo services a physical switch and verifies a motor-driven machine cycle."""

from __future__ import annotations

import time

import mujoco as mj
import numpy as np

from .humanoids import (STATE, HumanoidTrialRequest, _actuator_target, _control,
                        _frame, _reach_plan, compiled_model, configured_digest,
                        effective_physics, floor_contact_friction, initial_data)


def _integration_state(model, data):
    state = np.zeros(mj.mj_stateSize(model, STATE))
    mj.mj_getState(model, data, state, STATE)
    return state.tolist()


def _switch_contact(model, data, hand_geom, handle_geom):
    normal_force = 0.
    for index, contact in enumerate(data.contact[:data.ncon]):
        if contact.dist > 0 or {int(contact.geom1), int(contact.geom2)} != {hand_geom, handle_geom}:
            continue
        force = np.zeros(6)
        mj.mj_contactForce(model, data, index, force)
        normal_force += max(0., float(force[0]))
    return normal_force


def simulate_machine(request: HumanoidTrialRequest, *, on_frame=None, checkpoint=None):
    model, digest = compiled_model('apptronik_apollo', request.floor_friction,
                                   request.parcel_mass_kg, request.switch_y_m,
                                   request.switch_stiffness_n_m_rad)
    data = initial_data(model)
    targets, planning = _reach_plan(model, 'apptronik_apollo')
    initial = _frame(model, data)
    initial['phase'] = 'approach'
    frames = [initial]
    if on_frame:
        on_frame(initial, 0)
    initial_state = _integration_state(model, data)
    motor = model.actuator('machine_motor').id
    hinge_qadr = int(model.jnt_qposadr[model.joint('switch_hinge').id])
    shaft_qadr = int(model.jnt_qposadr[model.joint('machine_shaft').id])
    hand_geom = model.geom('collision_r_hand_plate').id
    handle_geom = model.geom('switch_handle').id
    home_ctrl = np.asarray([_actuator_target(model, data, i)[0] for i in range(model.nu)])
    activated_at = None
    first_contact_at = None
    retract_at = None
    retract_start = None
    peak_angle = 0.
    peak_force = 0.
    peak_joint_delta = 0.
    minimum_height = float(data.qpos[2])
    maximum_tilt = 0.
    contact_samples = 0
    floor_friction_samples = []
    shaft_travel = 0.
    peak_shaft_speed = 0.
    phase = 'approach'
    failure = None
    step_count = 0
    started = time.perf_counter()
    sample_stride = max(1, round(.05/model.opt.timestep))
    max_steps = round(request.task_timeout_s/model.opt.timestep)
    for step in range(max_steps):
        if checkpoint:
            checkpoint()
        elapsed = float(data.time)
        if phase in ('approach', 'operate'):
            _control(model, data, request, elapsed, targets)
        else:
            blend = float(np.sin(.5*np.pi*np.clip((elapsed-retract_at)/1.2, 0, 1))**2)
            data.ctrl[:] = (1-blend)*retract_start + blend*home_ctrl
        # The machine controller latches only after actual robot contact and
        # switch deflection. MuJoCo then integrates the shaft under motor torque.
        data.ctrl[motor] = .45 if activated_at is not None and phase != 'retract' else 0.
        data.xfrc_applied[1, 0] = request.perturbation_n if .4 <= elapsed <= .65 else 0.
        mj.mj_step(model, data)
        step_count += 1
        if not np.isfinite(data.qpos).all():
            failure = 'nonfinite_simulator_state'
            break
        angle = abs(float(data.qpos[hinge_qadr]))
        force = _switch_contact(model, data, hand_geom, handle_geom)
        if force > 0:
            contact_samples += 1
            if first_contact_at is None:
                first_contact_at = float(data.time)
        peak_force = max(peak_force, force)
        peak_angle = max(peak_angle, angle)
        minimum_height = min(minimum_height, float(data.qpos[2]))
        tilt = float(2*np.arccos(np.clip(abs(data.qpos[3]), 0, 1)))
        maximum_tilt = max(maximum_tilt, tilt)
        peak_joint_delta = max(peak_joint_delta, float(np.max(np.abs(data.qpos[7:7+model.nu-1]-initial['qpos'][7:7+model.nu-1]))))
        shaft_travel = max(shaft_travel, abs(float(data.qpos[shaft_qadr])))
        shaft_speed = abs(float(data.qvel[int(model.jnt_dofadr[model.joint('machine_shaft').id])]))
        peak_shaft_speed = max(peak_shaft_speed, shaft_speed)
        if (phase == 'approach' and first_contact_at is not None and
                data.time-first_contact_at <= .5 and angle >= .3):
            activated_at = float(data.time)
            phase = 'operate'
        elif phase == 'operate' and activated_at is not None and data.time-activated_at >= .8:
            retract_at = float(data.time)
            retract_start = data.ctrl.copy()
            phase = 'retract'
        if step_count % sample_stride == 0 or step_count == max_steps:
            floor_friction_samples.extend(floor_contact_friction(model, data))
            mj.mj_forward(model, data)
            frame = _frame(model, data)
            frame['phase'] = phase
            frame['switch_angle_rad'] = float(data.qpos[hinge_qadr])
            frame['machine_shaft_angle_rad'] = float(data.qpos[shaft_qadr])
            frames.append(frame)
            if on_frame:
                on_frame(frame, step_count)
        if minimum_height < .7 or maximum_tilt > .5:
            failure = 'unstable_stance'
            break
        if phase == 'approach' and data.time > 3.2:
            failure = 'switch_not_actuated'
            break
        if phase == 'retract' and data.time-retract_at >= 1.2:
            break
    if frames[-1]['time_s'] != float(data.time):
        mj.mj_forward(model, data)
        frame = _frame(model, data)
        frame['phase'] = phase
        frame['switch_angle_rad'] = float(data.qpos[hinge_qadr])
        frame['machine_shaft_angle_rad'] = float(data.qpos[shaft_qadr])
        frames.append(frame)
        if on_frame:
            on_frame(frame, step_count)
    hand_distance = float(np.linalg.norm(data.geom_xpos[hand_geom]-data.geom_xpos[handle_geom]))
    success = (failure is None and bool(planning['feasible']) and activated_at is not None and
               contact_samples > 0 and peak_angle >= .3 and shaft_travel >= .5 and
               peak_shaft_speed >= .3 and phase == 'retract' and
               data.time-retract_at >= 1.2 and hand_distance >= .10 and
               minimum_height >= .7 and maximum_tilt <= .5)
    if failure is None and not success:
        failure = ('machine_response_missing' if shaft_travel < .5 else
                   'retraction_incomplete' if hand_distance < .10 else 'task_timeout')
    return {
        'schema_version': 'vivacity.humanoid-trial/1.0', 'robot_id': 'apptronik_apollo',
        'environment_id': 'industrial_maintenance', 'action': 'service_machine',
        'parameters': request.model_dump(), 'seed': request.seed,
        'effective_physics': effective_physics(model, 'apptronik_apollo'),
        'model_hash': digest, 'scene_geometry_hash': configured_digest('apptronik_apollo'),
        'controller': 'damped_least_squares_contact_gated_machine_cycle',
        'policy_sha256': None,
        'simulator_version': mj.__version__, 'status': 'completed',
        'task_success': bool(success), 'failure_reason': None if success else failure,
        'planning': planning, 'initial_frame': initial, 'frames': frames,
        'final_frame': frames[-1], 'initial_integration_state': initial_state,
        'final_integration_state': _integration_state(model, data),
        'measurements': {
            'simulation_steps': step_count, 'simulation_duration_s': float(data.time),
            'compute_wall_s': time.perf_counter()-started,
            'minimum_base_height_m': minimum_height,
            'maximum_base_tilt_rad': maximum_tilt,
            'peak_joint_delta_rad': peak_joint_delta,
            'minimum_hand_goal_distance_m': hand_distance,
            'task_contact_samples': contact_samples,
            'maximum_parcel_height_m': None,
            'maximum_switch_angle_rad': peak_angle,
            'maximum_switch_angle_after_hand_contact_rad': peak_angle if activated_at is not None else 0.,
            'switch_activation_time_s': activated_at,
            'maximum_foot_slip_m_s': None,
            'peak_hand_switch_contact_force_n': peak_force,
            'observed_floor_sliding_friction_range':
                [min(floor_friction_samples), max(floor_friction_samples)]
                if floor_friction_samples else None,
            'machine_shaft_travel_rad': shaft_travel,
            'peak_machine_shaft_speed_rad_s': peak_shaft_speed,
            'final_hand_switch_distance_m': hand_distance,
            'final_base_position_m': data.qpos[:3].tolist(),
            'fallen': minimum_height < .7 or maximum_tilt > .5,
        },
        'scope': 'Stationary MuJoCo switch actuation and motor response with measured hand contact; '
                 'no autonomous diagnosis, mobile manipulation, or hardware claim.',
    }
