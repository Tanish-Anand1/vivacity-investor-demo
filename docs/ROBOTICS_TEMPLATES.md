# Current compatibility

This document describes the robotics picker. Isabella Labs also includes a
separate SciPy scientific-discovery world at `/discovery`; the picker matrix
below does not apply to it. The source and API contract are documented in
`docs/API.md` and `FRONTEND_HANDOFF.md`.

The older Panda-only availability notes below are historical. Current legacy
catalog tests cover 81 runnable combinations and 1,215 selection interactions:
five catalog arm models across four rigid worlds and four rigid tasks, plus
Panda's dedicated textile fixture. The extended workspace separately exposes
seven implemented models, thirteen environments and ten bounded operations.
See [WORLD_WORKSPACE_HANDOFF.md](WORLD_WORKSPACE_HANDOFF.md) for exact scopes,
provider/import workflows and interfaces. Feasibility remains measured per run;
this compatibility matrix does not assert every trajectory will succeed.

Historical implementation notes follow.

# Robotics template release

At the time of this earlier template release, the public product was
robotics-only and accepted `mujoco` and `cloth`. The 2026-10-21 Isabella Labs
release restored a bounded `scipy` scientific world, its configuration schema,
fixture and tests. The description below is retained as historical context
for the robotics template picker.

The picker has five options in each of three categories. These are workcell
presets and explicitly identified reference templates, not fifteen implemented
robot controllers. `vivacity/templates.py` is the source of truth;
`scripts/update-robotics-catalog.py` exports the frontend catalog.

| Category | Options | Implemented scope |
| --- | --- | --- |
| Arm | Panda, UR5e, KUKA iiwa, SCARA, dual arm | Panda is actuated. Other entries are planned references; server resolution rejects them. |
| World | Industrial workstation, warehouse packing, inspection bench, constrained industrial cell, textile station | Four rigid workcell presets with different object or obstacle conditions; one physical flex folding fixture. |
| Task | Pick & place, obstacle-aware transfer, cloth folding, machine tending, precision assembly | First two use measured pickup physics and contact validation. Cloth is a constrained experimental fold. Machine tending and assembly are planned references. |

Panda × any of the four rigid worlds × either rigid handling task gives eight
runnable combinations. Panda × textile × cloth folding gives the ninth.
Compatibility is checked on the server, not just by disabling a button.
Successful loading creates an idle world. Only Start experiments launches work.
Each loaded template has separate world/session/settings storage keys. Planned
arms and tasks are visible but disabled, with plain availability labels. Choosing
textile or cloth folding selects both; switching to object handling selects a
compatible rigid station. Changing between rigid stations preserves the chosen
handling task. Hardware is never silently substituted or relabeled.

Worlds are simplified task workcells, not complete factories or warehouse
digital twins. Warehouse uses a rigid parcel surrogate; inspection has no
vision inspection; textile has a pre-attached folding bar and fixed hinge.
No autonomous garment grasp, generic hardware controller, machine interlock,
force-guided insertion, real camera perception or real robot execution is
claimed. Template availability means the experiment can run, not that any
arbitrary changed geometry is physically reachable.

Business copy explains where automation teams could use the runtime: compare
actions before a physical cell trial, inspect failures, adjust conditions and
export measured evidence. These are application descriptions, not measured ROI,
customer traction or guaranteed production readiness.

## API

`GET /v1/templates` returns `TemplateCatalog`, version `vivacity.templates/1.0`.
Each option has `id`, `name`, `status`, `technical`, `business` and `scope`.
Status is `available`, `experimental` or `reference`.

`POST /v1/templates/resolve` validates compatibility and returns a versioned
`CreateWorld` request. It does not initialize physics or start a job.

```json
{"arm":"panda","world":"warehouse","task":"pick_place","seed":7}
```

Pass its response unchanged to `POST /v1/worlds`, or use its backend/config in
`POST /v1/sessions` when the user explicitly starts an experiment. Unsupported
hardware/tasks and incompatible pairings return HTTP 422 with an explanation.
Unknown IDs, extra fields and non-finite parameters are rejected by Pydantic.

## Reproduce

```powershell
.\.venv\Scripts\python -m scripts.export_openapi
.\.venv\Scripts\python scripts/update-robotics-catalog.py
npm --prefix frontend run generate:api
npm --prefix frontend run build
npm --prefix frontend run test:templates
$env:OPENBLAS_NUM_THREADS='1'; $env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'
.\.venv\Scripts\python -m pytest tests/test_templates.py -q
```

`test_templates.py` runs all nine combinations through MuJoCo, validates their
measured branches, compares replay frames to executed traces, tests unsupported
combination rejection and verifies Discovery's public removal. Shared runtime
regressions previously using numerical experiments now use real cloth dynamics.
The release's full-suite and live verification evidence belongs in
`IMPLEMENTATION_STATUS.md`; old release counts are historical.
