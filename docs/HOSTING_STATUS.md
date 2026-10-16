# Current workspace release — 2026-10-13

Backend source `ffa94fa`, Render `dep-db6r55gm7kps73b1kecg`, frontend source
`f2e5bb9`, Vercel `dpl_3X97ztxZvBMeBaCfr3ZUa9YaZKVc`. Both provider
credentials are mounted in a Render secret file, excluded from source/builds.
Production-image verification passed 198 tests in 693.269 s; its 512 MiB
checks passed two tests in 56.547 s. Public OpenAPI matches the export. Real UR5e HTTP/WSS/replay/invalidation flow
passed in 79.795 s; its initial job took 37.404 s. Seven models completed native
pickup under a real 512 MiB container limit (two checks passed in 54.767 s).
Free compute and ephemeral SQLite remain unchanged; continuous uptime and
cross-deployment persistence cannot be guaranteed. See IMPLEMENTATION_STATUS.md
and WORLD_WORKSPACE_HANDOFF.md for actual evidence and limitations.

Historical release evidence follows.

# Render hosting verification — 2026-10-13

## Current robotics templates release

Backend source `2bf89e761a9023c6df655e805c4424d581faf8c6` passed
[Linux verification](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38318104071):
156 passed, zero errors/failures/skips, 930.151 s. The separate 512 MB container
check passed one test in 52.580 s. Both retain the dependency warning.
Render deployed this source as `dep-db6me8e7bikc73ai2g50`. Public `/health`
advertises only MuJoCo robot/cloth adapters; the catalog has five entries per
category; retired science and unsupported hardware requests return 422.
The public OpenAPI matches both exported files. Real WSS delivered eight events
for a deliberate 100 ms timeout diagnostic with 50 integrated steps and matching
replay. This diagnostic is not a successful pickup claim.

Vercel production `dpl_8NukzFtw5CvbBjm6rtGPgXN6CWgV` serves
https://demo.tryvivacity.com/ from frontend source `12ee3aa`. The picker fix
disables unsupported hardware/tasks and selects compatible pairings. Five
selection tests, two catalog tests, live world loading, persisted mass changes,
390 px reflow and a fresh public HTTP/WSS timeout/replay diagnostic passed.
The backend source and hosting tier are unchanged. The frontend's actual
TypeScript/Vite build passed. In the earlier template-release verification,
public warehouse loading stayed idle; its five
validation trials succeeded, followed by a freshly measured physical execution.
Backend pause/resume and JSON download were tested, with no captured public
browser errors. Selected validation: 6,055 steps, 12.11 simulated seconds,
1.0712 mm placement error. Displayed job completion was 231.38 wall seconds,
including a pause between 134.98 and 208.65 s. Free CPU makes physical execution
substantially slower than simulated time.

The service remains Render Free: ephemeral storage, limited shared CPU and
possible cold starts. Uptime polling does not establish uninterrupted
availability. Paid durable hosting is not activated. Final cloth/mobile evidence
and limitations are in IMPLEMENTATION_STATUS.md. Earlier releases below are
historical.

The final public cloth run also completed: three actual validation rollouts and
fresh selected execution, 0.9234 mm alignment error, 100% vertex coverage,
2,758 steps and 112 frames in the selected validation export. The displayed
job wall time was 475.60 s. Public mobile at 390 px had 375 px content width,
no horizontal overflow, one actual canvas and no scene text. Public browser
errors remained empty. Numerical and screen evidence is summarized in
`artifacts/templates-public-summary.json`.

## Adaptive tabletop release

Private backend source `03532631c58a2fadaebe17f3e862298b15184dfc`
passed the [Docker workflow](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38311644414):
**155 passed, one warning in 353.54 s**. The separate 512 MB host check
passed **one test, one warning in 53.25 s**, including an adaptive pickup
and fresh authoritative physical execution. Local TypeScript/Vite build
passed; the Three.js vendor chunk still produces a size warning.

