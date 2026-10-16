"""Run distinct full MuJoCo trials across reproducible physical configurations.

This is a local audit, not a change to the free public host's resource budget.
Every trial has a persisted full integration state in SQLite. A JSONL catalog
records measured outcomes and fingerprints; best full traces are exported.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from vivacity.native_pick_place import NativePickup
from vivacity.runtime import Runtime
from vivacity.schemas import CreateWorld, ExperimentRequest, RoboticsConfig
from vivacity.storage import encode


def fingerprint(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def scenarios(count, seed):
    rng = np.random.default_rng(seed)
    for index in range(count):
        kind = 'blocked_control' if index % 5 == 4 else (
            'obstacle_outside_route' if index % 5 == 3 else 'clear')
        cube = [float(rng.uniform(.44, .56)), float(rng.uniform(-.20, -.11)), .026]
        config = RoboticsConfig(
            task='pick_place', cube_position=cube,
            placement_position=[float(rng.uniform(.44, .56)), float(rng.uniform(.12, .24)), .026],
            cube_mass=float(rng.uniform(.03, .12)), cube_friction=float(rng.uniform(.4, 1.3)),
            obstacle_enabled=kind != 'clear',
            obstacle_position=[cube[0], cube[1], .12] if kind == 'blocked_control' else [.74, .45, .10],
            obstacle_size=[.10, .10, .12] if kind == 'blocked_control' else [.03, .03, .10],
        )
        yield index, kind, (seed + index) % (2**32), config


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trials', type=int, default=5000)
    parser.add_argument('--scenarios', type=int, default=50)
    parser.add_argument('--seed', type=int, default=20261011)
    parser.add_argument('--output', default='artifacts/varied-physics-5000.json')
    parser.add_argument('--database', default='data/run/varied-physics-5000.sqlite3')
    args = parser.parse_args()
    if not 1 <= args.scenarios <= args.trials <= 5000 or args.trials % args.scenarios:
        parser.error('trials must be divisible by scenarios, with 1 <= scenarios <= trials <= 5000')
    if not 0 <= args.seed < 2**32:
        parser.error('seed must be an unsigned 32-bit integer')
    output, database = ROOT / args.output, ROOT / args.database
    catalog = output.with_name(output.stem + '-trials.jsonl')
    if output.exists() or database.exists() or catalog.exists():
        parser.error('use new output/database paths; previous evidence will not be overwritten')
    output.parent.mkdir(parents=True, exist_ok=True)
    database.parent.mkdir(parents=True, exist_ok=True)
    per_scene = args.trials // args.scenarios
    started, cpu = time.perf_counter(), time.process_time()
    report = {
        'schema_version': 'vivacity.audit/1.0', 'status': 'running',
        'started_unix_s': time.time(), 'seed': args.seed,
        'requested_trials': args.trials, 'requested_scenarios': args.scenarios,
        'trials_per_scenario': per_scene, 'python': platform.python_version(),
        'source_scope': 'Current Panda backend runtime; actual native MuJoCo integration.',
        'execution_environment': os.getenv('VIVACITY_AUDIT_ENVIRONMENT', 'local'),
        'scope': 'Bounded synthetic position/mass/friction variation; intentionally blocked controls. Not hardware or broad randomized reliability.',
        'database': str(database), 'trial_catalog': str(catalog),
        'actual_trials': 0, 'successful_trials': 0, 'failed_trials': 0,
        'trial_simulation_steps': 0, 'total_simulation_steps': 0,
        'failure_statuses': {}, 'scenarios': [], 'top_branch_exports': [],
    }
    distinct_controls, distinct_inputs, statuses = set(), set(), Counter()
    best, repeat_samples = [], {}
    runtime = Runtime(database)
    try:
        report['mujoco'] = runtime.backends['mujoco'].version
        save(output, report)
        with catalog.open('x', encoding='utf-8') as stream:
            for index, kind, seed, config in scenarios(args.scenarios, args.seed):
                world = runtime.create_world(CreateWorld(backend='mujoco', seed=seed, config=config))
                parent_hash, config_hash = fingerprint(world['state']), fingerprint(world['config'])
                experiment = runtime.submit(world['id'], ExperimentRequest(
                    physics_trials=per_scene, search_candidates=per_scene,
                    execute_selected=True, max_simulation_seconds=40))
                last_print = 0.
                while experiment['status'] in ('queued', 'running'):
                    now = time.perf_counter()
                    if now - last_print >= 20:
                        search = experiment['result'].get('search', {})
                        report['active_scenario'] = {
                            'index': index, 'kind': kind, 'world_id': world['id'],
                            'experiment_id': experiment['id'],
                            'completed_trials': search.get('fully_simulated', 0),
                            'successful_trials': search.get('verified_feasible', 0),
                            'physics_steps': search.get('trial_simulation_steps', 0),
                        }
                        report['elapsed_wall_seconds'] = now - started
                        save(output, report)
                        print(json.dumps({'completed_trials': report['actual_trials'],
                            'active': report['active_scenario'],
                            'elapsed_seconds': round(now-started, 2)}), flush=True)
                        last_print = now
                    time.sleep(.5)
                    experiment = runtime.get_experiment(experiment['id'])
                if experiment['status'] != 'completed':
                    raise RuntimeError(f"scenario {index}: {experiment['status']} / {experiment['error']}")
                records, after = [], -1
                while True:
                    page = runtime.store.trials(experiment['id'], after, 100)
                    if not page['items']:
                        break
                    records.extend(page['items'])
                    after = page['next_after']
                assert len(records) == per_scene
                assert {r['candidate_index'] for r in records} == set(range(per_scene))
                assert len({r['parent_state_reference'] for r in records}) == 1
                assert fingerprint(runtime.get_world(world['id'])['initial_state']) == parent_hash
                assert all(r['performance']['simulation_steps'] > 0 and
                           r['final_state']['integration_state'] for r in records)
                scene_steps = sum(r['performance']['simulation_steps'] for r in records)
                assert scene_steps == experiment['performance']['trial_simulation_steps']
                for record in records:
                    distinct_controls.add(record['control_sha256'])
                    intervention_hash = fingerprint([world['config'], record['action']['stages']])
                    distinct_inputs.add(intervention_hash)
                    evaluation = record['evaluation']
                    statuses[evaluation['status']] += 1
                    stream.write(encode({
                        'scenario_index': index, 'scenario_kind': kind,
                        'experiment_id': experiment['id'], 'world_id': world['id'],
                        'seed': seed, 'configuration_sha256': config_hash,
                        'candidate_index': record['candidate_index'],
                        'control_sha256': record['control_sha256'],
                        'intervention_sha256': intervention_hash,
                        'parent_state_reference': record['parent_state_reference'],
                        'final_state_sha256': fingerprint(record['final_state']),
                        'performance': record['performance'], 'evaluation': evaluation,
                    }) + '\n')
                    category = 'success' if evaluation['success'] else 'failure'
                    if category not in repeat_samples:
                        repeat_samples[category] = (world['state'], record)
                stream.flush()
                count_ok = sum(r['evaluation']['success'] for r in records)
                report['actual_trials'] += len(records)
                report['successful_trials'] += count_ok
                report['failed_trials'] += len(records) - count_ok
                report['trial_simulation_steps'] += scene_steps
                report['total_simulation_steps'] += experiment['performance']['simulation_steps']
                report['failure_statuses'] = {s: n for s, n in statuses.items() if s != 'execution_success'}
                report['distinct_commands'] = len(distinct_controls)
                report['distinct_interventions'] = len(distinct_inputs)
                report['scenarios'].append({
                    'index': index, 'kind': kind, 'seed': seed, 'configuration': world['config'],
                    'configuration_sha256': config_hash, 'model_hash': world['state']['model_hash'],
                    'initial_state_sha256': parent_hash,
                    'world_id': world['id'], 'experiment_id': experiment['id'],
                    'actual_trials': len(records), 'successful_trials': count_ok,
                    'failed_trials': len(records)-count_ok,
                    'measured_statuses': dict(Counter(r['evaluation']['status'] for r in records)),
                    'selected_branch_id': experiment['selected_branch_id'],
                    'fresh_execution_evaluation': experiment['result'].get('execution_evaluation'),
                    'performance': experiment['performance'],
                })
                for branch_id in experiment['result'].get('top_feasible_branch_ids', []):
                    branch = runtime.store.get('branches', branch_id)
                    best.append((branch['evaluation']['execution_duration_s'],
                                 branch['evaluation']['goal_error_m'], experiment['id'], branch_id))
                best = sorted(best)[:3]
                report['elapsed_wall_seconds'] = time.perf_counter()-started
                save(output, report)
        assert report['actual_trials'] == args.trials
        assert len(distinct_controls) == len(distinct_inputs) == args.trials
        assert len({s['configuration_sha256'] for s in report['scenarios']}) == args.scenarios
        repeat_results = {}
        for category, (snapshot, record) in repeat_samples.items():
            _, evaluation, final = NativePickup(runtime.backends['mujoco'].pick_place, snapshot).simulate(
                record['action'], {'max_simulation_seconds': 40})
            assert evaluation == record['evaluation'] and final == record['final_state']
            repeat_results[category] = {'evaluation_and_full_state_exact': True,
                                       'candidate_index': record['candidate_index']}
        for rank, (_, _, experiment_id, branch_id) in enumerate(best, 1):
            exported = runtime.export_branch(experiment_id, branch_id)
            path = output.with_name(output.stem + f'-top-{rank}.json')
            save(path, exported)
            report['top_branch_exports'].append(str(path))
        report.pop('active_scenario', None)
        report.update(status='passed', finished_unix_s=time.time(),
            elapsed_wall_seconds=time.perf_counter()-started,
            process_cpu_seconds=time.process_time()-cpu, repeat_verification=repeat_results,
            measurement_complete=True, distinct_configurations=args.scenarios,
            status_counts=dict(statuses), trial_catalog_sha256=hashlib.sha256(catalog.read_bytes()).hexdigest())
        with runtime.store.connect() as db:
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        report['sqlite_bytes'] = database.stat().st_size
        save(output, report)
        print(json.dumps({k: v for k, v in report.items() if k != 'scenarios'}, indent=2), flush=True)
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}',
                      elapsed_wall_seconds=time.perf_counter()-started)
        save(output, report)
        raise
    finally:
        runtime.close()


if __name__ == '__main__':
    main()
