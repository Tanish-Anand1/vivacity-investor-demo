"""Fresh native research trial: explicit tray height and rotating tool goals.

This is a development controller, never full cabinet service acceptance.
Model geometry is fixed before stepping. All robot motion uses native actuators.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from scipy.spatial.transform import Rotation
from vivacity.apollo_door import CabinetDoorPrimitive, SOURCE_HASHES
from vivacity.cabinet_mechanism import CabinetConfig
from vivacity.simulated_tooling import ParallelGripperConfig

p=argparse.ArgumentParser()
p.add_argument('--height',type=float,default=.89)
p.add_argument('--yaw-fraction',type=float,default=.5)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
task=CabinetDoorPrimitive(CabinetConfig(front_x_m=.65,tray_surface_height_m=a.height),
    ParallelGripperConfig(finger_force_n=40.,position_stiffness_n_m=2400.),opening_angle_rad=1.1)
source=Path(__file__).read_bytes()
a.output.parent.mkdir(parents=True,exist_ok=True)
(a.output.parent/'probe_source.py').write_bytes(source)
for name in SOURCE_HASHES:
    dest=a.output.parent/'sources'/name
    dest.parent.mkdir(exist_ok=True)
    dest.write_bytes(Path('vivacity',name).read_bytes())
(a.output.parent/'model.mjb').write_bytes(task.artifact.binary)

def arc(angle):
    g=task.state['wide_grasp_tracking']
    initial=g.setdefault('research_initial_angle',float(task.data.joint('service_door_hinge').qpos[0]))
    delta=angle-initial
    offset=Rotation.from_rotvec([0.,0.,-delta]).apply(g['tcp_offset_world'])
    position=np.asarray(g['hinge_position'])+Rotation.from_rotvec([0.,0.,-angle]).apply(g['button_in_door'])+offset
    orientation=Rotation.from_rotvec([0.,0.,-a.yaw_fraction*delta]).as_matrix()@g['rotation']
    return {'position':position.tolist(),'rotation':orientation.tolist()}

task._wide_grasp_pose=arc
compute=task.controller.compute
def control(data,reference,goals=None,released_hands=()):
    if task.state['phase']=='open_wide':
        goals={**goals}
        goal={**goals['l']}
        axis=data.site('l_service_tcp').xmat.reshape(3,3)[:,1]
        error=float(axis@(data.geom('service_latch_button').xpos-goal['position']))
        goal['position']=(np.asarray(goal['position'])+axis*np.clip(error,-.015,.015)).tolist()
        goals['l']=goal
    return compute(data,reference,goals,released_hands)
task.controller.compute=control
started=time.perf_counter()
frames=[]
last_phase=None
next_log=0.
while task.state['status']=='running' and task.data.time<90.:
    task.step()
    if task.state['phase']!=last_phase:
        (a.output.parent/f"{task.state['steps_completed']:07d}-{task.state['phase']}.json").write_text(task.snapshot().checkpoint.model_dump_json())
        last_phase=task.state['phase']
    if task.state['steps_completed']%50==0 or task.state['status']!='running':
        frames.append(task.frame())
    if task.data.time>=next_log:
        obs=task.observe()
        print(json.dumps({'phase':task.state['phase'],'time':task.data.time,'angle':obs['door_angle_rad'],
                          'grip':obs['grip_forces_n'],'failure':task.state['failure']}),flush=True)
        next_log+=2.
if task.state['status']=='running': task.fail('overall_timeout')
report={'state':task.state,'measurements':task.observe(),'frames':frames,
        'model_sha256':task.artifact.sha256,'source_hashes':SOURCE_HASHES,
        'research_source_sha256':hashlib.sha256(source).hexdigest(),
        'research_settings':{'tray_height':a.height,'yaw_fraction':a.yaw_fraction},
        'wall_s':time.perf_counter()-started,'equality_constraints':task.model.neq,'mocap_bodies':task.model.nmocap}
a.output.write_text(json.dumps(report))
print(json.dumps({k:v for k,v in report.items() if k not in ('frames','state','source_hashes')}),flush=True)
raise SystemExit(0 if task.state['success'] else 1)
