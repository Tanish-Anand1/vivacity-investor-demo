"""Experimental contact-operated door primitive, not a cabinet service result.

The floating-base robot, two visible bounded tools, latch and door share one
native model. No pose is changed during execution. Cabinet extraction, insertion
and full-cycle acceptance remain separate requirements.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import uuid

import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation

from .cabinet_mechanism import CabinetConfig, append_cabinet, measure
from .cabinet_tooling import SWIVEL_JOINT, append_latch_swivel, swivel_manifest
from .cabinet_route import route_approach
from .pickup_planning import stage_commands, stage_distance
from .execution_checkpoint import capture, restore, ImmutableModelArtifact
from .humanoid_embodiments import compile_embodiment
from .humanoids import _frame
from .humanoid_ik import site_pose
from .inverse_dynamics import ControllerInfeasible
from .simulated_tooling import ParallelGripperConfig
from .stance_control import StanceController


ARM_PARTS = ('shoulder_aa','shoulder_ie','shoulder_fe','elbow_fe','wrist_roll','wrist_yaw','wrist_pitch')
TOOL_ROTATIONS = {
    'l':np.array([[0.,0.,-1.],[0.,1.,0.],[1.,0.,0.]]),
    'r':np.array([[0.,0.,-1.],[-1.,0.,0.],[0.,1.,0.]]),
}
GRASP_SURFACES = {'l':{'service_latch_button','service_latch_crossbar_link_0.4'},
    'r':{'service_door_handle','service_handle_mount_-0.045','service_handle_mount_0.045'}}
LATCH_TCP_STANDOFF_M = .02
SOURCE_HASHES = {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ('apollo_door.py','cabinet_mechanism.py','humanoid_embodiments.py',
                             'simulated_tooling.py','humanoid_ik.py','stance_control.py','wrench_dynamics.py',
                             'cabinet_tooling.py','cabinet_route.py','pickup_planning.py')}


class ApolloToolController:
    version = 'vivacity.apollo-cartesian-contact/6-experimental'

    def __init__(self, model):
        self.stance = StanceController(model, 'apollo')
        self.wide_tooling = mj.mj_name2id(model,mj.mjtObj.mjOBJ_JOINT,SWIVEL_JOINT)>=0
        if self.wide_tooling:
            # The opposed tool needs more arm motion to unload the latch than
            # the historical 0.25-rad probe. Keep native torque/contact bounds;
            # the wider task still succeeds only on measured physics.
            self.stance.reference_weight = 1.
        self.integrals = {side:np.zeros(3) for side in ('l','r')}
        self.rotation_integrals = {side:np.zeros(3) for side in ('l','r')}
        self.dt = float(model.opt.timestep)

    def compute(self, data, reference, goals=None, released_hands=()):
        poses = {}
        for side, goal in (goals or {}).items():
            name = side+'_service_tcp'
            error = np.asarray(goal['position'])-data.site(name).xpos
            # Bounded task-space integral compensates static native friction and
            # model mismatch. It changes actuator references, never body poses.
            self.integrals[side] = np.clip(self.integrals[side]+self.dt*.8*error, -.06, .06)
            poses[name] = {**goal,'position':np.asarray(goal['position'])+self.integrals[side],
                'weight':10000.}
            if self.wide_tooling:
                angular=Rotation.from_matrix(np.asarray(goal['rotation']) @
                    data.site(name).xmat.reshape(3,3).T).as_rotvec()
                correction=self.rotation_integrals[side]+self.dt*.2*angular
                self.rotation_integrals[side]=correction*min(1.,.15/max(np.linalg.norm(correction),1e-12))
                poses[name]['rotation']=Rotation.from_rotvec(self.rotation_integrals[side]).as_matrix() @ goal['rotation']
        released_geoms = [self.stance.model.geom(f'{side}_service_{finger}_pad').id
            for side in released_hands for finger in ('positive','negative')]
        joint_targets = ({SWIVEL_JOINT:float(reference[
            self.stance.model.joint(SWIVEL_JOINT).qposadr[0]])} if self.wide_tooling else None)
        return self.stance.compute(data,reference,site_targets=poses,released_geoms=released_geoms,
            joint_targets=joint_targets)

    def snapshot(self):
        return {'version':self.version, 'stance':self.stance.snapshot(),
                'rotation_integrals':{name:value.tolist() for name,value in self.rotation_integrals.items()},
                'integrals':{name:value.tolist() for name,value in self.integrals.items()}}

    def restore(self, state):
        if state['version'] != self.version:
            raise ValueError('Apollo controller version changed')
        integrals = {}
        for side in ('l','r'):
            value = np.asarray(state['integrals'][side],dtype=float)
            if value.shape != (3,) or not np.isfinite(value).all() or np.max(np.abs(value)) > .06000001:
                raise ValueError('invalid Cartesian integral checkpoint')
            integrals[side] = value.copy()
        stance = StanceController(self.stance.model, 'apollo')
        stance.restore(state['stance'])
        angular_integrals={}
        for side in ('l','r'):
            value=np.asarray(state['rotation_integrals'][side],dtype=float)
            if value.shape!=(3,) or not np.isfinite(value).all() or np.linalg.norm(value)>.15000001:
                raise ValueError('invalid angular integral checkpoint')
            angular_integrals[side]=value.copy()
        self.integrals, self.stance = integrals, stance
        self.rotation_integrals=angular_integrals


class CabinetDoorPrimitive:
    version = 'vivacity.apollo-door-primitive/5-experimental'

    def __init__(self, config=None, tooling=None, seed=7, opening_angle_rad=.25):
        if not np.isfinite(opening_angle_rad) or not .25 <= opening_angle_rad <= 1.2:
            raise ValueError('door opening target must be between 0.25 and 1.2 radians')
        self.config = config or CabinetConfig(front_x_m=.75)
        self.tooling = tooling or ParallelGripperConfig()
        def scene(root):
            if opening_angle_rad > .25:
                append_latch_swivel(root)
            append_cabinet(root,self.config)
            if opening_angle_rad == .25:
                # The historical fixture has a shorter exposed latch button.
                # Preserve that complete model/controller contract while the
                # larger opening and opposed mount are developed separately.
                root.find(".//geom[@name='service_latch_button']").set('pos','-.045 .40 .065')
                link=root.find(".//geom[@name='service_latch_crossbar_link_0.4']")
                link.set('pos','-.034 .4 .065')
                link.set('size','.017 .010 .010')
        self.model,self.data,self.manifest = compile_embodiment('apollo',self.tooling,append_scene=scene)
        if opening_angle_rad > .25:
            self.manifest['identity'] = 'vivacity.apollo-cabinet-swivel-tool/3-experimental'
            self.manifest['cabinet_tooling'] = swivel_manifest(self.model)
        self.manifest['cabinet_fixture_profile'] = (
            'wide-opening-development' if opening_angle_rad>.25 else 'historical-partial-door')
        self.artifact = ImmutableModelArtifact(self.model)
        self.controller = ApolloToolController(self.model)
        self.rng = np.random.default_rng(seed)
        self.world_version = str(uuid.uuid4())
        self.state = dict(status='running',phase='settle',phase_started_s=0.,steps_completed=0,
            next_frame_seq=0,seed=seed,config=self.config.model_dump(),tooling=self.tooling.model_dump(),
            opening_angle_rad=float(opening_angle_rad),
            task_version=self.version,source_hashes=SOURCE_HASHES.copy(),
            success=False,cabinet_service_complete=False,failure=None,
            phase_events=[],planning_events=[],stable_samples=0,peak_tilt_rad=0.,peak_contact_force_n=0.,peak_gripper_actuator_force_n=0.,
            peak_swivel_torque_nm=0.,
            phase_start_qpos=self.data.qpos.tolist(),reference=self.model.key_qpos[0].tolist(),
            goals={},start_goals={},grip_forces={},model_manifest=self.manifest)

    def _tool_rotation(self, side, vertical=False):
        # A vertical pinch lets the latch button yaw between the pads while the
        # door swings. Horizontal pinch would demand an unreachable wrist yaw.
        # Native friction/contact still decides whether this grasp is retained.
        return TOOL_ROTATIONS['r'] if side=='l' and (vertical or self.controller.wide_tooling) else TOOL_ROTATIONS[side]

    def _plan(self, phase):
        x,y = self.config.front_x_m,self.config.center_y_m
        goals = deepcopy(self.state['goals'])
        if phase == 'approach':
            goals = {side:{'position':[x-.19,y+offset,z],'rotation':self._tool_rotation(side).tolist()}
                     for side,offset,z in (('r',-.11,1.1),('l',.145,1.165))}
            if self.state['opening_angle_rad']>.25:
                goals['l']['position'][0] = x-.21
        elif phase == 'insert':
            for side,goal in goals.items():
                # The button protrudes from its crossbar. Grasp its exposed
                # front section without driving the fingertips into the bar.
                offset = (.085+LATCH_TCP_STANDOFF_M if side=='l' else .10) if self.state['opening_angle_rad']>.25 else (
                    .095 if side=='l' else .08)
                goal['position'][0] = x-offset
                if side=='r' and self.controller.wide_tooling:
                    goal['position'][2] = 1.1
        elif phase == 'latch':
            goals['l']['position'][1] = y+.195
        elif phase == 'release_left':
            goals['l']['position'][0] -= .015
        elif phase == 'withdraw_left':
            goals['l']['position'][0] -= .08
        elif phase == 'rotate_left':
            goals['l']['rotation'] = self._tool_rotation('l',True).tolist()
        elif phase == 'insert_left':
            goals['l'] = {'position':(self.data.geom('service_latch_button').xpos+
                self._tool_rotation('l',True) @ np.array([0.,0.,.05])).tolist(),
                'rotation':self._tool_rotation('l',True).tolist()}
        elif phase in ('open','open_wide'):
            hinge = np.array([x,y+.28,1.1])
            angle = self.state['opening_angle_rad'] if phase=='open_wide' else .25
            rotation = Rotation.from_rotvec([0.,0.,-angle]).as_matrix()
            for side,relative in (('r',[-.10,-.39,0.]),('l',[-.135,-.085,.065])):
                if phase=='open_wide' and side=='r':
                    continue
                # The right pads grasp the horizontal top/bottom faces; their
                # vertical closing axis can stay fixed as the handle yaws.
                # Retention is still decided from actual contact, not a weld.
                wrist_angle = min(angle, .5)
                orientation = self._tool_rotation(side,phase=='open_wide') if side=='r' or phase=='open_wide' or self.controller.wide_tooling else (
                    Rotation.from_rotvec([0.,0.,-wrist_angle]).as_matrix() @ TOOL_ROTATIONS[side])
                position = hinge+rotation @ relative
                if side=='l':
                    # Keep the grasp point on the button, and offset the wrist
                    # along its own approach axis. Rotating this offset with the
                    # door while the wrist yaw is bounded loses the grasp.
                    button = hinge+rotation @ np.array([-.085,-.085,.065])
                    position = button+orientation @ np.array([0.,0.,LATCH_TCP_STANDOFF_M])
                goals[side] = {'position':position.tolist(),
                               'rotation':orientation.tolist()}
            if phase=='open' and self.state['opening_angle_rad']==.25:
                for side,relative in (('r',[-.08,-.39,0.]),('l',[-.095,-.085,.065])):
                    goals[side] = {'position':(hinge+rotation @ relative).tolist(),
                        'rotation':(TOOL_ROTATIONS[side] if side=='r' else
                                    rotation @ TOOL_ROTATIONS[side]).tolist()}
        elif phase == 'release_right':
            # Release before moving the wrist. Dragging a loaded upper pad
            # rotates the door into the finger while the other hand holds it.
            # Hold the measured pose while the pads unload; withdrawal follows
            # only after both fingers have actually separated from the handle.
            if self.controller.wide_tooling:
                site = self.data.site('r_service_tcp')
                goals['r'] = {'position':site.xpos.tolist(),
                              'rotation':site.xmat.reshape(3,3).tolist()}
            else:
                goals['r']['position'][0] -= .02
        elif phase == 'withdraw_right':
            goals['r']['position'][0] -= .08
            goals['r']['position'][2] -= .07
        elif phase == 'park_right':
            goals['r'] = {'position':[x-.35,y-.20,1.25],
                'rotation':(Rotation.from_rotvec([0.,-.6,0.]).as_matrix() @ self._tool_rotation('r')).tolist()}
        reference = self.model.key_qpos[0].copy()
        start_reference = reference.copy()
        planning_state = self.data.qpos.copy()
        for side,goal in goals.items():
            joints = [side+'_'+part for part in ARM_PARTS]
            if side=='l' and self.controller.wide_tooling:
                joints.append(SWIVEL_JOINT)
            seeds = [('measured',planning_state)]
            if self.controller.wide_tooling:
                # Native contact can displace a loaded arm from its feasible
                # IK basin. The stance controller is restoring the nominal
                # floating-base pose, so its previous full command supplies a
                # second kinematic seed. Neither seed changes live MjData;
                # native execution must still realize the planned pose.
                previous = np.asarray(self.state['reference'])
                if not np.array_equal(previous,planning_state):
                    seeds.append(('previous_command',previous))
            for initialization,seed in seeds:
                margins = ((None,) if phase=='release_right' and side=='r' and self.controller.wide_tooling
                           else (.08,.04,.01) if self.controller.wide_tooling else (None,))
                for margin in margins:
                    plan = site_pose(self.model,seed,side+'_service_tcp',
                        joints,goal['position'],goal['rotation'],joint_margin=margin)
                    self.state['planning_events'].append({'phase':phase,'hand':side,
                        'initialization':initialization,'joint_reserve_rad':margin,
                        'feasible':bool(plan.feasible),
                        'position_error_m':float(plan.position_error_m),
                        'angular_error_rad':float(plan.angular_error_rad)})
                    if plan.feasible:
                        break
                if plan.feasible:
                    break
            if not plan.feasible:
                self.fail('unreachable_target',{'phase':phase,'hand':side,
                    'position_error_m':plan.position_error_m,'angular_error_rad':plan.angular_error_rad})
                return
            planning_state = plan.qpos
            for name in joints:
                address = self.model.joint(name).qposadr[0]
                reference[address] = plan.qpos[address]
                start_reference[address] = (self.state['reference'][address]
                    if self.controller.wide_tooling else self.data.qpos[address])
            for finger in ('positive','negative'):
                address = self.model.joint(f'{side}_service_{finger}_slide').qposadr[0]
                # A loaded finger's measured position differs from its servo
                # target. Starting the next phase at the measured compression
                # would remove its preload and let a frictional grasp slip.
                # Preserve the commanded reference across wide-task phases;
                # opening still ramps through the native force-limited drive.
                start_reference[address] = (self.state['reference'][address]
                    if self.controller.wide_tooling else self.data.qpos[address])
                closing = phase in ('grasp','latch','open') or (
                    side=='l' and phase in ('grasp_left','release_right','withdraw_right','park_right','open_wide')) or (
                    side=='r' and phase in ('release_left','withdraw_left','rotate_left','insert_left','grasp_left'))
                opening = .03 if side=='r' and phase in ('release_right','withdraw_right','park_right','open_wide') else .035
                reference[address] = 0. if closing else opening
        previous = self.state['phase']
        route=None
        if phase=='approach' and self.controller.wide_tooling:
            route_joints=[side+'_'+part for side in ('l','r') for part in ARM_PARTS]
            route_joints.append(SWIVEL_JOINT)
            route_joints += [f'{side}_service_{finger}_slide'
                for side in ('l','r') for finger in ('positive','negative')]
            guides=[]
            for offset,height in ((.45,1.25),(.40,1.35),(.35,1.35)):
                guide=site_pose(self.model,reference,'r_service_tcp',
                    ['r_'+part for part in ARM_PARTS],[x-offset,y-.2,height],
                    self._tool_rotation('r'),joint_margin=.01)
                if guide.feasible:
                    guides.append(guide.qpos)
            route=route_approach(self.model,self.data.qpos,reference,route_joints,self.rng,guides=guides)
            self.state['planning_events'].append({'phase':phase,'planner':'seeded_joint_space_rrt',
                **{key:value for key,value in route.items() if key!='waypoints'},
                'waypoint_count':len(route['waypoints'])})
            if not route['feasible']:
                self.fail('collision_free_route_not_found',{'phase':phase,'collision_checks':route['collision_checks']})
                return
        self.state.update(phase=phase,phase_started_s=float(self.data.time),stable_samples=0,
            approach_route=route,
            lost_grip_samples=0,
            start_door_angle_rad=float(self.data.joint('service_door_hinge').qpos[0]),
            phase_start_qpos=start_reference.tolist(),reference=reference.tolist(),goals=goals,
            start_goals={side:(deepcopy(self.state['goals'][side])
                if self.controller.wide_tooling and side in self.state['goals'] and
                not (phase=='release_right' and side=='r') else
                {'position':self.data.site(side+'_service_tcp').xpos.tolist(),
                 'rotation':self.data.site(side+'_service_tcp').xmat.reshape(3,3).tolist()}) for side in goals})
        self.state['phase_events'].append({'from':previous,'to':phase,'time_s':float(self.data.time),
            'measurements':self.observe()})

    def fail(self, reason, detail=None):
        # Keep the first observed failure. A later check in the same native step
        # must not overwrite the causal event (for example collision then tilt).
        if self.state['status'] == 'running':
            self.state.update(status='failed',failure=reason,failure_detail=detail)

    def observe(self):
        result = measure(self.model,self.data,self.config)
        # Tilt excludes heading: yaw alone cannot make an upright robot fall.
        result['root_tilt_rad'] = float(np.arccos(np.clip(self.data.body('base_link').xmat[8],-1.,1.)))
        result['root_speed_m_s'] = float(np.linalg.norm(self.data.qvel[:3]))
        result['grip_forces_n'] = deepcopy(self.state['grip_forces'])
        result['pose_errors'] = {side:{
            'position_m':float(np.linalg.norm(self.data.site(side+'_service_tcp').xpos-goal['position'])),
            'angle_rad':float(np.linalg.norm(Rotation.from_matrix(np.asarray(goal['rotation']) @
                self.data.site(side+'_service_tcp').xmat.reshape(3,3).T).as_rotvec()))}
            for side,goal in self.state['goals'].items()}
        result['tool_swivel'] = ({'angle_rad':float(self.data.joint(SWIVEL_JOINT).qpos[0]),
            'speed_rad_s':float(self.data.joint(SWIVEL_JOINT).qvel[0]),
            'actuator_torque_nm':float(self.data.actuator_force[self.model.actuator('l_service_swivel_drive').id])}
            if self.controller.wide_tooling else None)
        return result

    def _contacts(self):
        grip = {side:{finger:0. for finger in ('positive','negative')} for side in ('l','r')}
        # Mounts are part of the same visible graspable handle assembly. The
        # door panel, full latch crossbar and cabinet shell remain prohibited.
        allowed = GRASP_SURFACES
        for index,contact in enumerate(self.data.contact[:self.data.ncon]):
            if contact.dist > 0.:
                continue
            names = [self.model.geom(contact.geom1).name or '',self.model.geom(contact.geom2).name or '']
            force = np.zeros(6)
            mj.mj_contactForce(self.model,self.data,index,force)
            for side in ('l','r'):
                for finger in ('positive','negative'):
                    pad = f'{side}_service_{finger}_pad'
                    if pad in names and allowed[side].intersection(names):
                        grip[side][finger] += max(0.,float(force[0]))
            if any('_service_' in name or name.startswith('collision_') for name in names):
                if any(name.startswith('service_') for name in names):
                    self.state['peak_contact_force_n'] = max(self.state['peak_contact_force_n'],float(force[0]))
                    if force[0] > 180.:
                        self.fail('excessive_contact_force',{'geoms':names,'normal_force_n':float(force[0])})
                    if not any(allowed[side].intersection(names) and any(f'{side}_service_{finger}_pad' in names
                               for finger in ('positive','negative')) for side in ('l','r')) and force[0] > 2.:
                        self.fail('prohibited_collision',{'geoms':names,'normal_force_n':float(force[0])})
        self.state['grip_forces'] = grip

    def step(self):
        if self.state['status'] != 'running':
            return
        phase = self.state['phase']
        elapsed = float(self.data.time)-self.state['phase_started_s']
        duration = {'settle':1.,'approach':3.,'insert':3.,'grasp':1.,'latch':2.,'open':3.,
                    'release_left':1.,'withdraw_left':2.,'rotate_left':3.,'insert_left':3.,'grasp_left':1.,
                    'release_right':1.,'withdraw_right':2.,'park_right':4.,'open_wide':6.}[phase]
        route=self.state.get('approach_route') if phase=='approach' else None
        if route:
            duration=max(duration,stage_distance(route)/.20)
        fraction = min(1.,elapsed/duration)
        blend = fraction*fraction*(3.-2.*fraction)
        reference = np.asarray(self.state['phase_start_qpos'])+(np.asarray(self.state['reference'])-
                     np.asarray(self.state['phase_start_qpos']))*blend
        if route:
            reference=stage_commands(route,[fraction])[0]
        tracking = None
        if phase != 'settle' and (phase != 'approach' or fraction==1.):
            tracking = {}
            for side,goal in self.state['goals'].items():
                start = self.state['start_goals'][side]
                relative = Rotation.from_matrix(np.asarray(goal['rotation']) @ np.asarray(start['rotation']).T)
                tracking[side] = {'position':(np.asarray(start['position'])+
                    blend*(np.asarray(goal['position'])-start['position'])).tolist(),
                    'rotation':(Rotation.from_rotvec(relative.as_rotvec()*blend).as_matrix() @ start['rotation']).tolist()}
            if phase == 'open_wide':
                angle = self.state['start_door_angle_rad']+blend*(
                    self.state['opening_angle_rad']-self.state['start_door_angle_rad'])
                hinge = np.array([self.config.front_x_m,self.config.center_y_m+.28,1.1])
                wrist = self._tool_rotation('l',True)
                tracking['l'] = {'position':(hinge+Rotation.from_rotvec([0.,0.,-angle]).apply(
                    [-.085,-.085,.065])+wrist @ np.array([0.,0.,LATCH_TCP_STANDOFF_M])).tolist(),
                    'rotation':wrist.tolist()}
        try:
            released = ('r',) if phase in ('release_right','withdraw_right','park_right','open_wide') else (
                ('l',) if phase in ('release_left','withdraw_left','rotate_left','insert_left') else ())
            self.data.ctrl[:] = self.controller.compute(self.data,reference,tracking,released)
        except (ControllerInfeasible,ValueError) as error:
            self.fail('controller_infeasible',str(error))
            return
        mj.mj_step(self.model,self.data)
        self.state['steps_completed'] += 1
        if (not np.isfinite(self.data.qpos).all() or not np.isfinite(self.data.qvel).all()
                or any(self.data.warning[warning].number for warning in (
                    mj.mjtWarning.mjWARN_BADQPOS,mj.mjtWarning.mjWARN_BADQVEL,mj.mjtWarning.mjWARN_BADQACC))):
            self.fail('nonfinite_simulator_state')
            return
        # mj_step integrates qpos after computing body transforms and forces.
        # Refresh them so measurements and rendered poses describe this time.
        mj.mj_forward(self.model,self.data)
        gripper_forces = [abs(float(self.data.actuator_force[self.model.actuator(
            f'{side}_service_{finger}_drive').id])) for side in ('l','r') for finger in ('positive','negative')]
        self.state['peak_gripper_actuator_force_n'] = max(self.state['peak_gripper_actuator_force_n'],max(gripper_forces))
        if max(gripper_forces) > self.tooling.finger_force_n+1e-6:
            self.fail('actuator_force_limit_violation')
        if self.controller.wide_tooling:
            torque=abs(float(self.data.actuator_force[self.model.actuator('l_service_swivel_drive').id]))
            self.state['peak_swivel_torque_nm']=max(self.state['peak_swivel_torque_nm'],torque)
            if torque>3.+1e-6:
                self.fail('actuator_force_limit_violation',{'actuator':'l_service_swivel_drive','torque_nm':torque})
        self._contacts()
        observed = self.observe()
        self.state['peak_tilt_rad'] = max(self.state['peak_tilt_rad'],observed['root_tilt_rad'])
        if observed['root_tilt_rad'] > .20 or self.data.qpos[2] < .9*self.model.key_qpos[0,2]:
            self.fail('unstable_posture')
        if self.state['status'] != 'running':
            return
        holding_side=('l' if phase in ('release_right','withdraw_right','park_right','open_wide') else
            'r' if phase in ('release_left','withdraw_left','rotate_left','insert_left','grasp_left') else None)
        if holding_side and elapsed>.3:
            self.state['lost_grip_samples'] = (self.state['lost_grip_samples']+1
                if min(self.state['grip_forces'][holding_side].values())<2. else 0)
            if self.state['lost_grip_samples']>=100:
                self.fail('lost_door_grip',{'door_angle_rad':observed['door_angle_rad'],
                    'holding_hand':holding_side,
                    'grip_forces_n':observed['grip_forces_n']})
                return
        if phase == 'latch' and elapsed > duration+.25 and observed['latch_retraction_m'] < .025:
            self.fail('latch_resistance_or_retention_failure', {
                'requested_retraction_m':.05,
                'measured_retraction_m':observed['latch_retraction_m'],
                'grip_forces_n':observed['grip_forces_n'],
                'pose_errors':observed['pose_errors'],
                'elapsed_s':elapsed,
            })
            return
        aligned = bool(observed['pose_errors']) and all(p['position_m'] < .006 and p['angle_rad'] < .10
                    for p in observed['pose_errors'].values())
        gripped = all(min(loads.values()) > 2. for loads in self.state['grip_forces'].values())
        ready = ((phase=='settle' and elapsed>=1.) or
                 (phase in ('approach','insert') and fraction==1. and aligned) or
                 (phase=='grasp' and fraction==1. and gripped) or
                 (phase=='grasp_left' and fraction==1. and gripped) or
                 (phase=='latch' and observed['latch_retraction_m'] > .035 and gripped) or
                 (phase=='open' and fraction==1. and observed['door_angle_rad']>.20 and gripped
                    and observed['root_speed_m_s']<.03) or
                 (phase=='release_left' and elapsed>.3 and
                    min(float(self.data.joint(f'l_service_{finger}_slide').qpos[0])
                        for finger in ('positive','negative'))>.025 and
                    min(self.state['grip_forces']['r'].values())>2. and
                    max(self.state['grip_forces']['l'].values())<1.) or
                 (phase in ('withdraw_left','rotate_left','insert_left') and fraction==1. and
                    observed['pose_errors']['l']['position_m']<.006 and
                    observed['pose_errors']['l']['angle_rad']<.10 and
                    min(self.state['grip_forces']['r'].values())>2. and
                    max(self.state['grip_forces']['l'].values())<1.) or
                 (phase=='release_right' and elapsed>.3 and
                    min(float(self.data.joint(f'r_service_{finger}_slide').qpos[0])
                        for finger in ('positive','negative'))>.025 and
                    min(self.state['grip_forces']['l'].values())>2. and
                    max(self.state['grip_forces']['r'].values())<1.) or
                 (phase in ('withdraw_right','park_right') and fraction==1. and
                    observed['pose_errors']['r']['position_m']<.006 and
                    observed['pose_errors']['r']['angle_rad']<.10 and
                    min(self.state['grip_forces']['l'].values())>2. and
                    max(self.state['grip_forces']['r'].values())<1.) or
                 (phase=='open_wide' and fraction==1. and
                    abs(observed['door_angle_rad']-self.state['opening_angle_rad'])<.05 and
                    abs(observed['door_angular_velocity_rad_s'])<.05 and
                    min(self.state['grip_forces']['l'].values())>2. and observed['root_speed_m_s']<.03))
        self.state['stable_samples'] = self.state['stable_samples']+1 if ready else 0
        if self.state['stable_samples'] >= 75:
            if phase=='open_wide' or (phase=='open' and self.state['opening_angle_rad']==.25):
                self.state.update(status='completed',success=True)
            else:
                next_phase = {'settle':'approach','approach':'insert','insert':'grasp','grasp':'latch','latch':'open',
                    'open':'release_right','release_left':'withdraw_left','withdraw_left':'rotate_left',
                    'rotate_left':'insert_left','insert_left':'grasp_left','grasp_left':'release_right',
                    'release_right':'withdraw_right','withdraw_right':'park_right',
                    'park_right':'open_wide'}[phase]
                self._plan(next_phase)
        elif elapsed > {'settle':2.,'approach':max(13.,duration+6.),'insert':10.,'grasp':6.,'latch':6.,'open':9.,
                        'release_left':5.,'withdraw_left':6.,'rotate_left':8.,'insert_left':8.,'grasp_left':5.,
                        'release_right':5.,'withdraw_right':6.,'park_right':8.,'open_wide':12.}[phase]:
            self.fail({'settle':'unstable_posture','approach':'approach_timeout','insert':'insertion_approach_timeout',
                'grasp':'insufficient_grip_contact','latch':'latch_resistance_or_retention_failure','open':'door_opening_timeout',
                'release_right':'tool_release_timeout','withdraw_right':'tool_retraction_timeout',
                'release_left':'tool_release_timeout','withdraw_left':'tool_retraction_timeout',
                'rotate_left':'tool_reorientation_timeout','insert_left':'insertion_approach_timeout',
                'grasp_left':'insufficient_grip_contact',
                'park_right':'tool_retraction_timeout',
                'open_wide':'door_opening_timeout'}[phase])

    def snapshot(self):
        return capture(self.model,self.data,self.controller,world_version=self.world_version,
            task_state=self.state,rng=self.rng,perception_state={'mode':'simulator_state'},order_ledger={},
            next_frame_seq=self.state['next_frame_seq'],steps_completed=self.state['steps_completed'],model_artifact=self.artifact)

    def frame(self):
        frame = {'seq':self.state['next_frame_seq'],'frame':_frame(self.model,self.data),
                 'phase':self.state['phase'],'measurements':self.observe()}
        self.state['next_frame_seq'] += 1
        return frame

    @classmethod
    def from_checkpoint(cls, bundle):
        if (bundle.checkpoint.task_state['task_version'] != cls.version
                or bundle.checkpoint.task_state['source_hashes'] != SOURCE_HASHES):
            raise ValueError('door primitive version changed')
        self = cls.__new__(cls)
        self.model,self.data,self.controller,self.rng = restore(bundle,ApolloToolController)
        self.state = deepcopy(bundle.checkpoint.task_state)
        self.config = CabinetConfig.model_validate(self.state['config'])
        self.tooling = ParallelGripperConfig.model_validate(self.state['tooling'])
        self.world_version = bundle.checkpoint.world_version
        self.manifest = self.state['model_manifest']
        self.artifact = ImmutableModelArtifact(self.model,bundle.model_binary)
        return self
