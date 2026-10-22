"""Compile licensed Menagerie scenes once for memory-bounded MuJoCo startup.

Run during the Docker build, before setting VIVACITY_HUMANOID_MODEL_DIR.
The .mjb files contain the same geometry, contacts, joints, and actuators as
the source XML; loading them avoids the much larger XML compiler peak RSS.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco as mj

from vivacity.humanoids import MODELS, _compiled_xml_model, _configured_tree


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for robot_id in MODELS:
        source_model, model_hash = _compiled_xml_model(robot_id, .8, .5)
        source_mesh_count = int(source_model.nmesh)
        model = source_model
        if robot_id == 'apptronik_apollo':
            # Apollo's large meshes are visual-only. MuJoCo documents that
            # discardvisual retains identical dynamics while eliminating
            # purely visual geometry from the server-side model.
            root, _ = _configured_tree(robot_id, .8, .5)
            root.find('compiler').set('discardvisual', 'true')
            model = mj.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'))
            assert model.nq == source_model.nq and model.nv == source_model.nv
            assert model.nu == source_model.nu and model.nbody == source_model.nbody
        binary = output / f'{robot_id}.mjb'
        mj.mj_saveModel(model, str(binary))
        digest = hashlib.sha256()
        with binary.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        (output / f'{robot_id}.json').write_text(json.dumps({
            'robot_id': robot_id,
            'simulator_version': mj.__version__,
            'model_hash': model_hash,
            'binary_sha256': digest.hexdigest(),
            'source_mesh_count': source_mesh_count,
        }, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        print(f'{robot_id}: compiled {binary.stat().st_size / 1048576:.1f} MiB', flush=True)
        del model, source_model
        _compiled_xml_model.cache_clear()
        gc.collect()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/app/precompiled_humanoids'))
    build(parser.parse_args().output)
