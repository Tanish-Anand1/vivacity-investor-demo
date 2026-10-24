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
SOURCE_HASHES = {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ('apollo_door.py','cabinet_mechanism.py','humanoid_embodiments.py',
                             'simulated_tooling.py','humanoid_ik.py','stance_control.py','wrench_dynamics.py')}


class ApolloToolController:
    version = 'vivacity.apollo-cartesian-contact/3-experimental'

    def __init__(self, model):
        self.stance = StanceController(model, 'apollo')
        self.integrals = {side:np.zeros(3) for side in ('l','r')}
        self.rotation_integrals = {side:np.zeros(3) for side in ('l','r')}
        self.tracking_weights = np.full(model.nu,self.stance.reference_weight)
        arm_joints = {side+'_'+part for side in ('l','r') for part in ARM_PARTS}
        for index,joint in enumerate(model.actuator_trnid[:,0]):
            if model.joint(int(joint)).name in arm_joints:
                self.tracking_weights[index] = .5
        self.dt = float(model.opt.timestep)
        self.clearance_pairs = [(model.geom(f'{side}_service_{finger}_pad').id,
            model.geom(fixture).id,.003) for side in ('l','r') for finger in ('positive','negative')
            for fixture in ('service_door_panel','service_latch_crossbar')]
        self.clearance_pairs.extend((model.geom('r_service_'+part).id,model.geom(fixture).id,.005)
            for part in ('palm','positive_pad','negative_pad') for fixture in (
                'service_replacement_tray','service_replacement_tray_wall_-1','service_replacement_tray_wall_1'))
        self.clearance_pairs.append((model.geom('l_service_palm').id,
            model.geom('service_latch_crossbar').id,.005))

    def compute(self, data, reference, goals=None, released_hands=()):
        poses = {}
        for side, goal in (goals or {}).items():
            name = side+'_service_tcp'
            error = np.asarray(goal['position'])-data.site(name).xpos
            # Bounded task-space integral compensates static native friction and
            # model mismatch. It changes actuator references, never body poses.
            self.integrals[side] = np.clip(self.integrals[side]+self.dt*.8*error, -.06, .06)
            angular = Rotation.from_matrix(np.asarray(goal['rotation']) @
                data.site(name).xmat.reshape(3,3).T).as_rotvec()
            correction = self.rotation_integrals[side]+self.dt*.6*angular
            self.rotation_integrals[side] = correction*min(1.,.15/max(np.linalg.norm(correction),1e-12))
            poses[name] = {**goal, 'position':np.asarray(goal['position'])+self.integrals[side],
                'rotation':Rotation.from_rotvec(self.rotation_integrals[side]).as_matrix() @ goal['rotation'],
                'weight':10000.}
        finger_targets = {}
        for side in ('l','r'):
            for finger in ('positive','negative'):
                name=f'{side}_service_{finger}_slide'
                requested=float(reference[self.stance.model.joint(name).qposadr[0]])
                # Keep both finger servos centered under gravity. Their desired
                # acceleration is a soft task, while native force limits and
                # contact prevent closing through a grasped object.
                finger_targets[name]=requested
                if side in released_hands:
                    finger_targets[name]=.03
        released_geoms = [self.stance.model.geom(f'{side}_service_{finger}_pad').id
            for side in released_hands for finger in ('positive','negative')]
        nearby_pairs = [pair for pair in self.clearance_pairs if mj.mj_geomDistance(
            self.stance.model,data,pair[0],pair[1],.12,None)<.12]
        return self.stance.compute(data, reference, site_targets=poses,joint_targets=finger_targets,
            released_geoms=released_geoms,clearance_pairs=nearby_pairs,
            posture_weights=self.tracking_weights if poses else None)

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
        rotation_integrals = {}
        for side in ('l','r'):
            value=np.asarray(state['rotation_integrals'][side],dtype=float)
            if value.shape!=(3,) or not np.isfinite(value).all() or np.linalg.norm(value)>.15000001:
                raise ValueError('invalid angular integral checkpoint')
            rotation_integrals[side]=value.copy()
        self.integrals, self.stance = integrals, stance
        self.rotation_integrals=rotation_integrals


