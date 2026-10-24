"""Execute native G1 contact trials and retain failures; never fabricate a gate.

python -m scripts.verify_bimanual --nominal 20 --held-out 100
Reports contain a seed and full parameters for every independently initialized
trial. Held-out samples are drawn before simulation from the declared envelope.
"""
import argparse
import json
import math
from pathlib import Path
import time

import numpy as np

from vivacity.bimanual import BimanualConfig, run_bimanual
from vivacity.physical_parameters import BoxPhysics


def wilson(successes, trials):
    if not trials:
        return None
    z = 1.959963984540054
    p = successes/trials
    denom = 1+z*z/trials
    center = (p+z*z/(2*trials))/denom
    radius = z*math.sqrt(p*(1-p)/trials+z*z/(4*trials**2))/denom
    return [max(0., center-radius), min(1., center+radius)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--nominal', type=int, default=1)
    parser.add_argument('--held-out', type=int, default=0)
    parser.add_argument('--output', default='artifacts/physical-truth-runtime/bimanual-acceptance.json')
    args = parser.parse_args()
    if not 0 <= args.nominal <= 100 or not 0 <= args.held_out <= 1000:
        parser.error('bounded counts required')
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261024)
    fixtures = [('nominal', BimanualConfig(seed=i+1)) for i in range(args.nominal)]
    envelope = {'source_x_m': [.315, .325], 'source_y_m': [-.005, .005],
                'destination_x_m': [.395, .405], 'destination_y_m': [-.005, .005],
                'mass_kg': [.4, .6], 'sliding_friction': [.7, .9]}
    for i in range(args.held_out):
        fixtures.append(('held_out', BimanualConfig(
            source_xy_m=(float(rng.uniform(*envelope['source_x_m'])), float(rng.uniform(*envelope['source_y_m']))),
            destination_xy_m=(float(rng.uniform(*envelope['destination_x_m'])), float(rng.uniform(*envelope['destination_y_m']))),
            parcel=BoxPhysics(mass_kg=float(rng.uniform(*envelope['mass_kg'])),
                              sliding_friction=float(rng.uniform(*envelope['sliding_friction']))), seed=1000+i)))
    report = {'schema_version': 'vivacity.bimanual-acceptance/1', 'held_out_seed': 20261024,
              'envelope': envelope, 'trials': [], 'started_unix_s': time.time(),
              'statistical_scope': 'Nominal trials are deterministic repetitions, not independent reliability samples. Wilson intervals apply only to the sampled held-out configuration distribution; neither estimates hardware reliability.',
              'scope': 'Native G1 contact baseline. Not the complete Physical Truth release or hardware reliability.'}
    for index, (kind, config) in enumerate(fixtures):
        result = run_bimanual(config)
        result.pop('frames')
        report['trials'].append({'index': index, 'kind': kind, **result})
        for category in ('nominal', 'held_out'):
            trials = [r for r in report['trials'] if r['kind'] == category]
            passed = sum(int(r['task_success']) for r in trials)
            report[category] = {'trials': len(trials), 'passed': passed,
                                'wilson_95_interval': wilson(passed, len(trials)) if category == 'held_out' else None}
        report['trial_count_gate_passed'] = (report['nominal']['trials'] >= 20 and
                                             report['nominal']['passed'] == report['nominal']['trials'] and
                                             report['held_out']['trials'] >= 100 and
                                             report['held_out']['passed']/report['held_out']['trials'] >= .95)
        report['finished_unix_s'] = time.time()
        destination.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf8')
        print(json.dumps({'index': index, 'kind': kind, 'success': result['task_success'],
                          'failure': result['failure_reason'], 'compute_s': result['compute_wall_s'],
                          'placement_error_m': result['measurements']['last_measurement'].get('destination_error_m')}), flush=True)
    print(str(destination.resolve()), flush=True)


if __name__ == '__main__':
    main()