This release removes scene overlays, expands dragging to the physical table,
adds independent object dimensions/mass/friction and adaptive physical
search with grasp yaw, seeded IK retries and joint-space RRT. The earlier
local bounded-drag checks and measured model-property checks are described
in `docs/ADAPTIVE_PICKUP.md`. OpenAPI and client declarations are regenerated.

Render activated this source as `dep-db6lh3ff3r2c73crqm4g` and reported
**Deploy succeeded | Live**. Vercel production deployment
`dpl_FEym83gapwyL5EeSyPTnfoqY2kuY` was followed by the final loading/error
placement correction, `dpl_EHwp139FoB9QFLYqEi9p5J6DpaaR`. Its TypeScript
and Vite build passed and it is aliased to `https://demo.tryvivacity.com/`.
A temporary stalled browser connection was
recovered before activation.

Public OpenAPI includes the adaptive request contract. An actual public API
world accepted independent half-dimensions `[0.022,0.028,0.026]` m, mass
`0.1` kg, friction `0.65` and position `[1.015,0.378,0.027]` m near the far
table edge. Its actual ray scan returned `[1.0125,0.376071]` m from 22,701
rays. Evidence: `artifacts/adaptive-public-api.json`. In the deployed browser,
the ready viewport has one canvas and **empty visible text**. Dimensions,
mass and friction edits applied successfully, and the world remained idle
until Start was clicked. An explicit adaptive run screened 256 distinct
commands, selected a host-bounded set for physical testing and streamed its
measured progress. The public run (`9f0ca9d8-48a1-4d66-828c-bdf1bd725ff8`)
stopped after **five integrated physics trials** at a measured improvement
plateau, with **two feasible results** and recorded dropped-object/grasp
failures. The selected candidate used **180° grasp yaw**, integrated **7,398
steps**, and completed a real grasp, lift, retention, release and placement
with **8.5498 mm** error in **14.796 simulation seconds**. Its export contains
**64 recorded frames**; native trial wall time was **8.5974 s**.
Evidence: `artifacts/adaptive-public-selected-branch.json`.

A separate authoritative execution then succeeded with **8.5 mm** error and
**zero prohibited contacts**. The page recorded Task verified and persisted
the result at **4:07.21** elapsed job wall time. Final production reload
restored that measured result. During loading the viewport had empty visible
text and no canvas; after initialization it had empty visible text and one
canvas. A 390 px mobile check reported no horizontal overflow and empty scene
text. No captured browser console errors occurred. A public drag to the far
table edge produced a new ray estimate `[1.065,0.385]` m and correctly marked
the previous result **World changed · run again**. The tested reachable
`[0.30,0.00]` m setup was restored without starting another job.

Screenshots: `artifacts/adaptive-public-success.png`,
`artifacts/adaptive-public-far-table.png`, and
`artifacts/adaptive-public-mobile.png`. The runtime and frontend disclose
compute-budget stops; this is best measured feasibility, not global optimality
or guaranteed reach over the entire table. Render Free remains subject to its
previous uptime and persistence limitations.

## Tabletop localization release

