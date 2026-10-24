"""Rendered RGB-D enters estimation; body pose is evaluator-only ground truth."""
import inspect

import mujoco as mj
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from vivacity.rgbd_perception import Calibration, CartonEstimator, RGBDFrame


def render(x=.32, y=0., yaw=0., light=1., occlusion=False):
    camera = np.array([1.1, -.85, 1.45])
    target = np.array([.35, 0., .8])
    z = camera-target
    z /= np.linalg.norm(z)
    right = np.cross([0, 0, 1], z)
    right /= np.linalg.norm(right)
    rotation = np.column_stack((right, np.cross(z, right), z))
    quat = Rotation.from_matrix(rotation).as_quat(scalar_first=True)
    pose = Rotation.from_euler('z', yaw).as_quat(scalar_first=True)
    occluder = '<geom type="box" pos=".40 -.13 .81" size=".05 .02 .09" rgba=".12 .12 .12 1"/>' if occlusion else ''
    model = mj.MjModel.from_xml_string(f'''<mujoco><visual><global offwidth="320" offheight="240"/></visual>
    <worldbody><light pos="1 -1 3" diffuse="{light} {light} {light}"/>
      <geom type="box" pos=".4 0 .72" size=".35 .45 .02" rgba=".4 .4 .4 1"/>
      <camera name="rgbd" pos="{' '.join(map(str,camera))}" quat="{' '.join(map(str,quat))}" fovy="50"/>
      <body name="truth_only_carton" pos="{x} {y} .82" quat="{' '.join(map(str,pose))}">
        <geom type="box" size=".09 .09 .08" rgba=".6 .39 .19 1"/>
      </body>{occluder}</worldbody></mujoco>''')
    data = mj.MjData(model)
    mj.mj_forward(model, data)
    with mj.Renderer(model, 240, 320) as renderer:
        renderer.update_scene(data, camera='rgbd')
        rgb = renderer.render().copy()
        renderer.enable_depth_rendering()
        depth = renderer.render().copy()
    transform = np.eye(4)
    transform[:3, :3], transform[:3, 3] = rotation, camera
    focal = 240/(2*np.tan(np.deg2rad(50)/2))
    calibration = Calibration(320, 240, focal, focal, 159.5, 119.5, transform)
    return RGBDFrame(rgb, depth, 1.), calibration, data.body('truth_only_carton').xpos.copy()


@pytest.mark.parametrize('x,y,yaw,light,occlusion', [
    (.32, 0., 0., 1., False), (.35, .025, .25, .7, False),
    (.29, -.025, -.3, .5, False), (.34, .015, .1, 1., True),
])
def test_image_depth_pose_recovery_with_heldout_conditions(x, y, yaw, light, occlusion):
    frame, calibration, truth = render(x, y, yaw, light, occlusion)
    rng = np.random.default_rng(8)
    frame = RGBDFrame(frame.rgb, frame.depth_m+rng.normal(0, .0008, frame.depth_m.shape), 1.)
    estimator = CartonEstimator(calibration, [.18, .18, .16])
    estimate = estimator.observe(frame, now_s=1.05)
    assert estimate.valid, estimate.reason
    assert np.linalg.norm(np.asarray(estimate.position_m)-truth) < .012
    assert abs(estimate.yaw_rad-yaw) < .08
    assert estimate.fit_rmse_m < .005
    assert estimate.supporting_pixels >= 60
    restored = CartonEstimator(calibration, [.18, .18, .16])
    restored.restore(estimator.snapshot())
    assert restored.snapshot() == estimator.snapshot()


def test_missing_stale_and_privileged_inputs_are_rejected():
    frame, calibration, _ = render()
    estimator = CartonEstimator(calibration, [.18, .18, .16])
    stale = estimator.observe(frame, now_s=2.)
    assert not stale.valid and stale.reason == 'stale_observation'
    missing = estimator.observe(RGBDFrame(frame.rgb, np.full_like(frame.depth_m, np.nan), 1.), now_s=1.)
    assert not missing.valid and missing.position_m is None
    with pytest.raises(TypeError):
        RGBDFrame(frame.rgb, frame.depth_m, 1., body_pose=[.32, 0., .82])
    import vivacity.rgbd_perception as perception
    source = inspect.getsource(perception)
    assert 'import mujoco' not in source and '.qpos' not in source and '.body(' not in source
