"""Native CPU reference environment for future complete-embodiment training.

Actions only reach data.ctrl. This is an unloaded flat-floor research contract,
not a walking policy, terrain/carry environment, running benchmark or API task.
The reward is an optimization objective, never a success certificate.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import mujoco as mj
import numpy as np

from vivacity.execution_checkpoint import capture, restore, ImmutableModelArtifact
from vivacity.humanoid_embodiments import compile_embodiment, ROOTS, FEET
from training.locomotion_contract import build_contract, commands, observation


SOURCE_HASHES={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
               for name in ('native_locomotion.py','locomotion_contract.py')}


@dataclass(frozen=True)
class Settings:
    command: tuple[float,float,float] = (.3, 0., 0.)
    duration_s: float = 8.
    control_steps: int = 10
    seed: int = 7

    def __post_init__(self):
        value=np.asarray(self.command,dtype=float)
        if value.shape!=(3,) or not np.isfinite(value).all() or np.any(np.abs(value)>[.6,.3,.6]):
            raise ValueError('command outside unloaded slow-walk research bounds')
        if not np.isfinite(self.duration_s) or not .1<=self.duration_s<=20.:
            raise ValueError('duration must be 0.1..20 seconds')
        if type(self.control_steps) is not int or not 1<=self.control_steps<=20:
            raise ValueError('control_steps must be an integer in 1..20')
        if type(self.seed) is not int or not 0<=self.seed<2**31:
            raise ValueError('seed must be a nonnegative 31-bit integer')


class ActionAdapter:
    version='vivacity.complete-locomotion-actions/1-experimental'

    def __init__(self,model):
        self.model=model
        self.last_action=np.zeros(model.nu)
        self.steps=0

    def snapshot(self):
        return {'last_action':self.last_action.tolist(),'steps':self.steps}

    def restore(self,state):
        value=np.asarray(state['last_action'],dtype=float)
        if value.shape!=(self.model.nu,) or not np.isfinite(value).all() or np.any(np.abs(value)>1.):
            raise ValueError('invalid action checkpoint')
        if type(state['steps']) is not int or state['steps']<0:
            raise ValueError('invalid completed-step checkpoint')
        self.last_action=value.copy()
        self.steps=state['steps']


class NativeLocomotion:
    version='vivacity.native-locomotion-research/1'

    def __init__(self,identity,settings=None):
        self.settings=settings or Settings()
        self.identity=identity
        self.model,self.data,self.embodiment=compile_embodiment(identity)
        self.artifact=ImmutableModelArtifact(self.model)
        if self.artifact.sha256!=self.embodiment['compiled_model_sha256']:
            raise ValueError('embodiment manifest does not match compiled model')
        self.contract=build_contract(self.model,self.embodiment)
        self.controller=ActionAdapter(self.model)
        self.rng=np.random.default_rng(self.settings.seed)
        self.world_version=hashlib.sha256((self.artifact.sha256+self.contract.sha256+
            json.dumps(self.settings.__dict__,sort_keys=True)).encode()).hexdigest()
        self.state={'version':self.version,'identity':identity,'embodiment':self.embodiment,
            'source_sha256':dict(SOURCE_HASHES),
            'settings':dict(self.settings.__dict__),'contract_sha256':self.contract.sha256,
            'status':'running','failure':None,'steps_completed':0,'next_frame_seq':0,
            'initial_root_position_m':self.data.body(ROOTS[identity]).xpos.tolist()}

    def observe(self):
        velocity=np.zeros(6)
        mj.mj_objectVelocity(self.model,self.data,mj.mjtObj.mjOBJ_BODY,
                            self.model.body(ROOTS[self.identity]).id,velocity,1)
        return observation(self.contract,self.data.qpos[self.contract.qadr],
            self.data.qvel[self.contract.dofs],self.data.body(ROOTS[self.identity]).xmat.reshape(3,3),
            velocity[:3],self.settings.command,self.controller.last_action)

    def measurements(self):
        model,data=self.model,self.data
        root=model.body(ROOTS[self.identity]).id
        velocity=np.zeros(6)
        mj.mj_objectVelocity(model,data,mj.mjtObj.mjOBJ_BODY,root,velocity,1)
        gravity=data.xmat[root].reshape(3,3).T @ np.array([0.,0.,-1.])
        tilt=float(np.arccos(np.clip(-gravity[2],-1.,1.)))
        joint_violation=float(max(0.,np.max(self.contract.joint_low-data.qpos[self.contract.qadr]),
                                  np.max(data.qpos[self.contract.qadr]-self.contract.joint_high)))
        floor=model.geom('floor').id
        feet={model.body(name).id:name for name in FEET[self.identity]}
        loads={name:0. for name in feet.values()}
        maximum_slip=0.
        for index,contact in enumerate(data.contact[:data.ncon]):
            if floor not in (contact.geom1,contact.geom2) or contact.dist>0:
                continue
            body=int(model.geom_bodyid[contact.geom2 if contact.geom1==floor else contact.geom1])
            if body not in feet:
                continue
            force=np.zeros(6)
            mj.mj_contactForce(model,data,index,force)
            loads[feet[body]]+=max(0.,float(force[0]))
            if force[0]>1.:
                jac=np.zeros((3,model.nv))
                mj.mj_jac(model,data,jac,None,contact.pos,body)
                maximum_slip=max(maximum_slip,float(np.linalg.norm((jac @ data.qvel)[:2])))
        return {'time_s':float(data.time),'local_linear_velocity_m_s':velocity[3:].tolist(),
            'local_angular_velocity_rad_s':velocity[:3].tolist(),'tilt_rad':tilt,
            'root_position_m':data.xpos[root].tolist(),'foot_normal_load_n':loads,
            'maximum_loaded_foot_slip_m_s':maximum_slip,'joint_limit_violation':joint_violation,
            'actuator_force_fraction':float(np.max(np.abs(data.qfrc_actuator[self.contract.dofs])/self.contract.force_limit)),
            'equality_constraints':model.neq,'mocap_bodies':model.nmocap}

    def step(self,action):
        if self.state['status']!='running':
            raise RuntimeError('terminal trial requires a new world or restored checkpoint')
        action=np.asarray(action,dtype=float)
        if action.shape!=(self.model.nu,) or not np.isfinite(action).all() or np.any(np.abs(action)>1.):
            raise ValueError('action must be a finite model-sized vector within [-1,1]')
        previous=self.controller.last_action.copy()
        for _ in range(self.settings.control_steps):
            self.data.ctrl[:]=commands(self.contract,action,self.data.qpos[self.contract.qadr],
                                      self.data.qvel[self.contract.dofs])
            mj.mj_step(self.model,self.data)
            self.state['steps_completed']+=1
            self.controller.steps+=1
            if (not np.isfinite(self.data.qpos).all() or not np.isfinite(self.data.qvel).all()
                    or any(self.data.warning[k].number for k in
                       (mj.mjtWarning.mjWARN_BADQPOS,mj.mjtWarning.mjWARN_BADQVEL,mj.mjtWarning.mjWARN_BADQACC))):
                self.state.update(status='failed',failure='nonfinite_simulator_state')
                break
        mj.mj_forward(self.model,self.data)
        self.controller.last_action=action.copy()
        measured=self.measurements()
        if self.state['failure'] is None:
            if (measured['tilt_rad']>.7 or measured['root_position_m'][2]<
                    .65*self.state['initial_root_position_m'][2]):
                self.state.update(status='failed',failure='fallen')
            elif measured['joint_limit_violation']>.02:
                self.state.update(status='failed',failure='joint_limit_violation')
            elif measured['actuator_force_fraction']>1.00001:
                self.state.update(status='failed',failure='actuator_force_limit_violation')
            elif self.data.time>=self.settings.duration_s:
                self.state['status']='time_limit'
        linear=np.asarray(measured['local_linear_velocity_m_s'])
        angular=np.asarray(measured['local_angular_velocity_rad_s'])
        requested=np.asarray(self.settings.command)
        terms={'velocity_tracking':float(np.exp(-np.sum((linear[:2]-requested[:2])**2)/.25)),
            'yaw_tracking':float(.5*np.exp(-(angular[2]-requested[2])**2/.25)),
            'tilt_penalty':-2.*measured['tilt_rad']**2,
            'vertical_speed_penalty':-2.*float(linear[2]**2),
            'effort_penalty':-.01*float(np.mean((self.data.qfrc_actuator[self.contract.dofs]/self.contract.force_limit)**2)),
            'action_rate_penalty':-.02*float(np.mean((action-previous)**2)),
            'failure_penalty':-5. if self.state['failure'] else 0.}
        reward=float(sum(terms.values())*self.settings.control_steps*self.model.opt.timestep)
        return {'observation':self.observe(),'reward':reward,'reward_terms':terms,
            'terminated':self.state['status']=='failed','truncated':self.state['status']=='time_limit',
            'failure':self.state['failure'],'measurements':measured,
            'task_success':False,'scope':'training objective only; no accepted mobility policy'}

    def snapshot(self):
        return capture(self.model,self.data,self.controller,world_version=self.world_version,
            task_state=self.state,rng=self.rng,perception_state={'mode':'proprioception_only'},order_ledger={},
            next_frame_seq=self.state['next_frame_seq'],steps_completed=self.state['steps_completed'],
            model_artifact=self.artifact)

    @classmethod
    def from_checkpoint(cls,bundle):
        state=deepcopy(bundle.checkpoint.task_state)
        if state['version']!=cls.version or state['source_sha256']!=SOURCE_HASHES:
            raise ValueError('locomotion research version changed')
        self=cls.__new__(cls)
        self.model,self.data,self.controller,self.rng=restore(bundle,ActionAdapter)
        self.state=state
        self.settings=Settings(**state['settings'])
        self.identity=state['identity']
        self.embodiment=state['embodiment']
        if self.embodiment['compiled_model_sha256']!=bundle.checkpoint.model_sha256:
            raise ValueError('embodiment manifest does not match checkpoint model')
        self.contract=build_contract(self.model,self.embodiment)
        if self.contract.sha256!=state['contract_sha256']:
            raise ValueError('locomotion policy contract changed')
        self.artifact=ImmutableModelArtifact(self.model,bundle.model_binary)
        self.world_version=bundle.checkpoint.world_version
        return self
