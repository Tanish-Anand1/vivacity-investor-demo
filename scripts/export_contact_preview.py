"""Static geometry and keyframe only; no experiment runs during page loading."""
import hashlib
import json
from pathlib import Path

from vivacity.bimanual import BimanualConfig, compile_scene
from vivacity.execution_checkpoint import ImmutableModelArtifact
from vivacity.humanoids import initial_data, _frame
from vivacity.render_geometry import render_geometry


def main():
    model = compile_scene(BimanualConfig())
    manifest, binary = render_geometry(model, ImmutableModelArtifact(model).sha256)
    root = Path('frontend/public')
    mesh_url = '/vivacity/humanoids/unitree_g1/robot-meshes.bin'
    if hashlib.sha256((root/mesh_url.lstrip('/')).read_bytes()).hexdigest() != manifest['mesh_buffer_sha256']:
        raise ValueError('Existing licensed G1 mesh asset differs from the native contact model')
    manifest.update(initial_frame=_frame(model, initial_data(model)), mesh_buffer_url=mesh_url,
                    provenance='native model keyframe, no experiment executed')
    (root/'vivacity/contact-preview.json').write_text(json.dumps(manifest),encoding='utf8')
    print(json.dumps({'model_hash':manifest['model_hash'], 'mesh_bytes':len(binary)}))


if __name__=='__main__':main()
