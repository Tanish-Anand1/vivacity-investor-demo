"""Contact-driven Panda pickup. The cube is a free body, never attached or repositioned.

The benchmark uses synthetic Coulomb friction, gravity compensation on the arm,
and the unmodified Menagerie finger actuator/collision pads. It is not calibrated
to a physical robot. All task evidence is sampled from integrated MuJoCo state.
"""
from copy import deepcopy
import hashlib
import time
import xml.etree.ElementTree as ET

import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation

from .robotics import ASSET_DIR, DOWN, RobotWorld, RoboticsBackend, asset_digest
from .compiled import remember, reuse_world
from .pickup_planning import joint_route, stage_commands, stage_distance


class PickPlaceBackend(RoboticsBackend):
    arm_dof = 7
    action_schema = {'type': 'pick_place', 'joints': 7, 'gripper_control': '0 closed, 255 open',
                     'milestone': 'physical_pick_and_place', 'planner': 'DLS pose IK; collision-screened joint segments'}

    @reuse_world('mujoco')
    def create_world(self, config, seed, diagnostics=False):
        root = ET.parse(ASSET_DIR / 'panda.xml').getroot()
        root.find('compiler').set('meshdir', str(ASSET_DIR / 'assets'))
        root.find('option').set('timestep', '.002')
        root.find('option').set('cone', 'elliptic')
        root.find('option').set('impratio', '5')
        root.remove(root.find('keyframe'))
        for body in root.findall('.//body'):
            body.set('gravcomp', '1')
        hand = root.find(".//body[@name='hand']")
        ET.SubElement(hand, 'site', name='pregrasp', pos='0 0 .103', size='.008')
        wb = root.find('worldbody')
        ET.SubElement(wb, 'geom', name='ground', type='plane', pos='0 0 -.8', size='2 2 .1')
        ET.SubElement(wb, 'geom', name='table', type='box', pos='.4 0 -.04', size='.7 .65 .04', friction='1 .005 .0001')
        target = ET.SubElement(wb, 'body', name='target', pos=' '.join(map(str, config['cube_position'])))
        ET.SubElement(target, 'freejoint', name='cube_free')
        half_size = config.get('cube_half_size', .025)
        half_sizes = config.get('cube_half_sizes') or [half_size] * 3
        cube_geometry = '.025 .025 .025' if config.get('cube_half_sizes') is None and half_size == .025 else ' '.join(map(str, half_sizes))
        ET.SubElement(target, 'geom', name='cube', type='box', size=cube_geometry,
                      mass=str(config['cube_mass']), friction=f"{config['cube_friction']} .005 .0001",
                      condim='4', priority='1', solref='.004 1', rgba='.05 .35 .9 1')
        obstacle = ET.SubElement(wb, 'body', name='obstacle', pos=' '.join(map(str, config['obstacle_position'])))
        ET.SubElement(obstacle, 'geom', name='obstacle_geom', type='box',
                      size=' '.join(map(str, config['obstacle_size'])),
                      contype='1' if config['obstacle_enabled'] else '0',
                      conaffinity='1' if config['obstacle_enabled'] else '0')
        if config.get('scene_profile') == 'orbital_salvage':
            from .orbital import adapt_scene
            adapt_scene(root, config)
        from .scene import append_scene
        append_scene(wb, config, root)
        from .physical_properties import configure_xml
        configure_xml(root, config)
        physical_root = deepcopy(root)
        physical_root.find('compiler').set('meshdir', 'assets')
        digest = hashlib.sha256((ET.tostring(physical_root, encoding='unicode') + asset_digest() + self.version).encode()).hexdigest()
        sensors=ET.SubElement(root,'sensor')
        for name,attributes in [
            ('robot_contacts',{'subtree1':'link0'}),('mount_contacts',{'body1':'link0','geom2':'table'}),
            ('left_grasp',{'body1':'left_finger','geom2':'cube'}),('right_grasp',{'body1':'right_finger','geom2':'cube'}),
            ('table_support',{'geom1':'cube','geom2':'table'}),('object_obstacle',{'geom1':'cube','geom2':'obstacle_geom'}),
            ('object_ground',{'geom1':'cube','geom2':'ground'})]:
            ET.SubElement(sensors,'contact',name=name,data='found force',reduce='maxforce',**attributes)
        from .scene import append_object_environment_sensors
        append_object_environment_sensors(root,sensors)
        from .headless import collision_only
        collision_only(root)
        model = mj.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'))
        data = mj.MjData(model)
        data.qpos[:9] = [0, 0, 0, -1.57079, 0, 1.57079, -.7853, .04, .04]
        data.ctrl[:self.arm_dof] = data.qpos[:self.arm_dof]; data.ctrl[self.arm_dof] = 255
        from .scene import initialize_task
        initialize_task(model,data,config)
        from .physical_properties import initialize_inputs
        initialize_inputs(model, data, config)
        mj.mj_forward(model, data)
        root.find('compiler').set('meshdir', 'assets')
        world = RobotWorld(model, data, deepcopy(config), seed, digest)
        # Contact sensors observe the same immutable physics layout in both
        # scalar stepping and native rollout. Every fork still owns its MjData.
        return world if diagnostics else remember(world, 'mujoco')

    def contact_evidence(self, world):
        m, d = world.model, world.data
        fingers = set(); force_total = 0.; support = False
        for i, c in enumerate(d.contact[:d.ncon]):
            if c.dist > .001:
                continue
            names = [mj.mj_id2name(m, mj.mjtObj.mjOBJ_BODY, int(m.geom_bodyid[g])) for g in (c.geom1, c.geom2)]
            geoms = [mj.mj_id2name(m, mj.mjtObj.mjOBJ_GEOM, int(g)) for g in (c.geom1, c.geom2)]
            if 'cube' not in geoms:
                continue
            force = np.zeros(6); mj.mj_contactForce(m, d, i, force)
            force_total += abs(float(force[0]))
            for finger in ('left_finger', 'right_finger'):
                if finger in names and force[0] > .01:
                    fingers.add(finger)
            support |= ('table' in geoms or world.config.get('physical_operation')=='stacking' and 'task_fixture_stack_base' in geoms) and force[0] > .01
        return {'finger_contacts': sorted(fingers), 'bilateral_grasp': len(fingers) == 2,
                'cube_contact_normal_force_n': force_total, 'table_support': bool(support)}

    def contacts(self, world):
        # Finger/cube contact is the intended grasp. All other robot contacts
        # retain the reaching adapter's prohibited-contact classification.
        contacts = super().contacts(world)
        violations = [c for c in contacts if not ('cube' in c['geoms'] and
                      any(b in ('left_finger', 'right_finger') for b in c['bodies']))]
        # A carried object may hit the obstacle even when the arm clears it.
        # Table support is intended; object/obstacle or object/ground impact is not.
        m, d = world.model, world.data
        for contact in d.contact[:d.ncon]:
            if contact.dist > 0:
                continue
            geoms = [mj.mj_id2name(m, mj.mjtObj.mjOBJ_GEOM, int(g)) for g in (contact.geom1, contact.geom2)]
            if 'cube' in geoms and any(g in ('obstacle_geom', 'ground') or (g or '').startswith(('environment_','task_fixture_source_tray_')) for g in geoms):
                bodies = [mj.mj_id2name(m, mj.mjtObj.mjOBJ_BODY, int(m.geom_bodyid[g])) or 'world'
                          for g in (contact.geom1, contact.geom2)]
                violations.append({'bodies': bodies, 'geoms': geoms,
                                   'penetration_m': float(-contact.dist), 'category': 'object_environment_collision'})
        return violations

    def observe(self, world):
        observation = super().observe(world)
        observation.update(cube_position=world.data.body('target').xpos.tolist(),
                           cube_quaternion_wxyz=world.data.body('target').xquat.tolist(),
                           placement_position=world.config['placement_position'],
                           grasp=self.contact_evidence(world), source='live_mujoco_state')
        if world.config.get('scene_profile') == 'orbital_salvage':
            from .orbital import SOURCE_SHA256, UPGRADES, scene_geometry
            observation.update(environment_geometries=scene_geometry(world),
                               import_provenance={'source_sha256': SOURCE_SHA256, 'adaptation': UPGRADES})
        if world.config.get('scene_geometries') or world.config.get('physical_operation') in ('stacking','assembly','insertion','machine_tending'):
            from .scene import observed_scene
            observation['environment_geometries'] = observation.get('environment_geometries', []) + observed_scene(world)
        observation['environment_provenance'] = world.config.get('environment')
        from .physical_properties import inspect
        observation['inspection'] = inspect(world, self.arm_dof)
        return observation

    def pose_ik(self, world, goal, start, orientation=None):
        m = world.model; d = mj.MjData(m); d.qpos[:] = world.data.qpos; d.qpos[:self.arm_dof] = start
        sid = m.site('pregrasp').id
        jp, jr = np.zeros((3, m.nv)), np.zeros((3, m.nv))
        for _ in range(250):
            mj.mj_kinematics(m, d); mj.mj_comPos(m, d)
            dp = np.asarray(goal) - d.site_xpos[sid]
            dr = Rotation.from_matrix((DOWN if orientation is None else orientation) @ d.site_xmat[sid].reshape(3, 3).T).as_rotvec()
            if np.linalg.norm(dp) < .0002 and np.linalg.norm(dr) < .003:
                return d.qpos[:self.arm_dof].copy(), True
            mj.mj_jacSite(m, d, jp, jr, sid)
            jac = np.vstack([jp[:, :self.arm_dof], .35 * jr[:, :self.arm_dof]])
            step = jac.T @ np.linalg.solve(jac @ jac.T + .003**2 * np.eye(6), np.r_[dp, .35 * dr])
            step *= min(1., .15 / max(np.linalg.norm(step), 1e-9))
            d.qpos[:self.arm_dof] = np.clip(d.qpos[:self.arm_dof] + step, m.jnt_range[:self.arm_dof, 0] + .005, m.jnt_range[:self.arm_dof, 1] - .005)
        return d.qpos[:self.arm_dof].copy(), False

    def candidates(self, world, count, iterations):
        tic = time.perf_counter(); actions = []
        if world.config.get('scene_profile') == 'workcell':
            from .perception import scan_cube
            sensing = scan_cube(world)
            if not sensing['detected']:
                return ([{'kind': 'pick_place', 'planner': 'staged_dls_contact_pick_place',
                          'candidate_index': index, 'seed': world.seed, 'stages': [],
                          'lift_height_m': None, 'speed_rad_s': None,
                          'planning_feasible': False, 'screening_rejection': 'object_not_visible',
                          'ik': {'converged': False}, 'object_localization': sensing}
                         for index in range(count)], time.perf_counter()-tic)
            cube = np.array([*sensing['estimated_xy_m'], float(world.data.body('target').xpos[2])])
        else:
            sensing = None
            cube = np.asarray(world.data.body('target').xpos)
        action_sensing = {key: value for key, value in sensing.items()
                          if key != 'visible_samples_xy_m'} if sensing else None
        dest = np.asarray(world.config['placement_position'])
        rng = np.random.default_rng(world.seed)
        assembly = world.config.get('assembly') if world.config.get('program_id') == 'precision_assembly' else None
        for index in range(count):
            height = .19 if index == 0 else float(rng.uniform(.17, .25))
            speed = (float(assembly['arm_speed_rad_s']) if index == 0 else
                     float(np.clip(assembly['arm_speed_rad_s'] * rng.uniform(.85, 1.15), .12, .5))) if assembly else (.32 if index == 0 else float(rng.uniform(.27, .36)))
            yaw = (float(assembly['grasp_yaw_rad']) if assembly else 0.) + (index % 8) * np.pi / 4
            orientation = Rotation.from_euler('z', yaw).as_matrix() @ DOWN
            half_sizes = world.config.get('cube_half_sizes') or [world.config.get('cube_half_size', .025)] * 3
            grasp_z = .038 + (half_sizes[2] - .025)
            specs = [('approach', [cube[0], cube[1], height], 255, .3),
                     ('descend', [cube[0], cube[1], grasp_z], 255, .3),
                     ('close', [cube[0], cube[1], grasp_z], 0, .7),
                     ('lift', [cube[0], cube[1], height], 0, .3),
                     ('transport', [dest[0], dest[1], height], 0, .3),
                     ('lower', [dest[0], dest[1], grasp_z], 0, .3),
                     ('release', [dest[0], dest[1], grasp_z], 255, .6),
                     ('retract', [dest[0], dest[1], height], 255, .7)]
            operation=world.config.get('physical_operation','pick_place')
            if operation=='stacking':
                for phase in ('lower','release'):
                    for spec in specs:
                        if spec[0]==phase:spec[1][2]+=dest[2]-cube[2]
            elif operation in ('assembly','insertion','machine_tending'):
                for spec in specs:
                    if spec[0] in ('lower','release'):spec[1][2]=.17
            q = world.data.qpos[:self.arm_dof].copy(); stages = []; converged = True
            for phase, pose, gripper, dwell in specs:
                goal, ok = self.pose_ik(world, pose, q, orientation)
                if not ok:
                    # DLS is local: try independently seeded configurations
                    # before concluding the requested tool pose is unreachable.
                    for retry in range(3):
                        seed_q = np.clip(q+rng.normal(0, .45, self.arm_dof), world.model.jnt_range[:self.arm_dof,0]+.01, world.model.jnt_range[:self.arm_dof,1]-.01)
                        retry_goal, retry_ok = self.pose_ik(world, pose, seed_q, orientation)
                        if retry_ok: goal, ok = retry_goal, True; break
                converged &= ok
                duration = 0. if phase in ('close', 'release') else max(.6, float(np.max(np.abs(goal-q))) / speed)
                stages.append({'phase': phase, 'start': q.tolist(), 'goal': goal.tolist(),
                               'duration_s': duration, 'dwell_s': dwell, 'gripper': gripper, 'tool_position': pose})
                q = goal
            # Actual kinematic contact checking of the robot against the world.
            scratch = RobotWorld(world.model, mj.MjData(world.model), world.config, world.seed, world.model_hash)
            scratch.data.qpos[:] = world.data.qpos
            rejected = None
            for stage in stages:
                scratch.data.qpos[self.arm_dof:self.arm_dof+2] = .04 if stage['gripper'] else .023
                def valid(q):
                    scratch.data.qpos[:self.arm_dof] = q
                    mj.mj_forward(scratch.model, scratch.data)
                    return not self.contacts(scratch)
                start_q, goal_q = np.asarray(stage['start']), np.asarray(stage['goal'])
                direct_ok = all(valid(start_q+(goal_q-start_q)*t) for t in np.linspace(0,1,max(12,int(np.linalg.norm(goal_q-start_q)/.05)+1)))
                if not direct_ok:
                    route = joint_route(start_q, goal_q, world.model.jnt_range[:self.arm_dof], valid,
                                        np.random.default_rng(world.seed+index+101), min(iterations,500)) if converged else None
                    if route is None:
                        rejected = 'kinematic_collision'
                    else:
                        stage['waypoints'] = [p.tolist() for p in route]
                        stage['duration_s'] = max(.6,stage_distance(stage)/speed)
                if rejected:
                    break
            actions.append({'kind': 'pick_place', 'planner': 'multi_yaw_dls_joint_rrt_contact_pick_place', 'candidate_index': index,
                            'grasp_yaw_rad':float(yaw),
                            'seed': world.seed, 'stages': stages, 'lift_height_m': height, 'speed_rad_s': speed,
                            'planning_feasible': converged and not rejected,
                            'screening_rejection': rejected or (None if converged else 'ik_failure'),
                            'ik': {'converged': bool(converged)}, 'object_localization': action_sensing})
        return actions, time.perf_counter()-tic

    def apply_action(self, world, action):
        if action.get('screening_rejection') == 'object_not_visible' and action.get('stages') == []:
            world.action = deepcopy(action)
            return
        if action.get('kind') != 'pick_place' or len(action.get('stages', [])) != 8:
            raise ValueError('expected eight-stage contact pick-and-place action')
        if not np.allclose(action['stages'][0]['start'], world.data.qpos[:self.arm_dof], atol=1e-6, rtol=0):
            raise ValueError('action must start at restored parent state')
        for stage in action['stages']:
            for key in ('start', 'goal'):
                q = np.asarray(stage[key])
                if q.shape != (self.arm_dof,) or not np.isfinite(q).all():
                    raise ValueError(f'finite {self.arm_dof}-coordinate joint targets required')
            if not (0 <= stage['duration_s'] <= 60 and 0 <= stage['dwell_s'] <= 2 and 0 <= stage['gripper'] <= 255):
                raise ValueError('stage command outside resource limits')
            if stage.get('waypoints'):
                path = np.asarray(stage['waypoints'])
                if path.ndim!=2 or path.shape[1]!=self.arm_dof or len(path)>512 or not np.isfinite(path).all() or not np.allclose(path[0],stage['start']) or not np.allclose(path[-1],stage['goal']):
                    raise ValueError('invalid routed pickup stage')
        world.action = deepcopy(action)

    def search(self, world, settings, emit):
        """Distinct timed plans; reuse measured kinematics for identical geometry.

        Height templates are screened once. Each proposal varies arm speed and
        close/release dwell, then receives its own finite/limit/horizon checks.
        Timing screening cannot prove a frictional grasp: only physics can.
        """
        tic=time.perf_counter();templates,_=self.candidates(world,8,settings['planner_iterations'])
        rng=np.random.default_rng(world.seed);eligible=[];all_actions=[];distinct=set();digest=hashlib.sha256()
        rejected={'kinematic_collision':0,'ik_failure':0,'simulation_horizon':0,'object_not_visible':0}
        total=settings['search_candidates']
        for i in range(total):
            if settings.get('checkpoint') and not settings['checkpoint']():raise InterruptedError('cancelled while generating candidates')
            action=deepcopy(templates[i%len(templates)])
            assembly=world.config.get('assembly') if world.config.get('program_id')=='precision_assembly' else None
            speed_bounds=(max(.12,assembly['arm_speed_rad_s']*.85),min(.5,assembly['arm_speed_rad_s']*1.15)) if assembly else getattr(self,'search_speed_bounds',(.27,.36))
            speed=float(rng.uniform(*speed_bounds));action['speed_rad_s']=speed;action['candidate_index']=i
            action['lift_template_index']=i%len(templates)
            for stage in action['stages']:
                if stage['duration_s']:
                    stage['duration_s']=max(.6,stage_distance(stage)/speed)
                if stage['phase']=='close':stage['dwell_s']=float(rng.uniform(.6,.9))
                if stage['phase']=='release':stage['dwell_s']=float(rng.uniform(.5,.8))
            duration=sum(s['duration_s']+s['dwell_s'] for s in action['stages'])
            if settings.get('physics_trials'):all_actions.append((duration,i,action))
            signature=hashlib.sha256(str(action['stages']).encode()).digest();distinct.add(signature);digest.update(signature)
            reason=action['screening_rejection']
            if not reason and duration>=settings['max_simulation_seconds']:reason='simulation_horizon'
            if reason:rejected[reason]+=1
            else:eligible.append((duration,i,action))
            if (i+1)%1000==0 or i+1==total:
                emit({'stage':'screening','generated':i+1,'screened':i+1,'rejected':sum(rejected.values()),
                      'screening_passed':len(eligible),'message':f'{i+1:,} distinct timed pickup plans checked; {len(eligible):,} passed screening.'})
        eligible.sort(key=lambda item:(item[0],item[1]))
        actions=[item[2] for item in eligible[:settings['physics_budget']]]
        if settings.get('adaptive_trials'):
            # Cover distinct geometric lift paths before spending the remaining
            # physics budget on the shortest predicted timings.
            diverse=[];seen=set()
            for item in eligible:
                template=item[2]['lift_template_index']
                if template not in seen:
                    diverse.append(item);seen.add(template)
                if len(diverse)>=min(len(templates),settings['physics_budget']):break
            chosen={item[1] for item in diverse}
            actions=[item[2] for item in (diverse+[item for item in eligible if item[1] not in chosen])[:settings['physics_budget']]]
        if settings.get('physics_trials'):
            if total!=settings['physics_trials']:raise ValueError('full physics requires one generated command per requested trial')
            actions=[item[2] for item in sorted(all_actions,key=lambda item:(item[0],item[1]))]
        if not actions:actions=[templates[0]]
        summary={'generated':total,'distinct_generated':len(distinct),'screened':total,'rejected':sum(rejected.values()),
                 'screening_passed':len(eligible),'promoted_to_physics':len(actions),
                 'candidate_catalog_sha256':digest.hexdigest(),'rejection_reasons':rejected,
                 'kinematic_templates_checked':len(templates),'diagnostic_rollouts':int(not eligible),
                 'sampling':'seeded lift-height templates and distinct speed/close-dwell/release-dwell commands',
                 'adaptive_stopping':bool(settings.get('adaptive_trials')),
                 'screening_scope':'actual template IK/kinematic contacts plus per-candidate timing/horizon checks; no dynamic success claim',
                 'ranking_objective':'successful execution, measured duration, placement error, candidate index'}
        emit(summary|{'stage':'screening_complete','message':f'{len(eligible):,} screened plans eligible; {len(actions)} promoted to actual physics.'})
        return actions,time.perf_counter()-tic,summary

    def tracking_errors(self,world,qpos,commands):
        error=np.abs(np.asarray(qpos)[...,:self.arm_dof]-np.asarray(commands)[...,:self.arm_dof])
        slide=world.model.jnt_type[:self.arm_dof]==mj.mjtJoint.mjJNT_SLIDE
        angular=float(np.max(error[...,~slide])) if (~slide).any() else 0.
        linear=float(np.max(error[...,slide])) if slide.any() else 0.
        return angular,linear

    def simulate(self, world, limits):
        tic = time.perf_counter(); d, m = world.data, world.model
        paused_start=limits.get('pause_seconds',lambda:0.)()
        start_time = float(d.time); trace = [self.observe(world) | {'phase': 'initializing'}]
        failure = None; violations = []; steps = 0; milestones = []; retention = True; lifted = False
        max_height = float(d.body('target').xpos[2]); max_tracking = 0.;max_linear_tracking=0.
        peak_effort={m.actuator(i).name:0. for i in range(m.nu)} if world.config.get('program_id')=='precision_assembly' else {}
        if not world.action['planning_feasible']:
            failure = 'planning_failure'
        for stage in world.action['stages']:
            if failure:
                break
            phase = stage['phase']; duration = stage['duration_s']; total = duration + stage['dwell_s']
            for i in range(int(np.ceil(total / m.opt.timestep))):
                if limits.get('checkpoint') and not limits['checkpoint']():failure='cancelled';break
                if limits.get('cancel_event') and limits['cancel_event'].is_set():
                    failure = 'cancelled'; break
                alpha = min(1., (i+1) * m.opt.timestep / max(duration, m.opt.timestep))
                d.ctrl[:self.arm_dof] = stage_commands(stage,[alpha])[0]
                d.ctrl[self.arm_dof] = stage['gripper']
                mj.mj_step(m, d); mj.mj_forward(m, d); steps += 1
                for index,name in enumerate(peak_effort):
                    peak_effort[name]=max(peak_effort[name],float(abs(d.actuator_force[index])))
                angular,linear=self.tracking_errors(world,d.qpos,d.ctrl)
                max_tracking=max(max_tracking,angular);max_linear_tracking=max(max_linear_tracking,linear)
                evidence = self.contact_evidence(world)
                height = float(d.body('target').xpos[2]); max_height = max(max_height, height)
                if phase in ('lift', 'transport', 'lower') and height > .075:
                    lifted = True
                    if not evidence['bilateral_grasp']:
                        retention = False; failure = 'dropped_object'
                if phase == 'transport' and height < .07:
                    retention = False; failure = 'dropped_object'
                contacts = self.contacts(world)
                if contacts:
                    failure = 'collision_failure'; violations.extend(contacts)
                if not np.isfinite(d.qpos).all() or np.any(d.warning.number) or max_tracking > .35 or max_linear_tracking > .035:
                    failure = 'controller_failure'
                if np.any((d.qpos[:self.arm_dof] < m.jnt_range[:self.arm_dof, 0]-.002)&m.jnt_limited[:self.arm_dof]) or np.any((d.qpos[:self.arm_dof] > m.jnt_range[:self.arm_dof, 1]+.002)&m.jnt_limited[:self.arm_dof]):
                    failure = 'joint_limit_failure'
                elapsed=time.perf_counter()-tic-(limits.get('pause_seconds',lambda:0.)()-paused_start)
                if d.time-start_time >= limits['max_simulation_seconds'] or elapsed > limits.get('max_wall_seconds', 120):
                    failure = 'timeout'
                if steps % 25 == 0 or failure:
                    frame = self.observe(world) | {'phase': phase}
                    trace.append(frame)
                    if limits.get('on_frame'):
                        limits['on_frame'](frame)
                        if limits.get('realtime'):
                            time.sleep(max(0., float(d.time-start_time)/limits.get('realtime_speed', 1.)-elapsed))
                if failure:
                    break
            evidence = self.contact_evidence(world)
            milestones.append({'phase': phase, 'time': float(d.time), 'cube_position': d.body('target').xpos.tolist(), **evidence})
            if phase == 'close' and not evidence['bilateral_grasp'] and not failure:
                failure = 'grasp_failure'
        if not failure:
            from .scene import finish_task
            extra,failure,contacts=finish_task(world,limits,trace,self,start_time,tic,paused_start)
            steps+=extra;violations.extend(contacts)
        trace.append(self.observe(world) | {'phase': 'evaluating'})
        return {'trace': trace, 'failure': failure, 'contact_violations': violations, 'milestones': milestones,
                'lifted': lifted, 'retained_during_transport': retention and lifted,
                'max_cube_height_m': max_height, 'max_tracking_error_rad': max_tracking,'max_tracking_error_m':max_linear_tracking,
                'peak_actuator_scalar': peak_effort,
                'simulation_steps': steps, 'execution_duration_s': float(d.time-start_time),
                'physics_wall_seconds': time.perf_counter()-tic}

    def evaluate(self, world, result):
        position = world.data.body('target').xpos.copy()
        error = float(np.linalg.norm(position-np.asarray(world.config['placement_position'])))
        evidence = self.contact_evidence(world)
        closed = next((m for m in result['milestones'] if m['phase'] == 'close'), {})
        failure = result['failure']
        if not failure and not result['lifted']:
            failure = 'lift_failure'
        if not failure and (error > .025 or not evidence['table_support'] or np.linalg.norm(world.data.qvel[int(world.model.jnt_dofadr[world.model.joint('cube_free').id]):]) > .05):
            failure = 'placement_failure'
        if not failure and (evidence['bilateral_grasp'] or world.data.ctrl[self.arm_dof] < 200):
            failure = 'release_failure'
        evaluation={'success': failure is None, 'status': failure or 'execution_success',
                'milestone': 'physical_pick_and_place', 'planning_feasible': world.action['planning_feasible'],
                'goal_error_m': error, 'final_cube_position': position.tolist(), 'grasp_established': closed.get('bilateral_grasp', False),
                'lifted': result['lifted'], 'retained_during_transport': result['retained_during_transport'],
                'released': bool(not evidence['bilateral_grasp'] and world.data.ctrl[self.arm_dof] >= 200),
                'table_supported': evidence['table_support'], 'max_cube_height_m': result['max_cube_height_m'],
                'max_tracking_error_rad': result['max_tracking_error_rad'],'max_tracking_error_m':result.get('max_tracking_error_m',0.), 'contact_violations': result['contact_violations'],
                'peak_actuator_scalar': result.get('peak_actuator_scalar',{}),
                'phase_evidence': result['milestones'], 'execution_duration_s': result['execution_duration_s']}
        from .operation_evaluation import evaluate_operation
        return evaluate_operation(world,evaluation)


