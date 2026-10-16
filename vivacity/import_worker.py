"""Disposable native probe. Input is data, never imported Python or a plugin.

Linux installs CPU/address-space/file limits and a seccomp filter before model
compilation. No host files, sockets, subprocesses or cross-process memory access
can be opened afterward. Windows is restricted to the exact trusted fixture.
"""
import base64
import ctypes
import json
import os
import platform
import sys
import xml.etree.ElementTree as ET


def restrict_linux():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024**2, 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    machine = platform.machine().lower()
    if machine in ('x86_64', 'amd64'):
        arch = 0xC000003E
        denied = [2, 85, 257, 437, 41, 42, 43, 49, 50, 53, 288,
                  57, 58, 56, 435, 59, 322, 101, 310, 311,
                  425, 426, 427, 304, 82, 83, 84, 86, 87, 88, 90, 92,
                  76, 132, 133, 165, 166, 272, 308, 263, 264, 265, 266,
                  267, 268, 280, 316]
    elif machine in ('aarch64', 'arm64'):
        arch = 0xC00000B7
        denied = [56, 437, 198, 199, 200, 201, 202, 203, 242,
                  220, 435, 221, 281, 117, 270, 271,
                  425, 426, 427, 265, 33, 34, 35, 36, 37, 38, 276,
                  40, 39, 97, 268, 53, 54]
    else:
        raise ValueError('native sandbox unavailable on this CPU architecture')

    class Filter(ctypes.Structure):
        _fields_ = [('code', ctypes.c_ushort), ('jt', ctypes.c_ubyte),
                    ('jf', ctypes.c_ubyte), ('k', ctypes.c_uint)]

    class Program(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ushort), ('filter', ctypes.POINTER(Filter))]

    instructions = [(0x20, 0, 0, 4), (0x15, 1, 0, arch),
                    (0x06, 0, 0, 0x80000000), (0x20, 0, 0, 0)]
    # Reject x32 ABI syscall numbers, which otherwise share the x86-64 arch tag.
    instructions.extend([(0x35, 0, 1, 0x40000000), (0x06, 0, 0, 0x80000000)])
    for number in denied:
        instructions.extend([(0x15, 0, 1, number), (0x06, 0, 0, 0x00050001)])
    instructions.append((0x06, 0, 0, 0x7FFF0000))
    filters = (Filter * len(instructions))(*(Filter(*i) for i in instructions))
    program = Program(len(filters), filters)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) or libc.prctl(22, 2, ctypes.byref(program), 0, 0):
        raise ValueError('native sandbox installation failed')


