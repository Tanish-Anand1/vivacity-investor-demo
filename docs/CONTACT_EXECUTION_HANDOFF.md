# Contact execution research handoff

This is an opt-in local research slice, not the completed Physical Truth release.
The existing `/works` UI and historical humanoid endpoints remain unchanged.
Do not connect the new table scene to the historical stand geometry.

## Run and verify

From the repository root, in PowerShell:

```powershell
python -m pip install -r requirements-lock.txt
$env:VIVACITY_EXPERIMENTAL_CONTACT_TASKS = '1'
$env:VIVACITY_DATABASE = 'data/contact-research.sqlite3'
python -m uvicorn vivacity.api:app --host 127.0.0.1 --port 8192
```

In a second terminal:

```powershell
python -m scripts.verify_contact_http --base-url http://127.0.0.1:8192
python -m scripts.verify_bimanual --nominal 20 --held-out 100
python -m scripts.render_contact_evidence
```

Without the environment flag, capabilities report `enabled: false` and execution
endpoints return 503. Loading capabilities never creates a trial. The experimental
constrained controller has not passed task acceptance; the default controller is
the stationary native position-servo contact baseline.

## Contract

Base: `/v1/robotics/contact`. All trial operations require the same
`X-Workspace-Token` capability (32–128 ASCII letters, digits, `_` or `-`). Keep it
in browser-owned storage, send it as a header, and never place it in a URL or log.
Other owners receive 404. Capability discovery is public.

| Method | Path below base | Operation |
| --- | --- | --- |
| GET | `/capabilities` | Experimental status and native parameter definitions |
| POST | `/experiments` | Validate and queue an independent native world |
| POST | `/apollo-door-experiments` | Queue the experimental Apollo latch-and-door primitive through the same worker |
| GET | `/experiments?limit=20` | Owner-scoped saved trials, newest first |
| GET | `/experiments/{id}` | Persisted state, measured progress and outcome |
| GET | `/experiments/{id}/frames?cursor=0&limit=32` | Ordered committed frames; maximum page size 64 |
| POST | `/experiments/{id}/pause` | Request pause; wait up to ten seconds for acknowledgement |
| POST | `/experiments/{id}/resume` | Continue an acknowledged paused state |
| POST | `/experiments/{id}/cancel` | Cooperative cancellation, retaining measured frames |
| GET | `/experiments/{id}/checkpoint` | Latest committed full-state checkpoint metadata |
| GET | `/experiments/{id}/scene` | Exact compiled geometry, native model hash and world version |
| GET | `/experiments/{id}/meshes` | Little-endian float32 vertices and uint32 indices; verify manifest SHA-256 |
| POST | `/experiments/{id}/fork` | Independent continuation from latest or named checkpoint |
| POST | `/compare` | Two to four owner-scoped result records, without inventing a ranking |
| GET | `/experiments/{id}/replay` | Terminal trace, only fetched when the visitor requests replay |
| GET | `/experiments/{id}/export` | Terminal JSON report, frames and checkpoint metadata |

Create a nominal trial:

```json
{
  "schema_version": "vivacity.contact-request/1",
  "task": "g1_stationary_bimanual",
  "config": {
    "source_xy_m": [0.32, 0],
    "destination_xy_m": [0.40, 0],
    "parcel": {"mass_mode": "mass", "mass_kg": 0.5,
               "dimensions_m": [0.18, 0.18, 0.16], "sliding_friction": 0.8},
    "seed": 7
  }
}
```

POST returns 202 with a `vivacity.checkpoint-job/1` record, a generated `id`,
`status: queued`, and no result. IDs and measurements in examples must be taken
from that response. There are no predetermined successful branches.

Fork with `{}` or `{"checkpoint_id":"<owned checkpoint id>"}`. The fork retains
its parent reference and world version, receives private simulator/controller
instances, and starts its own frame sequence at zero. It currently continues the
same intervention. Parameter changes use a **new trial/configuration**, preserving
the previous result; arbitrary mid-run configuration edits are not implemented.

