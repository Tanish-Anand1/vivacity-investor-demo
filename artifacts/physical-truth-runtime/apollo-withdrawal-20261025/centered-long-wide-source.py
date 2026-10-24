"""Bounded research fork with an explicitly longer door-phase time budget.

All contact, posture, torque and task success criteria remain unchanged.
This is not acceptance of the application's 12-second door controller.
"""
import hashlib
import inspect
import json
from pathlib import Path
import textwrap
import time
from types import MethodType

import numpy as np
from vivacity.apollo_door import CabinetDoorPrimitive
from vivacity.execution_checkpoint import Checkpoint, CheckpointBundle

root=Path(__file__).parent
origin=root/'measured-grasp'
report=json.loads((origin/'report.json').read_text())
file=origin/'checkpoints/0017763-open_wide.json'
task=CabinetDoorPrimitive.from_checkpoint(CheckpointBundle(
    Checkpoint.model_validate_json(file.read_bytes()),(origin/report['model_file']).read_bytes()))
source=textwrap.dedent(inspect.getsource(CabinetDoorPrimitive.step))
assert source.count("'open_wide':12.")==1
source=source.replace("'open_wide':12.","'open_wide':45.")
namespace=dict(CabinetDoorPrimitive.step.__globals__)
exec(compile(source,'research_door_budget','exec'),namespace)
task.step=MethodType(namespace['step'],task)
compute=task.controller.compute
command=task.state['start_door_angle_rad']

def override(data,reference,goals=None,released_hands=()):
    global command
    goals={**goals}
    if task.state['phase']=='open_wide':
        actual=float(data.joint('service_door_hinge').qpos[0])
        command=min(task.state['opening_angle_rad'],command+.08*task.model.opt.timestep,actual+.04)
        goal=task._wide_grasp_pose(command)
        axis=data.site('l_service_tcp').xmat.reshape(3,3)[:,1]
        position=np.asarray(goal['position'])
        error=float(axis@(data.geom('service_latch_button').xpos-position))
        goal['position']=(position+axis*np.clip(error,-.015,.015)).tolist()
        goals['l']=goal
    return compute(data,reference,goals,released_hands)

task.controller.compute=override
started=time.perf_counter()
frames=[]
next_progress=task.data.time+2.
while task.state['status']=='running':
    task.step()
    if task.state['steps_completed']%50==0:
        frames.append(task.frame())
    if task.data.time>=next_progress:
        measured=task.observe()
        print(json.dumps({'time_s':task.data.time,'door_angle_rad':measured['door_angle_rad'],
                          'grip':task.state['grip_forces']}),flush=True)
        next_progress+=2.
out={'parent_checkpoint_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
    'override_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'overridden_step_source':source,
    'scope':'Research controller with longer initial budget; not application controller acceptance.',
    'settings':{'centering':True,'rate_rad_s':.08,'lookahead_rad':.04,'phase_timeout_s':45.},
    'state':task.state,'controller_checkpoint':task.controller.snapshot(),
    'measurements':task.observe(),'frames':frames,'qpos':task.data.qpos.tolist(),
    'compute_s':time.perf_counter()-started}
(root/'centered-long-wide.json').write_text(json.dumps(out))
print(json.dumps({'status':task.state['status'],'success':task.state['success'],
                  'failure':task.state['failure'],'measurements':out['measurements'],
                  'compute_s':out['compute_s']}),flush=True)
