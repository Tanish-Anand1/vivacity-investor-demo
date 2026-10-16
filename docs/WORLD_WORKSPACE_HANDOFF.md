# World and experiment workspace

This extends the existing runtime. World libraries and saved configurations live
in SQLite; simulation still uses the Runtime/Supervisor and adapter operations.
Loading a configuration initializes an idle world. Only explicit Start creates
a session and submits experiments. OpenAI proposes typed configurations; MuJoCo
measures outcomes. World Labs geometry is never presented as a physics result.

## Available implementations

Seven actual simulation models: Panda, UR5e, KUKA iiwa 14, Kinova Gen3, xArm7,
analytical educational SCARA, and dual Panda. Four added manufacturer models
come from MuJoCo Menagerie with their original licenses/assets. Non-Panda arms
use a modeled Panda gripper flange; these are not certified hardware mounts or
validated manufacturer payload ratings. Dual Panda holds the secondary arm at
rest and executes the primary arm; coordinated bimanual planning is absent.

Thirteen environments: warehouse, factory, robotics lab, automotive cell,
logistics, research, packaging, cleanroom, workshop, desktop, cluttered cell,
quality control, and textile fixture. Rigid scenes use actual bounded MuJoCo
collision primitives around the standard workbench. They are simplified
workcells, not full facility digital twins. The textile choice initializes the
dedicated experimental flex fixture; its preview is an illustrative static
environment specification, not a reconstructed cloth simulation.

Ten operations: contact-driven pick/place; object transfer; pre-grasp reach;
seeded randomized manipulation; experimental fixture-assisted cloth folding;
one-part mass/width sorting; single-component passive fixture seating; one
component stacked on a second dynamic base; gravity-assisted receptacle
insertion; and a part loaded into an actuated-door bay. Assembly does not join
or fasten parts. Insertion is not a tight-tolerance force controller. Sorting
uses supplied simulator properties. Machine tending does not operate a real
production machine. Cloth uses attachment constraints, not autonomous cloth
grasp acquisition. Failures are retained and no best candidate is predetermined.

Object envelope: 40–60 mm side lengths, 20–150 g, friction 0.05–1.5. Arbitrary
poses or every combination are not guaranteed feasible. Failed grasp, IK,
contacts, tracking, joint limits and timeouts remain measured failures. Fixed
and adaptive policies are compute-bounded; no global optimum is claimed.

## Frontend files and commands

Existing React/Vite and Three.js stack is retained. Main surfaces:
`frontend/src/App.tsx`, `WorldLibrary.tsx`, `WorldPreview.tsx`,
`RegistryView.tsx`, `ExperimentSetup.tsx`, `ExperimentLibrary.tsx`,
`workspaceApi.ts`, `useRuntime.ts`, `RobotView.tsx`, and `studio.css`.
The older quick templates and native model verification remain available.

```powershell
.venv/Scripts/python.exe -m scripts.export_openapi
npm --prefix frontend run generate:api
npm --prefix frontend run test:templates
$env:VITE_API_BASE_URL='http://127.0.0.1:8000'
npm --prefix frontend run dev
# separate terminal
.venv/Scripts/python.exe -m uvicorn vivacity.api:app --host 127.0.0.1 --port 8000
```

Production frontend API base: `https://vivacity-runtime.onrender.com`.
Production origin: `https://demo.tryvivacity.com`. Never put provider keys in
VITE variables, browser storage, source files or frontend requests. Browser
storage contains only random workspace/session capabilities and draft state.

## API additions

All paths below are prefixed `/v1/workspace`. Owned routes require
`X-Workspace-Token`, a private random 32–128 character alphanumeric/underscore/
hyphen capability. Generate it with `crypto.randomUUID()` (36 characters),
persist locally, and retain it to access saved private items. This is capability
ownership for a demo, not an account/login/organization permission system.

