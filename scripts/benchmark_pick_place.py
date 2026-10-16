"""Executed fixed physical benchmark; no recorded trajectory is used as execution.

Run: python -m scripts.benchmark_pick_place --runs 20
"""
import argparse
import json
from pathlib import Path
import time

from vivacity.pick_place import PickPlaceBackend
from vivacity.schemas import RoboticsConfig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=20)
    parser.add_argument('--output', default='artifacts/pick-place-benchmark.json')
    args = parser.parse_args()
    if not 1 <= args.runs <= 100:
        parser.error('runs must be 1..100')
    b = PickPlaceBackend()
    w = b.create_world(RoboticsConfig(task='pick_place', obstacle_enabled=False).model_dump(), 7)
    initial = b.snapshot(w)
    actions, planning = b.candidates(w, 1, 100)
    report = {'scope': 'fixed unobstructed contact pickup and placement', 'simulator_version': b.version,
              'config': w.config, 'seed': w.seed, 'model_hash': w.model_hash,
              'planning_wall_seconds': planning, 'runs': [], 'started_unix_s': time.time()}
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    for index in range(args.runs):
        branch = b.fork(initial)
        b.apply_action(branch, actions[0])
        result = b.simulate(branch, {'max_simulation_seconds': 60})
        evaluation = b.evaluate(branch, result)
        report['runs'].append({'index': index, 'evaluation': evaluation,
                               'physics_wall_seconds': result['physics_wall_seconds'],
                               'simulation_steps': result['simulation_steps']})
        if index == 0:
            output.with_name(output.stem+'-trace.json').write_text(json.dumps({
                'initial_state': initial, 'action': actions[0], 'frames': result['trace'],
                'final_state': b.snapshot(branch), 'evaluation': evaluation}, allow_nan=False), encoding='utf-8')
        report['successes'] = sum(r['evaluation']['success'] for r in report['runs'])
        report['failures'] = len(report['runs'])-report['successes']
        report['elapsed_wall_seconds'] = time.time()-report['started_unix_s']
        output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
        print(f"{index+1}/{args.runs}: {evaluation['status']}; error={evaluation['goal_error_m']:.6f}m; "
              f"lift={evaluation['max_cube_height_m']:.4f}m; physics={result['physics_wall_seconds']:.2f}s", flush=True)
    print(json.dumps({k: v for k, v in report.items() if k not in ('runs', 'config')}, indent=2))


if __name__ == '__main__':
    main()
