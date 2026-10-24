"""Geometry from the exact compiled model; never a generated motion source."""
import hashlib

import mujoco as mj
import numpy as np


def render_geometry(model, model_sha256):
    buffer = bytearray()
    meshes = []
    for i in range(model.nmesh):
        va, vn = int(model.mesh_vertadr[i]), int(model.mesh_vertnum[i])
        fa, fn = int(model.mesh_faceadr[i]), int(model.mesh_facenum[i])
        positions = {'byte_offset':len(buffer),'count':vn*3}
        buffer.extend(np.asarray(model.mesh_vert[va:va+vn], dtype='<f4').tobytes())
        indices = {'byte_offset':len(buffer),'count':fn*3}
        buffer.extend(np.asarray(model.mesh_face[fa:fa+fn], dtype='<u4').tobytes())
        meshes.append({'id':i, 'positions':positions, 'indices':indices})
    geoms = []
    for i in range(model.ngeom):
        mat = int(model.geom_matid[i])
        geoms.append({'id':i,'name':model.geom(i).name or f'geom_{i}', 'body_id':int(model.geom_bodyid[i]),
            'type':mj.mjtGeom(int(model.geom_type[i])).name.removeprefix('mjGEOM_').lower(),
            'group':int(model.geom_group[i]), 'mesh_id':int(model.geom_dataid[i]) if model.geom_type[i] == mj.mjtGeom.mjGEOM_MESH else None,
            'position':model.geom_pos[i].tolist(),'quaternion_wxyz':model.geom_quat[i].tolist(),
            'size':model.geom_size[i].tolist(), 'rgba':(model.mat_rgba[mat] if mat >= 0 else model.geom_rgba[i]).tolist(),
            'contype':int(model.geom_contype[i]),'conaffinity':int(model.geom_conaffinity[i])})
    binary = bytes(buffer)
    manifest = {'schema_version':'vivacity.compiled-render-geometry/1', 'model_hash':model_sha256,
        'simulator_version':mj.__version__, 'source':'compiled_mujoco_model',
        'coordinates':'right-handed Z-up metres; world body poses; geometry-local poses; wxyz quaternions',
        'bodies':[{'id':i,'name':model.body(i).name,'parent_id':int(model.body_parentid[i])} for i in range(model.nbody)],
        'geoms':geoms,'meshes':meshes,'mesh_buffer_sha256':hashlib.sha256(binary).hexdigest(),
        'mesh_buffer_bytes':len(binary)}
    return manifest, binary
