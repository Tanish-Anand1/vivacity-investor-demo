"""Native MuJoCo integration with measured per-step contact sensors.

Only diagnostics are added to the physical model. Each candidate owns an MjData
and starts from the complete parent integration state. Native chunks retain the
actual warmstart and user inputs, and cooperate with pause/cancel between chunks.
"""
from copy import deepcopy
import time

import mujoco as mj
from mujoco.rollout import Rollout
import numpy as np

from .robotics import RobotWorld
from .pickup_planning import stage_commands


class NativePickup:
    engine = 'mujoco.rollout/contact-sensors-v1'

    def __init__(self, backend, snapshot):
        self.backend=backend
        self.snapshot=deepcopy(snapshot)
        # Contact diagnostics exist on the immutable normal model. Fork its data
        # instead of compiling a second copy of every high-resolution mesh.
        self.template=backend.fork(snapshot)
        backend.restore(self.template,snapshot)

    def simulate(self, action, limits):
        b=self.backend;m=self.template.model;arm_dof=b.arm_dof;cube_z=int(m.jnt_qposadr[m.joint('cube_free').id])+2
        w=RobotWorld(m,mj.MjData(m),deepcopy(self.template.config),self.template.seed,self.template.model_hash)
        b.restore(w,self.snapshot);b.apply_action(w,action);d=w.data
        tic=time.perf_counter();pause_start=limits.get('pause_seconds',lambda:0.)();start=float(d.time)
        trace=[b.observe(w)|{'phase':'initializing'}];steps=0;integration_calls=0
        failure='planning_failure' if not action['stages'] and not action['planning_feasible'] else None
        violations=[];milestones=[]
        lifted=False;retention=True;max_height=float(d.qpos[cube_z]);tracking=0.;linear_tracking=0.
        state=np.empty(mj.mj_stateSize(m,mj.mjtState.mjSTATE_FULLPHYSICS))
        user=np.empty(mj.mj_stateSize(m,mj.mjtState.mjSTATE_USER))
        sensor=lambda name: int(m.sensor_adr[m.sensor(name).id])
        ids={name:sensor(name) for name in ('robot_contacts','mount_contacts','left_grasp','right_grasp','table_support','object_obstacle','object_ground')}
        environment_ids=[int(m.sensor_adr[i]) for i in range(m.nsensor) if m.sensor(i).name.startswith('object_environment_')]
        secondary=[sensor(name) for name in ('secondary_robot_contacts','secondary_mount_contacts')] if b.arm_dof==7 and w.config.get('robot_model')=='dual_arm' else []
        with Rollout() as rollout:
            for stage in action['stages']:
                if failure:break
                phase=stage['phase'];count=int(np.ceil((stage['duration_s']+stage['dwell_s'])/m.opt.timestep))
                for offset in range(0,count,128):
                    if limits.get('checkpoint') and not limits['checkpoint']():failure='cancelled';break
                    if limits.get('cancel_event') and limits['cancel_event'].is_set():failure='cancelled';break
                    remaining=int(np.ceil((limits['max_simulation_seconds']-(d.time-start)-1e-12)/m.opt.timestep))
                    length=min(128,count-offset,remaining)
                    if length<=0:failure='timeout';break
                    alpha=np.minimum(1.,(np.arange(offset,offset+length)+1)*m.opt.timestep/max(stage['duration_s'],m.opt.timestep))
                    mj.mj_getState(m,d,state,mj.mjtState.mjSTATE_FULLPHYSICS)
                    mj.mj_getState(m,d,user,mj.mjtState.mjSTATE_USER)
                    commands=np.tile(user,(length,1))
                    commands[:,:arm_dof]=stage_commands(stage,alpha)
                    commands[:,arm_dof]=stage['gripper']
                    states,sensors=rollout.rollout(m,d,state[None],commands[None],control_spec=int(mj.mjtState.mjSTATE_USER),initial_warmstart=d.qacc_warmstart.copy()[None])
                    integration_calls+=1
                    states,sensors=states[0],sensors[0]
                    # Rollout fills stalled output after a native numerical warning.
                    advanced=int(np.count_nonzero(np.diff(np.r_[state[0],states[:,0]])>0));steps+=advanced
                    q=states[:,1:1+m.nq];height=q[:,cube_z];max_height=max(max_height,float(height.max()))
                    angular,linear=b.tracking_errors(w,q,commands)
                    tracking=max(tracking,angular);linear_tracking=max(linear_tracking,linear)
                    left=sensors[:,ids['left_grasp']+1]>.01;right=sensors[:,ids['right_grasp']+1]>.01
                    if phase in ('lift','transport','lower'):
                        raised=height>.075;lifted|=bool(raised.any())
                        if np.any(raised&~(left&right)):retention=False;failure='dropped_object'
                    if phase=='transport' and np.any(height<.07):retention=False;failure='dropped_object'
                    prohibited=sensors[:,ids['robot_contacts']]-sensors[:,ids['mount_contacts']]-sensors[:,ids['left_grasp']]-sensors[:,ids['right_grasp']]
                    collision=(prohibited>0)|(sensors[:,ids['object_obstacle']]>0)|(sensors[:,ids['object_ground']]>0)
                    if environment_ids:collision|=(sensors[:,environment_ids]>0).any(axis=1)
                    if secondary:collision|=(sensors[:,secondary[0]]-sensors[:,secondary[1]])>0
                    if collision.any():
                        failure='collision_failure';violations.append({'category':'native_contact_sensor_collision',
                            'bodies':[],'geoms':[],'first_step':steps-length+int(np.flatnonzero(collision)[0])+1,
                            'scope':'Aggregated prohibited-contact sensors; pair names are not inferred.'})
                    if np.any((q[:,:arm_dof]<m.jnt_range[:arm_dof,0]-.002)&m.jnt_limited[:arm_dof]) or np.any((q[:,:arm_dof]>m.jnt_range[:arm_dof,1]+.002)&m.jnt_limited[:arm_dof]):failure='joint_limit_failure'
                    if advanced!=length or not np.isfinite(states).all() or tracking>.35 or linear_tracking>.035:failure='controller_failure'
                    elapsed=time.perf_counter()-tic-(limits.get('pause_seconds',lambda:0.)()-pause_start)
                    if d.time-start+1e-10>=limits['max_simulation_seconds'] or elapsed>limits.get('max_wall_seconds',120):failure='timeout'
                    frame=b.observe(w)|{'phase':phase};trace.append(frame)
                    if limits.get('on_frame'):limits['on_frame'](frame)
                    if limits.get('realtime'):
                        delay=max(0.,float(d.time-start)/limits.get('realtime_speed',1.)-elapsed)
                        while delay>0:
                            if limits.get('checkpoint') and not limits['checkpoint']():failure='cancelled';break
                            if limits.get('cancel_event') and limits['cancel_event'].is_set():failure='cancelled';break
                            time.sleep(min(delay,.05))
                            elapsed=time.perf_counter()-tic-(limits.get('pause_seconds',lambda:0.)()-pause_start)
                            delay=max(0.,float(d.time-start)/limits.get('realtime_speed',1.)-elapsed)
                    if failure:break
                evidence=b.contact_evidence(w)
                milestones.append({'phase':phase,'time':float(d.time),'cube_position':d.body('target').xpos.tolist(),**evidence})
                if phase=='close' and not evidence['bilateral_grasp'] and not failure:failure='grasp_failure'
        if not failure:
            from .scene import finish_task
            extra,failure,contacts=finish_task(w,limits,trace,b,start,tic,pause_start)
            steps+=extra;integration_calls+=extra;violations.extend(contacts)
        trace.append(b.observe(w)|{'phase':'evaluating'})
        result={'trace':trace,'failure':failure,'contact_violations':violations,'milestones':milestones,'lifted':lifted,
                'retained_during_transport':retention and lifted,'max_cube_height_m':max_height,'max_tracking_error_rad':tracking,'max_tracking_error_m':linear_tracking,
                'simulation_steps':steps,'integration_calls':integration_calls,'execution_duration_s':float(d.time-start),'physics_wall_seconds':time.perf_counter()-tic,
                'engine':self.engine,'contact_measurement':'native per-step force sensors; forces precede integration by one timestep'}
        return result,b.evaluate(w,result),b.snapshot(w)
