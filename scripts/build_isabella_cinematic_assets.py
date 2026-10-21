"""Compile licensed MuJoCo meshes and authored kinematic poses for the opening film.

These poses are motion-design source material, not simulated experiment outcomes.
The release uses the pre-rendered film; these large intermediate files are not
shipped to visitors. Pass a checkout of google-deepmind/mujoco_menagerie.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import mujoco as mj
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARM_MODELS = {
    "panda": ROOT / "assets/menagerie/franka_emika_panda/panda.xml",
    "ur5e": ROOT / "assets/menagerie/universal_robots_ur5e/ur5e.xml",
    "iiwa": ROOT / "assets/menagerie/kuka_iiwa_14/iiwa14.xml",
    "xarm7": ROOT / "assets/menagerie/ufactory_xarm7/xarm7_nohand.xml",
}
HUMANOID_MODELS = {
    "unitree_g1": "unitree_g1/scene.xml",
    "unitree_h1": "unitree_h1/scene.xml",
    "berkeley_humanoid": "berkeley_humanoid/scene.xml",
}


def _pose(model: mj.MjModel, data: mj.MjData, name: str, fraction: float) -> list[list[list[float]]]:
    data.qpos[:] = model.qpos0
    if model.nkey:
        data.qpos[:] = model.key_qpos[0]
    for joint_id in range(model.njnt):
        if model.jnt_type[joint_id] not in (mj.mjtJoint.mjJNT_HINGE, mj.mjtJoint.mjJNT_SLIDE):
            continue
        joint_name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_JOINT, joint_id) or ""
        addr = int(model.jnt_qposadr[joint_id])
        if name in HUMANOID_MODELS:
            if any(piece in joint_name.lower() for piece in ("shoulder", "elbow", "wrist")):
                magnitude = 0.32 if "shoulder" in joint_name.lower() else 0.22
            elif name == "berkeley_humanoid" and any(piece in joint_name for piece in ("HFE", "KFE")):
                magnitude = 0.08
            else:
                continue
        else:
            magnitude = 0.24 if model.jnt_type[joint_id] == mj.mjtJoint.mjJNT_HINGE else 0.025
        phase = joint_id * 0.59 + (0.7 if "right" in joint_name.lower() else 0)
        delta = magnitude * math.sin(math.pi * fraction) * math.sin(math.pi * 1.5 * fraction + phase)
        value = float(data.qpos[addr]) + delta
        if model.jnt_limited[joint_id]:
            lo, hi = map(float, model.jnt_range[joint_id])
            value = min(hi - 0.001, max(lo + 0.001, value))
        data.qpos[addr] = value
    mj.mj_forward(model, data)
    return [[data.xpos[i].round(5).tolist(), data.xquat[i].round(5).tolist()] for i in range(model.nbody)]


def export(name: str, source: Path, destination: Path) -> dict:
    model = mj.MjModel.from_xml_path(str(source))
    data = mj.MjData(model)
    blob = bytearray()
    meshes = []
    visible_geoms = [i for i in range(model.ngeom) if model.geom_group[i] == 2 or (name == "xarm7" and model.geom_group[i] == 0 and model.geom_type[i] == mj.mjtGeom.mjGEOM_MESH)]
    used_meshes = sorted({int(model.geom_dataid[i]) for i in visible_geoms if model.geom_type[i] == mj.mjtGeom.mjGEOM_MESH})
    for mesh_id in used_meshes:
        va, vn = int(model.mesh_vertadr[mesh_id]), int(model.mesh_vertnum[mesh_id])
        fa, fn = int(model.mesh_faceadr[mesh_id]), int(model.mesh_facenum[mesh_id])
        vertices = np.asarray(model.mesh_vert[va : va + vn], dtype="<f4")
        indices = np.asarray(model.mesh_face[fa : fa + fn], dtype="<u4")
        position_offset = len(blob)
        blob.extend(vertices.tobytes())
        index_offset = len(blob)
        blob.extend(indices.tobytes())
        meshes.append({"id": mesh_id, "positions": [position_offset, vn * 3], "indices": [index_offset, fn * 3]})
    geoms = []
    for i in visible_geoms:
        mat = int(model.geom_matid[i])
        rgba = model.mat_rgba[mat] if mat >= 0 else model.geom_rgba[i]
        geoms.append({
            "body": int(model.geom_bodyid[i]),
            "mesh": int(model.geom_dataid[i]) if model.geom_type[i] == mj.mjtGeom.mjGEOM_MESH else None,
            "type": mj.mjtGeom(int(model.geom_type[i])).name.removeprefix("mjGEOM_").lower(),
            "position": model.geom_pos[i].round(5).tolist(),
            "quaternion": model.geom_quat[i].round(5).tolist(),
            "size": model.geom_size[i].round(5).tolist(),
            "rgba": rgba.round(4).tolist(),
        })
    manifest = {
        "model": name,
        "source": str(source),
        "schema_version": "vivacity.cinematic-geometry/1.0",
        "mujoco_version": mj.__version__,
        "meshes": meshes,
        "geoms": geoms,
        "poses": [_pose(model, data, name, i / 12) for i in range(13)],
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / f"{name}.json").write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    (destination / f"{name}.bin").write_bytes(blob)
    return {"model": name, "visual_geoms": len(geoms), "mesh_bytes": len(blob)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menagerie", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "frontend/cinematic/generated")
    args = parser.parse_args()
    result = []
    for name, source in ARM_MODELS.items():
        result.append(export(name, source, args.output))
    for name, relative in HUMANOID_MODELS.items():
        result.append(export(name, args.menagerie / relative, args.output))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
