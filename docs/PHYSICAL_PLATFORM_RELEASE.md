# Physical experimentation workspace release

2026-10-13. Public application: https://demo.tryvivacity.com/

Backend source `2406287595081632cc4e879d5667d9a95add3014`, Render deployment
`dep-db7402gu01pc73c6i860` (live, 54.1 s deployment). Frontend source `c51305d`,
Vercel deployment `dpl_5acrDVL7FUE9AVE6tse9aNk47xGb`. The canonical domain and
`vivacity-investor-demo.vercel.app` point to this frontend. Hosting remains Free;
no account/payment/compute upgrade was performed.

## What changed

Native MuJoCo physics settings now persist in world snapshots and saved
configurations: gravity, fluid density/viscosity/wind, blunt drag coefficient,
contact damping ratio, gripper actuator force scaling and constant object force
and torque. Scene settings are applied before compilation and model hashing;
shared compiled models are never mutated. Applied inputs survive full integration
state forks and native rollout chunks.

Eight illustrative contact presets: steel, aluminium, rubber, wood, plastic,
glass, concrete and cardboard. Presets set sliding, torsional and rolling friction
and use six-dimensional contacts. Custom mode preserves the previous controller
and coefficients. Mass stays independent. Reference material density does not
override an explicit mass or certify the inertia of a physical hollow object.

Inspection frames include actual object mass, principal inertia, COM, position,
linear/angular velocity, applied force/torque, contact points/world force vectors,
joint state/actuation, native solver settings and object mechanical energy.
Native contact/force solutions can precede displayed geometry by one 2 ms
timestep. The inspector reports the conservative sample interval ending at the
state time; it does not claim an exact substep timestamp for every execution path. Mechanical object energy is not motor electrical energy.
Contact force vectors act on the second named geometry.

Optional overlays show those measured vectors, COM, robot collision geometry
and a recorded object trajectory. Normal view stays clear. Vector lengths are
scaled/capped; labels explain units, direction and provenance. Arrow materials
are disposed when frames change; shared Three.js geometry is retained.

The instrument layout has a minimal side navigation, central world, contextual
object/robot/experiment inspector, camera presets, elapsed native time, and actual
execution controls. Load/reload stays idle. Results now include an actual current
runtime experiment even when it started from the preloaded, unsaved workcell.
Stale experiment inputs come from branch snapshots rather than the changed world.

Worlds has Explore / Generate / Import. The two curated thumbnails are actual
captured colored environments. Other previews project their actual typed box
collision geometry and explicitly label that simplification. Existing real
OpenAI → World Labs generation displays stages and a validated specification.
Import now validates and previews uploaded triangles before accepting/saving a
collision mapping. Preview material omission and conservative proxy limitations
are explicit. Embedded GLB materials remain available in the saved world.

## Executed evidence

Linux deployment-image suite: **235 passed**, zero failed/errors/skipped, across
three disjoint file shards: 55 / 67 / 113 tests, 61.662 / 147.745 / 592.854 s.
Separate **512 MiB** image checks: **3 passed**, 42.869 s. Exact source verification:
https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38411812860

Windows changed-area regression: **75 passed**, 201.10 s. Final new physics tests:
**22 passed**, 2.39 s. Frontend: **19 transport/recovery checks + 5 selection checks
passed**; TypeScript/Vite and Vercel production build passed. Remaining warnings:
large existing Three/Spark chunks and Starlette TestClient deprecation.

Public real-request verification, `artifacts/physical-platform-public.json`:

- 8/8 numerical benchmarks, 4,600 native steps, 0.363 s benchmark compute wall time.
- Three full rubber/air validation trials, followed by actual fresh execution.
- Successful bilateral grasp, lift, retention, release and table-supported placement.
  Final goal error **0.001069 m**, maximum object height **0.176800 m**, native
  execution duration **14.062 s**.
- 250 replay frames, 246 frames containing measured positive object contact forces;
  serialized replay **2,644,622 bytes**. Inspection increases replay payload size.
- 12 actual WSS events. HTTP goes through the frontend's same-origin `/runtime`;
  WSS connects to Render directly with capability subprotocols.
- World revision change invalidated the previous result. Two new weak-grip trials
  both measured `dropped_object`; no feasible result was fabricated.
- Complete public request journey **59.605 s** wall time. Experiment
  `bb71f261-13a1-40fa-ab18-a7326da8afd0`; hosted records can expire after restart.
- Public OpenAPI matches both exported specifications exactly (50 paths).

Local real HTTP/WSS probe also passed, 13.633 s, 250 frames / 12 WSS events.
The first local probe used the public origin against the local socket and was
correctly rejected with 403. The client origin was corrected; CORS was not widened. Local preview also logged
temporary connection refusals during the intentional local server restart; it
recovered after startup. These were not public production failures.