class RobotAdapter:
    """Keep persisted reach scenes compatible while selecting a domain-specific task."""
    version = RoboticsBackend.version
    action_schema = {'tasks': {'reach': RoboticsBackend.action_schema, 'pick_place': PickPlaceBackend.action_schema}}

    def __init__(self):
        self.reach = RoboticsBackend(); self.pick_place = PickPlaceBackend()
        self.models = {}

    def backend(self, config):
        identifier=config.get('robot_model','panda')
        if identifier!='panda':
            from .robot_models import ModelPickupBackend, ModelReachBackend
            key=(identifier,config.get('task'))
            if key not in self.models:self.models[key]=(ModelPickupBackend if config.get('task')=='pick_place' else ModelReachBackend)(identifier)
            return self.models[key]
        return self.pick_place if config.get('task') == 'pick_place' else self.reach

    def create_world(self, config, seed):
        return self.backend(config).create_world(config, seed)

    def fork(self, state):
        return self.backend(state['config']).fork(state)

    def commit(self, state):
        return self.backend(state['config']).commit(state)

    def snapshot(self, world):
        return self.backend(world.config).snapshot(world)

    def observe(self, world):
        return self.backend(world.config).observe(world)

    def candidates(self, world, count, iterations):
        return self.backend(world.config).candidates(world, count, iterations)

    def search(self, world, settings, emit):
        return self.backend(world.config).search(world,settings,emit)

    def contacts(self, world):
        return self.backend(world.config).contacts(world)

    def apply_action(self, world, action):
        return self.backend(world.config).apply_action(world, action)

    def simulate(self, world, limits):
        backend=self.backend(world.config)
        if world.config.get('task')=='pick_place' and world.action.get('planning_feasible'):
            from .native_pick_place import NativePickup
            result,_,final_state=NativePickup(backend,backend.snapshot(world)).simulate(world.action,limits)
            backend.restore(world,final_state)
            return result
        return backend.simulate(world, limits)

    def evaluate(self, world, result):
        return self.backend(world.config).evaluate(world, result)

    def replay(self, branch):
        return self.backend(branch['initial_state']['config']).replay(branch)
