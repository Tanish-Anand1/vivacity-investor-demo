"""Research: rotate the TCP offset with the wrist, retaining the measured local grasp."""
import gc
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from scipy.spatial.transform import Rotation
from vivacity.apollo_door import CabinetDoorPrimitive, ARM_PARTS
from vivacity.cabinet_tooling import SWIVEL_JOINT
from vivacity.execution_checkpoint import Checkpoint, CheckpointBundle
from vivacity.humanoid_ik import site_pose

root=Path('data/physical-truth-oct25/old-tray-swing')
file=root/'0017763-open_wide.json'
bundle=CheckpointBundle(Checkpoint.model_validate_json(file.read_bytes()),(root/'model.mjb').read_bytes())
source=Path(__file__).read_bytes()
for variant in ('servo_memory', 'force_tracking', 'finger_priority'):
    yaw,lead=.5,1.
    task=CabinetDoorPrimitive.from_checkpoint(bundle)
    g=task.state['wide_grasp_tracking']
    start=float(task.data.joint('service_door_hinge').qpos[0])
    def arc(angle):
        delta=angle-start
        offset=Rotation.from_rotvec([0.,0.,-yaw*delta]).apply(g['tcp_offset_world'])
        position=np.asarray(g['hinge_position'])+Rotation.from_rotvec([0.,0.,-angle]).apply(g['button_in_door'])+offset
        orientation=Rotation.from_rotvec([0.,0.,-yaw*delta]).as_matrix()@g['rotation']
        return {'position':position.tolist(),'rotation':orientation.tolist()}
    target=arc(1.1)
    joints=['l_'+part for part in ARM_PARTS]+[SWIVEL_JOINT]
    plan=site_pose(task.model,task.data.qpos,'l_service_tcp',joints,target['position'],target['rotation'],joint_margin=.01)
    if not plan.feasible:
        plan=site_pose(task.model,np.asarray(task.state['reference']),'l_service_tcp',joints,target['position'],target['rotation'],joint_margin=.01)
    print(json.dumps({'yaw':yaw,'lead':lead,'ik_feasible':bool(plan.feasible)}),flush=True)
    if not plan.feasible:
        task.fail('unreachable_target')
    else:
        for joint in joints:
            address=int(task.model.joint(joint).qposadr[0])
            task.state['reference'][address]=float(plan.qpos[address])
    task.state['goals']['l']=target
    solve=task.controller.stance.solver.compute
    diagnostics=[]
    def grip_solve(data,target_qpos,**kwargs):
        model=task.model
        # Preserve equivalent native force-limited servo commands; no external
        # force, model change, body-pose update or contact override is applied.
        kwargs['command_reference']=target_qpos[model.jnt_qposadr[model.actuator_trnid[:,0]]]
        if variant=='force_tracking':
            targets={}
            for i,c in enumerate(data.contact[:data.ncon]):
                names={model.geom(g).name for g in (c.geom1,c.geom2)}
                if any(f'l_service_{finger}_pad' in names for finger in ('positive','negative')) and names.intersection({'service_latch_button','service_latch_crossbar_link_0.4'}):
                    targets[i]=20.
            kwargs['normal_force_targets']=targets
        if variant=='finger_priority':
            weights=np.full(model.nu,kwargs.get('torque_weight',1.))
            for finger in ('positive','negative'): weights[model.actuator(f'l_service_{finger}_drive').id]=30.
            kwargs['torque_weight']=weights
        return solve(data,target_qpos,**kwargs)
    task.controller.stance.solver.compute=grip_solve
    compute=task.controller.compute
    def control(data,reference,goals=None,released_hands=()):
        f=min(1.,(data.time-task.state['phase_started_s'])/6.)
        scheduled=start+f*f*(3.-2.*f)*(1.1-start)
        angle=min(scheduled,float(data.joint('service_door_hinge').qpos[0])+lead)
        goal=arc(angle)
        axis=data.site('l_service_tcp').xmat.reshape(3,3)[:,1]
        error=float(axis@(data.geom('service_latch_button').xpos-goal['position']))
        goal['position']=(np.asarray(goal['position'])+axis*np.clip(error,-.015,.015)).tolist()
        command=compute(data,reference,{**goals,'l':goal},released_hands)
        if task.state['steps_completed']%50==0:
            diagnostics.append({'time_s':float(data.time),'door_rad':float(data.joint('service_door_hinge').qpos[0]),
                'tcp':data.site('l_service_tcp').xpos.tolist(),'goal':goal,
                'button':data.geom('service_latch_button').xpos.tolist(),
                'position_error':float(np.linalg.norm(np.asarray(goal['position'])-data.site('l_service_tcp').xpos)),
                'fingers':{finger:{'qpos':float(data.joint(f'l_service_{finger}_slide').qpos[0]),
                    'command':float(command[task.model.actuator(f'l_service_{finger}_drive').id]),
                    'force':float(data.actuator_force[task.model.actuator(f'l_service_{finger}_drive').id])}
                    for finger in ('positive','negative')},'grip':task.state['grip_forces']})
        return command
    task.controller.compute=control
    started=time.perf_counter();frames=[];next_log=0.
    while task.state['status']=='running':
        task.step()
        if task.state['steps_completed']%50==0 or task.state['status']!='running': frames.append(task.frame())
        if task.data.time>=next_log:
            print(json.dumps({'yaw':yaw,'lead':lead,'time':task.data.time,
                              'angle':task.observe()['door_angle_rad'],'grip':task.state['grip_forces']}),flush=True)
            next_log=task.data.time+2.
    report={'scope':'Research continuation; not fresh full task acceptance.',
            'parent_checkpoint_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
            'research_source_sha256':hashlib.sha256(source).hexdigest(),
            'variant':variant,'diagnostics':diagnostics,'settings':{'yaw_fraction':yaw,'maximum_angle_lead_rad':lead},
            'state':task.state,'measurements':task.observe(),'frames':frames,
            'model_sha256':task.artifact.sha256,'wall_s':time.perf_counter()-started,
            'equality_constraints':task.model.neq,'mocap_bodies':task.model.nmocap}
    (root/f'grip-feedback-{variant}.json').write_text(json.dumps(report))
    print(json.dumps({'done':True,'variant':variant,'yaw':yaw,'lead':lead,'status':task.state['status'],
                      'failure':task.state['failure'],'angle':report['measurements']['door_angle_rad'],
                      'wall_s':report['wall_s']}),flush=True)
    task.controller.compute=None
    task.controller.stance.solver.compute=None
    del task,compute,plan,solve
    gc.collect()