Browser acceptance includes native pause/resume, changing material/air, measured
inspection, overlays, actual import preview/save and clean JavaScript error logs.
Public UI evidence is saved with this release's screenshots and acceptance report.
Saved-run comparison: baseline 60 g/custom contact, 3/3 successful validations,
49.42 s wall; changed 90 g/rubber/air, 2/3 successful validations, 72.79 s wall
(including user pause). Both fresh executions succeeded. Older inputs/results
remain distinct and the invalidated baseline is marked stale. UI export:
894,913 bytes, 53 real inspection frames, 155 integration-state values; every
frame contains computed object mechanical energy. A 390 px emulated viewport
had document width 390 px, keyboard focus was visible, and camera presets worked.
The higher-level viewport override did not apply in this browser; CDP device
emulation was used and then fully cleared. No hardware screen reader or physical
phone acceptance is claimed.

## Numerical validation definitions

Executed MuJoCo mechanisms: RK4 free-fall position/velocity, static support force
`mg`, flat-box Coulomb sliding, small-angle uniform-rod pendulum, native inertia-box
quadratic drag against its analytical velocity, an ellipsoid wind intervention
against a separately executed vacuum control, and identical-state repeatability.
Reports retain numerical errors/tolerances, initial conditions, model hashes,
MJCF where analytical, solver settings and engine version. A failed benchmark
returns `benchmark_failure`, not an attractive success label.

Verified current references:
[MuJoCo fluid-force models](https://mujoco.readthedocs.io/en/latest/computation/fluid.html),
[World Labs quickstart](https://docs.worldlabs.ai/api),
[OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
The provider request/retrieval implementations were preserved; this release did
not spend credits on another complete World Labs generation. Existing generated
assets were rendered; automated provider contracts were rerun in the full suite.

## Implemented versus incomplete

| Capability | Status and practical boundary |
|---|---|
| Independent robot dynamics, contact pickup, parallel trials, replay, invalidation | Implemented; actual native execution covered by the suite and public probe |
| Seven robot models / compatible grippers | Existing tested models retained; only parallel jaws and the dedicated folding fixture are available |
| Rigid bodies, gravity, configurable forces and torque | Implemented in native rigid pickup tasks; bounded inputs |
| Air / wind / drag | Implemented native phenomenological fluid models; analytical drag and controlled wind tested |
| Buoyancy / CFD / air collision fields | Not implemented or claimed |
| Contact materials and rolling friction | Native contact parameters; illustrative presets, not calibrated pairs |
| Separate static/dynamic coefficients / exact restitution | Not provided by this UI model; one Coulomb coefficient and contact damping are explicit |
| Mechanical object energy | Computed from mass, inertia, measured velocities and gravity; no robot electrical energy |
| Falling, settling, sliding, pendulum | Benchmarked under stated cases; not arbitrary scene certification |
| Dynamic stacking / actuated machine-bay door | Existing bounded operations retained; tested suite, not new live acceptance for every combination |
| Conveyors, moving platforms, rotating machinery | Not implemented as configurable environment systems |
| World generation / import / library | Existing actual pipeline retained, new staged import and navigation verified |
| High-fidelity curated environments | Two actual colored worlds; eleven other presets remain simplified workcells |
| Collision twin reconstruction | Not implemented; generated/imported appearances use explicit conservative mappings |
| New UR3e/UR10e/ABB / vacuum / adaptive / three-finger systems | Reference/unsupported; not marketed as simulation-ready |
| Link calibration / manufacturer acceleration envelopes | Not certified; controllers use existing modeled dynamics and checks |
| Configurable arbitrary initial object orientation | Not added; measured quaternion transforms remain in native frames |
| Sensor realism | Existing semantic depth-ray experiment; no real-camera perception claim |
| Cloth / dual-arm coordination | Fixture-assisted pre-attached cloth; primary-arm dual-Panda execution, not autonomous bimanual grasping |
| Accounts / durable production history / unlimited concurrent work | Browser capabilities; Free host storage is ephemeral, separate experiments queue |
| 5,000 public iterations / always-on uptime | Not claimed; public full-physics budget remains eight trials and Free hosting can sleep |
| Real-world calibrated readiness | None; no measured hardware calibration supplied |

## Reproduce

From `P:\VIVACITY\DEMO-` in PowerShell:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_physical_platform.py -q
npm --prefix frontend run test:api
npm --prefix frontend run test:templates
npm --prefix frontend run build
.venv/Scripts/python.exe -m scripts.export_openapi
npm --prefix frontend run generate:api
.venv/Scripts/python.exe scripts/verify_physical_platform.py --base https://demo.tryvivacity.com/runtime --websocket-base https://vivacity-runtime.onrender.com --output artifacts/physical-platform-public.json
```

The last command executes actual hosted jobs. Keep credentials and browser
capabilities out of commits, URLs and frontend bundles. Follow the existing setup
and API handoff for local server startup and WebSocket ownership.

Next useful work: durable always-on hosting once billing is available; measured
real hardware/material calibration; more actual curated environments; orientation
planning and independently validated end effectors. Preserve the tested state
contract rather than adding unsupported catalogue entries.
