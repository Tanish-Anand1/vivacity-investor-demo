"""Constrained single fold: real flex dynamics, fixed hinge and pre-attached clamps.

No autonomous grasping is claimed. Only the mocap clamp is commanded; cloth
vertices are always produced by MuJoCo integration, including release/settling.
"""
from copy import deepcopy
from dataclasses import dataclass,field
import hashlib
import time
import mujoco as mj
import numpy as np
from .robotics import STATE_SPEC
from .compiled import fork_geometry

N=7


def scene(config):
    radius=config['side_length']/2;spacing=config['side_length']/(N-1)
    pins=' '.join(map(str,list(range(N))+list(range(N*(N//2),N*(N//2+1)))))
    connects=''.join(f'<connect name="grasp_{i}" body1="cloth_{N*(N-1)+i}" body2="clamp" anchor="0 0 0" solref=".006 1"/>' for i in range(N))
    friction=config['friction']
    return f'''<mujoco model="vivacity_constrained_fold"><option timestep=".002" integrator="implicitfast" iterations="50"/><default><geom friction="{friction} .01 .001" solref=".01 1"/></default><worldbody><geom name="table" type="box" pos="0 0 -.025" size=".5 .5 .025"/><body name="clamp" mocap="true" pos="{radius} 0 .012"><geom name="clamp_bar" type="box" size=".008 {radius+.01} .008" contype="0" conaffinity="0"/></body><flexcomp name="cloth" type="grid" dim="2" count="7 7 1" spacing="{spacing} {spacing} {spacing}" pos="0 0 .012" radius=".004" mass="{config['mass']}"><contact selfcollide="auto" friction="{friction} .01 .001" solref=".01 1"/><edge equality="true" damping=".02"/><pin id="{pins}"/></flexcomp></worldbody><equality>{connects}</equality></mujoco>'''


@dataclass
class ClothWorld:
    model: mj.MjModel
    data: mj.MjData
    config: dict
    seed: int
    model_hash: str
    initial_vertices: np.ndarray
    grasp_ids: list[int]
    action: dict=field(default_factory=dict)


class LegacyClothBackend:
    version=mj.__version__
    action_schema={'type':'clamp_fold','units':'meters, seconds','scope':'7x7 triangulated inextensible flex; fixed hinge/opposite edge; seven pre-attached ideal clamp constraints; one released fold','parameters':['lift_height','motion_seconds','lateral_offset']}

    def create_world(self,config,seed):
        xml=scene(config);model=mj.MjModel.from_xml_string(xml);data=mj.MjData(model);mj.mj_forward(model,data)
        return ClothWorld(model,data,deepcopy(config),seed,hashlib.sha256((xml+self.version).encode()).hexdigest(),data.flexvert_xpos.copy(),[mj.mj_name2id(model,mj.mjtObj.mjOBJ_EQUALITY,f'grasp_{i}') for i in range(N)])

    def observe(self,world):
        return {'time':float(world.data.time),'vertices':world.data.flexvert_xpos.tolist(),'triangles':world.model.flex_elem.reshape(-1,3).tolist(),'clamp_position':world.data.mocap_pos[0].tolist(),'grasp_active':world.data.eq_active[world.grasp_ids].tolist(),'scope':self.action_schema['scope']}

    def snapshot(self,world):
        state=np.zeros(mj.mj_stateSize(world.model,STATE_SPEC));mj.mj_getState(world.model,world.data,state,STATE_SPEC)
        return {'backend':'cloth','engine':'mujoco','version':self.version,'seed':world.seed,'config':deepcopy(world.config),'model_hash':world.model_hash,'state_spec':int(STATE_SPEC),'integration_state':state.tolist()}

    def fork(self,state):
        w=fork_geometry(state)
        if w is None:w=self.create_world(state['config'],state['seed'])
        if state['version']!=self.version or state['model_hash']!=w.model_hash or state['state_spec']!=int(STATE_SPEC):raise ValueError('cloth snapshot model/version mismatch')
        mj.mj_setState(w.model,w.data,np.asarray(state['integration_state']),STATE_SPEC);mj.mj_forward(w.model,w.data);mj.mj_setState(w.model,w.data,np.asarray(state['integration_state']),STATE_SPEC)
        return w

    def candidates(self,world,count,iterations):
        settings={'search_candidates':count,'physics_budget':count}
        actions,elapsed,_=self.search(world,settings,lambda _:None)
        return actions,elapsed

    def search(self,world,settings,emit):
        tic=time.perf_counter();count=settings['search_candidates'];radius=world.config['side_length']/2
        rng=np.random.default_rng(world.seed)
        samples=rng.uniform([radius*.6,1.5,-.04],[radius*1.25,5,.04],(count,3))
        emit({'stage':'generation','generated':count,'elapsed_seconds':time.perf_counter()-tic,'message':f'Generated {count:,} distinct clamp-motion parameter sets.'})
        # Geometric screening limits stretch and lateral clamp travel. It cannot
        # establish grasp or fold success; those are measured during rollouts.
        mask=(samples[:,0]<=radius*1.03)&(np.abs(samples[:,2])<=.025)
        indices=np.flatnonzero(mask)
        indices=sorted(indices,key=lambda i:(samples[i,1]+4*abs(samples[i,0]-radius),int(i)))
        actions=[{'kind':'clamp_fold','candidate_index':int(i),'lift_height':float(samples[i,0]),'motion_seconds':float(samples[i,1]),'lateral_offset':float(samples[i,2]),'planning_feasible':True} for i in indices[:settings['physics_budget']]]
        if not actions:
            actions=[{'kind':'clamp_fold','lift_height':radius*.85,'motion_seconds':4.,'lateral_offset':0.,'planning_feasible':False}]
        summary={'generated':count,'distinct_generated':int(len(np.unique(samples,axis=0))),'screened':count,'rejected':int(count-mask.sum()),'screening_passed':int(mask.sum()),'promoted_to_physics':len(actions),'candidate_catalog_sha256':hashlib.sha256(samples.astype('<f8').tobytes()).hexdigest(),'sampling':'seeded continuous uniform clamp height, duration and lateral offset','screening_scope':'geometric stretch/travel bounds only; grasp constraints, contacts and fold quality require MuJoCo','ranking_objective':'feasible first, alignment RMSE, descending vertex coverage, executed duration'}
        emit(summary|{'stage':'screening_complete','elapsed_seconds':time.perf_counter()-tic,'message':f'Screened {count:,}; {summary["rejected"]:,} geometric rejections; {len(actions)} full flex rollouts.'})
        return actions,time.perf_counter()-tic,summary

    def apply_action(self,world,action):
        if action.get('kind')!='clamp_fold':raise ValueError('unsupported cloth action')
        values=np.array([action['lift_height'],action['motion_seconds'],action['lateral_offset']])
        if not np.isfinite(values).all() or not (0.05<=values[0]<=.4 and .2<=values[1]<=8 and abs(values[2])<=.1):raise ValueError('clamp trajectory outside supported bounds')
        world.action=deepcopy(action)

    def simulate(self,world,limits):
        tic=time.perf_counter();m,d,a=world.model,world.data,world.action;start=float(d.time);trace=[self.observe(world)]
        radius=world.config['side_length']/2;steps=0;failure=None;violations=[];grasp_error=0.;max_penetration=0.
        if not a['planning_feasible'] or not np.all(d.eq_active[world.grasp_ids]):failure='planning_failure'
        duration=a['motion_seconds']+2.;offsets=world.initial_vertices[N*(N-1):]-np.array([radius,0,.012])
        while failure is None and d.time-start<duration:
            t=float(d.time-start);alpha=min(1,t/a['motion_seconds']);blend=alpha*alpha*(3-2*alpha)
            d.mocap_pos[0]=[radius*np.cos(np.pi*blend),a['lateral_offset']*blend,.012+a['lift_height']*np.sin(np.pi*blend)+.012*blend]
            if t>=a['motion_seconds']:d.eq_active[world.grasp_ids]=0
            mj.mj_step(m,d);mj.mj_forward(m,d);steps+=1
            if t<a['motion_seconds']:
                grasp_error=max(grasp_error,float(np.max(np.linalg.norm(d.flexvert_xpos[N*(N-1):]-(d.mocap_pos[0]+offsets),axis=1))))
            if d.ncon:max_penetration=max(max_penetration,float(-np.min(d.contact.dist[:d.ncon])))
            if not np.isfinite(d.qpos).all() or not np.isfinite(d.qvel).all() or np.any(d.warning.number):failure='controller_failure'
            elif max_penetration>.012:
                failure='collision_failure';violations=[{'category':'excessive_cloth_penetration','penetration_m':max_penetration,'bodies':['cloth','contact surface'],'geoms':[]}]
            elif d.time-start>=limits['max_simulation_seconds']:failure='timeout'
            if steps%25==0 or failure:trace.append(self.observe(world))
        trace.append(self.observe(world))
        return {'trace':trace,'failure':failure,'grasp_validated':steps>0 and failure!='planning_failure','grasp_constraint_error_m':grasp_error,'maximum_contact_penetration_m':max_penetration,'contact_violations':violations,'simulation_steps':steps,'execution_duration_s':float(d.time-start),'physics_wall_seconds':time.perf_counter()-tic}

    def evaluate(self,world,result):
        right=world.initial_vertices[:,0]>1e-6;vertices=world.data.flexvert_xpos[right];target=world.initial_vertices[right,:2].copy();target[:,0]*=-1
        alignment=float(np.sqrt(np.mean(np.sum((vertices[:,:2]-target)**2,axis=1))))
        radius=world.config['side_length']/2
        coverage=float(np.mean((vertices[:,0]>=-radius-.01)&(vertices[:,0]<=.01)&(np.abs(vertices[:,1])<=radius+.01)&(vertices[:,2]<.05)))
        grasp=result['grasp_validated'] and result['grasp_constraint_error_m']<=.012
        success=result['failure'] is None and grasp and alignment<=.015 and coverage>=.9
        return {'success':bool(success),'status':result['failure'] or ('fold_success' if success else 'fold_quality_failure'),'alignment_error_m':alignment,'vertex_coverage':coverage,'grasp_valid':bool(grasp),'grasp_constraint_error_m':result['grasp_constraint_error_m'],'maximum_contact_penetration_m':result['maximum_contact_penetration_m'],'contact_violations':result['contact_violations'],'execution_duration_s':result['execution_duration_s'],'fold_quality':max(0.,coverage*(1-alignment/.03)),'milestone':'constrained_single_fold','scope':self.action_schema['scope']}

    def choose(self,branches):
        ranked=sorted(branches,key=lambda b:(not b['evaluation']['success'],b['evaluation'].get('alignment_error_m',float('inf')),-b['evaluation'].get('vertex_coverage',0),b['evaluation'].get('execution_duration_s',float('inf'))))
        good=[b for b in ranked if b['evaluation']['success']]
        return (good[0]['id'] if good else None),{'conclusion':'Measured constrained cloth fold verified.' if good else 'No candidate met physical fold/grasp criteria.','ranked_branch_ids':[b['id'] for b in ranked],'top_feasible_branch_ids':[b['id'] for b in good[:3]],'milestone':'constrained_single_fold'}

    def commit(self,state):return self.snapshot(self.fork(state))
    def replay(self,branch):return {'branch_id':branch['id'],'source':'measured_mujoco_flex_trace','frames':branch['trace'],'evaluation':branch['evaluation']}
