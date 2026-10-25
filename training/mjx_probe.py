"""Run native/GPU controller parity, batch independence and actual throughput.

Not a trained policy or a locomotion acceptance test. Every failed check stays
in the report. Run as a bounded subprocess from the free-GPU notebook.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import time
import traceback


def run(robot, batch_size, transitions, report):
    import jax
    import jax.numpy as jp
    import numpy as np
    from training.mjx_locomotion import CompleteLocomotion
    from training.native_locomotion import NativeLocomotion, Settings
    from vivacity.execution_checkpoint import model_bytes

    started = time.perf_counter()
    env = CompleteLocomotion(robot)
    native = NativeLocomotion(robot, Settings())
    print('Complete models compiled; comparing closed-loop controls.',flush=True)
    assert native.artifact.sha256 == env.embodiment['compiled_model_sha256']
    report.update(robot=robot, implementation=env.implementation, model_sha256=native.artifact.sha256,
                  contract=native.contract.manifest, contract_sha256=native.contract.sha256,
                  source_hashes={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                 for name in ('mjx_locomotion.py','mjx_probe.py','locomotion_contract.py','native_locomotion.py')},
                  batch_size=batch_size, requested_transitions=transitions,
                  contact_buffer_capacities=env.capacities, seed=7)
    step = jax.jit(env.step)
    state = env.reset(jax.random.PRNGKey(7),jp.asarray(native.settings.command))
    checks = []
    for index in range(3):
        action = np.zeros(env.model.nu) if index == 0 else np.full(env.model.nu,.015)
        result = native.step(action)
        state = step(state,jp.asarray(action))
        state.obs.block_until_ready()
        checks.append({'transition':index+1,
            'qpos_max_abs':float(np.max(np.abs(np.asarray(state.data.qpos)-native.data.qpos))),
            'qvel_max_abs':float(np.max(np.abs(np.asarray(state.data.qvel)-native.data.qvel))),
            'observation_max_abs':float(np.max(np.abs(np.asarray(state.obs)-result['observation']))),
            'reward_abs':abs(float(state.reward)-result['reward']),
            'native_failure':result['failure'], 'gpu_failure':env.failures[int(state.failure)]})
        print(json.dumps(checks[-1]),flush=True)
    report['parity'] = checks
    report['parity_bounds'] = {'qpos_max_abs':.005,'qvel_max_abs':.1,'observation_max_abs':.01,'reward_abs':.001}
    report['parity_passed'] = all(all(row[key]<limit for key,limit in report['parity_bounds'].items())
        and (row['native_failure'] or 'none') == row['gpu_failure'] for row in checks)
    report['initialization_and_parity_wall_s'] = time.perf_counter()-started
    if not report['parity_passed']:
        report['passed'] = False
        return

    reset_batch,step_batch = env.batched()
    keys = jax.random.split(jax.random.PRNGKey(7),batch_size)
    states = reset_batch(keys)
    zeros = jp.zeros((batch_size,env.model.nu))
    compiled = step_batch(states,zeros)
    compiled.obs.block_until_ready()
    print('Independent GPU batch compiled.',flush=True)
    report['batch_compile_wall_s'] = time.perf_counter()-started-report['initialization_and_parity_wall_s']
    # One changed row must leave every other independent MjData trajectory equal.
    changed = step_batch(states,zeros.at[0].set(.02))
    changed.obs.block_until_ready()
    report['independent_rows_unchanged'] = bool(np.array_equal(
        np.asarray(compiled.data.qpos)[1:],np.asarray(changed.data.qpos)[1:]))
    report['changed_row_diverged'] = bool(not np.array_equal(
        np.asarray(compiled.data.qpos)[0],np.asarray(changed.data.qpos)[0]))
    replayed = step_batch(states,zeros)
    replayed.obs.block_until_ready()
    report['repeat_deterministic'] = bool(np.array_equal(np.asarray(replayed.data.qpos),np.asarray(compiled.data.qpos)))
    timed = time.perf_counter()
    for _ in range(transitions):
        states = step_batch(states,zeros)
        states.obs.block_until_ready()
    report['batch_execution_wall_s'] = time.perf_counter()-timed
    report['measured_steps_per_world'] = np.asarray(states.steps).tolist()
    report['total_measured_physics_steps'] = int(np.asarray(states.steps).sum())
    report['physics_steps_per_wall_second'] = report['total_measured_physics_steps']/report['batch_execution_wall_s']
    report['terminal_failures'] = [env.failures[int(value)] for value in np.asarray(states.failure)]
    report['final_root_heights_m'] = np.asarray(states.metrics['root_height_m']).tolist()
    report['model_unchanged'] = hashlib.sha256(model_bytes(env.model)).hexdigest()==report['model_sha256']
    report['max_resident_memory_bytes'] = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024
    report['passed'] = all(report[key] for key in ('parity_passed','independent_rows_unchanged',
        'changed_row_diverged','repeat_deterministic','model_unchanged'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--robot',choices=('h1','g1','apollo'),required=True)
    parser.add_argument('--batch-size',type=int,choices=range(2,17),default=2)
    parser.add_argument('--transitions',type=int,choices=range(1,101),default=10)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report={'schema_version':'vivacity.mjx-control-batch-probe/1','passed':False,
            'scope':'Control parity and batch independence; not locomotion acceptance',
            'trained_policy':None,'task_success':False}
    started=time.perf_counter()
    try:
        run(args.robot,args.batch_size,args.transitions,report)
    except Exception as error:
        report.update(failure_type=type(error).__name__,failure=str(error),traceback=traceback.format_exc())
    report['wall_s']=time.perf_counter()-started
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('contract','traceback')},allow_nan=False),flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':
    main()
