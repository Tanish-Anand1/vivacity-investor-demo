"""Observable factory state machine. Commands actuators, never object poses.

Pose DLS and seeded RRT generate a collision-screened robot path. Execution
checks actual contacts and retention. Roller drives and a lateral shuttle route
released cartons; a destination requires an actual bin-floor contact.
"""
import time
import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation
from .robotics import DOWN, RobotWorld, RoboticsBackend
from .pick_place import PickPlaceBackend
from .pickup_planning import joint_route, stage_commands, stage_distance


class FactoryFault(RuntimeError):
    def __init__(self,kind,detail):
        self.kind=kind
        super().__init__(detail)


def grasp_evidence(w,carton):
    fingers=set();support=[];normal=0.
    for i,c in enumerate(w.data.contact[:w.data.ncon]):
        bodies=[w.model.body(int(w.model.geom_bodyid[g])).name for g in (c.geom1,c.geom2)]
        if carton not in bodies:continue
        force=np.zeros(6);mj.mj_contactForce(w.model,w.data,i,force)
        if force[0]<=.01:continue
        normal+=float(force[0])
        fingers.update(b for b in bodies if b in ('left_finger','right_finger'))
        support.extend(w.model.geom(g).name for g in (c.geom1,c.geom2) if w.model.geom_bodyid[g]!=w.model.body(carton).id)
    return {'bilateral_grasp':len(fingers)==2,'finger_contacts':sorted(fingers),
            'normal_force_n':normal,'support_geoms':sorted(set(support))}


def prohibited(w,carton):
    return [c for c in RoboticsBackend.contacts(RoboticsBackend(),w)
            if not (carton in c['bodies'] and any(n in ('left_finger','right_finger') for n in c['bodies']))]


def plan(w,carton,checkpoint=lambda:True):
    planner=PickPlaceBackend();position=w.data.body(carton).xpos.copy()
    h=w.config['carton_half_size_m'];grasp_z=h+.013
    rng=np.random.default_rng(w.seed);started=time.perf_counter();attempts=[]
    scratch=RobotWorld(w.model,mj.MjData(w.model),w.config,w.seed,w.model_hash)
    scratch.data.qpos[:]=w.data.qpos
    for index in range(4):
        if not checkpoint():raise InterruptedError('Stopped during planning')
        height=.21+index*.02;orientation=Rotation.from_euler('z',(index%2)*np.pi/2).as_matrix()@DOWN
        specs=[('approach',[*position[:2],height],255,.3),('descend',[*position[:2],grasp_z],255,.3),
               ('close',[*position[:2],grasp_z],0,.8),('lift',[*position[:2],height],0,.3),
               ('transport',[.5,.26,height],0,.3),('lower',[.5,.26,grasp_z],0,.3),
               ('release',[.5,.26,grasp_z],255,.6),('retract',[.5,.26,height],255,.5)]
        q=w.data.qpos[:7].copy();stages=[];reason=None
        for phase,pose,gripper,dwell in specs:
            if not checkpoint():raise InterruptedError('Stopped during planning')
            goal,ok=planner.pose_ik(w,pose,q,orientation)
            if not ok:reason='inverse_kinematics';break
            scratch.data.qpos[7:9]=.04 if gripper else h-.002
            def valid(joints):
                scratch.data.qpos[:7]=joints;mj.mj_forward(scratch.model,scratch.data)
                return not prohibited(scratch,carton)
            route=joint_route(q,goal,w.model.jnt_range[:7],valid,rng,200,checkpoint)
            if route is None:reason='kinematic_collision';break
            stage={'phase':phase,'start':q.tolist(),'goal':goal.tolist(),'waypoints':[v.tolist() for v in route],
                   'gripper':gripper,'dwell_s':dwell}
            stage['duration_s']=0. if phase in ('close','release') else max(.6,stage_distance(stage)/.32)
            stages.append(stage);q=goal
        attempts.append({'index':index,'feasible':reason is None,'rejection':reason})
        if reason is None:return {'stages':stages,'attempts':attempts,'planning_seconds':time.perf_counter()-started,
                                  'localization_source':'MuJoCo body transform','source_position_m':position.tolist()}
    raise FactoryFault('planning_failure',f'No collision-free pose path for {carton}: {attempts}')


