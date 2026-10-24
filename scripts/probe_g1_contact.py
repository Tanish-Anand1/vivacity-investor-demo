"""Research probe, not a released task or acceptance claim.

Run from the repository: python -m scripts.probe_g1_contact
Only the planning scratch MjData changes qpos; execution uses native actuators.
"""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import sys

import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation

from vivacity.humanoids import _configured_tree, initial_data
from vivacity.humanoid_pickup import ARM_NAMES
from vivacity.inverse_dynamics import ConstrainedInverseDynamics, ControllerInfeasible
from vivacity.bimanual import BimanualConfig, compile_scene


def build():
    model = compile_scene(BimanualConfig())
    return model, initial_data(model)


def ik(model, initial, side, target, rotation=None):
    scratch = mj.MjData(model)
    scratch.qpos[:] = initial
    ids = np.array([model.joint(n).id for n in ARM_NAMES[side]])
    qadr = model.jnt_qposadr[ids]
    dofs = model.jnt_dofadr[ids]
    body = model.body(f'{side}_wrist_yaw_link').id
    rotation = np.eye(3) if rotation is None else rotation
    jp, jr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
    for _ in range(250):
        mj.mj_forward(model, scratch)
        error = target - scratch.xpos[body]
        angular = Rotation.from_matrix(rotation @ scratch.xmat[body].reshape(3, 3).T).as_rotvec()
        residual = np.r_[error, .18 * angular]
        if np.linalg.norm(residual) < 1e-4:
            break
        mj.mj_jacBody(model, scratch, jp, jr, body)
        jac = np.vstack((jp[:, dofs], .18 * jr[:, dofs]))
        delta = jac.T @ np.linalg.solve(jac @ jac.T + np.eye(6) * .0001, residual)
        scratch.qpos[qadr] = np.clip(scratch.qpos[qadr] + np.clip(delta, -.08, .08),
                                    model.jnt_range[ids, 0]+.005, model.jnt_range[ids, 1]-.005)
    return dict(zip(ids, scratch.qpos[qadr])), float(np.linalg.norm(error)), float(np.linalg.norm(angular))


def forces(model, data):
    out = {side: np.zeros(3) for side in ('left', 'right', 'other')}
    normal = {side: 0. for side in out}
    parcel = model.geom('parcel_box').id
    contact_names = []
    for i, contact in enumerate(data.contact[:data.ncon]):
        if parcel not in (contact.geom1, contact.geom2):
            continue
        other = int(contact.geom2 if contact.geom1 == parcel else contact.geom1)
        body = model.body(int(model.geom_bodyid[other])).name
        side = next((side for side in ('left', 'right') if body.startswith(side+'_hand') or body == side+'_wrist_yaw_link'), 'other')
        force = np.zeros(6)
        mj.mj_contactForce(model, data, i, force)
        world = contact.frame.reshape(3, 3).T @ force[:3]
        out[side] += world * (1 if contact.geom2 == parcel else -1)
        normal[side] += force[0]
        contact_names.append(body)
    return {s: v.tolist() for s, v in out.items()}, normal, sorted(set(contact_names))


