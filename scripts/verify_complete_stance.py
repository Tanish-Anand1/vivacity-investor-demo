"""Native standing/reaching/disturbance probe for complete robot embodiments.

This is a bounded stabilization probe, not locomotion/cabinet acceptance. Every
planned sample and failure is retained. Small development runs never satisfy
the twenty/one-hundred acceptance counts.
"""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import time

import mujoco as mj
import numpy as np

from scripts.verify_bimanual import wilson
from scripts.verify_constrained_envelope import write
from vivacity.execution_checkpoint import model_bytes
from vivacity.humanoid_embodiments import compile_embodiment, FEET, ROOTS
from vivacity.inverse_dynamics import ControllerInfeasible
from vivacity.stance_control import StanceController


def run(model_binary, identity, setting):
    started = time.perf_counter()
    model = mj.MjModel.from_binary_path('embodiment.mjb', assets={'embodiment.mjb':model_binary})
    floor = model.geom('floor').id
    model.geom_friction[floor, 0] = setting['floor_friction']
    for pair in range(model.npair):
        if floor in (model.pair_geom1[pair], model.pair_geom2[pair]):
            model.pair_friction[pair, :2] = setting['floor_friction']
    data = mj.MjData(model)
    mj.mj_resetDataKeyframe(model, data, 0)
    mj.mj_forward(model, data)
    controller = StanceController(model, identity)
    root = model.body(ROOTS[identity]).id
    feet = {model.body(name).id:name for name in FEET[identity]}
    shoulder_name = {'g1':'right_shoulder_pitch_joint', 'apollo':'r_shoulder_fe', 'h1':'right_shoulder_pitch'}[identity]
    shoulder = model.joint(shoulder_name).qposadr[0]
    tool_body = {'g1':'right_wrist_yaw_link', 'apollo':'r_service_tool', 'h1':'right_service_tool'}[identity]
    initial_tool = data.body(tool_body).xpos.copy()
    slips, supports, frames = [], [], []
    peak_tilt = peak_joint_error = peak_tool_motion = 0.
    minimum_height = float(data.qpos[2])
    failure = None
    steps = 0
    for index in range(3000):
        phase = 'standing' if data.time < 1. else 'reach' if data.time < 2.5 else 'disturbance' if data.time < 3. else 'settle'
        target = model.key_qpos[0].copy()
        if 1. <= data.time < 2.5:
            target[shoulder] += setting['reach_angle_rad']*np.sin(np.pi*(data.time-1.)/1.5)**2
        data.xfrc_applied[root, 0] = setting['disturbance_n'] if 2.5 <= data.time < 2.7 else 0.
        try:
            data.ctrl[:] = controller.compute(data, target)
        except ControllerInfeasible as error:
            failure = 'controller_infeasible'
            detail = str(error)
            break
        mj.mj_step(model, data)
        steps += 1
        if (not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all()
                or any(data.warning[warning].number for warning in (
                    mj.mjtWarning.mjWARN_BADQPOS,mj.mjtWarning.mjWARN_BADQVEL,mj.mjtWarning.mjWARN_BADQACC))):
            failure = 'nonfinite_simulator_state'
            break
        tilt = float(2*np.arccos(np.clip(abs(data.qpos[3]), 0, 1)))
        peak_tilt = max(peak_tilt, tilt)
        minimum_height = min(minimum_height, float(data.qpos[2]))
        peak_tool_motion = max(peak_tool_motion, float(np.linalg.norm(data.body(tool_body).xpos-initial_tool)))
        for joint in range(model.njnt):
            if model.jnt_limited[joint]:
                value = data.qpos[model.jnt_qposadr[joint]]
                peak_joint_error = max(peak_joint_error, float(model.jnt_range[joint, 0]-value),
                                       float(value-model.jnt_range[joint, 1]))
        loads = {name:0. for name in feet.values()}
        for contact_index, contact in enumerate(data.contact[:data.ncon]):
            if floor not in (contact.geom1, contact.geom2) or contact.dist > 0.:
                continue
            geom = contact.geom2 if contact.geom1 == floor else contact.geom1
            body = int(model.geom_bodyid[geom])
            if body not in feet:
                failure = 'prohibited_ground_contact'
                continue
            force = np.zeros(6)
            mj.mj_contactForce(model, data, contact_index, force)
            loads[feet[body]] += max(0., float(force[0]))
            if force[0] > 5. and data.time > .5:
                jac = np.zeros((3, model.nv))
                mj.mj_jac(model, data, jac, None, contact.pos, body)
                slips.append(float(np.linalg.norm((jac @ data.qvel)[:2])))
        if data.time > .5:
            supports.append(loads)
        if index % 50 == 0 or failure:
            frames.append({'time_s':float(data.time), 'phase':phase, 'qpos':data.qpos.tolist(),
                           'qvel':data.qvel.tolist(), 'ctrl':data.ctrl.tolist(), 'sole_loads_n':loads})
        if tilt > .6 or minimum_height < .7*model.key_qpos[0, 2]:
            failure = 'unstable_stance'
        if failure:
            break
    final_speed = float(np.linalg.norm(data.qvel[:3]))
    final_tilt = float(2*np.arccos(np.clip(abs(data.qpos[3]), 0, 1)))
    p95_slip = float(np.quantile(slips, .95)) if slips else None
    both_supported = bool(supports) and all(min(sample.values()) > 10. for sample in supports)
    accepted = (failure is None and steps == 3000 and peak_tilt < .15
                and final_tilt < .08 and final_speed < .03 and minimum_height > .9*model.key_qpos[0, 2]
                and peak_joint_error < .01 and both_supported and p95_slip is not None and p95_slip < .05
                and peak_tool_motion > .005)
    if not accepted and failure is None:
        failure = 'stabilization_metrics_failed'
    return {'robot':identity, 'settings':setting, 'success':bool(accepted), 'failure':failure,
        'controller_error':locals().get('detail'), 'controller':controller.version,
        'reference_weight':controller.reference_weight,
        'compiled_model_sha256':hashlib.sha256(model_bytes(model)).hexdigest(),
        'simulator_version':mj.__version__, 'steps':steps, 'simulation_time_s':float(data.time),
        'peak_tilt_rad':peak_tilt, 'final_tilt_rad':final_tilt, 'final_root_speed_m_s':final_speed,
        'minimum_root_height_m':minimum_height, 'peak_joint_limit_error':peak_joint_error,
        'p95_loaded_sole_slip_m_s':p95_slip, 'bilateral_support':both_supported,
        'peak_tool_motion_m':peak_tool_motion, 'compute_wall_s':time.perf_counter()-started,
        'frames':frames}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--robot', choices=['g1','apollo','h1'], required=True)
    parser.add_argument('--nominal', type=int, default=1)
    parser.add_argument('--held-out', type=int, default=0)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--failure-fixtures', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.nominal <= 20 or not 0 <= args.held_out <= 100:
        parser.error('bounded sample counts required')
    rng = np.random.default_rng(20261026)
    plan = [{'cohort':'nominal','settings':{'floor_friction':.8,'reach_angle_rad':-.08,'disturbance_n':15.}}
            for _ in range(args.nominal)]
    plan += [{'cohort':'held_out','settings':{'floor_friction':float(rng.uniform(.6,1.)),
              'reach_angle_rad':float(rng.uniform(-.09,-.07)), 'disturbance_n':float(rng.uniform(10.,20.))}}
             for _ in range(args.held_out)]
    if args.failure_fixtures:
        plan.append({'cohort':'deliberate_instability','settings':{
            'floor_friction':.8,'reach_angle_rad':-.08,'disturbance_n':1500.}})
    sources = {name:hashlib.sha256(Path('vivacity',name).read_bytes()).hexdigest() for name in (
        'stance_control.py','wrench_dynamics.py','humanoid_embodiments.py','simulated_tooling.py')}
    sources['verification_script'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    model, data, manifest = compile_embodiment(args.robot)
    binary = model_bytes(model)
    del model, data
    gc.collect()
    report = {'schema_version':'vivacity.complete-stance-probe/1', 'manifest':manifest, 'sources':sources,
        'planned':plan, 'trials':[], 'complete':False, 'acceptance_passed':False,
        'scope':'Six-second stationary control probe with a small joint-space reach and a 0.2-second horizontal force. Not walking, full manipulation, cabinet service or hardware reliability.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for sample in plan:
        result = run(binary, args.robot, sample['settings'])
        if report['trials']:
            result.pop('frames')
        report['trials'].append({'cohort':sample['cohort'], **result})
        write(args.output, report)
        print(json.dumps({k:v for k,v in result.items() if k!='frames'}),flush=True)
    report['complete'] = True
    report['counts'] = {cohort:{'total':sum(t['cohort']==cohort for t in report['trials']),
        'passed':sum(t['cohort']==cohort and t['success'] for t in report['trials'])} for cohort in ('nominal','held_out')}
    n,h = report['counts']['nominal'],report['counts']['held_out']
    report['held_out_wilson_95_interval'] = wilson(h['passed'],h['total'])
    negatives = [trial for trial in report['trials'] if trial['cohort']=='deliberate_instability']
    report['deliberate_instability_classified'] = bool(negatives) and all(not trial['success'] and
        trial['failure'] in ('unstable_stance','prohibited_ground_contact','controller_infeasible','stabilization_metrics_failed')
        for trial in negatives)
    report['acceptance_passed'] = (n['total']==n['passed']==20 and h['total']==100 and h['passed']>=95
                                  and report['deliberate_instability_classified'])
    report['development_only'] = n['total']<20 or h['total']<100
    write(args.output, report)
    passed = (all(t['success'] for t in report['trials'] if t['cohort']!='deliberate_instability')
              and (not args.failure_fixtures or report['deliberate_instability_classified'])) if report['development_only'] else report['acceptance_passed']
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
