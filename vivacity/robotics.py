"""Panda reaching; geometry planning is always verified by dynamic execution."""
from dataclasses import dataclass, field
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import time
import xml.etree.ElementTree as ET
import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation
from .compiled import remember, fork_geometry, reuse_world

ASSET_DIR = Path(__file__).resolve().parents[1] / 'assets/menagerie/franka_emika_panda'
STATE_SPEC = mj.mjtState.mjSTATE_INTEGRATION
DOWN = np.diag([1., -1., -1.])


@lru_cache(maxsize=1)
def asset_digest():
    digest = hashlib.sha256()
    for path in sorted((ASSET_DIR / 'assets').iterdir()):
        digest.update(path.name.encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


@dataclass
class RobotWorld:
    model: mj.MjModel
    data: mj.MjData
    config: dict
    seed: int
    model_hash: str
    action: dict = field(default_factory=dict)


class RoboticsBackend:
    arm_dof = 7
    version = mj.__version__
    action_schema = {'type': 'joint_trajectory', 'joints': 7, 'units': 'radians', 'planner': 'DLS pose IK + seeded joint-space RRT', 'milestone': 'reach_only'}

    @reuse_world('mujoco')
    def create_world(self, config, seed):
        root = ET.parse(ASSET_DIR / 'panda.xml').getroot()
        root.find('compiler').set('meshdir', str(ASSET_DIR / 'assets'))
        root.find('option').set('timestep', '0.002')
        hand = root.find(".//body[@name='hand']")
        ET.SubElement(hand, 'site', name='pregrasp', pos='0 0 0.103', size='0.008', rgba='1 0.4 0 1')
        wb = root.find('worldbody')
        ET.SubElement(wb, 'geom', name='ground', type='plane', pos='0 0 -0.8', size='2 2 0.1', rgba='0.15 0.15 0.15 1')
        ET.SubElement(wb, 'geom', name='table', type='box', pos='0.4 0 -0.04', size='0.7 0.65 0.04', rgba='0.6 0.55 0.45 1')
        target = config['target_position']
        ET.SubElement(wb, 'body', name='target', pos=f'{target[0]} {target[1]} 0.026')
        ET.SubElement(wb[-1], 'geom', name='cube', type='box', size='0.025 0.025 0.025', rgba='0.05 0.35 0.9 1')
        ET.SubElement(wb, 'body', name='obstacle', pos=' '.join(map(str, config['obstacle_position'])))
        ET.SubElement(wb[-1], 'geom', name='obstacle_geom', type='box', size=' '.join(map(str, config['obstacle_size'])), rgba='0.8 0.3 0.2 1')
        from .scene import append_scene
        append_scene(wb, config, root)
        from .physical_properties import configure_xml
        configure_xml(root, config)
        xml = ET.tostring(root, encoding='unicode')
        from .headless import collision_only
        collision_only(root)
        model = mj.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))
        data = mj.MjData(model)
        mj.mj_resetDataKeyframe(model, data, 0)
        mj.mj_forward(model, data)
        # Hash scene code's generated geometry plus mesh content, independent of installation path.
        root.find('compiler').set('meshdir', 'assets')
        digest = hashlib.sha256((ET.tostring(root, encoding='unicode') + asset_digest() + self.version).encode()).hexdigest()
        return remember(RobotWorld(model, data, deepcopy(config), seed, digest), 'mujoco')

    def snapshot(self, world):
        state = np.zeros(mj.mj_stateSize(world.model, STATE_SPEC))
        mj.mj_getState(world.model, world.data, state, STATE_SPEC)
        return {'backend': 'mujoco', 'version': self.version, 'model_hash': world.model_hash, 'config': deepcopy(world.config), 'seed': world.seed, 'state_spec': int(STATE_SPEC), 'integration_state': state.tolist()}

    def fork(self, state):
        world = fork_geometry(state)
        if world is None:
            world = self.create_world(state['config'], state['seed'])
        self.restore(world, state)
        return world

    def restore(self, world, state):
        if state['model_hash'] != world.model_hash or state['version'] != self.version or state['state_spec'] != int(STATE_SPEC):
            raise ValueError('snapshot model/version mismatch')
        vector = np.asarray(state['integration_state'])
        mj.mj_setState(world.model, world.data, vector, STATE_SPEC)
        mj.mj_forward(world.model, world.data)
        # Forward updates warmstart; restore integration inputs for exact continuation.
        mj.mj_setState(world.model, world.data, vector, STATE_SPEC)

    def observe(self, world):
        d, m = world.data, world.model
        mj.mj_kinematics(m, d)
        return {'time': float(d.time), 'qpos': d.qpos.tolist(), 'qvel': d.qvel.tolist(), 'ctrl': d.ctrl.tolist(), 'end_effector': d.site('pregrasp').xpos.tolist(), 'body_transforms': [{'name': mj.mj_id2name(m, mj.mjtObj.mjOBJ_BODY, i), 'position': d.xpos[i].tolist(), 'quaternion_wxyz': d.xquat[i].tolist()} for i in range(1, m.nbody)], 'target_pose': {'position': world.config['target_position'], 'rotation_matrix': DOWN.tolist()}, 'contacts': self.contacts(world)}

    def contacts(self, world):
        d, m = world.data, world.model
        violations = []
        for c in d.contact[:d.ncon]:
            if c.dist > 0:
                continue
            names = [mj.mj_id2name(m, mj.mjtObj.mjOBJ_BODY, int(m.geom_bodyid[g])) or 'world' for g in (c.geom1, c.geom2)]
            geoms = [mj.mj_id2name(m, mj.mjtObj.mjOBJ_GEOM, int(g)) or f'geom_{g}' for g in (c.geom1, c.geom2)]
            # Fixed base resting on table is the mounting fixture, not a motion collision.
            if 'link0' in names and 'table' in geoms:
                continue
            robot = any(n.startswith('link') or n in ('hand', 'left_finger', 'right_finger') for n in names)
            if robot:
                category = 'self_collision' if all(n.startswith('link') or n in ('hand', 'left_finger', 'right_finger') for n in names) else 'environment_collision'
                violations.append({'bodies': names, 'geoms': geoms, 'penetration_m': float(-c.dist), 'category': category})
        return violations

    def ik(self, world, start=None):
        m = world.model
        d = mj.MjData(m)
        d.qpos[:] = world.data.qpos
        if start is not None:
            d.qpos[:self.arm_dof] = start
        sid = mj.mj_name2id(m, mj.mjtObj.mjOBJ_SITE, 'pregrasp')
        jp, jr = np.zeros((3, m.nv)), np.zeros((3, m.nv))
        goal = np.asarray(world.config['target_position'])
        for _ in range(350):
            mj.mj_forward(m, d)
            dp = goal - d.site_xpos[sid]
            dr = Rotation.from_matrix(DOWN @ d.site_xmat[sid].reshape(3, 3).T).as_rotvec()
            error = np.r_[dp, dr * 0.35]
            if np.linalg.norm(dp) < 0.001 and np.linalg.norm(dr) < 0.01:
                return d.qpos[:self.arm_dof].copy(), {'position_error_m': float(np.linalg.norm(dp)), 'orientation_error_rad': float(np.linalg.norm(dr)), 'converged': True}
            mj.mj_jacSite(m, d, jp, jr, sid)
            jac = np.vstack([jp[:, :self.arm_dof], jr[:, :self.arm_dof] * 0.35])
            step = jac.T @ np.linalg.solve(jac @ jac.T + 0.003**2 * np.eye(6), error)
            step *= min(1., 0.15 / max(np.linalg.norm(step), 1e-9))
            d.qpos[:self.arm_dof] = np.clip(d.qpos[:self.arm_dof] + step, m.jnt_range[:self.arm_dof, 0] + 0.005, m.jnt_range[:self.arm_dof, 1] - 0.005)
        return d.qpos[:self.arm_dof].copy(), {'position_error_m': float(np.linalg.norm(dp)), 'orientation_error_rad': float(np.linalg.norm(dr)), 'converged': False}

    def candidates(self, world, count, iterations):
        tic = time.perf_counter()
        start = world.data.qpos[:self.arm_dof].copy()
        goal, ik = self.ik(world)
        scratch = RobotWorld(world.model, mj.MjData(world.model), world.config, world.seed, world.model_hash)
        scratch.data.qpos[:] = world.data.qpos

        def valid(q):
            scratch.data.qpos[:self.arm_dof] = q
            mj.mj_forward(scratch.model, scratch.data)
            return not self.contacts(scratch)

        def edge(a, b):
            return all(valid(a + (b-a)*t) for t in np.linspace(0, 1, max(2, int(np.linalg.norm(b-a)/0.035)+1)))

        direct = {'kind': 'joint_trajectory', 'planner': 'direct', 'waypoints': [start.tolist(), goal.tolist()], 'planning_feasible': ik['converged'] and edge(start, goal), 'ik': ik}
        actions = [direct]
        for k in range(count-1):
            rng = np.random.default_rng(world.seed + k + 1)
            nodes, parents = [start], [-1]
            found = None
            if ik['converged'] and valid(start) and valid(goal):
                for _ in range(iterations):
                    sample = goal if rng.random() < 0.2 else rng.uniform(world.model.jnt_range[:self.arm_dof, 0]+0.03, world.model.jnt_range[:self.arm_dof, 1]-0.03)
                    idx = int(np.argmin([np.linalg.norm(n-sample) for n in nodes]))
                    diff = sample-nodes[idx]
                    q = nodes[idx] + diff*min(1., 0.3/max(np.linalg.norm(diff), 1e-9))
                    if not edge(nodes[idx], q):
                        continue
                    nodes.append(q); parents.append(idx)
                    if np.linalg.norm(q-goal) < 0.65 and edge(q, goal):
                        path = [goal, q]
                        parent = idx
                        while parent >= 0:
                            path.append(nodes[parent]); parent = parents[parent]
                        found = list(reversed(path))
                        # Greedy deterministic shortcutting, preserving checked edges.
                        smooth = [found[0]]; i = 0
                        while i < len(found)-1:
                            j = len(found)-1
                            while j > i+1 and not edge(found[i], found[j]):
                                j -= 1
                            smooth.append(found[j]); i = j
                        found = smooth
                        break
            actions.append({'kind': 'joint_trajectory', 'planner': f'rrt_seed_{world.seed+k+1}', 'waypoints': [q.tolist() for q in found] if found else [], 'planning_feasible': found is not None, 'ik': ik})
        return actions, time.perf_counter()-tic

    def apply_action(self, world, action):
        waypoints = np.asarray(action['waypoints'])
        if len(waypoints) and (waypoints.ndim != 2 or waypoints.shape[1] != self.arm_dof or not np.isfinite(waypoints).all()):
            raise ValueError('trajectory joint count must match the selected model')
        if action.get('kind')!='joint_trajectory':
            raise ValueError('unsupported robot action')
        if len(waypoints)>2048:
            raise ValueError('trajectory exceeds waypoint limit')
        if len(waypoints) and not np.allclose(waypoints[0],world.data.qpos[:self.arm_dof],rtol=0,atol=1e-6):
            raise ValueError('trajectory must start from its independently restored parent')
        world.action = deepcopy(action)

    def simulate(self, world, limits):
        tic = time.perf_counter(); d, m = world.data, world.model
        path = world.action['waypoints']; trace = [self.observe(world)]
        failure = None; violations = []; steps = 0; start_time = float(d.time)
        if not path or not world.action['ik']['converged']:
            failure = 'planning_failure'
        else:
            initial_contacts = self.contacts(world)
            if initial_contacts:
                failure = 'collision_failure'; violations = initial_contacts
            for a, b in zip(path[:-1], path[1:]):
                if failure:
                    break
                a, b = np.asarray(a), np.asarray(b)
                duration = max(0.4, float(np.max(np.abs(b-a)))/0.35)
                for i in range(int(duration/m.opt.timestep)):
                    alpha = min(1., (i+1)*m.opt.timestep/duration)
                    # Smooth interpolation reduces actuator tracking transients.
                    blend = alpha*alpha*(3-2*alpha)
                    d.ctrl[:self.arm_dof] = a + (b-a)*blend
                    failure, contacts = self.step(world, start_time, limits)
                    steps += 1
                    if steps % 25 == 0 or failure:
                        trace.append(self.observe(world))
                    if failure:
                        violations.extend(contacts); break
            if not failure:
                d.ctrl[:self.arm_dof] = path[-1]
                for _ in range(500):
                    failure, contacts = self.step(world, start_time, limits); steps += 1
                    if steps % 25 == 0 or failure:
                        trace.append(self.observe(world))
                    if failure:
                        violations.extend(contacts); break
        trace.append(self.observe(world))
        return {'trace': trace, 'failure': failure, 'contact_violations': violations, 'simulation_steps': steps, 'execution_duration_s': float(d.time-start_time), 'physics_wall_seconds': time.perf_counter()-tic}

    def step(self, world, start_time, limits):
        d, m = world.data, world.model
        if limits.get('checkpoint') and not limits['checkpoint']():
            return 'cancelled', []
        if limits.get('cancel_event') and limits['cancel_event'].is_set():
            return 'cancelled', []
        mj.mj_step(m, d)
        if not np.isfinite(d.qpos).all() or not np.isfinite(d.qvel).all() or np.max(np.abs(d.qvel)) > 100 or np.any(d.warning.number):
            return 'controller_failure', []
        if np.any((d.qpos[:self.arm_dof] < m.jnt_range[:self.arm_dof, 0]-0.002)&m.jnt_limited[:self.arm_dof]) or np.any((d.qpos[:self.arm_dof] > m.jnt_range[:self.arm_dof, 1]+0.002)&m.jnt_limited[:self.arm_dof]):
            return 'joint_limit_failure', []
        mj.mj_forward(m, d)
        contacts = self.contacts(world)
        if contacts:
            return 'collision_failure', contacts
        if d.time-start_time >= limits['max_simulation_seconds']:
            return 'timeout', []
        return None, []

    def evaluate(self, world, result):
        mj.mj_forward(world.model, world.data)
        site = world.data.site('pregrasp')
        error = float(np.linalg.norm(site.xpos - world.config['target_position']))
        orientation = float(np.linalg.norm(Rotation.from_matrix(DOWN @ site.xmat.reshape(3, 3).T).as_rotvec()))
        failure = result['failure']
        if not failure and (error > 0.02 or orientation > 0.08):
            failure = 'controller_failure'
        trace=result['trace']
        slide=world.model.jnt_type[:self.arm_dof]==mj.mjtJoint.mjJNT_SLIDE
        changes=[np.asarray(b['qpos'][:self.arm_dof])-a['qpos'][:self.arm_dof] for a,b in zip(trace[:-1],trace[1:])]
        path_length=float(sum(np.linalg.norm(delta[~slide]) for delta in changes))
        linear_path=float(sum(np.linalg.norm(delta[slide]) for delta in changes))
        return {'success': failure is None, 'status': failure or 'execution_success', 'planning_feasible': world.action['planning_feasible'], 'goal_error_m': error, 'orientation_error_rad': orientation, 'contact_violations': result['contact_violations'], 'execution_duration_s': result['execution_duration_s'], 'joint_path_length_rad':path_length,'joint_path_length_m':linear_path, 'milestone': 'collision_free_reach'}

    def commit(self, state):
        return self.snapshot(self.fork(state))

    def replay(self, branch):
        source = 'failed_adapter_execution' if branch['evaluation']['status'] == 'adapter_failure' else 'measured_mujoco_trace'
        return {'branch_id': branch['id'], 'source': source, 'frames': branch['trace'], 'evaluation': branch['evaluation']}
