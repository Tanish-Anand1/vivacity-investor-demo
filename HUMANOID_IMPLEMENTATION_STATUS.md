# Humanoid lab — probe verification, 2026-10-22

This document records the earlier reach/switch/terrain probes. The separate
stationary G1 pickup-and-placement milestone, its physical assumptions, tests,
and current validation matrix are in
[`docs/HUMANOID_CAPABILITY_AUDIT.md`](docs/HUMANOID_CAPABILITY_AUDIT.md).
The G1 reach probe below remains a failed *probe*, while the newer bounded
pickup action can succeed with a documented contact-gated rigid grasp.

## Working and measured

- `/works` opens the humanoid category and loads a Unitree G1 with hands;
  switching tabs loads separate Apptronik Apollo and Unitree H1 physical
  models. A failed model/mesh load produces a visible error and retry action,
  and the UI checks each geometry manifest against the compiled model hash.
- The robots are distinct licensed MuJoCo Menagerie model descriptions with
  articulated bodies, joints, collision geometry, and visual meshes. The
  generated warehouse, maintenance bay, and terrain course have actual 3D
  collision geometry. Displayed body transforms are recorded from MuJoCo
  state; the frontend does not animate a root path or substitute a video.
- G1 and Apollo arm targets use damped least-squares position IK from the
  compiled scene. Independent jobs start from the model keyframe, use fresh
  `MjData`, apply joint controls, and step physics. Integration state, 41
  replay frames, contacts, measurements, model hash, and outcome are stored
  in SQLite. Replay returns the same recorded frames after the job finishes.
  The UI withholds an older trial's replay when its scene version does not
  match the loaded geometry, while preserving its measured result.
- The browser can vary motion scale, floor friction, G1 parcel mass, and a
  horizontal disturbance. Each submit runs another bounded physics job.
- The Apollo **momentary switch** probe produced actual hand/handle contact
  and a hinge deflection exceeding the measured threshold. This validates
  one nominal simulated interaction, not a general maintenance controller.

The three nominal 2-second jobs below were submitted to a running FastAPI
server through `scripts/verify_humanoid_http.py` on 2026-10-22. The script
also fetched and compared each persisted replay frame array with the job's
result. `compute_wall_s` is the backend's measured physics execution time on
this local machine, excluding HTTP, queue, model compilation, and asset load.

| Model / setting | Actual outcome | Key measurements | Physics compute |
| --- | --- | --- | ---: |
| G1, motion 1.0 | `parcel_not_transported` | 1,000 steps; 122 hand/parcel contact samples; IK residual 0.00476 m; peak parcel height 0.712 m, short of the 0.85 m pickup criterion | 1.01 s |
| Apollo, motion 1.0 | Momentary switch actuated | 400 steps; 2 hand/handle contact samples; hinge 0.315 rad after contact; 0.3 rad threshold reached at 1.765 s; IK residual 0.00053 m | 0.32 s |
| H1, motion 0.6 | `fall` | 1,000 steps; 3,470 foot/terrain contact points counted across steps; peak tangential contact speed 0.903 m/s; minimum base height 0.078 m | 0.70 s |

These are **simulation** results, not hardware validation. The H1 contact
count is a sum over contacts and time steps, not a count of unique feet or
successful steps. Its start stripe is visual-only so it cannot double-count
coplanar contacts with the ground. The code reports a failed task when
conditions are not met.

## Visual acceptance from the actual local browser

| Requested view | Evidence | Status |
| --- | --- | --- |
| G1 standing in warehouse | `artifacts/humanoid-g1-standing-current.png` | Captured |
| G1 touching parcel | `artifacts/humanoid-g1-parcel-contact.png` | Captured; parcel moved slightly but was not grasped or transported |
| Apollo in maintenance bay | `artifacts/humanoid-apollo-standing-current.png` | Captured |
| Apollo contacting switch | `artifacts/humanoid-apollo-switch-current.png` | Captured from successful recorded trial |
| H1 at terrain course | `artifacts/humanoid-h1-standing-current.png` | Captured initial keyframe, not a dynamically stable stance claim |
| H1 traversing terrain | `artifacts/humanoid-h1-fall-current.png` | **Not achieved**; captured the actual fall instead |
| Mechanical detail | `artifacts/humanoid-apollo-mechanical-closeup.png` | Cropped from an actual browser screenshot |

The three full-body silhouettes, limb assemblies, and scene objects were
visually inspected. The worlds are intentionally simple bounded collision
scenes; they are not photorealistic warehouse or factory twins. Surface
materials, ambient occlusion, textures, and terrain detail do not yet meet
the requested simulation-footage quality bar.

