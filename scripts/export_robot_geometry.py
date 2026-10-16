"""Export compiled MuJoCo geometry for Three.js, without another mesh parser.

The mesh compiler centers/rotates source vertices. Exporting its actual vertex
arrays together with compiled geom poses avoids applying that correction twice.
This is a static frontend asset, never a trajectory or simulation replacement.
"""
import json
from pathlib import Path

import mujoco as mj
import numpy as np

from vivacity.robotics import RoboticsBackend
from vivacity.schemas import RoboticsConfig


def export(directory=Path('docs'), world=None):
    directory.mkdir(parents=True, exist_ok=True)
    world = world or RoboticsBackend().create_world(RoboticsConfig().model_dump(), 7)
    model = world.model
    binary = bytearray()
    meshes = []
    for i in range(model.nmesh):
        va, vn = int(model.mesh_vertadr[i]), int(model.mesh_vertnum[i])
        fa, fn = int(model.mesh_faceadr[i]), int(model.mesh_facenum[i])
        vertices = np.asarray(model.mesh_vert[va:va+vn], dtype='<f4')
        indices = np.asarray(model.mesh_face[fa:fa+fn], dtype='<u4')
        position_offset = len(binary)
        binary.extend(vertices.tobytes())
        index_offset = len(binary)
        binary.extend(indices.tobytes())
        meshes.append({'id': i, 'name': mj.mj_id2name(model, mj.mjtObj.mjOBJ_MESH, i),
                       'positions': {'byte_offset': position_offset, 'count': vn*3, 'dtype': 'float32'},
                       'indices': {'byte_offset': index_offset, 'count': fn*3, 'dtype': 'uint32'}})
    bodies = [{'id': i, 'name': mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, i),
               'parent_id': int(model.body_parentid[i])} for i in range(model.nbody)]
    geoms = []
    for i in range(model.ngeom):
        mat = int(model.geom_matid[i])
        rgba = model.mat_rgba[mat] if mat >= 0 else model.geom_rgba[i]
        geoms.append({'id': i, 'name': mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, i) or f'geom_{i}',
                      'body_id': int(model.geom_bodyid[i]),
                      'type': mj.mjtGeom(int(model.geom_type[i])).name.removeprefix('mjGEOM_').lower(),
                      'group': int(model.geom_group[i]), 'mesh_id': int(model.geom_dataid[i]) if model.geom_type[i] == mj.mjtGeom.mjGEOM_MESH else None,
                      'position': model.geom_pos[i].tolist(), 'quaternion_wxyz': model.geom_quat[i].tolist(),
                      'size': model.geom_size[i].tolist(), 'rgba': rgba.tolist(),
                      'contype': int(model.geom_contype[i]), 'conaffinity': int(model.geom_conaffinity[i])})
    manifest = {'schema_version': '1.0', 'source': 'compiled_mujoco_model',
                'simulator_version': mj.__version__, 'model_hash': world.model_hash,
                'config': world.config, 'coordinates': 'right-handed Z-up meters; quaternions wxyz',
                'mesh_buffer': 'robot-meshes.bin', 'byte_order': 'little-endian',
                'bodies': bodies, 'geoms': geoms, 'meshes': meshes,
                'site': {'name': 'pregrasp', 'body': 'hand', 'position': [0, 0, 0.103]}}
    (directory / 'robot-meshes.bin').write_bytes(binary)
    (directory / 'robot-geometry.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print({'bodies': len(bodies), 'geoms': len(geoms), 'meshes': len(meshes), 'buffer_bytes': len(binary)})
    return manifest


if __name__ == '__main__':
    export()
