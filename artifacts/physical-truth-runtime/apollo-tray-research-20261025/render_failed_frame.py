from pathlib import Path
import hashlib,json
import mujoco as mj
import numpy as np
from PIL import Image
base=Path('data/physical-truth-oct25/old-tray-swing')
report=json.loads((base/'grip-feedback-force_tracking.json').read_bytes())
model=mj.MjModel.from_binary_path(str(base/'model.mjb'))
data=mj.MjData(model)
frame=report['frames'][-1]['frame']
data.qpos[:]=frame['qpos'];data.qvel[:]=frame['qvel'];data.time=frame['time_s']
mj.mj_forward(model,data)
# Static illustration reconstructed from the measured frame. This is not a
# resumed checkpoint and no forces recomputed here are used as task evidence.
renderer=mj.Renderer(model,height=480,width=640)
for azimuth in (180,270):
    camera=mj.MjvCamera();camera.lookat[:]=[.4,0,1.1];camera.distance=1.75
    camera.azimuth=azimuth;camera.elevation=-20
    renderer.update_scene(data,camera=camera)
    Image.fromarray(renderer.render()).save(base/f'terminal-view-{azimuth}.png')
renderer.close()
print(json.dumps({'report_sha256':hashlib.sha256((base/'grip-feedback-force_tracking.json').read_bytes()).hexdigest(),'time_s':frame['time_s'],'status':report['state']['status'],'failure':report['state']['failure']}))
