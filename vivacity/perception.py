"""Orthographic overhead ray sensor for the synthetic Panda workcell.

This is simulator semantic-depth sensing, not a trained vision system. Rays
intersect current MuJoCo geometry; the cube estimate is derived only from
visible cube-labelled hits. The true body pose is used solely to report error.
"""

import mujoco as mj
import numpy as np


SCAN_X = (-0.30, 1.10)
SCAN_Y = (-0.65, 0.65)
SCAN_SHAPE = (161, 141)
CAMERA_HEIGHT_M = 1.0


def scan_cube(world):
    model, data = world.model, world.data
    cube_id = model.geom('cube').id
    geom_id = np.zeros(1, dtype=np.int32)
    origin = np.array([0.0, 0.0, CAMERA_HEIGHT_M], dtype=np.float64)
    downward = np.array([0.0, 0.0, -1.0], dtype=np.float64)
    hits = []
    # Disabled obstacles are absent from the workcell view. MuJoCo's static
    # ray filter also excludes the table, while retaining the free cube and
    # articulated arm. Enabled obstacles can genuinely occlude the cube.
    include_static = bool(world.config.get('obstacle_enabled', True))
    for x in np.linspace(*SCAN_X, SCAN_SHAPE[0]):
        origin[0] = x
        for y in np.linspace(*SCAN_Y, SCAN_SHAPE[1]):
            origin[1] = y
            distance = mj.mj_ray(model, data, origin, downward, None,
                                 include_static, -1, geom_id)
            if distance >= 0 and geom_id[0] == cube_id:
                hits.append([float(x), float(y)])
    visible = len(hits)
    detected = visible >= 4
    estimate = np.mean(hits, axis=0).tolist() if detected else None
    actual = data.body('target').xpos[:2].tolist()
    return {
        'schema_version': 'vivacity.perception/1.0',
        'method': 'mujoco_overhead_semantic_depth_rays',
        'scope': 'synthetic_simulator_semantic_labels_not_real_camera_vision',
        'camera_origin_m': [0.4, 0.0, CAMERA_HEIGHT_M],
        'camera_direction': [0.0, 0.0, -1.0],
        'coverage_x_m': list(SCAN_X), 'coverage_y_m': list(SCAN_Y),
        'resolution': list(SCAN_SHAPE),
        'ray_count': SCAN_SHAPE[0] * SCAN_SHAPE[1],
        'visible_cube_rays': visible,
        'detected': detected,
        'estimated_xy_m': estimate,
        'localization_error_m': float(np.linalg.norm(np.asarray(estimate)-actual)) if detected else None,
        'visible_samples_xy_m': hits if detected else [],
    }