Compare with `{"ids":["<original id>","<fork id>"]}`. Results report whether world
versions match. They retain parameters and measurements even when worlds differ.

Frames have this structure (shape only, not fabricated measurement values):

```text
{
  schema_version: "vivacity.checkpoint-frames/1",
  id, status, steps_completed, current_phase, partial_measurements,
  frames: [{seq, frame: {time_s, qpos, body_transforms,
                         phase, measurement, steps_completed,
                         grasp_constraint_active: false, ...}}],
  next_cursor
}
```

Request the next page using `next_cursor`. Do not infer motion beyond received
frames. `pausing` is a pending request; `paused` means the checkpoint and the
displayable final frame have been committed and physics/controller state is
frozen. Terminal statuses are `completed`, `failed`, `cancelled`, `interrupted`.
`completed` requires the task evaluator to pass; solver or restore errors never
produce successful substitute animation. A restart resumes a compatible committed
state. Incompatible task/controller/simulator versions become `interrupted`.

Select `task: "g1_constrained_carton"` to test the new native-actuator constrained
controller. Its failed nominal acceptance run is retained; it is experimental.
The default API task remains the independently measured native-servo baseline.
`partial_measurements` is the latest measurement object (for example `support`
and `destination_error_m`), whereas terminal `result.measurements` contains the
whole task ledger with `last_measurement` and aggregate counters.

The new contact interface uses HTTP cursor polling, not a new WebSocket protocol.
The existing general experiment WebSocket contract is unchanged. `/contact-lab`
implements live polling, pause/resume/cancel, fork, history, comparison, explicit
replay, export and changed-condition trials. The three-engine journey passed at
`f3d9817`, including actual WebGL2, network interruption, cancellation and direct
final-frame history loading. Each changed physics revision still requires a new
integration pass. Loading the route makes read-only requests only.

### Apollo door research through the shared contract

`POST /v1/robotics/contact/apollo-door-experiments` accepts a versioned request:

```json
{"schema_version":"vivacity.apollo-door-request/1","config":{
  "cabinet":{"front_x_m":0.75,"latch_stiffness_n_m":300},
  "tooling":{"finger_force_n":40},"opening_angle_rad":0.25,"seed":7}}
```

Omitted nested fields use validated model defaults. The experimental flag and
owner token requirements are identical to the G1 route. The response is a
`vivacity.checkpoint-job/1` record with `task: apollo_door_primitive`; use its ID
with the existing status, frames, pause, resume, cancel, checkpoint, scene,
meshes, fork, compare, replay and export endpoints above. Frames contain actual
MuJoCo body transforms, phase and mechanism measurements. Results explicitly set
`cabinet_service_complete: false`, even when the latch-and-door primitive passes.
Opening requests up to 1.2 rad are accepted as experiments, but the wide-opening
controller has not passed acceptance. A failed wide request remains a failed run;
it never substitutes the verified 0.25 rad partial goal. No cabinet control is
exposed in the current visitor UI.

## Geometry and physical meaning

Native coordinates are right-handed, Z-up, metres. Body transforms are **world**
transforms; do not apply the native body hierarchy a second time. Quaternions are
`[w,x,y,z]`; Three.js accepts `(x,y,z,w)`. Geometry-local rotations and positions
must come from the same compiled model. The model SHA-256 identifies that binary.

The scene contains the licensed G1 with articulated hands, a physical table and
a free carton. It has zero equality constraints. Object motion comes from contact
forces, gravity and integration. IK writes only independent planning scratch
state; execution issues actuator commands.