## API and reproduction

The versioned schemas are in `openapi.json`; these are the humanoid routes:

```text
GET  /v1/robotics/humanoids/models/{robot_id}
POST /v1/robotics/humanoids/experiments
GET  /v1/robotics/humanoids/experiments?robot_id={robot_id}
GET  /v1/robotics/humanoids/experiments/{trial_id}
GET  /v1/robotics/humanoids/experiments/{trial_id}/replay
```

Experiment requests need `X-Workspace-Token` (32–128 URL-safe characters).
This token groups local trials; it is **not** production authentication.
Example body:

```json
{"robot_id":"apptronik_apollo","action":"attempt_task","duration_s":2,"movement_scale":1,"floor_friction":0.8,"parcel_mass_kg":0.5,"perturbation_n":0,"seed":7}
```

The POST responds `202` with `schema_version`, `id`, `status`, `request`,
`created_unix_s`, `result`, and `error`. Poll the job GET until `completed`
or `failed`. A completed `result` includes `task_success`, `failure_reason`,
`planning`, `measurements`, `scene_geometry_hash`, `initial_frame`, `frames`,
`final_frame`, and `final_integration_state`. Each frame contains `time_s`, `qpos`, `qvel`,
`base_position_m`, `base_quaternion_wxyz`, body transforms, and contacts.
The replay GET is available only after completion.

```powershell
.\.venv\Scripts\python.exe -m uvicorn vivacity.api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm run dev
```

Visit `http://127.0.0.1:5173/works`, select a robot, and press **Run physics
probe**. For the HTTP-only acceptance, run:

```powershell
.\.venv\Scripts\python.exe scripts\verify_humanoid_http.py
```

## Provenance and limits

- Robot assets came from MuJoCo Menagerie commit
  `cda5236f98383f6fbaa4820c6b18dba892cd087f`. The [G1](https://github.com/google-deepmind/mujoco_menagerie/tree/main/unitree_g1)
  and [H1](https://github.com/google-deepmind/mujoco_menagerie/tree/main/unitree_h1)
  assets carry their bundled BSD-style licenses; [Apollo](https://github.com/google-deepmind/mujoco_menagerie/tree/main/apptronik_apollo)
  carries Apache 2.0. Original license files are included next to source and
  exported visual assets. No purchased assets or Cosmos checkpoints were used.
- The original G1 reach probe only reaches and nudges the parcel. The new
  stationary pickup task is separate and does not establish walking or
  shared-world warehouse logistics. The H1 gait probe falls and cannot traverse
  the ramp, steps, or uneven blocks. Apollo's nominal actuation works; robust
  balance and success across varying conditions have not been established.
- Jobs run on one in-process worker with a two-job active cap. SQLite and
  workspace tokens are local-demo mechanisms, not a multi-user production
  identity, rate-limit, or distributed queue. A server restart marks
  interrupted jobs failed; completed jobs remain in SQLite.
- Visual binaries total about 42.7 MB across three robots (Apollo 26.1 MB,
  G1 11.4 MB, H1 5.2 MB). Model and scene compilation and first asset transfer
  add latency beyond the physics compute values above. Slow-network and
  low-memory browsers are not yet qualified.
- This release did not change the homepage, opening film, branding, global
  typography, scientific routes, or existing arm controllers.

## Verification record

- `python scripts/verify_humanoid_http.py`: three real HTTP jobs completed;
  replay arrays matched persisted results; one measured Apollo task success,
  two honest task failures.
- `pytest tests/test_humanoids.py tests/test_v_robotics.py tests/test_api.py tests/test_visual_assets.py -q`:
  36 passed, 1 Starlette/httpx deprecation warning on the first full
  regression run. After the final contact-metric, frame-alignment, and scene
  version changes, `pytest tests/test_humanoids.py -q` passed **9/9** with
  the same upstream deprecation warning.
- `npm run build`: final TypeScript check and Vite production build passed;
  Vite reported existing large Three/WorldPreview chunks.
- Browser: direct `/works` load and reload, G1/Apollo/H1 selection, scene
  load, G1 contact replay, Apollo successful replay and side orbit, H1 fall
  replay, saved history, version-mismatched H1 replay rejection, reset, and
  narrow mobile viewport were exercised.
  No page exception was observed; development logs include upstream Three
  renderer warnings. The production public URL was not changed. A concurrent
  stress run briefly dropped a polling HTTP connection without losing its
  completed trial; the acceptance script now retries transient transport
  errors, and its final isolated three-job run passed.
