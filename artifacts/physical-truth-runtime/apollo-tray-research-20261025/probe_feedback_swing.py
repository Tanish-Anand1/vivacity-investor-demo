"""Native continuation with measured rigid grasp references in the first swing."""
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from scipy.spatial.transform import Rotation
from vivacity.apollo_door import CabinetDoorPrimitive
from vivacity.execution_checkpoint import Checkpoint, CheckpointBundle

root=Path('data/physical-truth-oct25/lower-tray-swing')
file=root/'0009678-open.json'
task=CabinetDoorPrimitive.from_checkpoint(CheckpointBundle(
    Checkpoint.model_validate_json(file.read_bytes()),(root/'model.mjb').read_bytes()))
initial_angle=float(task.data.joint('service_door_hinge').qpos[0])
hinge=task.data.body('service_door').xpos.copy()
poses={side:{'position':task.data.site(side+'_service_tcp').xpos.copy(),
             'rotation':task.data.site(side+'_service_tcp').xmat.reshape(3,3).copy()} for side in ('l','r')}
def first_arc(side,angle):
    rotation=Rotation.from_rotvec([0.,0.,-(angle-initial_angle)])
    return {'position':(hinge+rotation.apply(poses[side]['position']-hinge)).tolist(),
            'rotation':poses[side]['rotation'].tolist()}
task.state['goals']={side:first_arc(side,.25) for side in ('l','r')}
task.state['start_goals']={side:first_arc(side,initial_angle) for side in ('l','r')}
def arc(angle):
    g=task.state['wide_grasp_tracking']
    initial=g.setdefault('research_initial_angle',float(task.data.joint('service_door_hinge').qpos[0]))
    delta=angle-initial
    offset=Rotation.from_rotvec([0.,0.,-delta]).apply(g['tcp_offset_world'])
    position=np.asarray(g['hinge_position'])+Rotation.from_rotvec([0.,0.,-angle]).apply(g['button_in_door'])+offset
    orientation=Rotation.from_rotvec([0.,0.,-.5*delta]).as_matrix()@g['rotation']
    return {'position':position.tolist(),'rotation':orientation.tolist()}
task._wide_grasp_pose=arc
compute=task.controller.compute
def control(data,reference,goals=None,released_hands=()):
    if task.state['phase']=='open':
        f=min(1.,(data.time-task.state['phase_started_s'])/3.)
        angle=initial_angle+f*f*(3.-2.*f)*(.25-initial_angle)
        goals={side:first_arc(side,angle) for side in ('l','r')}
    if task.state['phase'] in ('open','open_wide'):
        goals={**goals}
        goal={**goals['l']}
        axis=data.site('l_service_tcp').xmat.reshape(3,3)[:,1]
        error=float(axis@(data.geom('service_latch_button').xpos-goal['position']))
        goal['position']=(np.asarray(goal['position'])+axis*np.clip(error,-.015,.015)).tolist()
        goals['l']=goal
    return compute(data,reference,goals,released_hands)
task.controller.compute=control
started=time.perf_counter();frames=[];next_log=0.
while task.state['status']=='running' and task.data.time<90.:
    task.step()
    if task.state['steps_completed']%50==0 or task.state['status']!='running': frames.append(task.frame())
    if task.data.time>=next_log:
        print(json.dumps({'phase':task.state['phase'],'time':task.data.time,'angle':task.observe()['door_angle_rad'],
                          'grip':task.state['grip_forces'],'failure':task.state['failure']}),flush=True)
        next_log=task.data.time+2.
out={'scope':'Research continuation, not full-cycle acceptance.',
     'parent_checkpoint_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
     'research_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
     'state':task.state,'measurements':task.observe(),'frames':frames,
     'wall_s':time.perf_counter()-started,'model_sha256':task.artifact.sha256,
     'equality_constraints':task.model.neq,'mocap_bodies':task.model.nmocap}
(root/'measured-open-continuation.json').write_text(json.dumps(out))
print(json.dumps({'state':{k:task.state[k] for k in ('status','failure','failure_detail','steps_completed') if k in task.state},
                  'measurements':task.observe(),'wall_s':out['wall_s']}),flush=True)