| Method | Path | Result |
|---|---|---|
| GET | `/capabilities` | Public provider configuration booleans, registry, host limits |
| GET | `/worlds` | Prebuilt plus owned active worlds |
| GET | `/worlds/{id}` | Typed library record and collision specification |
| POST | `/worlds` | Duplicate `{ "source_id": "desktop" }` |
| PATCH | `/worlds/{id}` | Rename `{ "name": "My workcell" }` |
| POST | `/worlds/{id}/archive` | Soft removal |
| POST | `/worlds/{id}/restore` | Undo removal |
| GET | `/worlds/{id}/preview` | Imported/provider triangle preview; primitives use `spec` |
| POST | `/imports?filename=scene.obj` | Raw file bytes; maximum 16 MiB |
| POST | `/imports/{id}/map` | Explicit scale, source up-axis, position and solid AABB proxy |
| POST | `/generations` | Asynchronous provider job; also requires `Idempotency-Key` |
| GET | `/generations`, `/generations/{id}` | Actual persisted job stages and costs |
| POST | `/generations/{id}/retry-retrieval` | Resume existing failed operation; no new paid generation |
| POST | `/configurations/resolve` | Validated world/session request; does not start work |
| POST | `/configurations` | Save validated configuration |
| GET | `/configurations`, `/configurations/{id}` | Owned saved inputs |
| POST | `/configurations/{id}/runs` | Explicit Start; returns session plus its private capability |
| GET | `/runs` | Actual saved inputs, sessions, experiment evaluations and metrics |
| POST | `/operations/interpret` | Real OpenAI bounded operation proposal; never starts physics |

Request examples (optional fields omitted use server defaults):

```json
{"prompt":"A compact workshop with a clear central workbench and shelving along the back wall.","provider":"worldlabs","seed":7,"model":"marble-1.0-draft"}
```

```json
{"name":"Imported workshop","scale":0.5,"position_m":[2.5,2.5,0.5],"up_axis":"y"}
```

```json
{"name":"UR5e repeatable pickup","environment_id":"desktop","robot_id":"ur5e","gripper_id":"panda_parallel","operation_id":"pick_place","seed":7,"target_position":[0.5,-0.15,0.026],"destination_position":[0.5,0.18,0.026],"object_half_sizes":[0.025,0.025,0.025],"object_mass_kg":0.06,"object_friction":1,"trial_mode":"fixed","validation_trials":3,"randomization_cycles":1,"realtime_speed":1}
```

Save response shape: `{ "schema_version":"vivacity.saved-configuration/1.0",
"id":"<id>", "configuration":{...}, "created_unix_s":<number>,
"sha256":"<digest>", "deleted":false }`.

Start body: `{}`. Start response: `{ "session":{...},
"session_token":"<private capability>" }`. Use `X-Session-Token` for existing
session/world/experiment routes. Session creation begins a real background job;
do not POST on mount, effect cleanup, navigation or automatic reconnect.
Heartbeat with GET `/v1/sessions/{id}` while participating. Pause/resume/stop
use POST `/v1/sessions/{id}/pause`, `/resume`, `/stop` with the same capability.
Run-start HTTP retries are not idempotent; query history before retrying an
ambiguous response. Generation retries ARE idempotent under a retained key.

Generation status vocabulary: `queued`, `interpreting`, `generating`,
`receiving`, `completed`, `failed`. Events include stage, actual timestamp and
message. Poll every 2.5–5 seconds. `operation_id` exists only after provider
submission; `provider_cost_credits` is null until reported by World Labs.
No estimated progress percentages or fabricated thumbnail/video are used.

## Live transforms, sockets and replay

MuJoCo uses meters, seconds, radians, a Z-up frame and quaternion ordering
`[w,x,y,z]`. Three.js quaternions need `[x,y,z,w]`. Set `camera.up=(0,0,1)`.
`body_transforms` is an array of named bodies with measured `position` and
`quaternion_wxyz`. A robot mesh is expressed in its owning body frame; apply
that body's measured transform exactly once. `environment_geometries`
contains actual geom position/quaternion, MuJoCo type, half sizes and RGBA.
Boxes use twice the reported size. Cylinder size is radius/half-height, axis Z.
`qpos` length includes gripper/object/fixture coordinates; never assume seven
arm joints. SCARA has a prismatic coordinate measured in meters. Tracking
diagnostics separate `max_tracking_error_rad` and `max_tracking_error_m`.

Compiled geometry assets: Panda at `/vivacity/robot-geometry.json` and
`/vivacity/robot-meshes.bin`; others at
`/vivacity/robots/{ur5e,iiwa,gen3,xarm7,scara,dual_arm}/robot-geometry.json`
and `robot-meshes.bin`. Companion `robot-preview.json` files contain genuine
initialized states for catalog inspection, not recorded successful experiments.
Load geometry from the selected robot ID. `RobotView.tsx` implements mesh
index/offset parsing and actual measured body updates.

For owned jobs use:

