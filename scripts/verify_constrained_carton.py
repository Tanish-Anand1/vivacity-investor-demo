"""Execute the experimental wrench controller in native MuJoCo; retain failures."""
import argparse
import json
from pathlib import Path
import time

from vivacity.bimanual import BimanualConfig
from vivacity.constrained_bimanual import ConstrainedBimanualTask


def run(config):
    start = time.perf_counter()
    task = ConstrainedBimanualTask(config)
    frames = [task.frame()]
    while task.state['status'] == 'running':
        task.step()
        if task.state['steps'] % 25 == 0 or task.state['status'] != 'running':
            frames.append(task.frame())
    result = task.result()
    result.update(frames=frames, compute_wall_s=time.perf_counter()-start)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path)
    parser.add_argument('--output', type=Path, default=Path('artifacts/physical-truth-runtime/constrained-carton.json'))
    args = parser.parse_args()
    config = BimanualConfig.model_validate_json(args.config.read_text()) if args.config else BimanualConfig()
    result = run(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, allow_nan=False), encoding='utf8')
    print(json.dumps({k: result[k] for k in ('status', 'failure_reason', 'compute_wall_s')} | {
        'steps': result['measurements']['steps'], 'phase': result['measurements']['phase'],
        'minimum_hold_share': result['measurements']['minimum_hold_share'],
        'placement_error_m': result['measurements']['last_measurement'].get('destination_error_m'),
        'solver_calls': result['controller_diagnostics']['calls'],
        'maximum_constraint_violation': result['controller_diagnostics']['maximum_violation']}), flush=True)
    print(result['measurements'].get('controller_error'), flush=True)


if __name__ == '__main__':
    main()
