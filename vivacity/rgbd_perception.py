"""Image/depth-only pose estimation for a bounded, known brown carton.

No simulator object, segmentation ID or ground-truth body pose enters this
module. Static camera calibration, workspace bounds and known carton dimensions
are explicit inputs. This is a geometric baseline, not general object vision.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.optimize import least_squares


@dataclass(frozen=True)
class Calibration:
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    camera_to_world: np.ndarray

    def __post_init__(self):
        transform = np.array(self.camera_to_world, dtype=float, copy=True)
        if transform.shape != (4, 4) or not np.isfinite(transform).all():
            raise ValueError('finite 4x4 camera calibration required')
        if not np.allclose(transform[3], [0, 0, 0, 1]) or not np.allclose(transform[:3, :3].T @ transform[:3, :3], np.eye(3), atol=1e-6) or not np.isclose(np.linalg.det(transform[:3, :3]), 1.):
            raise ValueError('camera transform must be rigid')
        if not 1 <= self.width <= 4096 or not 1 <= self.height <= 4096 or self.fx <= 0 or self.fy <= 0 or not np.isfinite([self.fx, self.fy, self.cx, self.cy]).all():
            raise ValueError('invalid camera intrinsics')
        transform.setflags(write=False)
        object.__setattr__(self, 'camera_to_world', transform)


@dataclass(frozen=True)
class RGBDFrame:
    rgb: np.ndarray
    depth_m: np.ndarray
    timestamp_s: float


@dataclass(frozen=True)
class PoseEstimate:
    timestamp_s: float
    position_m: tuple[float, float, float] | None
    yaw_rad: float | None
    position_std_m: tuple[float, float, float] | None
    fit_rmse_m: float | None
    supporting_pixels: int
    plane: tuple[float, float, float, float] | None
    valid: bool
    reason: str | None


def unproject(depth, calibration: Calibration):
    """Optical convention: x right, y up, camera looking along negative z."""
    v, u = np.indices(depth.shape)
    camera = np.stack(((u-calibration.cx)*depth/calibration.fx,
                       -(v-calibration.cy)*depth/calibration.fy, -depth), axis=-1)
    return camera @ calibration.camera_to_world[:3, :3].T+calibration.camera_to_world[:3, 3]


def _support_plane(points):
    if len(points) < 80:
        return None
    points = points[np.linspace(0, len(points)-1, min(len(points), 3000), dtype=int)]
    rng = np.random.default_rng(19)
    best = None
    best_count = 0
    for _ in range(80):
        a, b, c = points[rng.choice(len(points), 3, replace=False)]
        normal = np.cross(b-a, c-a)
        norm = np.linalg.norm(normal)
        if norm < 1e-9:
            continue
        normal /= norm
        if normal[2] < 0:
            normal *= -1
        if normal[2] < .97:
            continue
        offset = -normal @ a
        mask = np.abs(points @ normal+offset) < .004
        count = int(mask.sum())
        if count > best_count:
            best, best_count = mask, count
    if best is None or best_count < 80:
        return None
    center = np.mean(points[best], axis=0)
    _, _, directions = np.linalg.svd(points[best]-center, full_matrices=False)
    normal = directions[-1]
    if normal[2] < 0:
        normal *= -1
    return np.r_[normal, -normal @ center]


class CartonEstimator:
    def __init__(self, calibration: Calibration, dimensions_m, *,
                 workspace_min=(.1, -.4, .5), workspace_max=(.75, .4, 1.25),
                 maximum_age_s=.2):
        self.calibration = calibration
        self.dimensions = np.asarray(dimensions_m, dtype=float)
        self.lower, self.upper = np.asarray(workspace_min), np.asarray(workspace_max)
        if self.dimensions.shape != (3,) or not np.isfinite(self.dimensions).all() or np.any(self.dimensions <= 0):
            raise ValueError('known positive carton dimensions required')
        self.maximum_age_s = maximum_age_s
        self.last: PoseEstimate | None = None

    def observe(self, frame: RGBDFrame, *, now_s: float, expected_on_support=True):
        calibration = self.calibration
        rgb = np.asarray(frame.rgb)
        depth = np.asarray(frame.depth_m)
        if rgb.shape != (calibration.height, calibration.width, 3) or depth.shape != rgb.shape[:2]:
            raise ValueError('image dimensions differ from calibration')
        def missing(reason, pixels=0, plane=None):
            result = PoseEstimate(frame.timestamp_s, None, None, None, None, pixels,
                                  tuple(plane) if plane is not None else None, False, reason)
            self.last = result
            return result
        if not np.isfinite(frame.timestamp_s) or not np.isfinite(now_s) or frame.timestamp_s > now_s+1e-6:
            return missing('invalid_timestamp')
        if now_s-frame.timestamp_s > self.maximum_age_s:
            return missing('stale_observation')
        valid_depth = np.isfinite(depth) & (depth > .01) & (depth < 10.)
        safe_depth = np.where(valid_depth, depth, 0.)
        cloud = unproject(safe_depth, calibration)
        in_workspace = valid_depth & np.all((cloud >= self.lower) & (cloud <= self.upper), axis=-1)
        color = rgb.astype(float)
        brown = (color[:, :, 0] > 1.15*color[:, :, 1]) & (color[:, :, 1] > 1.20*color[:, :, 2]) & (color[:, :, 0] > 25)
        plane = _support_plane(cloud[in_workspace & ~brown])
        if plane is None:
            return missing('support_plane_unobserved')
        foreground = in_workspace & brown & (cloud @ plane[:3]+plane[3] > .008)
        # Mixed RGB edge pixels can carry the occluder's depth. Erode one
        # pixel before fitting so color antialiasing is not treated as a
        # genuine surface measurement of the carton.
        foreground = ndimage.binary_erosion(foreground, structure=np.ones((3, 3)))
        components, count = ndimage.label(foreground)
        if not count:
            return missing('object_unobserved', plane=plane)
        sizes = np.bincount(components.ravel())
        sizes[0] = 0
        selected = components == int(np.argmax(sizes))
        pixels = int(selected.sum())
        if pixels < 60:
            return missing('insufficient_visible_surface', pixels, plane)
        points = cloud[selected]
        points = points[np.linspace(0, len(points)-1, min(len(points), 1800), dtype=int)]
        half = self.dimensions/2
        center = (np.min(points, axis=0)+np.max(points, axis=0))/2
        if expected_on_support:
            center[2] = -(plane[0]*center[0]+plane[1]*center[1]+plane[3])/plane[2]+half[2]

        def residual(parameters):
            x, y, z, yaw = parameters
            c, s = np.cos(yaw), np.sin(yaw)
            rotation = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
            local = (points-np.array([x, y, z])) @ rotation
            offset = np.abs(local)-half
            distance = np.linalg.norm(np.maximum(offset, 0), axis=1)+np.minimum(np.max(offset, axis=1), 0)
            if expected_on_support:
                support = (plane[:3] @ np.array([x, y, z])+plane[3]-half[2])*10
                return np.r_[distance, support]
            return distance

        fits = []
        for yaw in (-.4, 0., .4):
            initial = np.clip(np.r_[center, yaw], np.r_[self.lower, -.78]+1e-6, np.r_[self.upper, .78]-1e-6)
            fits.append(least_squares(residual, initial, bounds=(np.r_[self.lower, -.78], np.r_[self.upper, .78]),
                                      loss='soft_l1', f_scale=.002, max_nfev=120))
        fit = min(fits, key=lambda f: f.cost)
        errors = residual(fit.x)
        rmse = float(np.sqrt(np.mean(errors**2)))
        singular = np.linalg.svd(fit.jac, compute_uv=False)
        if not fit.success or singular[-1] < 1e-6 or rmse > .008:
            return missing('pose_fit_uncertain', pixels, plane)
        covariance = np.linalg.pinv(fit.jac.T @ fit.jac)*float(errors @ errors/max(1, len(errors)-4))
        # Include a 1 mm calibration/noise floor; optimization covariance alone
        # understates systematic sensor and surface-model error.
        standard = np.sqrt(np.maximum(np.diag(covariance)[:3], 0)+.001**2)
        if np.max(standard) > .015:
            return missing('pose_fit_uncertain', pixels, plane)
        result = PoseEstimate(frame.timestamp_s, tuple(fit.x[:3]), float(fit.x[3]), tuple(standard),
                              rmse, pixels, tuple(plane), True, None)
        self.last = result
        return result

    def snapshot(self):
        from dataclasses import asdict
        return {'last': asdict(self.last) if self.last is not None else None}

    def restore(self, state):
        self.last = PoseEstimate(**state['last']) if state['last'] is not None else None
