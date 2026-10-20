"""Record reproducible MuJoCo trials for the interactive homepage preview.

The cinematic opening reveals the homepage scene. Visitors can inspect these
recorded states there. The laboratory starts new backend runs from the same
configuration; this file is never used as a live experiment result.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vivacity.factory import FactoryBackend, FactorySettings
from vivacity.factory_controller import FactoryFault, ProductionController


OUTPUT = ROOT / "frontend/src/generated/labOpening.json"
BASE = FactorySettings(
    name="Grip-force laboratory",
    seed=19,
    carton_count=1,
    carton_start_y_m=-0.4,
    carton_mass_kg=0.06,
    carton_friction=0.8,
    realtime_speed=8,
    gripper_force_scale=0.008,
).model_dump()
VISIBLE = {"target", "shuttle", "hand", "left_finger", "right_finger"}


def compact_frame(frame):
    def rounded(values):
        return [round(float(value), 5) for value in values]

    return {
        "time": round(frame["time"], 4),
        "phase": frame.get("phase", "initial"),
        "carton_half_size_m": frame["carton_half_size_m"],
        "body_transforms": [
            {
                "name": body["name"],
                "position": rounded(body["position"]),
                "quaternion_wxyz": rounded(body["quaternion_wxyz"]),
            }
            for body in frame["body_transforms"]
            if body["name"] in VISIBLE or body["name"].startswith("link")
        ],
    }


def record(force):
    config = BASE | {"gripper_force_scale": force}
    backend = FactoryBackend()
    world = backend.create_world(config)
    frames = []
    events = []
    last_phase = None

    def capture(_, phase):
        nonlocal last_phase
        if phase != last_phase or controller.steps % 200 == 0:
            frame = backend.observe(world)
            frame["phase"] = phase
            frames.append(compact_frame(frame))
            last_phase = phase

    controller = ProductionController(
        backend, world, on_frame=capture, on_event=events.append, pace=False
    )
    initial = backend.observe(world)
    initial["phase"] = "initial"
    frames.append(compact_frame(initial))
    try:
        metrics = controller.run()
        status, failure_kind, detail = "completed", None, None
    except FactoryFault as error:
        status, failure_kind, detail = "failed", error.kind, str(error)
        metrics = {"cartons_sorted": controller.sorted, "simulation_steps": controller.steps}
    final = backend.observe(world)
    final["phase"] = "final"
    frames.append(compact_frame(final))
    return {
        "condition": "weak_grip" if force < 1 else "full_grip",
        "status": status,
        "failure_kind": failure_kind,
        "detail": detail,
        "gripper_force_scale": force,
        "model_sha256": world.model_hash,
        "metrics": metrics,
        "frames": frames,
        "events": [{"time_s": round(event["time_s"], 4), "kind": event["kind"]} for event in events],
    }


def main():
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    trials = [record(0.008), record(1.0)]
    assert trials[0]["status"] == "failed" and trials[0]["failure_kind"] == "dropped_object"
    assert trials[1]["status"] == "completed" and trials[1]["metrics"]["cartons_sorted"] == 1
    payload = {
        "schema_version": "vivacity.lab-opening/1.0",
        "source": "recorded_mujoco_physics",
        "purpose": "recorded homepage preview only; live results come from the backend",
        "generator": "scripts/generate_lab_opening.py",
        "config": BASE,
        "trials": trials,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    OUTPUT.write_bytes(encoded)
    print(json.dumps({
        "file": str(OUTPUT),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
        "trials": [{"condition": trial["condition"], "status": trial["status"],
                    "failure_kind": trial["failure_kind"], "frames": len(trial["frames"]),
                    "steps": trial["metrics"]["simulation_steps"]} for trial in trials],
    }))


if __name__ == "__main__":
    main()
