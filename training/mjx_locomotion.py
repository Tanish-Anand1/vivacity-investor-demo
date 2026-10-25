"""Batched research environment for the complete, unchanged native robots.

This module belongs to the isolated GPU environment, never the API image. It
uses the CPU reference's sensor/action contract and recomputes torque commands
on every physics step. Rewards are learning objectives, not task acceptance.
"""
from flax import struct
import jax
import jax.numpy as jp
from mujoco import mjx
import numpy as np

from training.locomotion_contract import build_contract, commands, observation
from vivacity.humanoid_embodiments import compile_embodiment, ROOTS


@struct.dataclass
class State:
    data: object
    obs: jax.Array
    command: jax.Array
    previous_action: jax.Array
    steps: jax.Array
    reward: jax.Array
    terminated: jax.Array
    truncated: jax.Array
    failure: jax.Array
    metrics: dict


class CompleteLocomotion:
    """One immutable model; vmap creates independent integration states."""

    version = 'vivacity.mjx-complete-locomotion/1-experimental'
    failures = {0:'none', 1:'nonfinite_simulator_state', 2:'fallen',
                3:'joint_limit_violation', 4:'actuator_force_limit_violation'}

    def __init__(self, robot, *, implementation=None, control_steps=10, duration_s=8.):
        if type(control_steps) is not int or not 1 <= control_steps <= 20:
            raise ValueError('control_steps must be an integer in 1..20')
        if not np.isfinite(duration_s) or not .1 <= duration_s <= 20.:
            raise ValueError('duration must be 0.1..20 seconds')
        if not any(device.platform == 'gpu' for device in jax.devices()):
            raise RuntimeError('This batched probe requires an available GPU')
        jax.config.update('jax_enable_x64', False)
        self.robot = robot
        self.model, self.native, self.embodiment = compile_embodiment(robot)
        self.contract = build_contract(self.model, self.embodiment)
        self.implementation = implementation or ('jax' if robot == 'apollo' else 'warp')
        self.control_steps = control_steps
        self.duration_s = duration_s
        self.root = self.model.body(ROOTS[robot]).id
        self.tree_root = int(self.model.body_rootid[self.root])
        self.initial_height = float(self.native.xpos[self.root, 2])
        self.capacities = {'naconmax':2048, 'njmax':8192} if self.implementation == 'warp' else {}
        # Do not use the older Playground wrapper, which suppresses overflow
        # warnings. Preserve contact margins, solver settings and model hashes.
        self.device_model = mjx.put_model(self.model, impl=self.implementation)
        self.initial_data = mjx.put_data(self.model, self.native,
            impl=self.implementation, **self.capacities)

    def body_velocity(self, data):
        rotation = data.xmat[self.root].reshape(3, 3)
        velocity = data.cvel[self.root]
        # cvel is world-oriented and referred to the kinematic tree's COM.
        linear = velocity[3:] + jp.cross(velocity[:3],
            data.xpos[self.root] - data.subtree_com[self.tree_root])
        return rotation.T @ velocity[:3], rotation.T @ linear

    def observe(self, data, command, previous_action):
        angular, _ = self.body_velocity(data)
        return observation(self.contract, data.qpos[self.contract.qadr],
            data.qvel[self.contract.dofs], data.xmat[self.root], angular,
            command, previous_action, xp=jp)

    def reset(self, key, command=None):
        if command is None:
            command = jax.random.uniform(key, (3,), minval=jp.array([.05,-.1,-.2]),
                                        maxval=jp.array([.5,.1,.2]))
        command = jp.asarray(command, dtype=jp.float32)
        previous = jp.zeros(self.model.nu)
        data = self.initial_data
        metrics = {'tilt_rad':jp.array(0.), 'root_height_m':jp.asarray(self.initial_height),
                   'joint_limit_violation':jp.array(0.), 'actuator_force_fraction':jp.array(0.),
                   'local_linear_velocity_m_s':jp.zeros(3), 'physics_steps':jp.array(0)}
        return State(data, self.observe(data, command, previous), command, previous,
            jp.array(0), jp.array(0.), jp.array(False), jp.array(False), jp.array(0), metrics)

    def step(self, state, action):
        action = jp.clip(action, -1., 1.)

        def integrate(data, _):
            ctrl = commands(self.contract, action, data.qpos[self.contract.qadr],
                            data.qvel[self.contract.dofs], xp=jp)
            return mjx.step(self.device_model, data.replace(ctrl=ctrl)), None

        data, _ = jax.lax.scan(integrate, state.data, None, self.control_steps)
        data = mjx.forward(self.device_model, data)
        angular, linear = self.body_velocity(data)
        tilt = jp.arccos(jp.clip(data.xmat[self.root, 2, 2], -1., 1.))
        joints = data.qpos[self.contract.qadr]
        violation = jp.maximum(0., jp.maximum(jp.max(jp.asarray(self.contract.joint_low)-joints),
                                             jp.max(joints-jp.asarray(self.contract.joint_high))))
        fractions = data.qfrc_actuator[self.contract.dofs]/jp.asarray(self.contract.force_limit)
        force_fraction = jp.max(jp.abs(fractions))
        finite = jp.all(jp.isfinite(data.qpos)) & jp.all(jp.isfinite(data.qvel)) & jp.all(jp.isfinite(action))
        fallen = (tilt > .7) | (data.xpos[self.root, 2] < .65*self.initial_height)
        failure = jp.where(~finite, 1, jp.where(fallen, 2,
            jp.where(violation > .02, 3, jp.where(force_fraction > 1.00001, 4, 0))))
        terminated = failure != 0
        truncated = data.time >= self.duration_s
        terms = (jp.exp(-jp.sum((linear[:2]-state.command[:2])**2)/.25)
            + .5*jp.exp(-(angular[2]-state.command[2])**2/.25)
            - 2.*tilt**2 - 2.*linear[2]**2 - .01*jp.mean(fractions**2)
            - .02*jp.mean((action-state.previous_action)**2)
            - jp.where(terminated, 5., 0.))
        reward = terms*self.control_steps*self.model.opt.timestep
        steps = state.steps + self.control_steps
        metrics = {'tilt_rad':tilt, 'root_height_m':data.xpos[self.root, 2],
                   'joint_limit_violation':violation, 'actuator_force_fraction':force_fraction,
                   'local_linear_velocity_m_s':linear, 'physics_steps':steps}
        updated = State(data, self.observe(data,state.command,action), state.command, action,
                        steps, reward, terminated, truncated, failure, metrics)
        # Explicitly absorbing terminal state: no integration after a failed or
        # timed-out episode. The trainer must reset it and retain the terminal flag.
        return jax.tree.map(lambda old,new:jp.where(state.terminated|state.truncated,old,new), state,updated)

    def batched(self):
        return jax.jit(jax.vmap(self.reset)), jax.jit(jax.vmap(self.step))
