import hashlib

import mujoco as mj
import numpy as np

from vivacity.render_geometry import render_geometry


def test_render_geometry_uses_native_mesh_coordinates_and_local_geom_poses():
    model = mj.MjModel.from_xml_string('''<mujoco><asset>
    <mesh name="tetra" vertex="0 0 0 .1 0 0 0 .1 0 0 0 .1"/>
    </asset><worldbody><body name="object" pos="1 2 3">
    <geom name="visual" type="mesh" mesh="tetra" pos=".2 0 0"/>
    <geom name="box" type="box" size=".03 .04 .05"/></body></worldbody></mujoco>''')
    manifest, buffer = render_geometry(model, 'a'*64)
    assert hashlib.sha256(buffer).hexdigest() == manifest['mesh_buffer_sha256']
    mesh = manifest['meshes'][0]
    vertices = np.frombuffer(buffer,dtype='<f4',offset=mesh['positions']['byte_offset'],count=mesh['positions']['count']).reshape(-1,3)
    np.testing.assert_array_equal(vertices,model.mesh_vert)
    box = next(g for g in manifest['geoms'] if g['name']=='box')
    assert box['size'] == [.03,.04,.05] and box['position'] == [0.,0.,0.]
    data = mj.MjData(model)
    mj.mj_forward(model,data)
    for geom in manifest['geoms']:
        body = geom['body_id']
        world_position = data.xpos[body]+data.xmat[body].reshape(3,3) @ geom['position']
        np.testing.assert_allclose(world_position,data.geom_xpos[geom['id']])