```javascript
const base = 'wss://vivacity-runtime.onrender.com';
const protocols = ['vivacity.live', `vivacity.token.${sessionToken}`];
const live = new WebSocket(`${base}/v1/experiments/${experimentId}/live`, protocols);
const events = new WebSocket(`${base}/v1/experiments/${experimentId}/events?after=0`, protocols);
```

Live messages have `schema_version`, `experiment_id`, `world_id`, `sequence`,
`stage`, `frame`, `timestamp_unix_s`. `frame` contains actual simulator state and
phase. Latest-only delivery handles slow consumers; it is not a full audit
trace. Event messages have `schema_version`, `seq`, `kind` and `details`.
The details contain the actual stage/message and available timestamps; the
experiment identifier is in the subscribed URL. Reconnect events using the last delivered `seq` as
`after`. Sockets close normally at a terminal job state. Unknown capability or
disallowed Origin fails authorization. Use existing `useRuntime.ts` HTTP polling
fallback for interrupted sockets. Complete schemas are in `openapi.json`
including `x-websockets` and `frontend/src/generated/api.d.ts`.

GET `/v1/experiments/{id}/replay` returns measured `branches[].frames` plus
evaluations/action/performance. Branch JSON download at
`/v1/experiments/{id}/branches/{branch_id}/export` includes full initial/final
integration state, parent reference, command stages, seed and configuration
hash. Replay is recorded physics, not an MP4. Committing requires a successful
current revision. Environment changes invalidate older results; reproduce with
a new run, preserving the old evidence. The previous handoff documents the
stable Runtime world/experiment endpoints in more detail.

## Providers, imports and operational limits

OpenAI uses Responses structured JSON (`gpt-4.1-mini` default), validated server
schemas and explicit unsupported scopes. World Labs uses documented Marble
`worlds:generate`, operation polling, then world asset retrieval. Both keys are
loaded server-side via env or `/etc/secrets/server-secrets.json`. That file is
configured in Render and excluded from Git. The shared public demo bounds paid
generation to four requests per rolling day and custom interpretation to twenty.
Failed retrieval preserves the provider operation; it never automatically
resubmits paid generation. Supported asset hosts and public DNS are checked;
downloads carry no keys, cookies, ambient proxy or automatic redirects.

Normal uploads: GLB/static embedded GLTF, OBJ, STL or scoped manifest ZIP;
16 MiB, bounded decoded geometry. Native MJCF/URDF inspection/isolated Linux
verification remains separate and does not grant arbitrary robot controllers.
World Labs collider retrieval has a separate 64 MiB bound, bounded source
accessors and a deterministic reduced display mesh. Full source bounds are
retained for the solid collision proxy. Original source hashes are recorded.
Materials, textures, Gaussian splat rendering, animated/skinned/extension-heavy
GLTF and USD are not supported. Concave imported rooms use an explicitly
declared solid AABB, not automatic accurate room collisions. An imported room
proxy is initially placed beside the workbench to avoid enclosing the arm.

SQLite persistence is real, but Render Free's filesystem is ephemeral across
redeploys/restarts. Free compute can sleep; uptime checks cannot guarantee
continuous availability. No paid hosting upgrade was made. Report downloads are
the durable user-controlled export. Accounts, access revocation, cross-device
identity, production queues, persistent disk and long-term monitoring remain
future production work. Energy is null because energy accounting is absent;
reported steps, timings, residual errors and success rates are measured.


## Executed release verification

Backend source `ffa94fa` passed all 198 production-image tests (693.269 s)
and both 512 MiB capacity checks (56.547 s). UR5e HTTP/WSS/replay/geometry
invalidation and fresh numerical recomputation passed against the public host.
The full journey took 79.795 s; its first experiment took 37.404 s. Live KUKA
UI pickup verified three validations and fresh execution in 51.480 s. Its
exported report, pointer drag, stale-result feedback and recomputation worked.

```powershell
.venv/Scripts/python.exe -m scripts.verify_workspace_live --base https://vivacity-runtime.onrender.com --output artifacts/workspace-public-http-ws.json
# On a interrupted verification, retain the ignored data/workspace-live-*.json
# capability file and use --resume; never commit it.
.venv/Scripts/python.exe -m pytest -q
```

Evidence, performance and explicit incomplete features are in
IMPLEMENTATION_STATUS.md. A green build is not the verification boundary:
exercise the custom domain and actual HTTP/WSS/physics flow after a release.
