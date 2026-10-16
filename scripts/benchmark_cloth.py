"""Repeat the fixed, explicitly constrained Panda/flex fixture in real MuJoCo."""
import argparse
import json
from pathlib import Path
import time

from vivacity.cloth import ClothBackend
from vivacity.schemas import ClothConfig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--output', default='artifacts/cloth-reliability.json')
    args = parser.parse_args()
    if not 1 <= args.runs <= 100:
        parser.error('runs must be 1..100')
    backend = ClothBackend()
    world = backend.create_world(ClothConfig().model_dump(), 7)
    initial = backend.snapshot(world)
    action = {'kind': 'clamp_fold', 'planning_feasible': True,
              'lift_height': .2, 'motion_seconds': 3., 'lateral_offset': 0.}
    report = {'scope': 'fixed pre-attached bar and hinged 7x7 flex fixture; not autonomous cloth grasping',
              'seed': 7, 'config': world.config, 'simulator_version': backend.version,
              'model_hash': initial['model_hash'], 'runs': [], 'started_unix_s': time.time()}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    for index in range(args.runs):
        branch = backend.fork(initial)
        backend.apply_action(branch, action)
        result = backend.simulate(branch, {'max_simulation_seconds': 25})
        evaluation = backend.evaluate(branch, result)
        report['runs'].append({'index': index, 'evaluation': evaluation,
                              'physics_wall_seconds': result['physics_wall_seconds'],
                              'simulation_steps': result['simulation_steps']})
        report['successes'] = sum(run['evaluation']['success'] for run in report['runs'])
        report['failures'] = len(report['runs']) - report['successes']
        report['elapsed_wall_seconds'] = time.time() - report['started_unix_s']
        output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
        print(f"{index+1}/{args.runs}: {evaluation['status']}; "
              f"alignment={evaluation['alignment_error_m']:.6f}m; "
              f"coverage={evaluation['vertex_coverage']:.3f}", flush=True)
    return 0 if not report['failures'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