class ProductionController:
    def __init__(self,backend,world,on_frame=lambda w,p:None,on_event=lambda e:None,checkpoint=lambda:True,pace=True):
        self.backend=backend;self.w=world;self.on_frame=on_frame;self.on_event=on_event;self.checkpoint=checkpoint;self.pace=pace
        self.physics_seconds=0.;self.steps=0;self.sorted=0;self.arrivals=0;self.carton='target';self.plans=[];self.max_tracking=0.;self._tick=time.perf_counter()

    def event(self,kind,**fields):
        self.on_event({'time_s':float(self.w.data.time),'kind':kind,'carton_id':self.carton,**fields})

    def advance(self,phase,command=None):
        w=self.w;m,d=w.model,w.data
        if self.steps%25==0:
            if not self.checkpoint():raise InterruptedError('Simulation stopped')
            self._tick=time.perf_counter()
        if command is not None:d.ctrl[:8]=command
        physics_start=time.perf_counter()
        self.backend.step(w);self.steps+=1
        self.physics_seconds+=time.perf_counter()-physics_start
        # Contacts/forces describe the integration step just performed.
        violations=prohibited(w,self.carton)
        if violations:raise FactoryFault('collision_failure',str(violations[:3]))
        if np.any(d.qpos[:7]<m.jnt_range[:7,0]-.002) or np.any(d.qpos[:7]>m.jnt_range[:7,1]+.002):
            raise FactoryFault('joint_limit_failure','Robot exceeded a joint limit')
        tracking=float(np.max(np.abs(d.qpos[:7]-d.ctrl[:7])));self.max_tracking=max(self.max_tracking,tracking)
        if tracking>.35:raise FactoryFault('controller_failure',f'Robot tracking error {tracking:.3f} rad')
        if self.steps%25==0:
            self.on_frame(w,phase)
            if self.pace:time.sleep(max(0.,.05/w.config['realtime_speed']-(time.perf_counter()-self._tick)))

    def until(self,predicate,timeout,phase):
        deadline=self.w.data.time+timeout
        while not predicate():
            if self.w.data.time>=deadline:raise FactoryFault('timeout',f'{phase} did not complete in {timeout:g} simulation seconds')
            self.advance(phase)

    def hold(self,duration,phase):
        until=self.w.data.time+duration
        while self.w.data.time<until:self.advance(phase)

    def drive(self,**values):self.backend.apply_action(self.w,values)

    def pickup(self):
        w=self.w;self.event('planning_started')
        action=plan(w,self.carton,self.checkpoint);self.plans.append(action)
        self.event('plan_selected',planning_seconds=action['planning_seconds'],attempts=action['attempts'])
        lifted=False
        for stage in action['stages']:
            phase=stage['phase'];duration=stage['duration_s']
            count=int(np.ceil((duration+stage['dwell_s'])/w.model.opt.timestep))
            commands=stage_commands(stage,np.minimum(1.,(np.arange(count)+1)*w.model.opt.timestep/max(duration,w.model.opt.timestep)))
            for joints in commands:
                self.advance(phase,np.r_[joints,stage['gripper']])
                evidence=grasp_evidence(w,self.carton)
                if phase in ('lift','transport','lower') and w.data.body(self.carton).xpos[2]>.075:
                    lifted=True
                    if not evidence['bilateral_grasp']:raise FactoryFault('dropped_object','Bilateral finger contact was lost during transfer')
                if phase=='transport' and w.data.body(self.carton).xpos[2]<.07:
                    raise FactoryFault('lift_failure','The carton did not clear the conveyor')
            evidence=grasp_evidence(w,self.carton)
            self.event(phase+'_completed',position_m=w.data.body(self.carton).xpos.tolist(),grasp=evidence)
            if phase=='close' and not evidence['bilateral_grasp']:raise FactoryFault('grasp_failure','Both fingers did not establish contact')
        position=w.data.body(self.carton).xpos
        if not lifted or np.linalg.norm(position[:2]-[.5,.26])>.035 or not any(g.startswith('transfer_roller_') for g in evidence['support_geoms']):
            raise FactoryFault('placement_failure','The released carton is not supported on the transfer conveyor')
        self.event('physical_transfer_verified')

    def route(self):
        w=self.w;speed=w.config['conveyor_speed_m_s']
        self.drive(transfer=speed,shuttle=speed)
        self.until(lambda:w.data.body(self.carton).xpos[1]>=.67,12.,'transfer_conveying')
        self.drive(transfer=0,shuttle=0);self.hold(.3,'shuttle_loading')
        mass=float(w.model.body(self.carton).mass[0]);lane='A' if mass<w.config['sort_threshold_kg'] else 'B';offset=-.2 if lane=='A' else .2
        self.event('route_selected',lane=lane,mass_kg=mass,rule='A if simulator mass < threshold; otherwise B')
        aid=w.model.actuator('shuttle_slide').id;initial=float(w.data.ctrl[aid])
        for fraction in np.linspace(0,1,1000):
            w.data.ctrl[aid]=initial+(offset-initial)*fraction*fraction*(3-2*fraction)
            self.advance('shuttle_routing')
        self.hold(.3,'shuttle_routing')
        if abs(w.data.body(self.carton).xpos[0]-(.5+offset))>.045:
            raise FactoryFault('routing_failure','Carton slipped outside the selected lane alignment')
        self.drive(shuttle=speed,**{'lane_'+lane:speed})
        self.until(lambda:'bin_'+lane+'_floor' in grasp_evidence(w,self.carton)['support_geoms'],14.,'outfeed_conveying')
        self.hold(.4,'destination_settling');self.drive(shuttle=0,**{'lane_'+lane:0})
        self.sorted+=1;self.event('destination_arrival',lane=lane,position_m=w.data.body(self.carton).xpos.tolist())
        initial=float(w.data.ctrl[aid])
        for fraction in np.linspace(0,1,1000):
            w.data.ctrl[aid]=initial*(1-fraction*fraction*(3-2*fraction));self.advance('shuttle_returning')

    def run(self):
        w=self.w;last_arrival=-w.config['arrival_interval_s']
        for index in range(w.config['carton_count']):
            self.carton='target' if index==0 else f'carton_{index}'
            delay=max(0.,last_arrival+w.config['arrival_interval_s']-w.data.time)
            self.hold(delay,'arrival_spacing');self.drive(infeed=w.config['conveyor_speed_m_s'])
            self.event('infeed_started')
            self.until(lambda:w.data.body(self.carton).xpos[1]>=-.27,45.,'conveying')
            self.drive(infeed=0);self.hold(.5,'station_settling')
            self.arrivals+=1;last_arrival=float(w.data.time);self.event('station_arrival')
            self.pickup();self.route()
        return {'cartons_sorted':self.sorted,'station_arrivals':self.arrivals,'simulation_steps':self.steps,
                'simulation_time_s':float(w.data.time),'max_tracking_error_rad':self.max_tracking,
                'sorting_accuracy':self.sorted/w.config['carton_count'],'scope':'small-carton contact sorting; simulator mass classification'}
