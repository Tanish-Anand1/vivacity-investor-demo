# Isabella Labs by Vivacity

Live investor demo: [demo.tryvivacity.com](https://demo.tryvivacity.com/works).
The three bounded humanoid tasks and explicit replay passed the production
browser journey on 2026-10-22. See the [release evidence](IMPLEMENTATION_STATUS.md)
for the exact checks and limitations.

The current `/works` source implements three measured MuJoCo humanoid tasks:
G1 parcel placement, Apollo machine service, and H1 short threshold walking.
Trials stream persisted simulator frames while they run, support actual
pause/resume/cancel, compare saved outcomes, and replay only on request. The
[live task frontend contract](FRONTEND_HANDOFF.md) and
[implementation status](IMPLEMENTATION_STATUS.md) record the tested scope and
limits. The H1 policy is pinned to a matching Unitree model and checked against
its TorchScript reference; no hardware behavior is claimed.

Earlier release evidence: [Isabella Labs report](docs/ISABELLA_LABS_REPORT.md).
The staged physical-world editor and measured fulfillment SORT work are documented in
[PHYSICAL_WORK_STATUS.md](PHYSICAL_WORK_STATUS.md), including unsupported stages and
local verification evidence. Check each dated status record before treating a
historical result as current production behavior.
The earlier [robotics visual release](docs/VISUAL_RELEASE.md) documents SPZ
worlds and embedded GLB resources as a separate, historical launch.

Isabella Labs is Vivacity's robotics-first science and experimentation lab. Two
disciplines are executable today: robotic handling using MuJoCo dynamics and
The Invisible Planet, a bounded 2D orbital-inference experiment using SciPy. Visitors
can create worlds, change supported conditions, run independent branches,
inspect measured outcomes, replay, and export. Other scientific fields are
not implemented.

The public `/` route opens **Isabella Labs by Vivacity**. A 7.5-second authored
3D film moves through four robot arms and three humanoid models, then reveals
the robotics-led homepage. It plays on every reload, can be skipped, includes
optional sound, and is omitted for reduced-motion visitors. The film is motion
design, not simulated evidence; it does not start physics. Source, licenses,
rebuild steps, tests, and timing limits are in
[the cinematic handoff](docs/ISABELLA_CINEMATIC.md).
`ENTER THE LAB` opens `/laboratory`, where visitors select a discipline.
`/discovery` generates new orbital observations and fits competing hypotheses
after explicit actions. `/lab` opens the idle robotic laboratory; the visitor
starts the baseline and matched six-trial comparison. Recorded homepage
examples never populate new experiment results.

Regenerate the saved homepage experiment evidence after changing the model or controller with
`.\.venv\Scripts\python scripts\generate_lab_opening.py`; the generator asserts
the measured failure and success before writing the fixture. The audit and
current acceptance evidence are in [docs/DEMO_AUDIT.md](docs/DEMO_AUDIT.md)
and [docs/ISABELLA_LABS_REPORT.md](docs/ISABELLA_LABS_REPORT.md).
Regenerate the orbital preview with
`.\.venv\Scripts\python scripts\generate-isabella-science-preview.py`.

Public UI: [demo.tryvivacity.com](https://demo.tryvivacity.com/).
Backend: [API reference](https://isabella-labs-runtime.onrender.com/docs).

Seven models are implemented: Panda, UR5e, KUKA iiwa 14, Kinova Gen3, xArm7,
analytical educational SCARA and dual Panda (primary-arm execution). Non-Panda
arms use a modeled Panda flange gripper, not a certified hardware mount.
Thirteen environments use actual bounded collision geometry. Ten operations
include pickup, transfer, reaching, seeded manipulation, experimental folding,
rule-based sorting, passive fixture seating, two-body stacking, gravity-assisted
insertion and actuated-door bay loading. Exact limits and API/setup examples are
in [docs/WORLD_WORKSPACE_HANDOFF.md](docs/WORLD_WORKSPACE_HANDOFF.md).

Optional OpenAI and World Labs integrations are separate from the two flagship
experiments and were not exercised in this Isabella release. When configured,
generated/imported meshes use a conservative solid collision proxy beside the
workbench; they are not accurate full-facility digital twins. Provider keys
remain backend-only environment variables or host secret files. The two
flagship experiments work without provider keys.

The product explains both the application and runtime: automation teams can
compare actions before a physical trial, inspect failures, change conditions and
export measured evidence. Business copy does not claim measured ROI or traction.

## Actual simulation

MuJoCo supplies robot and flex dynamics. Pose IK and joint-space planning propose
alternatives; independent branches restore the full integration state. Contacts,
joint limits, grasp retention and supported placement determine success.
Adaptive pickup compares actual physics outcomes within the host budget, then
performs a fresh selected execution. The frontend streams that execution.

Dragging and condition controls update real configuration and invalidate old
results. Object dimensions, mass and friction are bounded by the supported
gripper/workcell. Changed positions can be unreachable or occluded and must fail
honestly. Cloth uses a pre-attached folding bar and fixed hinge; autonomous garment
grasp is not implemented.

The scientific adapter integrates a restricted nondimensional 2D gravitational
model with `scipy.integrate.solve_ivp`, generates seeded noisy observations,
and fits central-only and fixed-perturber hypotheses with
`scipy.optimize.least_squares`. Only training observations enter the fit.
Chronological held-out RMSE and training BIC govern model selection. World
state does not expose the hidden observation-generator mass or central
parameter. This is model comparison, not discovery of a new physical law.

## Run

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-lock.txt
npm ci --prefix frontend
.\.venv\Scripts\python scripts/update-robotics-catalog.py
.\.venv\Scripts\python -m scripts.export_openapi
npm --prefix frontend run generate:api
npm --prefix frontend run build
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-demo.ps1 -NoBrowser -Dev
```

Open `http://127.0.0.1:5173/`. For separate terminals, run
`python -m uvicorn vivacity.api:app --host 127.0.0.1 --port 8000` and
`npm --prefix frontend run dev`. Use one backend worker. `VITE_API_BASE_URL`
selects the API; `VIVACITY_CORS_ORIGINS` must allow the exact UI origin.
Never place API keys in frontend environment variables.

## Verify and integrate

```powershell
$env:OPENBLAS_NUM_THREADS='1'; $env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'
.\.venv\Scripts\python -m scripts.test_backend -q --junitxml=artifacts/verification.xml
.\.venv\Scripts\python -m scripts.demo --base-url http://127.0.0.1:8000
```

Current executed results: [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
OpenAPI: [openapi.json](openapi.json). REST/WebSocket/geometry/replay integration:
[FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md). The Linux workflow executes the full
suite in the deployment image and separately checks the 512 MB host limit.
Old release artifacts are historical.

Render Free has ephemeral SQLite and can cold-start; uptime polling cannot
guarantee availability or durability. The public host limits pickup to eight
actual trials; the default local runtime permits up to 5,000. A previous hosted
[5,000-trial audit](docs/PHYSICS_5000_VARIED_AUDIT.md) is retained as history, not
a claim that every public UI run executes 5,000.

Session capabilities protect session-owned worlds and WebSockets. Standalone
worlds/imports remain public demo data; account authentication, comprehensive
abuse limits, durable paid hosting and hardware execution remain outside this
demo. Attribution: `assets/PROVENANCE.md` and the Menagerie Panda Apache 2.0 license.
