"""Export model/controller identity and actual simulated sensor recordings."""
import argparse
import hashlib
import json
from pathlib import Path

import mujoco as mj

from vivacity.bimanual import BimanualConfig, compile_scene, SOURCE_HASHES
from vivacity.constrained_bimanual import CONTROLLER_HASHES, ConstrainedCartonController
from vivacity.execution_checkpoint import ImmutableModelArtifact
from vivacity.hardware_transfer import validate_sensor_replay


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = json.loads(args.result.read_text())
    if result['source_sha256'] != SOURCE_HASHES or result['controller_source_sha256'] != CONTROLLER_HASHES:
        raise ValueError('Cannot export stale controller evidence')
    model = compile_scene(BimanualConfig.model_validate(result['parameters']))
    artifact = ImmutableModelArtifact(model)
    if artifact.sha256 != result['model_sha256']:
        raise ValueError('Recorded model and native rebuilt model differ')
    joints = model.actuator_trnid[:, 0]
    names = [model.joint(jid).name for jid in joints]
    records = []
    for frame in result['frames']:
        records.append({'schema_version':'vivacity.recorded-proprioception/1',
            'provenance':'native_mujoco_simulation', 'timestamp_s':frame['time_s'],
            'joint_names':names, 'position_rad':[frame['qpos'][model.jnt_qposadr[jid]] for jid in joints],
            'velocity_rad_s':[frame['qvel'][model.jnt_dofadr[jid]] for jid in joints]})
    replay = validate_sensor_replay(records, names)
    manifest = {'schema_version':'vivacity.hardware-transfer/1', 'status':'offline_package_only',
        'hardware_validated':False, 'transport_implemented':False,
        'simulator':{'name':'MuJoCo','version':mj.__version__,'model_sha256':artifact.sha256},
        'controller':{'version':ConstrainedCartonController.version, 'source_sha256':CONTROLLER_HASHES,
                      'task_source_sha256':SOURCE_HASHES, 'policy':'constrained native servo references; no learned policy'},
        'coordinates':{'handedness':'right','world_up':'+Z','position_unit':'metre','joint_unit':'radian',
                       'quaternion_order':'wxyz','body_transforms':'world poses, not parent-relative'},
        'watchdog_s':.1, 'command_mode':'position_reference_with_native_servo_gains',
        'commissioning_rate_limit_note':'2 rad/s is an offline software ceiling, not a verified hardware rating.',
        'joints':[{'actuator_id':i,'joint':names[i],'qpos_index':int(model.jnt_qposadr[jid]),
            'qvel_index':int(model.jnt_dofadr[jid]), 'position_bounds_rad':model.actuator_ctrlrange[i].tolist(),
            'torque_bounds_nm':model.jnt_actfrcrange[jid].tolist(),
            'kp_nm_rad':float(model.actuator_gainprm[i,0]), 'kd_nm_s_rad':float(-model.actuator_biasprm[i,2]),
            'commissioning_rate_limit_rad_s':2.} for i,jid in enumerate(joints)],
        'sensor_replay':replay, 'simulation_task_success':result['task_success'],
        'simulation_failure':result['failure_reason'], 'parameters':result['parameters']}
    args.output.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(manifest, indent=2, allow_nan=False).encode()
    (args.output/'manifest.json').write_bytes(encoded)
    (args.output/'manifest.sha256').write_text(hashlib.sha256(encoded).hexdigest()+'\n')
    (args.output/'simulated-proprioception.jsonl').write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in records),encoding='utf8')
    print(json.dumps({'model_sha256':artifact.sha256,'samples':len(records),
                      'hardware_validated':False,'output':str(args.output)}))


if __name__ == '__main__':
    main()