class CabinetDoorPrimitive:
    version = 'vivacity.apollo-door-primitive/2-experimental'

    def __init__(self, config=None, tooling=None, seed=7, opening_angle_rad=.25):
        if not np.isfinite(opening_angle_rad) or not .25 <= opening_angle_rad <= 1.2:
            raise ValueError('door opening target must be between 0.25 and 1.2 radians')
        self.config = config or CabinetConfig(front_x_m=.75)
        self.tooling = tooling or ParallelGripperConfig()
        def scene(root):
            if opening_angle_rad > .25:
                # A visible rigid mounting adapter rotates the left fingers,
                # leaving the native wrist away from its yaw limit. This is a
                # different plant, never an attachment to the cabinet.
                root.find(".//body[@name='l_service_tool']").set(
                    'quat','.7071067811865476 0 0 -.7071067811865476')
            append_cabinet(root,self.config)
        self.model,self.data,self.manifest = compile_embodiment('apollo',self.tooling,append_scene=scene)
        if opening_angle_rad > .25:
            self.manifest['identity'] = 'vivacity.apollo-cabinet-opposed-tools/1-experimental'
        self.artifact = ImmutableModelArtifact(self.model)
        self.controller = ApolloToolController(self.model)
        self.rng = np.random.default_rng(seed)
        self.world_version = str(uuid.uuid4())
        self.state = dict(status='running',phase='settle',phase_started_s=0.,steps_completed=0,
            next_frame_seq=0,seed=seed,config=self.config.model_dump(),tooling=self.tooling.model_dump(),
            opening_angle_rad=float(opening_angle_rad),
            task_version=self.version,source_hashes=SOURCE_HASHES.copy(),
            success=False,cabinet_service_complete=False,failure=None,
            phase_events=[],stable_samples=0,peak_tilt_rad=0.,peak_contact_force_n=0.,peak_gripper_actuator_force_n=0.,
            phase_start_qpos=self.data.qpos.tolist(),reference=self.model.key_qpos[0].tolist(),
            goals={},start_goals={},grip_forces={},model_manifest=self.manifest)

    def _tool_rotation(self, side):
        # A vertical pinch lets the latch button yaw between the pads while the
        # door swings. Horizontal pinch would demand an unreachable wrist yaw.
        # Native friction/contact still decides whether this grasp is retained.
        return TOOL_ROTATIONS['r'] if side=='l' and self.state['opening_angle_rad']>.25 else TOOL_ROTATIONS[side]

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
                goal['position'][0] = x-(.135 if side=='l' else .10)
        elif phase == 'latch':
            goals['l']['position'][1] = y+.195
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
                orientation = self._tool_rotation(side) if side=='r' or phase=='open_wide' else (
                    Rotation.from_rotvec([0.,0.,-wrist_angle]).as_matrix() @ TOOL_ROTATIONS[side])
                position = hinge+rotation @ relative
                if side=='l':
                    # Keep the grasp point on the button, and offset the wrist
                    # along its own approach axis. Rotating this offset with the
                    # door while the wrist yaw is bounded loses the grasp.
                    button = hinge+rotation @ np.array([-.085,-.085,.065])
                    position = button+orientation @ np.array([0.,0.,.05])
                goals[side] = {'position':position.tolist(),
                               'rotation':orientation.tolist()}
        elif phase == 'release_right':
            # Release before moving the wrist. Dragging a loaded upper pad
            # rotates the door into the finger while the other hand holds it.
            # A small outward clearance motion accommodates the passive door's
            # rotation while the pads unload; it does not carry the handle.
            goals['r']['position'][0] -= .02
        elif phase == 'withdraw_right':
            goals['r']['position'][0] -= .08
            goals['r']['position'][2] -= .07
        elif phase == 'park_right':
            goals['r'] = {'position':[x-.35,y-.20,1.25],
                'rotation':(Rotation.from_rotvec([0.,-.6,0.]).as_matrix() @ TOOL_ROTATIONS['r']).tolist()}
        reference = self.model.key_qpos[0].copy()
        start_reference = reference.copy()
        planning_state = self.data.qpos.copy()
        for side,goal in goals.items():
            joints = [side+'_'+part for part in ARM_PARTS]
            plan = site_pose(self.model,planning_state,side+'_service_tcp',
                joints,goal['position'],goal['rotation'],
                joint_margin=.08 if self.state['opening_angle_rad']>.25 else None)
            if not plan.feasible:
                self.fail('unreachable_target',{'phase':phase,'hand':side,
                    'position_error_m':plan.position_error_m,'angular_error_rad':plan.angular_error_rad})
                return
            planning_state = plan.qpos
            for name in joints:
                address = self.model.joint(name).qposadr[0]
                reference[address] = plan.qpos[address]
                start_reference[address] = self.data.qpos[address]
            for finger in ('positive','negative'):
                address = self.model.joint(f'{side}_service_{finger}_slide').qposadr[0]
                start_reference[address] = self.data.qpos[address]
                closing = phase in ('grasp','latch','open') or (
                    side=='l' and phase in ('release_right','withdraw_right','park_right','open_wide'))
                opening = .03 if side=='r' and phase in ('release_right','withdraw_right','park_right','open_wide') else .035
                reference[address] = 0. if closing else opening
        previous = self.state['phase']
        self.state.update(phase=phase,phase_started_s=float(self.data.time),stable_samples=0,
            lost_grip_samples=0,
            start_door_angle_rad=float(self.data.joint('service_door_hinge').qpos[0]),
            phase_start_qpos=start_reference.tolist(),reference=reference.tolist(),goals=goals,
            start_goals={side:{'position':self.data.site(side+'_service_tcp').xpos.tolist(),
                'rotation':self.data.site(side+'_service_tcp').xmat.reshape(3,3).tolist()} for side in goals})
        self.state['phase_events'].append({'from':previous,'to':phase,'time_s':float(self.data.time),
            'measurements':self.observe()})

    def fail(self, reason, detail=None):
        # Keep the first observed failure. A later check in the same native step
        # must not overwrite the causal event (for example collision then tilt).
        if self.state['status'] == 'running':
            self.state.update(status='failed',failure=reason,failure_detail=detail)

    def observe(self):
        result = measure(self.model,self.data,self.config)
        result['root_tilt_rad'] = float(2*np.arccos(np.clip(abs(self.data.qpos[3]),0,1)))
        result['root_speed_m_s'] = float(np.linalg.norm(self.data.qvel[:3]))
        result['grip_forces_n'] = deepcopy(self.state['grip_forces'])
        result['pose_errors'] = {side:{
            'position_m':float(np.linalg.norm(self.data.site(side+'_service_tcp').xpos-goal['position'])),
            'angle_rad':float(np.linalg.norm(Rotation.from_matrix(np.asarray(goal['rotation']) @
                self.data.site(side+'_service_tcp').xmat.reshape(3,3).T).as_rotvec()))}
            for side,goal in self.state['goals'].items()}
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
                    'release_right':1.,'withdraw_right':2.,'park_right':4.,'open_wide':6.}[phase]
        fraction = min(1.,elapsed/duration)
        blend = fraction*fraction*(3.-2.*fraction)
        reference = np.asarray(self.state['phase_start_qpos'])+(np.asarray(self.state['reference'])-
                     np.asarray(self.state['phase_start_qpos']))*blend
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
                wrist = self._tool_rotation('l')
                tracking['l'] = {'position':(hinge+Rotation.from_rotvec([0.,0.,-angle]).apply(
                    [-.085,-.085,.065])+wrist @ np.array([0.,0.,.05])).tolist(),
                    'rotation':wrist.tolist()}
        try:
            released = ('r',) if phase in ('release_right','withdraw_right','park_right','open_wide') else ()
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
        self._contacts()
        observed = self.observe()
        self.state['peak_tilt_rad'] = max(self.state['peak_tilt_rad'],observed['root_tilt_rad'])
        if observed['root_tilt_rad'] > .20 or self.data.qpos[2] < .9*self.model.key_qpos[0,2]:
            self.fail('unstable_posture')
        if self.state['status'] != 'running':
            return
        if phase in ('release_right','withdraw_right','park_right','open_wide') and elapsed>.3:
            self.state['lost_grip_samples'] = (self.state['lost_grip_samples']+1
                if min(self.state['grip_forces']['l'].values())<2. else 0)
            if self.state['lost_grip_samples']>=100:
                self.fail('lost_door_grip',{'door_angle_rad':observed['door_angle_rad'],
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
                 (phase=='latch' and observed['latch_retraction_m'] > .035 and gripped) or
                 (phase=='open' and fraction==1. and observed['door_angle_rad']>.20 and gripped
                    and observed['root_speed_m_s']<.03) or
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
                    'open':'release_right','release_right':'withdraw_right','withdraw_right':'park_right',
                    'park_right':'open_wide'}[phase]
                if phase=='latch' and self.state['opening_angle_rad']>.25:
                    next_phase = 'release_right'
                self._plan(next_phase)
        elif elapsed > {'settle':2.,'approach':13.,'insert':10.,'grasp':6.,'latch':6.,'open':9.,
                        'release_right':5.,'withdraw_right':6.,'park_right':8.,'open_wide':12.}[phase]:
            self.fail({'settle':'unstable_posture','approach':'approach_timeout','insert':'insertion_approach_timeout',
                'grasp':'insufficient_grip_contact','latch':'latch_resistance_or_retention_failure','open':'door_opening_timeout',
                'release_right':'tool_release_timeout','withdraw_right':'tool_retraction_timeout',
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
