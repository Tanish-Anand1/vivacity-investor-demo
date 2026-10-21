# V-Robotics architecture

## Implemented boundary

The first executable V-Robotics program is **precision assembly**: a UR5e arm, a modeled parallel-jaw gripper, a free rigid workpiece, a source tray, and a passive receiving fixture. The other six requested programs are catalogued as `not_implemented`; they cannot be opened as experiments. A model asset or a 3D preview alone does not qualify as a program.

The existing Vivacity runtime owns world creation, state snapshots, independent branches, background experiment jobs, evaluations, SQLite records, events, replay, and branch export. This slice adds a typed program boundary and a persisted-measurement report without replacing those contracts. The browser renders poses and traces returned by the runtime; MuJoCo remains the authority for dynamics and contact.

| Boundary | Implementation | Evidence |
| --- | --- | --- |
| V-WORLD | `RoboticsConfig`, `AssemblySettings`, versioned workcell configuration, MJCF model hash, world revision and seed | `vivacity/schemas.py`, `vivacity/scene.py` |
| V-DYNAMICS | MuJoCo `MjModel`/independent `MjData`, 2 ms physics step, contact and actuator-force sensors | `vivacity/robot_models.py`, `vivacity/native_pick_place.py` |
| V-CONTROL | Damped least-squares pose IK, sampled joint-path collision checks, joint-space RRT fallback, staged position/gripper commands | `vivacity/pick_place.py`, `vivacity/pickup_planning.py` |
| V-EXPERIMENT | Snapshot/fork, bounded candidate search, physics validation, persistence, replay, export and measured result report | `vivacity/runtime.py`, `vivacity/v_robotics.py` |
| V-RENDER | Three.js workcell consumes measured transforms and recorded replay frames | `frontend/src/RobotView.tsx`, `frontend/src/PrecisionAssemblyResult.tsx` |
| V-VERIFY | Pytest, real-run verification script and Playwright browser journey | `tests/test_v_robotics.py`, `scripts/verify_v_robotics.py`, `frontend/e2e/v-robotics.spec.ts` |

World-space coordinates are right-handed, Z-up, in metres; joint angles are radians, mass is kilograms, time is seconds. Geometry and transforms are generated for the same MuJoCo model used for physics. The report exposes the solver version, model SHA-256, timestep, integrator, solver, iteration count, tolerance, gravity vector, state dtype, seed and world revision. The full integration state and configuration are saved for the initial and selected terminal state. Replays are recorded state samples, not fresh physics integrations.

The [NVIDIA Cosmos repository](https://github.com/NVIDIA/cosmos) and [official introduction](https://docs.nvidia.com/cosmos/latest/introduction.html) informed only the **separation of concerns**: world representation, action-conditioned prediction, observations, control, curation and evaluation are distinct layers. Vivacity implements its own typed world and experiment contracts with a conventional physics solver. It installs no Cosmos package, checkpoint or API; it does not claim a world foundation model. No generated video determines a physical result.

The current program is simulation evidence. It is not a hardware controller, safety-rated cell, calibrated digital twin, or validated commercial assembly process. See [Known limitations](KNOWN_LIMITATIONS.md) and the [verification matrix](VALIDATION_MATRIX.md).