The [backend release](https://github.com/Tanish-Anand1/vivacity-runtime/commit/43d43f846ada0bbdf85b8e6bd1ab996c3913e380)
is live on Render as `dep-db6keac9v7es73frteeg`. The [deployment-image CI
run](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38305744573)
passed **147 tests, one warning in 199.33 s**; its separate 512 MB host check
passed **one test, one warning in 36.08 s**. Frontend Vercel production
deployment `dpl_4VxYmJkgbBUcKBRVHMcEZhM8LZLQ` passed TypeScript and Vite
builds. A scoped copy fix for the paused sensor readout passed another local
TypeScript/Vite build and was released as final deployment
`dpl_5UcnkRedkS5VnN8GrvmBNH83bLJT`, aliased to
`https://demo.tryvivacity.com/`. Reloading that URL restored the changed
workcell, sensor estimate, and stale-result message. The production JS asset
contains the corrected execution-time sensor status.

The public API created a fresh pickup world at cube center `[0.20,0.40,0.026]`
m. Its actual MuJoCo ray response reported `8,181` rays, `25` cube hits,
estimated XY `[0.203125,0.400000]` m, and `0.003125` m localization error.
In the deployed browser, the initial cube estimated `[0.503,-0.150]` m;
dragging toward the arm mount caused a new world state with estimated
`[0.152,-0.160]` m and 30 cube ray hits. The page returned to **Ready to
start** without automatically submitting an experiment. Subsequent settings
changed the center to `[0.20,0.40]` m and the public readout recomputed
`[0.203,0.400]` m. The explicit experiment then evaluated **8/8 independent
physics trials** as feasible. A separate authoritative run finished with
physical pickup and placement, **2.0 mm** final error and **zero prohibited
contacts** at 5:19 elapsed wall time. Another public drag changed the readout
to `[0.428,-0.380]` m and marked the completed result **World changed · run
again**. No browser console errors were captured. Details and screenshots are
in `docs/PERCEPTION_DEMO.md`.

This is simulator semantic-depth localization of a dynamic cube, not an RGB
camera or real-world perception system. Sensing coverage spans a bounded
tabletop and reachable manipulation is not guaranteed everywhere. The Render
Free service is subject to idle restarts and ephemeral SQLite storage; the
five-minute uptime checks are monitoring, not an availability guarantee.

## Uptime monitoring release

Render deployed backend source `a133a56ea7d51f48303e8690633b08af2b4a98b1`
as `dep-db6hm2c9v7es73ffs8vg`. Docker CI passed **139 tests** and the separate
512 MB lab check passed **one test**. Public `HEAD /health`, `GET /health`, and
frontend HEAD returned HTTP 200. [UptimeRobot](UPTIME_MONITORING.md) now checks
the frontend and backend every five minutes with the existing email alert
contact. Both monitors reported **Up** after their first checks. This
mitigates idle sleep; Render Free still offers no continuous
uptime guarantee or durable SQLite storage.

## Current bounded-drag and validation release

Backend `8cfa7fcd60e5acd01f1075d59eec5de2e2a03212` is live as Render
`dep-db6fie2jnfac73djg6ag`. The deployment-image workflow completed **139
passed, one warning in 352.77 s**; the 512 MB lab check completed **1 passed
in 55.83 s**. Vercel `dpl_E7CdpcAXC29sJyiMBNAg5E5wdnzD` is ready on
both public aliases; both served HTTP 200 and `/assets/index-CykectX7.js`.
The production build passed TypeScript and Vite checks. `/health` returned
MuJoCo 3.15.0, SciPy 1.18.1 and an eight-trial pickup limit.

On the public backend, the exact formerly rejected 60 mm scene with pickup
`[0.5,-0.15,0.031]` and placement `[0.5,-0.05,0.031]` returned HTTP 200
and world revision 1. In the public browser, dragging the cube changed the
pickup center to approximately `[0.64,0.09]`; applying the exact 60 mm scene
also succeeded. Setting placement on top of pickup displayed a short 10 cm
message and disabled Apply. The initial page remained idle until Start.
Desktop and mobile pointer drags, boundary clamping, invalid-drop reversal,
and stale-result indication also passed against the local runtime. The public
browser emitted no captured errors; existing Three.js deprecation warnings
remain. The public browser then submitted an explicit experiment after
restoring the standard 50 mm cube scene: **8/8 measured physics trials were
feasible**, followed by a separate authoritative physical pickup and placement
with **1.7 mm** goal error and **zero prohibited contacts**. The result was
persisted at event time **4:08.25**; the page showed Task verified. A subsequent
public cube drag rebuilt the world and changed the result status to **World
changed · run again**, retaining the old cards only as stale history. The
browser still had zero captured console errors. The following section
describes the preceding release.

The same public site also completed its four-cycle SciPy Discovery lab after
this release. The final cycle compared actual central-only and additional-mass
fits: both held-out RMSE values displayed about **0.00168**, while the
complexity-penalized training BIC favored central-only (**72.2 vs 76.8**).
The page reported that extra mass was not sufficiently supported and showed
the computed predictions and residual panel. Earlier cycles in the same
live event log favored the perturbed model when its held-out error was lower;
the final result was not hardcoded to always select one hypothesis.

## Current configurable pickup release

Render deployment `dep-db60ej0473hc73clmuo0` runs backend commit
`e4d6d2c4f0ad23c4d34c32bd0751a19d3af1c704`. Its Docker CI passed
**138 tests** (225.85 s) and the constrained-memory lab check **1 test**
(41.74 s). Vercel `dpl_w1tHiBqKWM4bzNmso4iWnjtVXETQ` built successfully
and aliases both `https://demo.tryvivacity.com/` and
`https://vivacity-investor-demo.vercel.app/` (same built asset, HTTP 200).
Public `/health` reports
`max_physics_trials: 8`; public OpenAPI confirms `cube_half_size` 0.02–0.03 m.

An actual public-browser run set a 60 mm cube, applied the physical scene,
submitted eight backend trials, observed **8/8 feasible**, and watched the
independent authoritative execution finish with **1.7 mm** placement error,
**zero prohibited contacts**, and a persisted result. The page showed backend
trial events and no captured console errors. The frontend requests up to 5,000
trials in its build, then limits each session to `/health` capacity. Thus the
current public host runs eight, not 5,000, per visitor. The prior hosted 5,000
audit was a separate backend Docker run with 2 GB of memory. Free hosting
remains non-durable and can sleep; no paid plan was activated.

The rest of this document records earlier deployments and historical evidence.

## Current verified native-import release

Backend source `69013a8f6b538398a042a4f862638aac50865f20`, Render deployment
`dep-db5s8hks728c738sccf0`, live 22:46 IST. Linux Docker **135 passed**, zero
failed/skipped, **351.494 s**; 512 MB smoke **one passed, 56.313 s**. Vercel
`dpl_9kYzmrxJgMi2mLFmB8fAX8a1bBEX` serves both public aliases with explicit
Render API and eight-trial build settings. No paid service or disk was activated.

Public Orbital import/probe/configure/native-three-trials/fresh-execution/export/
geometry/mobile/reload journey passed ten checks: 426 actual live frames, ten
events, no page errors or axe violations in the tested scope. Cargo delivery
error **1.717717 mm**, **30,757 steps**, wall **169.474161 s**, CPU **25.381585 s**.
Record: `artifacts/orbital-public.json`. Fixed local workcell benchmark **20/20**.
Windows bounded-thread suite: **134 passed, one Linux-only skip, 408.16 s**;
unrestricted Windows deadline failures remain recorded. Full current handoff:
`docs/FINAL_VERIFICATION.md`, `docs/ORBITAL_HANDOFF.md`.

Final camera-only frontend follow-up passed **12 public checks**, including
native blocked-reactor recomputation and invalidation without auto-start.
`artifacts/orbital-public-final.json`: 428 frames, 17 events, successful job wall
179.380164 s, CPU 26.848431 s, unchanged 1.717717 mm delivery error. The blocked
job produced **three actual collision failures, 128 steps each**, no selected
branch, 5.440279 s wall. No successful result was fabricated.

The remaining sections retain prior-release detail where their source differs.

Public UI: https://demo.tryvivacity.com/ and https://vivacity-investor-demo.vercel.app/.
Backend: https://vivacity-runtime.onrender.com/. API: https://vivacity-runtime.onrender.com/docs.

Render service `srv-db5p7pjbc2fs739lnl6g`: Oregon, Docker Free, 0.1 CPU / 512 MB.
No paid compute, disk or workspace upgrade was activated; the unrelated suspended
`vivacity-api` service was untouched. The $100 credits did not waive Render's
payment prerequisite: the normal upgrade returned `Plan requires payment information on file`.
The user reported a declined debit card; its issuer's reason is unknown. No card
information was collected and no payment gate was bypassed.

This is a limited demo deployment, **not always-on production hosting**.
[Render Free](https://render.com/docs/free) sleeps after 15 idle minutes and can
need 50 seconds or more to wake. Local SQLite data disappears on restart, redeploy
or sleep. Download experiment exports while running. No keep-alive loop is installed.
Cold-start reconnection, sustained reliability and concurrent public load are not guaranteed.

## Release

- Backend revision: `2f6138927442906e989e105b9539f00f190d8ee7` in https://github.com/Tanish-Anand1/vivacity-runtime.
- Render deployment: `dep-db5r3v0473hc73c4cen0`, verified Live.
- Frontend: `dpl_7YERMyaXLpNcZQb614HXCsUnuY8F`, https://vivacity-demo-1gy0o4jjw-tanishs-projects-66633ee2.vercel.app/.
- Both public aliases use that frontend compiled against Render. Layout/styles/scene were preserved.
- Exact CORS origins are the two public frontend origins. One Uvicorn process, one simulation worker, numerical thread pools set to one.
- `VIVACITY_IMMUTABLE_MODEL_FORKS=1`, `VIVACITY_MAX_PHYSICS_TRIALS=8`,
  `VIVACITY_MAX_PICKUP_WALL_SECONDS=300`; frontend `VITE_PHYSICS_TRIALS=8`.
  Real-time execution remains enabled. The host deadline changes wall time only,
  not simulator stepping, physical limits, contacts or the chosen command.

Each public pickup runs eight real independent physics trials and then executes the
selected successful command again in a fresh state. Oversized requests return
422 before allocating worlds/jobs; no silent replacement of a requested 5,000.
Live guard proof: `artifacts/render-host-guard.json`. Local/default paid budgets
remain 5,000; cloth screens 5,000 proposals and validates three in physics; science
fits two hypotheses. No hardcoded winners or prerecorded simulation outputs.

## Memory correction

Render confirmed the original instance exceeded 512 MB at 19:27 IST and restarted.
Repeated later jobs returned 502 and lost records. Fork compilation duplicated
large Panda meshes; repeated world compilation also accumulated allocator pages.
The opt-in constrained profile shares read-only compiled geometry while each branch
owns independent `MjData`, controls, full integration state, action and configuration.
At most two pristine compiled layouts are retained **without MjData**. Repeated world
creation restores pristine initial state instead of recompiling meshes or returning
advanced state. A new layout clears old cache entries before compilation; active
worlds retain their model references. Garbage collection and Linux allocator trimming
release unused allocations. Weak references retain no active worlds. Instrumented
native models do not replace ordinary models in the active-world registry.

Geometry changes compile new models. The default profile keeps separate model
objects; direct model mutation is unsupported under the opt-in immutable profile,
so use the environment API. MJCF, hashes, controllers, solver and state formats
were preserved. This follows MuJoCo's [read-only model / independent data pattern](https://mujoco.readthedocs.io/en/stable/programming/simulation.html#multi-threading).

## Executed tests

Latest [Linux workflow](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38152910776):
**125 passed**, zero failures/errors/skips, JUnit **314.099 s** in the actual Docker
image. Separate `--memory=512m --memory-swap=512m` run: **1 passed, 56.502 s**,
with two consecutive eight-trial pickups plus fresh execution, three cloth
validations plus fresh execution, and two SciPy fits with nonzero integration calls.
Reports: `artifacts/render-deadline-linux/backend-linux.xml`, `host-memory.xml`.
This proves the tested sequential memory-limited journey, not Render throughput
or unrestricted traffic. One upstream Starlette TestClient deprecation remains.

Windows pristine-cache fork regression: **3 passed, 3.233 s**, exact restore,
independent data, seed and pristine repeated creation (`render-cached-forks.xml`).
API host-limit regression: **2 passed, 0.89 s**. Strict TypeScript and Vercel build passed.

Failed checks are retained: first shared-model revision failed two existing default
model-object-isolation assertions; opt-in sharing preserves those tests. Earlier
Windows run: 114 passed / 5 failed; scoped run: 22 passed / 1 timeout. Later full
Windows run: **120 passed / 3 failed**, JUnit 1058.127 s, worker-completion deadlines
for host smoke, 16-trial paused completion and two-cycle pickup. Cause was not
isolated; latest full suite was verified on Linux, not successfully rerun on Windows.
Reports: `render-memory-backend.xml`, `render-memory-regression.xml`, `render-final-backend.xml`.

The earlier 5,000-trial audit is **local fixed-scene evidence** in
`artifacts/physics-5000.json`. A later, separate 5,000-trial varied audit
completed in the backend Docker image on a GitHub-hosted 2 GB runner, with
measured live logs and a persisted artifact; see
`docs/PHYSICS_5000_VARIED_AUDIT.md`. The 512 MB Render Free service still
supports only eight trials per public request. General cloth grasp acquisition, generalized
pickup detours, native execution of imported robots and distributed durable workers
remain incomplete. Cloth uses an actuated Panda, pre-attached bar and hinge; it is
not arbitrary garment grasping. Deterministic planning is labelled correctly.

## Public verification

Actual page: connected, initialized Panda, Ready to start, no experiment on load.
Health: MuJoCo 3.15.0, cloth MuJoCo 3.15.0, SciPy 1.18.1, maximum eight full trials.
OpenAPI snapshot: `artifacts/render-final-openapi.json`.

Older partial attempts remain failures: first reaching run measured collision
failure, planning failure and success at 0.008826829741 m (`render-free-live-api-retry.json`).
Later jobs exhausted memory. `render-bounded-public-pause.json` passed six checks,
299 measured WS frames / 10 events (real Pause/Resume/Stop, frozen state, camera),
then failed 502 during the second run. No partial run is labelled a full pass.

After geometry caching, an actual public UI run passed manual start, actual native
pause/freeze/resume/stop and all eight pickup rollouts (60,475 physics steps), but
the separate selected physical pickup hit the 120-second wall timeout while
holding the cube during transport. This is retained in
`artifacts/render-cached-public-verified.json` as a failed run. The 0.1 CPU service
was unable to finish the selected motion within its 120-second wall budget.
The deployed host setting raises that deadline to 300 seconds, while preserving
real-time execution, full integration stepping, measured contacts and UI controls.
The final live test verified the complete fresh physical result: pickup succeeded
with 0.001749392576 m placement error, grasp/lift/retention/release/table support
all measured, no prohibited contacts, eight full trials (60,475 trial steps),
67,488 total steps and 269.270334 s job wall time / 40.317765 s process CPU.
The selected export contains 61 recorded frames, 416,463 bytes. Public proof:
`artifacts/render-final-public.json`, `render-final-public-branch.json`.

The interrupted first 2f61389 browser run did not persist its final report and
is not counted as a pass. The repeated run passed nine checks including successful fresh pickup, exports
and settings remaining idle, with 851 live frames and 22 events; the composite
run then failed its 30-second click timeout during cloth world initialization.
That report remains **failed**, not a full-suite pass. The separate cloth/science
partition passed eight checks in `render-final-labs-long.json`, with 113 measured
frames, 27 events, zero page errors and zero axe violations in the checked scope.
The earlier six-minute cloth report remains failed. Its successful rerun used
a 15-minute overall client allowance and actual bounded simulator execution.

## Reproduce

```powershell
$env:API_URL='https://vivacity-runtime.onrender.com'
$env:UI_URL='https://demo.tryvivacity.com/'
$env:EXPECTED_PHYSICS_TRIALS='8'
$env:PROOF_PREFIX='render-final-public'
node scripts/check-pause-live.mjs
.venv/Scripts/python.exe -u scripts/demo.py --base-url $env:API_URL --timeout-seconds 600 --output artifacts/render-live-demo.json
$env:UI_URL=$null
$env:BOUNDARY_PROOF_PREFIX='render-final-public'
node scripts/check-public-boundaries.mjs
```

Frontend build: set `VITE_API_BASE_URL=https://vivacity-runtime.onrender.com` and
`VITE_PHYSICS_TRIALS=8` before `npm run build --prefix frontend`.
The paid 1 CPU / 2 GB plus 5 GB disk proposal remains $26.25/month before tax/overages,
in `render.yaml`. It requires a working payment method. Even paid single-instance
hosting has restart/deployment interruptions; no 100% availability guarantee.

