"""Explicit research intervention on an independent full-state native fork."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from vivacity.apollo_door import CabinetDoorPrimitive
from vivacity.execution_checkpoint import Checkpoint,CheckpointBundle

p=argparse.ArgumentParser();p.add_argument('--centering',action='store_true');p.add_argument('--rate',type=float)
p.add_argument('--label',required=True);args=p.parse_args()
root=Path(__file__).parent
origin=root/'measured-grasp'
report=json.loads((origin/'report.json').read_text())
file=origin/'checkpoints/0017763-open_wide.json'
task=CabinetDoorPrimitive.from_checkpoint(CheckpointBundle(Checkpoint.model_validate_json(file.read_text()),
    (origin/report['model_file']).read_bytes()))
compute=task.controller.compute
command=task.state['start_door_angle_rad']
def override(data,reference,goals=None,released_hands=()):
    global command
    goals={**goals}
    if task.state['phase']=='open_wide':
        if args.rate:
            actual=float(data.joint('service_door_hinge').qpos[0])
            command=min(task.state['opening_angle_rad'],command+args.rate*task.model.opt.timestep,actual+.04)
            goals['l']=task._wide_grasp_pose(command)
        if args.centering:
            goal={**goals['l']}
            axis=data.site('l_service_tcp').xmat.reshape(3,3)[:,1]
            position=np.asarray(goal['position'])
            error=float(axis@(data.geom('service_latch_button').xpos-position))
            goal['position']=(position+axis*np.clip(error,-.015,.015)).tolist()
            goals['l']=goal
    return compute(data,reference,goals,released_hands)
task.controller.compute=override
started=time.perf_counter();frames=[]
while task.state['status']=='running':
    task.step()
    if task.state['steps_completed']%50==0:
        frames.append(task.frame())
out={'parent_checkpoint_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
    'override_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope':'Research controller override; not acceptance for the application controller.',
    'settings':vars(args),'state':task.state,'measurements':task.observe(),'frames':frames,
    'qpos':task.data.qpos.tolist(),'compute_s':time.perf_counter()-started}
(root/(args.label+'.json')).write_text(json.dumps(out))
print(json.dumps({'label':args.label,'status':task.state['status'],'failure':task.state['failure'],
    'door_angle':out['measurements']['door_angle_rad'],'grip':task.state['grip_forces'],
    'compute_s':out['compute_s']}),flush=True)
