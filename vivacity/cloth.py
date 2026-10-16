"""Actuated Panda folding a flex sheet with a pre-attached folding fixture.

Only joint actuator targets and grip release are commanded during integration.
Old mocap worlds remain readable through the version-preserving legacy adapter.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import time
import xml.etree.ElementTree as ET
import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation
from .robotics import ASSET_DIR, DOWN, asset_digest
from .legacy_cloth import LegacyClothBackend, ClothWorld, N
from .compiled import remember, reuse_world


@dataclass
class RobotClothWorld(ClothWorld):
    site_id: int = 0
    clamp_id: int = 0


class ClothBackend(LegacyClothBackend):
    action_schema = {'type':'clamp_fold', 'units':'meters, seconds',
        'scope':'Actuated Franka Panda carries a folding bar with seven pre-attached constraints; 7x7 MuJoCo flex, fixed hinge/opposite edge, release and settling; no autonomous grasp acquisition.',
        'parameters':['lift_height','motion_seconds','lateral_offset'],
        'controller':'DLS pose IK waypoints and joint position actuators with gravity compensation'}

    def __init__(self):
        self.legacy = LegacyClothBackend()

    @reuse_world('cloth')
    def create_world(self, config, seed):
        if config.get('robot_model') != 'panda':
            return self.legacy.create_world(config, seed)
        root = ET.parse(ASSET_DIR/'panda.xml').getroot()
        root.find('compiler').set('meshdir', str(ASSET_DIR/'assets'))
        root.remove(root.find('keyframe'))
        root.find('option').attrib.update(timestep='.002', integrator='implicitfast', iterations='50')
        for body in root.findall('.//body'):
            body.set('gravcomp', '1')
        radius = config['side_length']/2
        hand = root.find(".//body[@name='hand']")
        bar = ET.SubElement(hand, 'body', name='clamp', pos='0 0 .18', gravcomp='1')
        ET.SubElement(bar, 'geom', name='clamp_bar', type='box', size=f'.008 {radius+.01} .008', mass='.03', contype='0', conaffinity='0')
        ET.SubElement(bar, 'geom', name='fixture_stem', type='cylinder', pos='0 0 -.07', size='.007 .07', mass='.005', contype='0', conaffinity='0')
        ET.SubElement(bar, 'site', name='cloth_grip', size='.004')
        wb = root.find('worldbody')
        ET.SubElement(wb, 'geom', name='table', type='box', pos='.4 0 -.04', size='.7 .65 .04', friction=f"{config['friction']} .01 .001")
        flex = ET.SubElement(wb, 'flexcomp', name='cloth', type='grid', dim='2', count='7 7 1', spacing=' '.join([str(config['side_length']/(N-1))]*3), pos='.5 0 .012', radius='.004', mass=str(config['mass']))
        ET.SubElement(flex, 'contact', selfcollide='auto', friction=f"{config['friction']} .01 .001", solref='.01 1')
        ET.SubElement(flex, 'edge', equality='true', damping='.02')
        ET.SubElement(flex, 'pin', id=' '.join(map(str,list(range(N))+list(range(N*(N//2),N*(N//2+1))))))
        equality = root.find('equality')
        for i in range(N):
            ET.SubElement(equality, 'connect', name=f'grasp_{i}', body1=f'cloth_{N*(N-1)+i}', body2='clamp', anchor='0 0 0', solref='.006 1')
        from .headless import collision_only
        collision_only(root)
        model = mj.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'))
        data = mj.MjData(model)
        data.qpos[:7] = [0,0,0,-1.57079,0,1.57079,-.7853]
        data.qpos[7:9] = .01
        site = mj.mj_name2id(model, mj.mjtObj.mjOBJ_SITE, 'cloth_grip')
        clamp = mj.mj_name2id(model, mj.mjtObj.mjOBJ_BODY, 'clamp')
        world = RobotClothWorld(model,data,deepcopy(config),seed,'',np.empty((0,3)),[mj.mj_name2id(model,mj.mjtObj.mjOBJ_EQUALITY,f'grasp_{i}') for i in range(N)],site_id=site,clamp_id=clamp)
        q, error = self.ik(world, np.array([.5+radius,0,.012]), data.qpos[:7])
        if error > .001:
            raise ValueError(f'Initial robot folding pose unreachable: {error:.6f} m')
        data.qpos[:7] = q
        data.ctrl[:7] = q
        data.ctrl[7] = 0
        mj.mj_kinematics(model,data)
        # Equality anchors are calibrated once to the actual initial robot pose.
        # They are deterministic model configuration, never updated during stepping.
        rotation = data.xmat[clamp].reshape(3,3)
        for i, eq in enumerate(world.grasp_ids):
            vertex = np.array([.5+radius,-radius+i*config['side_length']/(N-1),.012])
            model.eq_data[eq,:3] = 0
            model.eq_data[eq,3:6] = rotation.T@(vertex-data.xpos[clamp])
        mj.mj_forward(model,data)
        world.initial_vertices = data.flexvert_xpos.copy()
        root.find('compiler').set('meshdir','assets')
        world.model_hash = hashlib.sha256((ET.tostring(root,encoding='unicode')+asset_digest()+self.version).encode()+model.eq_data.tobytes()).hexdigest()
        return remember(world, 'cloth')

    def ik(self, world, position, initial):
        m=world.model; d=mj.MjData(m); d.qpos[:]=world.data.qpos
        q=np.asarray(initial).copy(); jp=np.zeros((3,m.nv));jr=np.zeros((3,m.nv))
        for _ in range(180):
            d.qpos[:7]=q; mj.mj_kinematics(m,d);mj.mj_comPos(m,d)
            error=position-d.site_xpos[world.site_id]
            angle=Rotation.from_matrix(DOWN@d.site_xmat[world.site_id].reshape(3,3).T).as_rotvec()
            if np.linalg.norm(error)<.0001 and np.linalg.norm(angle)<.002:break
            mj.mj_jacSite(m,d,jp,jr,world.site_id)
            jac=np.vstack((jp[:,:7],.35*jr[:,:7])); residual=np.r_[error,.35*angle]
            step=jac.T@np.linalg.solve(jac@jac.T+.003**2*np.eye(6),residual)
            step*=min(1,.15/(np.linalg.norm(step)+1e-12))
            q=np.clip(q+step,m.jnt_range[:7,0]+.005,m.jnt_range[:7,1]-.005)
        return q,float(np.linalg.norm(error))

    def observe(self,world):
        if not isinstance(world,RobotClothWorld):return self.legacy.observe(world)
        m,d=world.model,world.data
        return {'time':float(d.time),'vertices':d.flexvert_xpos.tolist(),'triangles':m.flex_elem.reshape(-1,3).tolist(),
            'clamp_position':d.xpos[world.clamp_id].tolist(),'clamp_quaternion_wxyz':d.xquat[world.clamp_id].tolist(),
            'grasp_active':d.eq_active[world.grasp_ids].tolist(),'scope':self.action_schema['scope'],
            'qpos':d.qpos[:9].tolist(),'qvel':d.qvel[:9].tolist(),'ctrl':d.ctrl.tolist(),
            'body_transforms':[{'name':mj.mj_id2name(m,mj.mjtObj.mjOBJ_BODY,i),'position':d.xpos[i].tolist(),'quaternion_wxyz':d.xquat[i].tolist()} for i in range(1,world.clamp_id+1)],
            'source':'measured_mujoco_robot_cloth_trace'}

    def search(self,world,settings,emit):
        if not isinstance(world,RobotClothWorld):return self.legacy.search(world,settings,emit)
        # Existing geometric screening remains a cheap filter, not proof of success.
        actions,elapsed,summary=super().search(world,settings,emit)
        for a in actions:
            a['motion_seconds']=min(8.,a['motion_seconds']+2.)
        summary['sampling']='seeded clamp height, lateral travel and duration; Panda joint IK before physics'
        return actions,elapsed,summary

    def apply_action(self,world,action):
        if not isinstance(world,RobotClothWorld):return self.legacy.apply_action(world,action)
        super().apply_action(world,action)
        tic=time.perf_counter();a=world.action;r=world.config['side_length']/2
        q=world.data.qpos[:7].copy();times=np.linspace(0,a['motion_seconds'],61);waypoints=[];max_error=0.
        for t in times:
            alpha=t/a['motion_seconds'];blend=alpha*alpha*(3-2*alpha)
            p=np.array([.5+r*np.cos(np.pi*blend),a['lateral_offset']*blend,.012+a['lift_height']*np.sin(np.pi*blend)+.012*blend])
            q,error=self.ik(world,p,q);max_error=max(max_error,error);waypoints.append(q.tolist())
        for t in np.linspace(.1,1.,10):
            q,error=self.ik(world,np.array([.5-r,a['lateral_offset'],.024+.15*t]),q)
            max_error=max(max_error,error);times=np.append(times,a['motion_seconds']+t);waypoints.append(q.tolist())
        world.action.update(joint_waypoints=waypoints,waypoint_times=times.tolist(),ik_max_position_error_m=max_error,ik_planning_seconds=time.perf_counter()-tic)
        world.action['planning_feasible']=bool(action.get('planning_feasible',True) and max_error<.002)

    def simulate(self,world,limits):
        if not isinstance(world,RobotClothWorld):return self.legacy.simulate(world,limits)
        tic=time.perf_counter();m,d,a=world.model,world.data,world.action;start=float(d.time);trace=[self.observe(world)]
        paused_start=limits.get('pause_seconds',lambda:0.)()
        steps=0;failure=None;violations=[];grasp_error=0.;max_penetration=0.;tracking=0.
        initial_q=d.qpos[:7].copy();duration=a['motion_seconds']+2.
        if not a['planning_feasible'] or not np.all(d.eq_active[world.grasp_ids]):failure='planning_failure'
        while failure is None and d.time-start<duration:
            if limits.get('checkpoint') and not limits['checkpoint']():failure='cancelled';break
            if limits.get('cancel_event') and limits['cancel_event'].is_set():failure='cancelled';break
            t=float(d.time-start)
            d.ctrl[:7]=[np.interp(t,a['waypoint_times'],np.asarray(a['joint_waypoints'])[:,j]) for j in range(7)]
            if t>=a['motion_seconds']:d.eq_active[world.grasp_ids]=0
            mj.mj_step(m,d);mj.mj_forward(m,d);steps+=1
            tracking=max(tracking,float(np.max(np.abs(d.qpos[:7]-d.ctrl[:7]))))
            if t<a['motion_seconds']:
                rotation=d.xmat[world.clamp_id].reshape(3,3)
                desired=d.xpos[world.clamp_id]+m.eq_data[world.grasp_ids,3:6]@rotation.T
                grasp_error=max(grasp_error,float(np.max(np.linalg.norm(d.flexvert_xpos[N*(N-1):]-desired,axis=1))))
            for contact in d.contact[:d.ncon]:
                depth=max(0.,float(-contact.dist));max_penetration=max(max_penetration,depth)
                names=[mj.mj_id2name(m,mj.mjtObj.mjOBJ_BODY,int(m.geom_bodyid[g])) if g>=0 else 'cloth' for g in contact.geom]
                robot=[n for n in names if n and (n.startswith('link') or n in ('hand','left_finger','right_finger'))]
                mounted=set(names)=={'link0','world'}
                tool_cloth='cloth' in names and all(n in ('cloth','hand','left_finger','right_finger') for n in names)
                if (robot and not mounted and not tool_cloth and depth>.003) or depth>.012:
                    violations.append({'category':'robot_prohibited_contact' if robot else 'excessive_cloth_penetration','penetration_m':depth,'bodies':names,'geoms':[]});failure='collision_failure';break
            if not np.isfinite(d.qpos).all() or not np.isfinite(d.qvel).all() or np.any(d.warning.number):failure='controller_failure'
            elif np.any(d.qpos[:7]<m.jnt_range[:7,0]) or np.any(d.qpos[:7]>m.jnt_range[:7,1]):failure='joint_limit_failure'
            elif tracking>.35:failure='controller_failure'
            elif d.time-start>=limits['max_simulation_seconds']:failure='timeout'
            if steps%25==0 or failure:
                frame=self.observe(world);trace.append(frame)
                if limits.get('on_frame'):
                    limits['on_frame'](frame)
                    if limits.get('realtime'):time.sleep(max(0.,float(d.time-start)/limits.get('realtime_speed',1.)-(time.perf_counter()-tic)+(limits.get('pause_seconds',lambda:0.)()-paused_start)))
        trace.append(self.observe(world))
        return {'trace':trace,'failure':failure,'grasp_validated':steps>0 and failure!='planning_failure','grasp_constraint_error_m':grasp_error,'maximum_contact_penetration_m':max_penetration,'contact_violations':violations,'simulation_steps':steps,'execution_duration_s':float(d.time-start),'physics_wall_seconds':time.perf_counter()-tic,'robot_joint_displacement_rad':float(np.linalg.norm(d.qpos[:7]-initial_q)),'maximum_joint_tracking_error_rad':tracking,'ik_planning_seconds':a['ik_planning_seconds'],'executed_action':deepcopy(a)}

    def evaluate(self,world,result):
        if not isinstance(world,RobotClothWorld):return self.legacy.evaluate(world,result)
        right=world.initial_vertices[:,0]>.500001;vertices=world.data.flexvert_xpos[right];target=world.initial_vertices[right,:2].copy();target[:,0]=1-target[:,0]
        alignment=float(np.sqrt(np.mean(np.sum((vertices[:,:2]-target)**2,axis=1))));radius=world.config['side_length']/2
        coverage=float(np.mean((vertices[:,0]>=.5-radius-.01)&(vertices[:,0]<=.51)&(np.abs(vertices[:,1])<=radius+.01)&(vertices[:,2]<.05)))
        grasp=result['grasp_validated'] and result['grasp_constraint_error_m']<=.012
        success=result['failure'] is None and grasp and alignment<=.015 and coverage>=.9 and result['robot_joint_displacement_rad']>.1
        return {'success':bool(success),'status':result['failure'] or ('fold_success' if success else 'fold_quality_failure'),'alignment_error_m':alignment,'vertex_coverage':coverage,'grasp_valid':bool(grasp),'grasp_constraint_error_m':result['grasp_constraint_error_m'],'maximum_contact_penetration_m':result['maximum_contact_penetration_m'],'contact_violations':result['contact_violations'],'execution_duration_s':result['execution_duration_s'],'fold_quality':max(0.,coverage*(1-alignment/.03)),'milestone':'constrained_single_fold','scope':self.action_schema['scope'],'robot_joint_displacement_rad':result['robot_joint_displacement_rad'],'maximum_joint_tracking_error_rad':result['maximum_joint_tracking_error_rad'],'manipulator':'Franka Panda joint actuators'}

    def replay(self,branch):
        if branch['evaluation']['status']=='adapter_failure':
            return {'branch_id':branch['id'],'source':'failed_adapter_execution','frames':branch['trace'],'evaluation':branch['evaluation']}
        replay=super().replay(branch)
        if branch['trace'] and 'body_transforms' in branch['trace'][0]:
            replay['source']='measured_mujoco_robot_cloth_trace'
        return replay
