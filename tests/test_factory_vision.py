import base64
import mujoco as mj
import numpy as np
from vivacity.factory import FactoryBackend,FactorySettings
from vivacity.factory_vision import observe_camera
from vivacity.robotics import RobotWorld

def test_rendered_camera_tracks_moved_carton_and_out_of_view():
    b=FactoryBackend();w=b.create_world(FactorySettings(carton_count=1).model_dump())
    original=observe_camera(w)
    assert not original['detections'][0]['detected']
    assert original['detections'][0]['visibility']=='outside_view'
    adr=w.model.jnt_qposadr[w.model.joint('cube_free').id]
    # Initial-condition fixtures; production only drives actuators.
    for position in ([.5,-.24,.025],[.54,-.32,.025]):
        w.data.qpos[adr:adr+3]=position
        observation=observe_camera(w);detection=observation['detections'][0]
        assert detection['detected'] and detection['visible_pixels']>10
        assert detection['confidence'] is None
        np.testing.assert_allclose(detection['estimated_center_m'],position,atol=.01)
        assert observation['image_data_url']!=original['image_data_url']
        assert base64.b64decode(observation['image_data_url'].split(',')[1]).startswith(b'\x89PNG')

def test_occluder_prevents_detection_in_real_render():
    model=mj.MjModel.from_xml_string('''<mujoco><visual><global offwidth="320" offheight="240"/></visual><worldbody>
      <camera name="inspection" pos="0 0 1"/><light pos="0 0 2"/>
      <body name="target"><geom name="cube" type="box" size=".025 .025 .025"/></body>
      <geom name="occluder" type="box" pos="0 0 .2" size=".2 .2 .02"/>
    </worldbody></mujoco>''')
    w=RobotWorld(model,mj.MjData(model),{'carton_count':1,'carton_half_size_m':.025},7,'test')
    value=observe_camera(w)['detections'][0]
    assert not value['detected'] and value['visibility']=='occluded' and value['confidence'] is None