def probe(request):
    # Imports and dynamic libraries are resolved before filesystem access closes.
    import mujoco as mj
    import numpy as np
    xml = base64.b64decode(request['xml'], validate=True)
    assets = {name: base64.b64decode(value, validate=True)
              for name, value in request['assets'].items()}
    root = ET.fromstring(xml)
    if root.tag == 'mujoco':
        compiler = root.find('compiler')
        if compiler is None:
            compiler = ET.SubElement(root, 'compiler')
        compiler.set('usethread', 'false')
        # VFS names have already been resolved by the parent validator.
        for key in ('meshdir', 'texturedir', 'assetdir'):
            compiler.attrib.pop(key, None)
        xml = ET.tostring(root, encoding='unicode')
    else:
        xml = xml.decode('utf-8-sig')
    if sys.platform.startswith('linux'):
        restrict_linux()
        sandbox = 'linux_seccomp_cpu_memory_file_caps'
    elif request.get('trusted_fixture') is True:
        sandbox = 'trusted_fixed_fixture_child_only'
    else:
        raise ValueError('untrusted native execution requires the Linux sandbox')
    model = mj.MjModel.from_xml_string(xml, assets=assets)
    if model.nv > 128 or model.nu > 64 or model.ngeom > 512 or model.nbody > 256:
        raise ValueError('compiled model exceeds probe bounds')
    if not .001 <= model.opt.timestep <= .01:
        raise ValueError('native timestep must be 0.001..0.01 seconds')
    data = mj.MjData(model)
    mj.mj_forward(model, data)
    name = lambda kind, i: mj.mj_id2name(model, kind, i)
    joints = [{'name': name(mj.mjtObj.mjOBJ_JOINT, i),
               'type': int(model.jnt_type[i]), 'range': model.jnt_range[i].tolist(),
               'limited': bool(model.jnt_limited[i]), 'qpos_address': int(model.jnt_qposadr[i])}
              for i in range(model.njnt)]
    actuators = []
    for i in range(model.nu):
        joint = int(model.actuator_trnid[i, 0])
        position = (int(model.actuator_trntype[i]) == 0 and 0 <= joint < model.njnt
                    and int(model.jnt_type[joint]) in (2, 3)
                    and model.actuator_gainprm[i, 0] > 0
                    and np.isclose(model.actuator_biasprm[i, 1], -model.actuator_gainprm[i, 0]))
        actuators.append({'name': name(mj.mjtObj.mjOBJ_ACTUATOR, i),
                          'joint': joints[joint]['name'] if position else None,
                          'position_control_supported': bool(position),
                          'control_range': model.actuator_ctrlrange[i].tolist()})
        if position:
            data.ctrl[i] = data.qpos[model.jnt_qposadr[joint]]
    spec = mj.mjtState.mjSTATE_INTEGRATION
    initial = np.empty(mj.mj_stateSize(model, spec))
    mj.mj_getState(model, data, initial, spec)
    q0 = data.qpos.copy()
    driven = next((i for i, a in enumerate(actuators) if a['position_control_supported']), None)
    if driven is not None:
        joint = int(model.actuator_trnid[driven, 0])
        current = float(data.qpos[model.jnt_qposadr[joint]])
        lo, hi = (-1e3, 1e3)
        if model.actuator_ctrllimited[driven]:
            lo, hi = model.actuator_ctrlrange[driven]
        if model.jnt_limited[joint]:
            lo, hi = max(lo, model.jnt_range[joint, 0]), min(hi, model.jnt_range[joint, 1])
        data.ctrl[driven] = np.clip(current + (.1 if current + .1 < hi else -.1), lo, hi)
    steps = int(np.ceil(.5 / model.opt.timestep))
    for _ in range(steps):
        mj.mj_step(model, data)
    mj.mj_forward(model, data)
    final = np.empty_like(initial)
    mj.mj_getState(model, data, final, spec)
    displacement = 0. if driven is None else abs(float(data.qpos[model.jnt_qposadr[int(model.actuator_trnid[driven, 0])]] - q0[model.jnt_qposadr[int(model.actuator_trnid[driven, 0])]]))
    stable = bool(np.isfinite(data.qpos).all() and np.isfinite(data.qvel).all()
                  and not np.any(data.warning.number))
    return {'simulator': 'mujoco', 'simulator_version': mj.__version__, 'sandbox': sandbox,
            'physics_model_valid': True, 'robot_actuation_verified': bool(driven is not None and stable and displacement > 1e-5),
            'task_execution_verified': False, 'joints': joints, 'actuators': actuators,
            'sites': [name(mj.mjtObj.mjOBJ_SITE, i) for i in range(model.nsite)],
            'dynamic_bodies': [name(mj.mjtObj.mjOBJ_BODY, i) for i in range(1, model.nbody) if model.body_jntnum[i]],
            'collision_geometries': int(np.count_nonzero(model.geom_contype | model.geom_conaffinity)),
            'simulation_steps': steps, 'simulated_seconds': float(data.time),
            'driven_actuator': driven, 'joint_displacement': displacement, 'stable': stable,
            'state_encoding': 'mjSTATE_INTEGRATION', 'initial_state': initial.tolist(),
            'final_state': final.tolist(), 'initial_qpos': q0.tolist(), 'final_qpos': data.qpos.tolist(),
            'scope': 'Bounded initial-state and one-position-actuator probe; not a manipulation controller.'}


if __name__ == '__main__':
    try:
        raw = sys.stdin.buffer.read(48 * 1024**2 + 1)
        if len(raw) > 48 * 1024**2:
            raise ValueError('worker input exceeds bound')
        result = probe(json.loads(raw))
        print(json.dumps({'ok': True, 'result': result}, allow_nan=False))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)[:700]}))
        sys.exit(1)
