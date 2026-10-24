"""Render measured replay poses, explicitly separate from live execution."""
import json
from pathlib import Path

import mujoco as mj
import numpy as np
from PIL import Image

from vivacity.bimanual import BimanualConfig, compile_scene
from vivacity.execution_checkpoint import ImmutableModelArtifact


def main():
    folder = Path('artifacts/physical-truth-runtime')
    report = json.loads((folder/'http-journey.json').read_text(encoding='utf8'))
    result = report['export']['trial']['result']
    model = compile_scene(BimanualConfig.model_validate(result['parameters']))
    assert ImmutableModelArtifact(model).sha256 == result['model_sha256']
    data = mj.MjData(model)
    camera = mj.MjvCamera()
    camera.lookat[:] = [.3, 0, .85]
    camera.distance, camera.azimuth, camera.elevation = 2.6, 135, -15
    frames = [entry['frame'] for entry in report['replay']['frames']]
    images = []
    with mj.Renderer(model,480,640) as renderer:
        for phase in ('approach','grip','lift','hold','transfer','lower','release','settle'):
            frame = [frame for frame in frames if frame['phase'] == phase][-1]
            data.qpos[:] = frame['qpos']
            mj.mj_forward(model,data)
            renderer.update_scene(data,camera)
            path=folder/f'verified-native-{phase}.png'
            Image.fromarray(renderer.render()).save(path)
            images.append({'phase':phase,'time_s':frame['time_s'],'path':path.name,
                           'measurement':frame.get('measurement')})
    image = Image.new('RGB',(640*4,480*2))
    for i,row in enumerate(images):
        with Image.open(folder/row['path']) as frame:
            image.paste(frame,((i%4)*640,(i//4)*480))
    image.save(folder/'verified-native-contact-sheet.png')
    (folder/'verified-native-images.json').write_text(json.dumps({
        'scope':'Render of measured replay poses; not a new execution or live footage.',
        'model_sha256':result['model_sha256'],'frames':images},indent=2),encoding='utf8')
    print(str((folder/'verified-native-contact-sheet.png').resolve()))


if __name__=='__main__':main()
