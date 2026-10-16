# Vivacity robotics runtime

Current visual release: [VISUAL_RELEASE.md](docs/VISUAL_RELEASE.md) documents
colored SPZ worlds, embedded GLB resources, the simplified workspace and actual
release evidence. Earlier reduced-collider preview descriptions are historical.

The investor demo is robotics-only. Choose or generate a world, select a real
robot and a bounded operation, save its conditions, then explicitly Start.
Loading stays idle. Scientific Discovery remains retired.

Public UI: [demo.tryvivacity.com](https://demo.tryvivacity.com/).
Backend: [API reference](https://vivacity-runtime.onrender.com/docs).

Seven models are implemented: Panda, UR5e, KUKA iiwa 14, Kinova Gen3, xArm7,
analytical educational SCARA and dual Panda (primary-arm execution). Non-Panda
arms use a modeled Panda flange gripper, not a certified hardware mount.
Thirteen environments use actual bounded collision geometry. Ten operations
include pickup, transfer, reaching, seeded manipulation, experimental folding,
rule-based sorting, passive fixture seating, two-body stacking, gravity-assisted
insertion and actuated-door bay loading. Exact limits and API/setup examples are
in [docs/WORLD_WORKSPACE_HANDOFF.md](docs/WORLD_WORKSPACE_HANDOFF.md).

OpenAI provides real structured proposals; World Labs generates real 3D meshes.
Generated/imported meshes use an explicit conservative solid collision proxy
beside the workbench. They are not accurate full-facility digital twins.
Provider keys are backend-only environment variables or a host secret file.
Prebuilt worlds and deterministic experiments work without provider keys.

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
grasp is not implemented. SciPy remains for robotics rotation mathematics.

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
