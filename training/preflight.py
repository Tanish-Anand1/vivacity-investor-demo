"""Check exact complete embodiments against MJX before buying GPU time.

This is a model compatibility and numerical comparison probe. It does not train
a policy or establish locomotion capability. Compilation or numerical failures
remain failures; collision shapes and actuator properties are never simplified
to make this probe pass.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import resource
import time
import traceback


def run(robot, steps):
    import jax
    import mujoco as mj
    from mujoco import mjx
    import numpy as np
    from mujoco_playground._src import mjx_env
    from vivacity.humanoid_embodiments import compile_embodiment
    from vivacity.execution_checkpoint import model_bytes

    jax.config.update('jax_enable_x64', True)
    started = time.perf_counter()
    model, native, embodiment = compile_embodiment(robot)
    binary = model_bytes(model)
    model_hash = hashlib.sha256(binary).hexdigest()
    assert model_hash == embodiment['compiled_model_sha256']
    assert model.neq == model.nmocap == 0
    report = {
        'schema_version':'vivacity.mjx-preflight/1', 'robot':robot,
        'scope':'Exact-embodiment CPU MJX compatibility, not learned locomotion.',
        'hardware_validation':False, 'trained_policy':None,
        'playground_commit':'12ad7f3842791ced39f27e5ac96d066bbe361653',
        'compiled_model_sha256':model_hash, 'embodiment':embodiment,
        'versions':{name:importlib.metadata.version(name) for name in
                    ('mujoco','mujoco-mjx','jax','jaxlib','playground','numpy','scipy')},
        'devices':[str(device) for device in jax.devices()],
        'native_compile_s':time.perf_counter()-started,
        'float_precision':'float64', 'simulation_steps':steps,
        'timestep_s':float(model.opt.timestep),
    }
    compiled = time.perf_counter()
    # The exact compiled model is shared. In particular, preserve native contact
    # dimensions, solver settings, torque limits and the added grippers' inertia.
    device_model = mjx_env.put_model(model, impl='jax')
    device_data = mjx.put_data(model, native, impl='jax')
    step = jax.jit(lambda data: mjx_env.step(device_model, data, data.ctrl, 1))
    device_data = step(device_data)
    device_data.qpos.block_until_ready()
    report['first_compiled_step_s'] = time.perf_counter()-compiled
    mj.mj_step(model,native)
    measured = time.perf_counter()
    differences=[]
    for index in range(steps):
        if index:
            device_data=step(device_data)
            device_data.qpos.block_until_ready()
            mj.mj_step(model,native)
        qpos=np.asarray(device_data.qpos)
        qvel=np.asarray(device_data.qvel)
        if not np.isfinite(qpos).all() or not np.isfinite(qvel).all():
            raise RuntimeError('Nonfinite MJX integration state')
        differences.append({'step':index+1,
            'qpos_max_abs':float(np.max(np.abs(qpos-native.qpos))),
            'qvel_max_abs':float(np.max(np.abs(qvel-native.qvel)))})
    report['subsequent_step_wall_s']=time.perf_counter()-measured
    report['native_vs_mjx']=differences
    report['max_resident_memory_bytes']=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024
    report['compiled_model_unchanged']=hashlib.sha256(model_bytes(model)).hexdigest()==model_hash
    report['passed']=bool(report['compiled_model_unchanged'] and
        max(row['qpos_max_abs'] for row in differences)<.005 and
        max(row['qvel_max_abs'] for row in differences)<.1)
    report['comparison_bounds']={'qpos_max_abs':.005,'qvel_max_abs':.1}
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--robot',choices=('g1','apollo','h1'),required=True)
    parser.add_argument('--steps',type=int,default=3,choices=range(1,11))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    started=time.perf_counter()
    try:
        report=run(args.robot,args.steps)
    except Exception as error:
        report={'schema_version':'vivacity.mjx-preflight/1','robot':args.robot,
            'passed':False,'failure_type':type(error).__name__,'failure':str(error),
            'traceback':traceback.format_exc(),'trained_policy':None}
    report['wall_s']=time.perf_counter()-started
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('embodiment','traceback')}),flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':
    main()
