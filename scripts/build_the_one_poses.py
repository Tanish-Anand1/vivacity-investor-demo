"""Author the opening's Panda motion from exact MuJoCo forward kinematics.

This is cinematography source, not a grasp experiment or a dynamics result.
The arm's positions come from joint-space splines between damped least-squares
IK waypoints. The cube is explicitly attached to the hand until release; the
later suspended beat is an intentional time-stop, followed by a gravity arc.

Run from the repository root with ``.venv/Scripts/python scripts/build_the_one_poses.py``.
The generated JSON uses the same body indices as cinematic/generated/panda.json.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import mujoco as mj
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "assets/menagerie/franka_emika_panda/panda.xml"
DESTINATION = ROOT / "frontend/cinematic/generated/the-one-panda-motion.json"
FPS = 60
DURATION = 7.5
CUBE_EDGE = 0.06
# Pad centre: finger-body offset 0.0584 + pad local centre 0.0445.
CUBE_IN_HAND = np.array([0.0, 0.0, 0.1029])
DOWN = np.diag([1.0, -1.0, -1.0])
CLOSED_FINGER = CUBE_EDGE / 2 - (0.0055 - 0.004)
RELEASE_TIME = 2.2
DROP_TIME = 2.82
LAND_TIME = 3.05
GRAVITY = 9.81


def smooth(value: float) -> float:
    """Quintic ease, with zero velocity and acceleration at both ends."""
    x = float(np.clip(value, 0.0, 1.0))
    return x**3 * (x * (6 * x - 15) + 10)


class JointSpline:
    """Clamped cubic spline over seven joint angles, using a small linear solve."""

    def __init__(self, times: np.ndarray, values: np.ndarray):
        self.times, self.values = times, values
        intervals = np.diff(times)
        slopes = np.diff(values, axis=0) / intervals[:, None]
        matrix = np.zeros((len(times), len(times)))
        rhs = np.zeros_like(values)
        matrix[0, :2] = [2 * intervals[0], intervals[0]]
        matrix[-1, -2:] = [intervals[-1], 2 * intervals[-1]]
        rhs[0], rhs[-1] = 6 * slopes[0], -6 * slopes[-1]
        for i in range(1, len(times) - 1):
            matrix[i, i - 1 : i + 2] = [intervals[i - 1], 2 * (intervals[i - 1] + intervals[i]), intervals[i]]
            rhs[i] = 6 * (slopes[i] - slopes[i - 1])
        self.second = np.linalg.solve(matrix, rhs)

    def __call__(self, time: float) -> np.ndarray:
        i = int(np.clip(np.searchsorted(self.times, time) - 1, 0, len(self.times) - 2))
        width = self.times[i + 1] - self.times[i]
        a, b = self.times[i + 1] - time, time - self.times[i]
        return (
            (self.second[i] * a**3 + self.second[i + 1] * b**3) / (6 * width)
            + (self.values[i] - self.second[i] * width**2 / 6) * a / width
            + (self.values[i + 1] - self.second[i + 1] * width**2 / 6) * b / width
        )


def inverse_kinematics(model: mj.MjModel, data: mj.MjData, centre: list[float]) -> np.ndarray:
    """Solve the hand's actual 6-D pose using MuJoCo's body Jacobian."""
    hand = model.body("hand").id
    goal = np.array(centre) - DOWN @ CUBE_IN_HAND
    jp = np.zeros((3, model.nv))
    jr = np.zeros_like(jp)
    for _ in range(500):
        mj.mj_forward(model, data)
        dp = goal - data.xpos[hand]
        error_quaternion, dr = np.zeros(4), np.zeros(3)
        mj.mju_mat2Quat(error_quaternion, (DOWN @ data.xmat[hand].reshape(3, 3).T).ravel())
        mj.mju_quat2Vel(dr, error_quaternion, 1.0)
        if np.linalg.norm(dp) < 1e-7 and np.linalg.norm(dr) < 1e-6:
            return data.qpos[:7].copy()
        mj.mj_jacBody(model, data, jp, jr, hand)
        jac = np.vstack([jp[:, :7], 0.35 * jr[:, :7]])
        delta = jac.T @ np.linalg.solve(jac @ jac.T + 0.003**2 * np.eye(6), np.r_[dp, 0.35 * dr])
        delta *= min(1.0, 0.12 / max(float(np.linalg.norm(delta)), 1e-12))
        data.qpos[:7] = np.clip(
            data.qpos[:7] + delta,
            model.jnt_range[:7, 0] + 0.005,
            model.jnt_range[:7, 1] - 0.005,
        )
    raise RuntimeError(f"Panda IK did not converge: centre={centre}, error={np.linalg.norm(dp):.6g} m")


def export() -> dict:
    model = mj.MjModel.from_xml_path(str(MODEL))
    data = mj.MjData(model)
    data.qpos[:] = model.key_qpos[0]
    hand = model.body("hand").id
    left = model.body("left_finger").id
    right = model.body("right_finger").id
    # Smooth transfer with a small vertical arc. Endpoint spline derivatives
    # are zero; FK is recalculated after every joint sample, never interpolated
    # independently for mesh pieces.
    key_times = np.array([0.8, 1.16, 1.55, 1.9, 2.2])
    targets = [
        [0.48, -0.18, 0.40],
        [0.48, -0.15, 0.51],
        [0.49, 0.03, 0.62],
        [0.50, 0.20, 0.63],
        [0.50, 0.25, 0.60],
    ]
    joints = np.array([inverse_kinematics(model, data, point) for point in targets])
    transfer = JointSpline(key_times, joints)
    retreat = inverse_kinematics(model, data, [0.32, 0.15, 0.70])
    release_centre = np.array(targets[-1], dtype=float)
    floor = float(release_centre[2] - 0.5 * GRAVITY * (LAND_TIME - DROP_TIME) ** 2 - CUBE_EDGE / 2)
    frames = []
    largest_step = 0.0
    largest_joint_step = 0.0
    min_joint_clearance = float("inf")
    max_attachment_error = 0.0
    previous_cube = None
    previous_qpos = None
    max_self_penetration = 0.0
    for sample in range(round(DURATION * FPS) + 1):
        time = sample / FPS
        if time <= key_times[0]:
            data.qpos[:7] = joints[0]
        elif time <= RELEASE_TIME:
            data.qpos[:7] = transfer(time)
        else:
            weight = smooth((time - RELEASE_TIME) / 0.6)
            data.qpos[:7] = joints[-1] * (1 - weight) + retreat * weight
        close = smooth((time - 0.25) / 0.45)
        opening = smooth((time - 2.1) / 0.18)
        finger = 0.04 + (CLOSED_FINGER - 0.04) * close * (1 - opening)
        data.qpos[7:9] = finger
        mj.mj_forward(model, data)
        hand_position = data.xpos[hand]
        hand_rotation = data.xmat[hand].reshape(3, 3)
        attachment = hand_position + hand_rotation @ CUBE_IN_HAND
        cube_position = attachment.copy() if time <= RELEASE_TIME else release_centre.copy()
        cube_quaternion = data.xquat[hand].copy() if time <= RELEASE_TIME else np.array([0.0, 1.0, 0.0, 0.0])
        if time > DROP_TIME:
            elapsed = min(time, LAND_TIME) - DROP_TIME
            cube_position[2] -= 0.5 * GRAVITY * elapsed**2
        phase = "grip" if time < 0.8 else "transfer" if time <= RELEASE_TIME else "time_stop" if time <= DROP_TIME else "fall" if time < LAND_TIME else "settled"
        if time <= RELEASE_TIME:
            max_attachment_error = max(max_attachment_error, float(np.linalg.norm(cube_position - attachment)))
        if previous_cube is not None:
            largest_step = max(largest_step, float(np.linalg.norm(cube_position - previous_cube)))
            largest_joint_step = max(largest_joint_step, float(np.max(np.abs(data.qpos[:7] - previous_qpos[:7]))))
        previous_cube = cube_position.copy()
        previous_qpos = data.qpos.copy()
        min_joint_clearance = min(min_joint_clearance, float(np.min(np.minimum(
            data.qpos[:7] - model.jnt_range[:7, 0], model.jnt_range[:7, 1] - data.qpos[:7]))))
        for contact in data.contact[: data.ncon]:
            max_self_penetration = max(max_self_penetration, -float(contact.dist))
        frames.append({
            "time": round(time, 9),
            "phase": phase,
            "qpos": data.qpos.round(9).tolist(),
            "poses": [[data.xpos[i].round(9).tolist(), data.xquat[i].round(9).tolist()] for i in range(model.nbody)],
            "cube": {"position": cube_position.round(9).tolist(), "quaternion": cube_quaternion.round(9).tolist(), "attached": time <= RELEASE_TIME},
        })
    # These checks protect the rendering contract, not a claim of dynamic grasping.
    assert len(frames) == 451
    assert min_joint_clearance > 0
    assert max_attachment_error < 1e-9
    assert largest_step < 0.05, f"Discontinuous cube: {largest_step} m / frame"
    assert largest_joint_step < 0.1, f"Discontinuous arm: {largest_joint_step} rad / frame"
    assert max_self_penetration < 0.001, f"Visible self-collision: {max_self_penetration} m"
    assert np.isclose(frames[-1]["cube"]["position"][2] - CUBE_EDGE / 2, floor, atol=1e-8)
    visual = json.loads((DESTINATION.parent / "panda.json").read_text(encoding="utf-8"))
    # Compare the supplied render mesh's body-space topology to the native model.
    assert max(item["body"] for item in visual["geoms"]) == model.nbody - 1
    stats = {
        "frames": len(frames),
        "max_cube_step_m": largest_step,
        "max_joint_step_rad": largest_joint_step,
        "minimum_joint_limit_clearance_rad": min_joint_clearance,
        "max_attachment_error_m": max_attachment_error,
        "max_self_penetration_m": max_self_penetration,
        "visual_geometries": len(visual["geoms"]),
        "unique_meshes": len(visual["meshes"]),
        "unique_mesh_triangles": sum(mesh["indices"][1] // 3 for mesh in visual["meshes"]),
    }
    result = {
        "schema_version": "vivacity.cinematic-motion/1.0",
        "provenance": "Authored film; real MuJoCo forward kinematics, attached prop and deliberate time-stop. Not a physics experiment.",
        "model": "franka_emika_panda",
        "model_sha256": hashlib.sha256(MODEL.read_bytes()).hexdigest(),
        "mujoco_version": mj.__version__,
        "fps": FPS,
        "duration_seconds": DURATION,
        "axes": "right-handed, Z up; metres and radians; body transforms in model coordinates",
        "quaternion_order": "wxyz",
        "body_names": [mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, i) for i in range(model.nbody)],
        "hand_body_id": hand,
        "finger_body_ids": [left, right],
        "cube_edge_m": CUBE_EDGE,
        "cube_local_hand_position": CUBE_IN_HAND.tolist(),
        "closed_finger_qpos_m": CLOSED_FINGER,
        "initial_cube_position": targets[0],
        "release_cube_position": release_centre.tolist(),
        "initial_support_surface_z": targets[0][2] - CUBE_EDGE / 2,
        "landing_support_surface_z": floor,
        "cue_times": {"close_start": 0.25, "close_end": 0.7, "move_start": 0.8, "open_start": 2.1, "release": RELEASE_TIME, "drop": DROP_TIME, "land": LAND_TIME},
        "checks": stats,
        "frames": frames,
    }
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    return {"output": str(DESTINATION.relative_to(ROOT)), "bytes": DESTINATION.stat().st_size, **stats}


if __name__ == "__main__":
    print(json.dumps(export(), indent=2))
