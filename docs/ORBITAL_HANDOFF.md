# Orbital Salvage: exact frontend contract

The fixture is `fixtures/imports/orbital_salvage_lab.zip`, unchanged from the
user-supplied ZIP. Its manifest is exactly
`{"entrypoint":"Orbital_Salvage_Lab.xml"}`. Source SHA-256:
`6d623c9fbd7aa337b195282f55dbbcc83432ffad69a95090dde2a831a4763354`.

The original three-hinge robot has position actuators but fixed fingers. Its
0.13 m finger gap cannot enclose its 0.21 m cargo; endpoints also exceed its
reachable workspace. A native motion probe proves motion, not grasping.

## Explicit import lifecycle

1. `POST /v1/imports?filename=Orbital_Salvage_Lab_FIXED.zip` with the binary ZIP
   and `Content-Type: application/octet-stream`; 201 `ImportResponse`.
2. `POST /v1/imports/{id}/verify`; 202, status `physics_verifying`. Poll
   `GET /v1/imports/{id}` until `actuation_verified`, `physics_valid` or
   `physics_failed`. Compilation is background work; uploading alone never
   executes native physics.
3. Successful probe exposes `capabilities`: actual joints, actuators, dynamic
   bodies, sites, collision count, state encoding, integration states,
   displacement, steps, simulation time, warnings and isolation method.
   `task_execution_verified:false` describes the original probe.
4. `POST /v1/imports/{id}/configure-task`; 200, `manipulation_configured`,
   `physics_ready:true`, `configured_world_id`. Only this checksum-matched
   supplied fixture has a configured manipulation adapter. A different model
   receives an actionable 422. Repeating configuration returns the same world.
5. Use all existing shared world/experiment APIs with that world ID. Opening
   it does not start an experiment. Example request:

```json
{"candidates":3,"physics_trials":3,"search_candidates":3,"physics_budget":3,"execute_selected":true,"realtime_execution":true,"max_simulation_seconds":40}
```

Submit with `POST /v1/worlds/{world_id}/experiments`, an `Idempotency-Key`, then
poll status and subscribe to `WS /v1/experiments/{id}/live` and `/events`.
Every branch is independently restored. The selected action runs again in
fresh physics. Success comes from its `execution_evaluation`, not selection.

Stop uses `POST /v1/experiments/{id}/cancel`; no video/player controls exist.
Unloading an active Orbital task requests cancellation. Conditions use the
existing environment PATCH and make earlier experiment responses `stale:true`.
Commit/reset/export/replay follow the shared contract in `FRONTEND_HANDOFF.md`.

## Adaptation and geometry

This explicitly replaces the original arm with the validated Menagerie Panda
and its actuated contact gripper. Cargo is a free 0.05 m cube, 0.06 kg. Cargo,
dock and reactor are relocated into/around the Panda workspace. The original
dark deck and rails inform the adapted physical workcell; docking means a
marked region on the physical deck, not a latch or a separate spacecraft.
Gravity is -9.81 m/s², not orbital/microgravity dynamics. The original GLB is
visual data, not a simulated trajectory or a replacement Panda mesh.

`scene_profile:"orbital_salvage"` and `source_import_id` travel in world
configuration and branch exports. The configured default reactor is a
collision-enabled cylinder at `[0.75,-0.4,0.33]`, radius 0.18 m, half-height
0.33 m. Radial X/Y sizes must agree. Cube `[0.5,-0.15,0.026]`, docking target
`[0.5,0.18,0.026]`; goal tolerance 0.025 m, additionally requiring bilateral
contact, lifting, retention, release and measured deck support.

Every measured robot frame includes `environment_geometries`:

```json
{"name":"obstacle_geom","type":"cylinder","position":[0.75,-0.4,0.33],"quaternion_wxyz":[1,0,0,0],"size":[0.18,0.33,0],"rgba":[0.9,0.24,0.06,1]}
```

Values come from MuJoCo, not a separate browser physics engine. Positions are
world-space meters, Z-up; quaternions WXYZ. Boxes use half-extents; cylinders
use radius and half-height. Three.js cylinders/capsules have Y-axis geometry,
so rotate their local geometry 90° about X before the MuJoCo world quaternion.
Render these primitives instead of the default workcell table/obstacle/cube.
Use the existing Panda mesh manifest and actual `body_transforms` for the arm.

`import_provenance` records the source checksum and explicit upgrades in actual
observations and exported recorded frames. Selecting an alternative inspects
its data; it does not substitute a recording into the live viewport.

## Limits

Generic GLB/GLTF imports remain visual-only. Arbitrary MJCF/URDF uploads can
undergo bounded native capability probes on Linux; they do not automatically
gain a manipulation controller. On Windows only the exact trusted fixture is
enabled. Linux uses CPU/address-space/file limits and seccomp denying host
file opens, network sockets, subprocesses, filesystem mutations and io_uring.
This is a restricted demo importer, not a general hostile-code hosting service.
Native plugins, generated flex/composite assets and heightfields are excluded
from probes. The task remains a constrained, terrestrial-gravity benchmark;
blocked layouts can genuinely fail. General obstacle-routing for pickup,
spacecraft dynamics and arbitrary robot-task configuration are incomplete.

Reproduce against a running backend:

```powershell
.venv/Scripts/python.exe scripts/demo_orbital.py --base-url https://vivacity-runtime.onrender.com --output artifacts/orbital-public-api.json
$env:API_URL='https://vivacity-runtime.onrender.com'
$env:UI_URL='https://demo.tryvivacity.com/'
$env:PROOF_PREFIX='orbital-public'
node scripts/check-orbital-live.mjs
```