def main():
    model, data = build()
    home = data.ctrl.copy()
    home_qpos = data.qpos.copy()
    feet = {side: data.body(f'{side}_ankle_roll_link').xpos.copy() for side in ('left', 'right')}
    use_inverse = '--inverse' in sys.argv
    controller = None
    if use_inverse:
        native_damping = -model.actuator_biasprm[:, 2].copy()
        for i, joint in enumerate(model.actuator_trnid[:, 0]):
            model.dof_damping[model.jnt_dofadr[joint]] += native_damping[i]
        model.actuator_gainprm[:] = 0
        model.actuator_gainprm[:, 0] = 1
        model.actuator_biasprm[:] = 0
        model.actuator_biastype[:] = int(mj.mjtBias.mjBIAS_NONE)
        model.actuator_ctrllimited[:] = True
        for i, joint in enumerate(model.actuator_trnid[:, 0]):
            model.actuator_ctrlrange[i] = model.jnt_actfrcrange[joint]
        data.ctrl[:] = 0
        controller = ConstrainedInverseDynamics(model)
        mj.mj_forward(model, data)
    history = []
    print('model', model.nq, model.nv, model.nu, 'equalities', model.neq, flush=True)
    phases = [
        ('raise', 2., [.04, .24, 1.00], [.04, -.24, 1.00]),
        ('above', 2., [.22, .185, .98], [.22, -.185, .98]),
        ('approach', 2., [.22, .185, .82], [.22, -.185, .82]),
        ('grip', 1.5, [.22, .115, .82], [.22, -.115, .82]),
        ('lift', 2., [.22, .115, .96], [.22, -.115, .96]),
        ('hold', 1., [.22, .115, .96], [.22, -.115, .96]),
        ('transfer', 2., [.30, .115, .96], [.30, -.115, .96]),
        ('lower', 2., [.30, .115, .82], [.30, -.115, .82]),
        ('release', 1.5, [.30, .18, .82], [.30, -.18, .82]),
    ]
    for phase, duration, left, right in phases:
        start = data.qpos[model.jnt_qposadr[model.actuator_trnid[:, 0]]].copy() if controller else data.ctrl.copy()
        hand_start = {side: data.body(f'{side}_wrist_yaw_link').xpos.copy() for side in ('left', 'right')}
        hand_rot = {side: data.body(f'{side}_wrist_yaw_link').xmat.reshape(3,3).copy() for side in ('left', 'right')}
        goal = home.copy()
        for side, target in [('left', left), ('right', right)]:
            joints, poserr, roterr = ik(model, data.qpos.copy(), side, np.array(target))
            print('ik', phase, side, round(poserr, 5), round(roterr, 5), flush=True)
            for aid in range(model.nu):
                if int(model.actuator_trnid[aid, 0]) in joints:
                    goal[aid] = joints[int(model.actuator_trnid[aid, 0])]
        steps = int(duration/model.opt.timestep)
        for step in range(steps):
            s = min(1., step/(steps*.8))
            blend = s*s*(3-2*s)
            targets = start + (goal-start)*blend
            if controller:
                if step % 5 == 0:
                    qtarget = home_qpos.copy()
                    qtarget[model.jnt_qposadr[model.actuator_trnid[:, 0]]] = targets
                    try:
                        reference = 500.*(targets-data.qpos[model.jnt_qposadr[model.actuator_trnid[:, 0]]])
                        tasks = []
                        for side, destination in [('left', left), ('right', right)]:
                            for part, desired_pos, rotation, weight in [
                                ('ankle_roll_link', feet[side], np.eye(3), 1000.),
                                ('wrist_yaw_link', hand_start[side]+blend*(np.array(destination)-hand_start[side]),
                                 Rotation.from_rotvec((1-blend)*Rotation.from_matrix(hand_rot[side]).as_rotvec()).as_matrix(), 100.)]:
                                bid = model.body(f'{side}_{part}').id
                                jp, jr = np.zeros((3,model.nv)), np.zeros((3,model.nv))
                                mj.mj_jacBody(model, data, jp, jr, bid)
                                j = np.vstack((jp, .2*jr))
                                err = np.r_[desired_pos-data.xpos[bid], .2*Rotation.from_matrix(rotation@data.xmat[bid].reshape(3,3).T).as_rotvec()]
                                acc = 200.*err-30.*(j@data.qvel)
                                tasks.append((j, acc, weight))
                        data.ctrl[:] = controller.compute(data, qtarget, torque_reference=reference,
                                                         torque_weight=.01, base_weight=40., extra_tasks=tasks).commands
                    except ControllerInfeasible as exc:
                        print('controller_failed', str(exc), data.time, flush=True)
                        return
            else:
                data.ctrl[:] = targets
            mj.mj_step(model, data)
            mj.mj_forward(model, data)
            if step % 50 == 0 or step == steps-1:
                f, normal, names = forces(model, data)
                history.append(dict(time=float(data.time), phase=phase, parcel=data.body('parcel').xpos.tolist(),
                    base=data.qpos[:7].tolist(), forces=f, normal=normal, contacts=names,
                    qpos=data.qpos.tolist()))
        print(json.dumps({k:v for k,v in history[-1].items() if k!='qpos'}), flush=True)
    target = Path('artifacts/physical-truth-runtime/g1-inverse-probe.json' if controller else 'artifacts/physical-truth-runtime/g1-contact-probe.json')
    target.parent.mkdir(exist_ok=True, parents=True)
    target.write_text(json.dumps(history), encoding='utf8')
    try:
        with mj.Renderer(model, 480, 640) as renderer:
            camera = mj.MjvCamera()
            camera.lookat[:] = [.3, 0, .85]
            camera.distance, camera.azimuth, camera.elevation = 2.6, 135, -15
            for phase in ['approach', 'grip', 'lift', 'hold', 'release']:
                rec = [r for r in history if r['phase'] == phase][-1]
                scratch = mj.MjData(model)
                scratch.qpos[:] = rec['qpos']
                mj.mj_forward(model, scratch)
                renderer.update_scene(scratch, camera)
                from PIL import Image
                Image.fromarray(renderer.render()).save(target.parent/f'g1-{phase}.png')
    except Exception as exc:
        print('render', repr(exc), flush=True)


if __name__ == '__main__':
    main()
