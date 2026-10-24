# Physical Truth hardware-transfer package

This is an **offline simulation handoff**, not a tested robot driver. No hardware
transport, manufacturer SDK, safety-rated controller, physical calibration, or
physical robot test is included. The complete Physical Truth release is still
open. Do not interpret a simulated placement or a validated message as hardware
validation.

## Contents and reproducibility

- `g1-carton/manifest.json`: exact native model hash, MuJoCo version, controller
  source hashes, joint order, servo gains, command bounds, torque limits, units,
  initial task configuration and evidence status.
- `g1-carton/manifest.sha256`: hash of those exact manifest bytes.
- `g1-carton/simulated-proprioception.jsonl`: measured joint positions and
  velocities from the successful native simulation, with explicit simulated
  provenance. It is sensor replay data, not a motion command file.
- `vivacity/hardware_transfer.py`: dry-run command validation, explicit arming,
  rate checks, latching watchdog and recording validation. It contains no device
  access and always reports `hardware_command_sent: false`.

Regenerate from an executed, matching controller result:

```powershell
python -m scripts.verify_constrained_carton --output artifacts/physical-truth-runtime/transfer-source.json
python -m scripts.export_hardware_transfer --result artifacts/physical-truth-runtime/transfer-source.json --output hardware-transfer/g1-carton
python -m pytest tests/test_hardware_transfer.py tests/test_wrench_dynamics.py
```

Export refuses mismatched controller hashes, task source, model binary, joint
mapping, or unordered sensor timestamps. Rebuilding a native model requires the
repository's licensed G1 Menagerie assets and the pinned MuJoCo version. A model
hash identifies the exact compiled model; it is not a hardware serial number.

## Coordinates and timing

The simulation world is right-handed, +Z upward, metres and seconds. The nominal
G1 faces +X with +Y to its left. Hinge positions and rates use radians and radians
per second. Body poses in experiment frames are world transforms, not local
parent transforms. Quaternion order is `[w,x,y,z]`; Three.js needs `(x,y,z,w)`.

The RGB-D estimator uses an optical frame with +X right, +Y up and forward along
-Z. OpenCV-style +X right, +Y down, +Z forward converts with `diag(1,-1,-1)`.
Depth values are metric distance along the optical axis. Extrinsics map optical
points into the declared world frame. Never apply the frame conversion twice.

Recorded samples have simulation timestamps and typically 50 ms spacing, with a
final partial interval. They are not a 100 Hz hardware control stream. A future
hardware adapter must establish a monotonic clock mapping, retain sequence
numbers, and account for measured acquisition, network and actuation latency.
Neither wall-clock time nor browser playback time may replace sensor timestamps.

## Calibration procedure to perform before any hardware claim

1. Identify the exact robot revision, finger/tooling revision and firmware. Compare
   every joint name, axis, sign, zero, gear ratio, encoder scale and order with the
   manifest. A matching visual mesh is insufficient.
2. Establish joint zero offsets with the manufacturer's supported procedure. Check
   each joint separately in a supervised, mechanically supported commissioning
   setup. Model limits and gains are simulation data, not certified hardware limits.
3. Measure tool transforms, mass, centre of mass and inertia. Measure the carton,
   support surface and effective contact response. Do not substitute the model's
   assumed friction or stiffness for measured materials.
4. Calibrate camera intrinsics, distortion and depth scale on independent targets.
   Estimate camera-to-base extrinsics, then validate them on held-out poses. Store
   calibration version, measurement date, uncertainty and residuals with recordings.
5. Validate estimator error and missing/occluded/stale observation handling before
   connecting any perception output to motion. The current estimator is a bounded
   known-carton RGB-D baseline; it is not yet the task's control observation source.

The estimator's 1 mm uncertainty floor is a software assumption, not measured
camera calibration. Real calibration data and certified operating ranges are not
available in this package.

## Command limits, watchdog and failure behavior

`DryRunCommandGate` starts disarmed. Arming requires an exact manifest hash,
ordered finite measured positions, and explicit operator acknowledgement. It
rejects wrong-sized vectors, out-of-bounds positions, reversed clocks, duplicate
or reordered commands, excessive position-reference rate, and late commands.

The default watchdog is 100 ms. Expiry latches `disable`; later commands do not
clear the fault. Explicit re-arming is required. The 2 rad/s commissioning rate
ceiling in the manifest is only an offline software limit. It must be replaced by
an approved embodiment-specific envelope before use with a real device.

`disable` is a **dry-run decision**, not a motor command or an assurance that a
humanoid will remain standing. A hardware adapter would need an independent
watchdog, manufacturer-supported fault behavior, a physical emergency stop,
supervision and a supported test setup. This package provides none of those.

The source G1 keyframe places two thumb joints about 0.0028 rad beyond their
command bounds; native joint limits are compliant. Recorded positions are kept
unchanged as evidence. The dry-run gate deliberately refuses to arm from an
out-of-envelope measurement. Commissioning must resolve the model/calibration
difference; do not silently clip recorded measurements or loosen the gate.

## Recorded-sensor replay and supervised progression

First validate the JSONL recording with `validate_sensor_replay(records,
manifest_joint_names)`. Its records must retain `native_mujoco_simulation`
provenance. Use recordings to test observation adapters and timing faults without
hardware. Reordered, stale, missing and nonfinite data must fail closed.

A future supervised transfer should progress through transport-only message
checks, passive sensor recordings, individual supported-joint checks, supported
whole-body posture, low-load contact tests and only then a bounded task. Each step
needs measured limits, logs, an abort procedure and a human approval in the actual
hardware environment. Stop on disagreement between commands, observed state and
the manifest. Do not replay this simulated trajectory directly on a physical robot.

The remaining evidence gaps are explicit: physical model identification, camera
calibration, actual latency, thermal/electrical limits, real contact response,
manufacturer command integration and all physical robot performance.
