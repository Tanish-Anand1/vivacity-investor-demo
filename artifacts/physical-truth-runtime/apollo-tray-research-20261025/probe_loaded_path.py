"""Test a continuously solved grasp path through bounded native actuators.

Kinematic planning is scratch work; only measured native execution can succeed.
"""
import gc
import hashlib
import json
from pathlib import Path
import time
import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation
from vivacity.apollo_door import CabinetDoorPrimitive, ARM_PARTS, GRASP_SURFACES
from vivacity.cabinet_tooling import SWIVEL_JOINT
from vivacity.execution_checkpoint import Checkpoint, CheckpointBundle
from vivacity.humanoid_ik import site_pose

root=Path('data/physical-truth-oct25/old-tray-swing')
file=root/'0017763-open_wide.json'
bundle=CheckpointBundle(Checkpoint.model_validate_json(file.read_bytes()),(root/'model.mjb').read_bytes())
source=Path(__file__).read_bytes()
for yaw in (1.,.65):
    task=CabinetDoorPrimitive.from_checkpoint(bundle)
    g=task.state['wide_grasp_tracking']
    start=float(task.data.joint('service_door_hinge').qpos[0])
    def arc(angle):
        delta=angle-start
        turn=Rotation.from_rotvec([0.,0.,-yaw*delta])
        position=np.asarray(g['hinge_position'])+Rotation.from_rotvec([0.,0.,-angle]).apply(g['button_in_door'])+turn.apply(g['tcp_offset_world'])
        return {'position':position.tolist(),'rotation':(turn.as_matrix()@g['rotation']).tolist()}
    joints=['torso_yaw']+['l_'+part for part in ARM_PARTS]+[SWIVEL_JOINT]
    addresses=[int(task.model.joint(name).qposadr[0]) for name in joints]
    before=task.data.qpos.copy()
    angles=np.linspace(start,1.1,41)
    waypoints=[before.copy()]
    residuals=[]
    planning_start=time.perf_counter()
    for angle in angles[1:]:
        goal=arc(angle)
        plan=site_pose(task.model,waypoints[-1],'l_service_tcp',joints,goal['position'],goal['rotation'],joint_margin=.01)
        residuals.append({'angle':float(angle),'feasible':bool(plan.feasible),
                          'position_error':plan.position_error_m,'angular_error':plan.angular_error_rad})
        if not plan.feasible:
            task.fail('continuous_grasp_path_unreachable',residuals[-1]);break
        # Only arm references enter the controller. Passive-door coordinates
        # below belong to the planning collision test, never the native world.
        waypoints.append(plan.qpos.copy())
    assert np.array_equal(before,task.data.qpos)
    scratch=mj.MjData(task.model)
    minimum=1.
    for angle,point in zip(angles,waypoints):
        scratch.qpos[:]=point
        scratch.joint('service_door_hinge').qpos[0]=angle
        mj.mj_forward(task.model,scratch)
        for c in scratch.contact[:scratch.ncon]:
            names=[task.model.geom(i).name or '' for i in (c.geom1,c.geom2)]
            if any(name.startswith('service_') for name in names) and any('_service_' in name or name.startswith('collision_') for name in names):
                intended=any(GRASP_SURFACES[side].intersection(names) and any(
                    f'{side}_service_{finger}_pad' in names for finger in ('positive','negative')) for side in ('l','r'))
                if not intended:
                    minimum=min(minimum,float(c.dist))
                    if c.dist < -.0001: task.fail('planned_prohibited_collision',{'names':names,'distance':float(c.dist),'angle':float(angle)})
    del scratch
    task.state['goals']['l']=arc(1.1)
    compute=task.controller.compute
    def control(data,reference,goals=None,released_hands=()):
        f=min(1.,(data.time-task.state['phase_started_s'])/6.)
        angle=start+f*f*(3.-2.*f)*(1.1-start)
        point=reference.copy()
        for name,address in zip(joints,addresses): point[address]=np.clip(np.interp(angle,angles,[q[address] for q in waypoints])+(task.state['phase_start_qpos'][address]-waypoints[0][address])*(1.-f*f*(3.-2.*f)),*task.model.joint(name).range)
        goal=arc(angle)
        axis=data.site('l_service_tcp').xmat.reshape(3,3)[:,1]
        error=float(axis@(data.geom('service_latch_button').xpos-goal['position']))
        goal['position']=(np.asarray(goal['position'])+axis*np.clip(error,-.015,.015)).tolist()
        return compute(data,point,{**goals,'l':goal},released_hands)
    planning_s=time.perf_counter()-planning_start
    print(json.dumps({'yaw':yaw,'planning_s':planning_s,'waypoints':len(waypoints),'failure':task.state['failure'],
                      'detail':task.state.get('failure_detail')}),flush=True)
    task.controller.compute=control
    started=time.perf_counter();frames=[];next_log=0.
    while task.state['status']=='running':
        task.step()
        if task.state['steps_completed']%50==0 or task.state['status']!='running': frames.append(task.frame())
        if task.data.time>=next_log:
            print(json.dumps({'yaw':yaw,'time':task.data.time,'angle':task.observe()['door_angle_rad'],
                              'grip':task.state['grip_forces']}),flush=True)
            next_log=task.data.time+2.
    report={'scope':'Independent research continuation, not full task acceptance.',
            'parent_checkpoint_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
            'research_source_sha256':hashlib.sha256(source).hexdigest(),'yaw_fraction':yaw,
            'state':task.state,'measurements':task.observe(),'frames':frames,
            'model_sha256':task.artifact.sha256,'wall_s':time.perf_counter()-started,
            'planning_s':planning_s,'planning_residuals':residuals,'waypoints':[q.tolist() for q in waypoints],
            'equality_constraints':task.model.neq,'mocap_bodies':task.model.nmocap}
    (root/f'loaded-path-{yaw}.json').write_text(json.dumps(report))
    print(json.dumps({'done':True,'yaw':yaw,'status':task.state['status'],'failure':task.state['failure'],
                      'angle':report['measurements']['door_angle_rad'],'wall_s':report['wall_s']}),flush=True)
    task.controller.compute=None
    del task,compute,plan
    gc.collect()



