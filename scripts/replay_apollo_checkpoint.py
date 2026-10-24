"""Verify native continuation from a version-compatible Apollo checkpoint.

A reproduced failure is a successful reproducibility check, never a successful
cabinet task. This CLI does not upgrade or bypass incompatible checkpoints.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from vivacity.apollo_door import CabinetDoorPrimitive
from vivacity.execution_checkpoint import Checkpoint, CheckpointBundle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--expected-report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-steps',type=int,default=20000)
    args=parser.parse_args()
    if not 1<=args.max_steps<=50000:
        parser.error('--max-steps must be 1..50000')
    saved=args.checkpoint.read_bytes()
    bundle=CheckpointBundle(Checkpoint.model_validate_json(saved),args.model.read_bytes())
    reference_bytes=args.expected_report.read_bytes()
    expected=json.loads(reference_bytes)
    if expected['compiled_model_sha256']!=bundle.checkpoint.model_sha256:
        raise ValueError('reference report and checkpoint models differ')
    for key in ('task_version','source_hashes'):
        if expected['state'][key]!=bundle.checkpoint.task_state[key]:
            raise ValueError('reference report and checkpoint controller provenance differs')
    task=CabinetDoorPrimitive.from_checkpoint(bundle)
    started=time.perf_counter()
    steps=0
    while task.state['status']=='running' and steps<args.max_steps:
        task.step()
        steps+=1
    reference=expected['frames'][-1]
    state_matches={name:bool(np.array_equal(getattr(task.data,name),reference[name]))
                   for name in ('qpos','qvel','ctrl')}
    state_matches['time_s']=bool(task.data.time==reference['time_s'])
    state_matches['outcome']=all(task.state[key]==expected['state'][key]
                                for key in ('status','phase','success','failure','steps_completed'))
    reproduced=bool(task.state['status']!='running' and all(state_matches.values()))
    report={'schema_version':'vivacity.apollo-checkpoint-replay/1',
        'checkpoint_sha256':hashlib.sha256(saved).hexdigest(),
        'reference_report_sha256':hashlib.sha256(reference_bytes).hexdigest(),
        'model_sha256':bundle.checkpoint.model_sha256,
        'controller':task.controller.version,'source_sha256':task.state['source_hashes'],
        'initial_steps':bundle.checkpoint.steps_completed,'executed_steps':steps,
        'reproduced':reproduced,'checks':state_matches,'status':task.state['status'],
        'task_success':task.state['success'],'failure':task.state['failure'],
        'measurements':task.observe(),'elapsed_wall_s':time.perf_counter()-started}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('reproduced','checks','status','task_success','failure','executed_steps')}))
    raise SystemExit(0 if reproduced else 1)


if __name__=='__main__':
    main()
