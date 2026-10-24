"""Execute bounded negative G1 fixtures and retain the actual failure reason."""
import json
from pathlib import Path

from vivacity.bimanual import BimanualConfig, run_bimanual
from vivacity.physical_parameters import BoxPhysics


def main():
    fixtures = {
        'low_friction': BimanualConfig(parcel=BoxPhysics(sliding_friction=.001,torsional_friction_m=0.,rolling_friction_m=0.)),
        'weak_hand_actuators': BimanualConfig(hand_torque_scale=.01),
        'heavy_carton': BimanualConfig(parcel=BoxPhysics(mass_kg=20.)),
        'unreachable_source': BimanualConfig(source_xy_m=(.68,0.)),
        'large_disturbance': BimanualConfig(disturbance_n=150.),
        'insufficient_time_budget': BimanualConfig(timeout_s=8.),
    }
    report = {'scope':'Native stationary G1 negative fixtures; classifications are measured outcomes, not assumed causes.', 'trials':[]}
    for name, config in fixtures.items():
        result = run_bimanual(config)
        result.pop('frames')
        report['trials'].append({'fixture':name,**result})
        print(name,result['task_success'],result['failure_reason'],flush=True)
    report['all_failed_physically'] = all(not result['task_success'] and result['failure_reason'] for result in report['trials'])
    Path('artifacts/physical-truth-runtime/failure-fixtures.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf8')
    if not report['all_failed_physically']:
        raise SystemExit('A proposed negative fixture succeeded; inspect its actual operating limit')


if __name__=='__main__':main()
