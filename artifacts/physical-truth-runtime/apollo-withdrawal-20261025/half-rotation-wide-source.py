"""Independent native research fork with a partially door-aligned wrist.

Original time, contact, collision and task success limits are unchanged.
"""
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from scipy.spatial.transform import Rotation
from vivacity.apollo_door import CabinetDoorPrimitive
from vivacity.execution_checkpoint import Checkpoint, CheckpointBundle

root=Path(__file__).parent
origin=root/'measured-grasp'
report=json.loads((origin/'report.json').read_text())
file=origin/'checkpoints/0017763-open_wide.json'
task=CabinetDoorPrimitive.from_checkpoint(CheckpointBundle(
    Checkpoint.model_validate_json(file.read_bytes()),(origin/report['model_file']).read_bytes()))
initial=task.data.site('l_service_tcp').xpos.copy()
rotation=task.data.site('l_service_tcp').xmat.reshape(3,3).copy()
hinge=task.data.body('service_door').xpos.copy()
initial_angle=float(task.data.joint('service_door_hinge').qpos[0])
compute=task.controller.compute

def override(data,reference,goals=None,released_hands=()):
    goals={**goals}
    if task.state['phase']=='open_wide':
        fraction=min(1.,(data.time-task.state['phase_started_s'])/6.)
        blend=fraction*fraction*(3.-2.*fraction)
        turn=blend*(task.state['opening_angle_rad']-initial_angle)
        position=hinge+Rotation.from_rotvec([0.,0.,-turn]).apply(initial-hinge)
        orient=Rotation.from_rotvec([0.,0.,-.5*turn]).as_matrix()@rotation
        axis=data.site('l_service_tcp').xmat.reshape(3,3)[:,1]
        error=float(axis@(data.geom('service_latch_button').xpos-position))
        goal={'position':(position+axis*np.clip(error,-.015,.015)).tolist(),'rotation':orient.tolist()}
        goals['l']=goal
        task.state['research_goal']=goal
    return compute(data,reference,goals,released_hands)

task.controller.compute=override
started=time.perf_counter();frames=[]
while task.state['status']=='running':
    task.step()
    if task.state['steps_completed']%50==0:
        frame=task.frame()
        frame['applied_research_goal']=task.state.get('research_goal')
        frames.append(frame)
out={'parent_checkpoint_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
    'override_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope':'Research controller override; not application controller acceptance.',
    'settings':{'centering':True,'wrist_rotation_fraction':.5,'rigid_door_tcp_path':True,'phase_timeout_s':12.},
    'state':task.state,'controller_checkpoint':task.controller.snapshot(),
    'measurements':task.observe(),'frames':frames,'qpos':task.data.qpos.tolist(),
    'compute_s':time.perf_counter()-started}
(root/'half-rotation-wide.json').write_text(json.dumps(out))
print(json.dumps({'status':task.state['status'],'success':task.state['success'],
                  'failure':task.state['failure'],'door_angle_rad':out['measurements']['door_angle_rad'],
                  'grip':task.state['grip_forces'],'compute_s':out['compute_s']}),flush=True)
