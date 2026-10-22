"""Reproducible bounded G1 pickup variation study; no outcome is preselected.

Example: python -m scripts.benchmark_humanoid_pickup --trials 12
The output is an experiment record, not a guarantee of real-robot reliability.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from vivacity.humanoids import HumanoidTrialRequest, simulate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--trials', type=int, default=12)
    parser.add_argument('--seed', type=int, default=2027)
    parser.add_argument('--output', type=Path, default=Path('artifacts/humanoid-pickup-variation.json'))
    args = parser.parse_args()
    if not 1 <= args.trials <= 100:
        parser.error('trials must be between 1 and 100')
    rng = np.random.default_rng(args.seed)
    trials = []
    for index in range(args.trials):
        settings = {
            'robot_id': 'unitree_g1', 'action': 'pickup_place',
            'parcel_mass_kg': float(rng.uniform(.2, 1.2)),
            'parcel_xy_m': (float(rng.uniform(.32, .36)), float(rng.uniform(-.01, .01))),
            'destination_xy_m': (float(rng.uniform(.60, .68)), float(rng.uniform(-.50, -.44))),
        }
        result = simulate(HumanoidTrialRequest(**settings))
        measurement = result['measurements']
        trials.append({
            'index': index, 'configuration': settings,
            'success': result['task_success'], 'failure_reason': result['failure_reason'],
            'simulated_seconds': measurement['simulation_duration_s'],
            'steps': measurement['simulation_steps'],
            'physics_compute_wall_s': measurement['compute_wall_s'],
            'final_parcel_position_m': measurement['final_parcel_position_m'],
            'destination_error_m': measurement['destination_error_m'],
            'minimum_base_height_m': measurement['minimum_base_height_m'],
            'prohibited_contacts': measurement['prohibited_contacts'],
        })
        print(f"{index+1}/{args.trials}: {'PASS' if result['task_success'] else result['failure_reason']}", flush=True)
    successes = sum(trial['success'] for trial in trials)
    interval = binomtest(successes, args.trials).proportion_ci(
        confidence_level=.95, method='exact')
    output = {
        'schema_version': 'vivacity.humanoid-pickup-variation/1.0',
        'seed': args.seed, 'trials': args.trials, 'successes': successes,
        'failures': args.trials-successes,
        'observed_success_fraction': successes/args.trials,
        'exact_binomial_95pct_interval': [interval.low, interval.high],
        'domain': {'parcel_mass_kg': [.2, 1.2], 'parcel_x_m': [.32, .36],
                   'parcel_y_m': [-.01, .01], 'destination_x_m': [.60, .68],
                   'destination_y_m': [-.50, -.44]},
        'disclaimer': 'Uncalibrated MuJoCo simulation with a contact-gated rigid-grasp fixture; not a hardware reliability estimate.',
        'records': trials,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(f"{successes}/{args.trials} success; exact 95% interval [{interval.low:.3f}, {interval.high:.3f}]; {args.output}")


if __name__ == '__main__':
    main()
