"""Kinematic diagnostic only: no task success or executed motion claim."""
import hashlib
import json
from pathlib import Path
import mujoco as mj
import numpy as np
from scipy.spatial.transform import Rotation
from vivacity.apollo_door import ARM_PARTS
from vivacity.cabinet_tooling import SWIVEL_JOINT
from vivacity.humanoid_ik import site_pose

root=Path(__file__).parent
report=json.loads((root/'measured-grasp/report.json').read_text())
model=mj.MjModel.from_binary_path(str(root/'measured-grasp'/report['model_file']))
data=mj.MjData(model)
fixture=json.loads(Path('tests/fixtures/apollo_parked_grasp.json').read_text())
data.qpos[:]=fixture['qpos']
mj.mj_forward(model,data)
angle=float(data.joint('service_door_hinge').qpos[0])
hinge=data.body('service_door').xpos.copy()
site=data.site('l_service_tcp')
initial=site.xpos.copy()
rotation=site.xmat.reshape(3,3).copy()
results=[]
for amount in (0.,.5,1.):
    for target in (.5,.8,1.1):
        turn=Rotation.from_rotvec([0,0,-(target-angle)])
        goal=hinge+turn.apply(initial-hinge)
        orient=Rotation.from_rotvec([0,0,-amount*(target-angle)]).as_matrix()@rotation
        plan=site_pose(model,data.qpos,'l_service_tcp',
            ['l_'+part for part in ARM_PARTS]+[SWIVEL_JOINT],goal,orient,joint_margin=.01)
        entry={'rotation_fraction':amount,'door_target_rad':target,'feasible':plan.feasible,
               'position_error_m':plan.position_error_m,'angular_error_rad':plan.angular_error_rad,
               'iterations':plan.iterations,'goal':goal.tolist(),'rotation':orient.tolist()}
        results.append(entry)
        print(json.dumps(entry),flush=True)
(root/'rotation-ik.json').write_text(json.dumps({'scope':__doc__,
    'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'results':results},indent=2))