The scene API reads the persisted compiled model binary. Geometry records carry
body IDs, local position, `quaternion_wxyz`, MuJoCo half-sizes, RGBA, collision
masks and mesh IDs. Mesh ranges specify byte offsets and scalar counts. Vertices
are little-endian float32 triples; faces are little-endian uint32 indices.
The browser verifies the mesh-buffer SHA-256 before constructing geometry and
applies received world body transforms without duplicating the body hierarchy.
The static preview is explicitly a native keyframe; it never starts physics.

Local UI command (after starting the API above):

```powershell
cd frontend
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8192'
npm run dev -- --port 5186
# Open http://127.0.0.1:5186/contact-lab
npx playwright test --config playwright.contact.config.ts
```

Configure `VIVACITY_CORS_ORIGINS=http://127.0.0.1:5186` on the local API.
Use separate processes for offline acceptance and browser checks on small PCs.
The hosted browser workflow uses the built frontend and its real HTTP proxy.

Dimensions are full lengths. In mass mode, resizing preserves mass and changes
inertia; density mode changes mass with volume. Custom inertia is validated for
positive principal moments, triangle inequalities and bounded mass distribution.
Contact parameters map to native MuJoCo `friction`, `condim=6` and positive-format
`solref`. There are no independent static/dynamic friction or restitution controls.

The tested held-out envelope is deliberately small: source X 0.315–0.325 m,
source Y ±0.005 m, destination X 0.395–0.405 m, destination Y ±0.005 m, mass
0.4–0.6 kg and sliding friction 0.7–0.9; dimensions remain 0.18×0.18×0.16 m.
Broader request bounds allow failure experiments, not guaranteed successful grasps.

## Persistence, limits and backup

Each frame batch, matching full `mjSTATE_INTEGRATION` checkpoint and job progress
commit in one SQLite transaction. A content-addressed native model binary includes
model configuration; controller/FSM/RNG/perception/ledger/cursor fields accompany
the state. The new service shares the existing single humanoid executor. Its
persistent queue admits two nonterminal trials, with 12 starts per owner/hour and
24 per network admission key/hour. A trial is limited to 15,000 physics steps and
120 seconds of measured initialization/step computation. Paused time is excluded.
An acknowledged pause has a fifteen-minute lease; expiry cancels the trial,
retains its evidence, and releases the queue. The response exposes its deadline.
Checkpoint I/O and scheduling latency are not included in that compute metric.
Admission also reserves 150 MB below a 3 GB database/WAL budget. These are research
defaults, not a complete app-wide abuse or retention audit.

The JSON export is **not** a portable simulator: the compiled model artifact stays
in SQLite. A consistent database backup includes it. Run:

```powershell
python -m scripts.sqlite_backup backup data/contact-research.sqlite3 data/contact-backup.sqlite3
# Use the checksum returned by the backup command, and a new destination:
python -m scripts.sqlite_backup restore data/contact-backup.sqlite3 data/contact-restored.sqlite3 --sha256 <returned-sha256>
```

Backups use SQLite's online backup API; restore verifies checksum and integrity
and refuses to overwrite an existing database. Persistent disk, production
capacity, maintenance draining across all legacy services, and 24-hour soak remain
release gates. No new paid resources or production deployment are implied here.

## Experimental cabinet layout parameters

`POST /v1/robotics/contact/apollo-door-experiments` accepts independently bounded
`config.cabinet.old_tray_surface_height_m` and
`config.cabinet.replacement_tray_surface_height_m`, in metres, from 0.75 to 1.05
(both default to 0.99). Each height rebuilds that tray's pedestal, support slab
and collision walls before execution. The replacement cartridge starts on its
configured support; the old-cartridge destination measurement follows its tray.
The cartridge seat inside the cabinet remains at its original height.

These parameters describe physical layout, not a promise that the controller
can service every layout. Invalid values return 422 before a job is queued.
The configuration, compiled model hash and source identity are retained with
the experiment. A layout change requires a new world; neither tray can move
during task execution. Native causality coverage is in
`test_tray_height_rebuilds_supports_initial_cartridge_and_measured_destination`.
