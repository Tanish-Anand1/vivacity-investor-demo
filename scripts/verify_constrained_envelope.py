"""Resumable native trials; planned samples and every outcome are retained.

Development corners are not held-out evidence. The acceptance command draws its
complete held-out set before execution and refuses to resume with changed code.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np

from scripts.verify_constrained_carton import run
from vivacity.bimanual import BimanualConfig, SOURCE_HASHES
from vivacity.constrained_bimanual import CONTROLLER_HASHES
from vivacity.physical_parameters import BoxPhysics


def write(path, value):
    temporary = path.with_suffix('.writing')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf8')
    os.replace(temporary, path)


def plan(args):
    if args.development:
        samples = [dict(source_xy_m=(sx, sy), destination_xy_m=(dx, dy),
                        parcel=BoxPhysics(mass_kg=mass, sliding_friction=friction))
            for sx, sy, dx, dy, mass, friction in [
                (.315, -.005, .405, .005, .4, .9), (.325, .005, .395, -.005, .6, .7),
                (.325, -.005, .405, -.005, .4, .7), (.315, .005, .395, .005, .6, .9),
                (.32, 0., .40, 0., .5, .8)]]
        return [{'cohort':'development', 'config':BimanualConfig(**sample).model_dump()} for sample in samples]
    rng = np.random.default_rng(args.seed)
    samples = [{'cohort':'nominal', 'config':BimanualConfig(seed=7+i).model_dump()} for i in range(args.nominal)]
    for _ in range(args.held_out):
        config = BimanualConfig(source_xy_m=(rng.uniform(.315, .325), rng.uniform(-.005, .005)),
            destination_xy_m=(rng.uniform(.395, .405), rng.uniform(-.005, .005)),
            parcel=BoxPhysics(mass_kg=rng.uniform(.4, .6), sliding_friction=rng.uniform(.7, .9)),
            seed=int(rng.integers(0, 2**31-1)))
        samples.append({'cohort':'held_out', 'config':config.model_dump()})
    return samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--development', action='store_true')
    parser.add_argument('--nominal', type=int, default=20)
    parser.add_argument('--held-out', type=int, default=100)
    parser.add_argument('--seed', type=int, default=20261025)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.nominal <= 100 or not 0 <= args.held_out <= 1000:
        parser.error('Trial counts exceed the offline verification budget')
    planned = plan(args)
    identity = {'controller_sources':CONTROLLER_HASHES, 'task_sources':SOURCE_HASHES,
                'plan_sha256':hashlib.sha256(json.dumps(planned, sort_keys=True).encode()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        report = json.loads(args.output.read_text())
        if report['identity'] != identity:
            raise ValueError('Cannot combine results from changed source or sample plans')
    else:
        report = {'schema_version':'vivacity.constrained-carton-acceptance/1', 'identity':identity,
                  'planned':planned, 'trials':[], 'complete':False, 'acceptance_passed':False,
                  'statistical_scope':'Deterministic nominal repetitions and bounded simulated samples; not hardware reliability.'}
        write(args.output, report)
    for index in range(len(report['trials']), len(planned)):
        sample = planned[index]
        print(json.dumps({'event':'trial_started','index':index,'cohort':sample['cohort']}), flush=True)
        result = run(BimanualConfig.model_validate(sample['config']))
        frames = result.pop('frames')
        result.update(index=index, cohort=sample['cohort'])
        report['trials'].append(result)
        # Retain one full measured replay for each outcome classification.
        key = result['failure_reason'] or 'success'
        replay = args.output.with_name(args.output.stem+'-'+key+'.json.gz')
        if not replay.exists():
            replay.write_bytes(gzip.compress(json.dumps({'trial':result,'frames':frames},allow_nan=False).encode(),mtime=0))
        report['updated_unix_s'] = time.time()
        write(args.output, report)
        print(json.dumps({'event':'trial_finished','index':index,'cohort':sample['cohort'],
            'success':result['task_success'],'reason':result['failure_reason'],
            'compute_wall_s':result['compute_wall_s']}), flush=True)
    report['complete'] = True
    report['counts'] = {cohort:{'trials':sum(t['cohort']==cohort for t in report['trials']),
        'passed':sum(t['cohort']==cohort and t['task_success'] for t in report['trials'])}
        for cohort in ('nominal','held_out','development')}
    n, h = report['counts']['nominal'], report['counts']['held_out']
    report['acceptance_passed'] = (n['trials'] >= 20 and n['passed'] == n['trials']
        and h['trials'] >= 100 and h['passed']/h['trials'] >= .95)
    write(args.output, report)
    print(json.dumps({'complete':True,'counts':report['counts'],'acceptance_passed':report['acceptance_passed']}), flush=True)
    if args.development:
        raise SystemExit(0 if all(t['task_success'] for t in report['trials']) else 1)
    raise SystemExit(0 if report['acceptance_passed'] else 1)


if __name__ == '__main__':
    main()
