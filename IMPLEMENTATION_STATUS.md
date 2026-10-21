# Isabella Labs robotics-first interface release — 2026-10-21

The current frontend opens with a 7.5-second, skippable brand film: three
authored robot-arm silhouettes give way to two humanoid silhouettes, then the
identity fades into the already-mounted homepage. These figures are brand
illustrations, not simulated hardware. Reduced-motion visitors go directly to
the homepage; a visitor can also skip with the button or Escape. The homepage
leads with an actual saved robotic workcell, a measured weak-grip failure and
full-grip delivery, and direct paths into the working robotics and scientific
labs. It never starts an experiment on load. The consumer interface uses
Instrument Sans, Manrope and restrained IBM Plex Mono from Google Fonts and
does not display the simulator vendor name in its ordinary routes.

This release changed frontend presentation and navigation, not the physics
backend or its API. The existing Explore/Research progression, world library,
condition controls, numerical lab, replay and export remain operational.
The generated homepage fixture came from `scripts/generate_lab_opening.py`;
selecting a saved condition does not create a new job. New experiments still
run through the backend after an explicit visitor action.

Actual local release checks: TypeScript and Vite build passed; frontend unit
checks passed **5 template + 4 settings + 19 API = 28 tests**. The complete
Chromium suite passed **12/12 in 3.4 minutes**, covering timed intro, desktop
and mobile accessibility, direct routes, world entry, configuration changes,
real robotic failure and six independent comparison trials, replay, SciPy
inference, stale results, export and recovery. The opening was repeated five
times against the rebuilt production bundle, **5/5 passed in 1.1 minutes**.
Two additional route checks for visible engine-brand copy passed. The local
physics benchmark measured **76.1197 s wall time** with 0/2 weak-grip versus
2/2 full-grip training deliveries and 0/1 versus 1/1 held-out deliveries;
its six native step counts were 4,148, 17,083, 4,148, 17,083, 4,148 and
17,088. These results describe this fixed simulated case only. The prior
full backend Pytest result below is historical; it was not rerun because this
release made no backend changes.

Remaining risks: the opening artwork is a stylized SVG sequence, not a rendered
humanoid physics simulation. The homepage evidence is recorded, clearly
labelled and separate from live runs. The large `WorldPreview` chunk remains
about 901 KiB gzip, and no new field performance measurement was taken. Render
Free can sleep and its SQLite storage is ephemeral; durable history and
always-on availability remain incomplete.

# Historical scientific laboratory release — 2026-10-21

The current working checkout makes Isabella Labs a science and experimentation
lab by Vivacity. The science-led homepage shows explicitly recorded SciPy
orbital evidence. `/laboratory` offers two executable disciplines:
`/discovery` creates a restricted 2D gravitational observation world and fits
two competing SciPy hypotheses; `/lab` preserves the MuJoCo Factory case.
No experiment starts on page load. Both use the versioned world, branch,
evaluation, replay, commit/reset and persistence contract. An environment
change marks old results stale. The opening remains 7.5 seconds with reduced
motion and keyboard escape paths.

Actual local checks: full Pytest **310 passed, 1 skipped, 1 warning** in
1,543.94 s; focused API/science **27 passed, 1 warning** in 91.73 s;
frontend unit suites **5 template, 4 Factory settings, 19 API passed**;
TypeScript/Vite production build passed; final Chromium E2E **12 passed**
in 3.5 minutes. The browser suite executed a real six-trial MuJoCo comparison
and both real SciPy hypothesis fits, plus stale-state, replay, export,
commit/reset, mobile, opening and expired-storage recovery paths.

The new Render Free backend at
`https://isabella-labs-runtime.onrender.com` deployed private source
`4b45d9e` successfully. Public health returned HTTP 200 and advertised
MuJoCo 3.15.0, SciPy 1.18.1 and cloth 3.15.0. Live HTTP/WSS science jobs
returned two branches and six events each; a changed world invalidated the
old fit. A live MuJoCo diagnostic executed 50 steps, reported an honest
timeout, and replayed the same trace. The public Factory script completed one
physical delivery (17,080 steps) and one weak-grip failure (4,636 steps), with
camera detection, pause/resume, replay, import/export, PDF and ZIP report
checks. Linux backend CI run `39520415915` passed all three shards. Vercel
deployment `dpl_HkC5AAawBkRtuo2ZcuGGnHcQ8rQZ` was READY and aliased to
`https://demo.tryvivacity.com/`; all six direct route/API checks returned
HTTP 200. Seven public browser tests passed in 1.1 minutes, including the
real SciPy visitor journey. A separate public Factory Chromium suite passed
**3/3 tests in 13.1 minutes**. Its six independently restored MuJoCo trials
measured a **706.1039-second** backend batch, with training baseline 0/2,
candidate 2/2, held-out baseline 0/1, candidate 1/1, and native step counts
4,147, 17,080, 4,147, 17,080, 4,149, 17,088. Replay and export passed.
The recorded SciPy source-label correction was redeployed as Vercel
`dpl_iquVohZXZzFFsczTw1PUYeNf7hxC`, READY at the same alias. Six direct
site/API checks again returned HTTP 200; a targeted public Chromium homepage
test passed. Final live visual inspection covered homepage, lab selector,
and idle discovery controls. The production browser console had only the
known non-fatal Three.js Clock deprecation warning.

Limits: the science case is a synthetic, nondimensional 2D Newtonian model
with a stationary declared perturber, not a real astronomical discovery.
Local uncertainty is a linearized estimate, not a Bayesian posterior.
Render Free can spin down and has ephemeral SQLite; always-on service and
durable user history are not provided. The broad robotics catalog still has
capability-dependent entries; hardware validation and arbitrary scientific
world generation are incomplete. A homepage recording is labelled as saved
evidence and never substitutes for a fresh experiment.

# Historical Factory discovery release — 2026-10-14

The current public build is https://demo.tryvivacity.com/ (Vercel deployment
`dpl_3NVSBD53rJK3fznForaNu8ic9Axz`). Its `/`, `/runtime/health` and
`/runtime/openapi.json` routes returned HTTP 200 after promotion. Render deploy
`dep-db7j6u6k1f9s73fv66g0` is Live on backend commit `0ed1e94`; the source
manifest, Docker build and Linux CI passed. The scoped checkout changes are
documented in `docs/FINAL_PRODUCT_AUDIT.md`.

Working and directly verified in this release: a browser-started public
MuJoCo conveyor run completed at 2.100 s simulated time, displayed 43 saved
frames, and published eight descriptive model series with a genuine poor-fit
label for carton height. A separate public run returned all 43 frames in eight
pages of at most seven, without cursor gaps, and a 177,046-byte ZIP containing
matching `discovery.json` plus a 57,643-byte PDF. The local equivalent executed
1,050 MuJoCo steps and produced 43 frames. The production browser logged zero
JavaScript errors; at a 375 px client width it had no horizontal overflow.
The released robotics API sent nine WebSocket events for a completed four-branch
experiment, including collision/planning failures and an execution success.
All four branches were replayable. Changing its obstacle invalidated the old
result, and a new two-branch experiment completed with a selected branch.

Tests actually executed: full Windows Pytest **297 passed, 1 skipped, 1
warning** in 1,298.49 s. The skip is Linux-specific; the warning is the
existing Starlette TestClient/httpx deprecation. Linux GitHub Actions
[run 38529411185](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38529411185)
passed **298 backend tests** across three shards (87 + 102 + 109) and **4/4
hard 512 MiB host checks**. The focused Factory API/discovery/report/paging
suite passed 15 tests. Frontend API/template/settings/numerical/snapshot
checks passed **36**, and TypeScript/Vite and Vercel production builds passed.
The 512 MiB host peaked at its exact memory cap without an OOM kill, leaving
no measured memory headroom for larger simultaneous reports.

Limits: the official interactive Desmos adapter has no authorized production
key or commercial agreement and was not browser-tested. Its local equation
view, MathML, CSV and JSON export remain available; opaque calculator-state
reopen has unit tests only. A 5,000–6,000 experiment-definition campaign and
cross-run causal law discovery are not implemented. Render currently uses a
Free instance with ephemeral SQLite and possible sleep; always-on uptime and
durable storage cannot be claimed. The remaining web-preview chunk is about
901 KiB gzip. This release did not establish a p95 latency or throughput SLO.

# Factory configurator release verification — 2026-10-14

Working in the deployed Factory page: editing mass, friction and other bounded
production conditions creates a fresh MuJoCo cell; previous run analysis and
benchmark frames clear when the cell changes. Empty or out-of-range values
show a specific validation message and cannot be applied. Factory startup no
longer starts an unrelated robotics world. The decorative scanner mast beside
the High fidelity conveyor was removed. The local development server now runs
without per-request access-log output to avoid a blocked terminal pipe.

Verification on this Windows checkout: **296 passed, 1 skipped** in the full
Python suite (20:06). The skipped test requires a Linux syscall sandbox. The
focused Factory suite passed 10/10; frontend API, template and settings tests
passed 19/19, 5/5 and 3/3; TypeScript and Vite production builds passed. Both
Factory Playwright browser cases passed individually: a one-carton physical
production/configuration/replay journey, and invalid-input/mobile reflow. The
physical browser run recorded 696 MuJoCo samples from 17,086 simulation steps.
One measured run consumed 22.7 seconds of worker CPU and 479 seconds of wall
time on this memory-constrained host; wall time is not a representative service
latency benchmark.

Vercel deployment `dpl_G9Mxdzxxwe146vhoPLeZkytwKWqY` serves
https://demo.tryvivacity.com/. Its production build passed; live HTML used the
new asset hash, the page and `/runtime/health` returned HTTP 200, and an
in-app browser showed the High fidelity workcell, validation behavior and no
console errors. Local preview `http://127.0.0.1:5173/` was restored with its
documented port-8010 backend; the browser loaded a persisted three-carton run
and all 2,200 replay samples without a console error. The work was committed
as `040b938`; this status note is a follow-up documentation change.

Known limits: headless MuJoCo/browser integration is slow on this 8 GB Windows
host. A passing finite test suite cannot rule out every runtime failure.
Optional Desmos embedding remains unconfigured. Unrelated existing artifact
files were left untouched.

# Mathematical discovery verification — 2026-10-14

Implemented locally: MuJoCo-frame scalar projection; automatic 25-sample
checkpoint and 100-sample numerical updates; final eight-family equation
comparison with chronological held-out metrics and poor-fit reporting;
SQLite persistence/restart; owner-scoped discovery API; measured-plus-fitted
browser chart, model switching, saved-run comparison, CSV and Desmos-ready JSON
export; conventional LaTeX for each new fitted model, KaTeX/MathML display and
LaTeX copy; optional official Desmos Graphing Calculator adapter. A joint-torque
association is reported only when acceleration and torque vary sufficiently.

Focused numerical/API tests: 8 passed. The final Linux container gate ran
297/297 backend tests plus 4/4 hard-512 MiB tests, with zero failures, errors
or skips ([run 38485502046](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38485502046)).
The current frontend check ran 25 API/analysis/number tests and five template
tests, all passing. TypeScript and production Vite build passed. A local browser observed two real
conveyor conditions (174 and 236 samples), a 25-sample provisional checkpoint,
eight final series, a validated carton-Y fit (held-out R² 0.9504), a correctly
rejected height fit, model switching, two-run overlay and measured CSV export.
A one-pair 4,225-step local conveyor comparison measured 6.599 s without
discovery and 6.606 s with it; this does not establish general throughput.

The final backend source is commit `5e481e9` on the private backend repository's
`main` branch, live in Render deploy `dep-db7c6le7bikc73ab2gqg`. Vercel
deployment `dpl_2DKas6D8YaLo4PdvL4UAKjGVkjpt` is live at
https://demo.tryvivacity.com/. A fresh public conveyor run
recorded 43 MuJoCo frames. At 25 frames it published a provisional equation;
at completion it published eight persisted series. The low-variance held-out
R² displayed as undefined at both stages, and the selected height model was
marked poor-fit. Public `/health` and `/openapi.json` returned HTTP 200; the
deployed page showed conventional piecewise `cases` notation with accessible
MathML, updated correctly when the model changed, copied valid LaTeX, and
logged zero browser console errors. Sixteen backend-generated expressions
rendered through KaTeX in an independent parser check. The public browser
screenshot is `artifacts/factory-latex-public.png` (local verification evidence,
outside tracked source).

Two pre-existing 60-second **Windows** factory production tests timed out
while native MuJoCo was still running. A controlled earlier no-discovery run
also timed out on this host, so attribution to discovery is unsupported.
The optional Desmos embed has no licensed production key and has
not been exercised. 5,000–6,000 experiment-definition campaigns are not
implemented. See [FACTORY_DISCOVERY.md](docs/FACTORY_DISCOVERY.md) for details.

# Autonomous factory release — 2026-10-14

Deployed and verified at https://demo.tryvivacity.com/. Built as P0–P10 slices,
then checked through the P11 release gate; each stage has its own test/browser
evidence in [FACTORY_STAGE_GATES.md](docs/FACTORY_STAGE_GATES.md).

Working: physical conveyor transport, native Panda contact grasp/lift/transfer,
shuttle routing and verified bin delivery; explicit Start/Pause/Resume/Reset;
real MuJoCo camera/depth/semantic observations; measured SI telemetry; synchronized
charts/replay; repeated training/held-out comparisons; strict idle JSON import;
complete exports; saved-data PDF/ZIP; versioned project notebooks. Existing
workcells, spatial assets and REST/WSS remain available.

Executed results: **289/289 Linux tests**, zero failures/errors/skips; **4/4 hard
512 MiB tests twice**; **31/31 frontend checks**; TypeScript, Vite and Vercel builds
passed. Public HTTP completed successful and failed contact runs and all six
benchmark trials (three baseline successes, three weak-grip failures). Public WSS,
replay and geometry invalidation passed. The deployed browser completed a physical
delivery, froze/resumed at 7.000 s, replayed 9.188 s, captured an actual camera,
imported without starting, downloaded a PDF and passed narrow-layout inspection.

Actual public measurements: one delivery used 17,080 integration steps, 34.160
simulated seconds, 125.402 wall seconds and 17.244 worker CPU seconds. The six-trial
benchmark used 65,145 steps and 482.340 wall seconds. Both hard-limit tests reached
512 MiB peak during archives with zero OOM kills; unrestricted concurrency is not
validated. Initial OOM failures and a Vercel packaging failure were fixed and the
corresponding gates rerun. All six public PDF pages were visually inspected.

Limits: 1–3 cartons, one tested factory Panda controller, 6–10 serial comparison
trials; semantic camera labels are simulator annotations, not learned perception;
no hardware calibration, electrical-consumption model, authenticated team roles
or live collaboration. Render Free sleeps and uses ephemeral storage. A paid,
durable always-on deployment was not activated. Export important experiments.

[FACTORY_RELEASE.md](docs/FACTORY_RELEASE.md) records exact source/deployment IDs,
tests, public performance, corrected failures and remaining risks.
[FACTORY_CAPABILITIES.md](docs/FACTORY_CAPABILITIES.md) lists implemented versus
incomplete functionality. [FACTORY_RUNTIME_HANDOFF.md](docs/FACTORY_RUNTIME_HANDOFF.md)
contains exact APIs, frontend files, examples and reproduction commands.

# Spatial world pipeline — 2026-10-13

Deployed owned image/multi-image/panorama/video capture contracts, actual asynchronous World Labs generation, preserved original collider/thumbnail assets, separated representation/readiness evidence, streamed SPZ decoding with view-dependent Spark LoD, three rendering quality levels and seeded physical condition/held-out reports. Added persisted object-trajectory measurement comparison. Physics remains real MuJoCo and the current interface/runtime are preserved.

Executed final backend checks: **261/261 Linux tests**, zero failures/errors/skips; **3/3 hard 512 MiB checks**; **67/67 Windows spatial/schema/workspace checks**; **26/26 frontend checks**; TypeScript and production/Vercel builds passed. Real public image generation completed. Public baseline/training/held-out conditions executed nine physics candidates plus fresh executions (74,867 steps, peak two workers), all three successful; a separate weak-grip run failed all three conditions honestly. REST, native WSS, replay, owned artifacts and exact 55-path OpenAPI were verified. Numerical self-reference comparison is not hardware validation.

Fixed provider-schema geometry bounds, hidden active canvases, idle collection recursion and LoD teardown/framing. Generation mode mounts zero canvases. Device-specific idle/load measurements and evidence are recorded in [SPATIAL_PIPELINE_RELEASE.md](docs/SPATIAL_PIPELINE_RELEASE.md).

Limitations: conservative solid proxies, not reconstructed concave-room physics; uncalibrated physical properties; real hardware alignment/robot-contact matching unavailable; multi-image/panorama/video adapters require further full live-provider validation; Atlas unavailable in the verified API; no RAD paging output; Render Free sleeps and its persistence is ephemeral. Full capability status, exact endpoints/examples, measurements and reproduction commands are in the linked release document.

# Physical experimentation workspace — 2026-10-13

Deployed native gravity/air/wind, bounded object force/torque, gripper actuator
limits, eight illustrative contact materials, real engineering inspection/overlays,
mechanical object energy and analytical validation reports. Added Explore / Generate
/ Import with actual previews, staged import validation and current-run results.

Executed: **235/235 Linux tests passed**, zero failures/errors/skips; **3/3** hard
512 MiB checks passed; **22/22** new Windows physics tests; **75/75** changed-area
regression; **19 + 5** frontend checks and production build passed. Public real
HTTP/WSS experiment: three validations and successful fresh placement (1.069 mm
error), 250 replay frames, 12 WSS events; changed weak-grip inputs invalidated the
old run and produced two actual dropped-object failures. Public OpenAPI matches.

This remains a bounded physical demonstration, not a calibrated universal factory
simulator. Two curated visual worlds, one implemented object gripper, simplified
fluid/contact models, fixture cloth, primary-arm dual robot, eight public trials,
Free idle sleep/ephemeral persistence. Full implemented/incomplete inventory,
measurements, evidence and commands: [PHYSICAL_PLATFORM_RELEASE.md](docs/PHYSICAL_PLATFORM_RELEASE.md).

# Runtime stability and parallel trials — 2026-10-13

Fixed the reproduced Render 512 MB memory crash and persistent stale-session 404
loop. Production HTTP now uses same-origin `/runtime`, with uncached capability
forwarding and bounded read retries. Writes are never automatically repeated.
Two independent native MuJoCo trials run concurrently; adaptive stopping counts
complete batches and reports exhausted budgets accurately. Detailed frontend
geometry/UI is preserved; the headless backend keeps all physics geometry/inertia.

Executed: Linux **213/213 passed**, zero failures/errors/test skips; separate hard
512 MiB image checks **3/3 passed (68.756 s)**; frontend **19/19 passed** and build
passed. Targeted Windows backend **13/13 passed (83.42 s)**. Public multi-candidate
experiments, measured overlapping integrations, concurrent reads, pause/resume,
stop, mass changes, stale-world recovery, replay/export and WSS were exercised.
The first Linux run's 1 stopping-report failure was corrected and remains recorded.

Limits: Render Free still sleeps and loses SQLite/imports on restart. Public host
budget remains eight physics trials; no 5,000-trial public run or uptime guarantee
is claimed. Separate experiments queue; existing physical fidelity/controller and
cloth/dual-arm limitations remain. Full evidence and reproduction:
[RUNTIME_STABILITY_RELEASE.md](docs/RUNTIME_STABILITY_RELEASE.md).

# Visual correction release — 2026-10-13

Working: real colored SPZ warehouse/laboratory rendering, preserved standalone
GLB materials/textures, camera reset without Canvas remount, owned asynchronous
renderer cleanup, four contextual configuration stages, concise robot catalogue.
Real MuJoCo execution remains the source of measured results.

Executed: Linux 201/201 passed (854.882 s), 512 MiB 2/2 passed (65.424 s),
Windows scoped 60/60 passed (133.91 s), frontend 5 selection + 4 response checks
passed. Real World Labs warehouse: 7,421,219 bytes, 1,580 actual credits.
Eight environment switches and a textured GLB UI import produced no new browser
exceptions after fixes. No experiment starts automatically.

Limitations: two curated visual environments; other presets are explicitly
simplified collision fixtures. Gaussian appearance has baked lighting and is
not a reconstructed collision twin. Old laboratory scale is visually calibrated,
not verified metric data. ZIP material bundles remain unsupported. Existing
cloth/dual-arm/controller limits remain. Render Free can sleep and lose SQLite
on redeploy. Large renderer chunks and a dependency deprecation warning remain.

Details and current release evidence: `docs/VISUAL_RELEASE.md`.

---

# World and robotic experiment workspace — 2026-10-13

Current backend source: `ffa94fad8628defc20664469335c6de3b6586c5e`.
Render deploy: `dep-db6r55gm7kps73b1kecg`. Frontend source: `f2e5bb9`,
Vercel deploy `dpl_3X97ztxZvBMeBaCfr3ZUa9YaZKVc`.
Public URL: https://demo.tryvivacity.com/.

Working capabilities:

- Seven actual arm models: Panda, UR5e, KUKA iiwa 14, Kinova Gen3, xArm7,
  analytical educational SCARA and dual Panda (primary-arm task execution).
  Every model completed actual native pickup trials in the 512 MiB container.
- Thirteen selectable environments with real static collision primitives,
  plus owned generated/imported worlds and explicit collision-proxy mapping.
- Ten bounded operations: pickup, transfer, reaching, seeded manipulation,
  experimental fixture fold, one-part rule sorting, passive fixture seating,
  dynamic two-body stack, gravity-assisted insertion and actuated-door bay loading.
- Actual OpenAI structured world/operation interpretation and actual World Labs
  generation/retrieval, failed-operation recovery, reported credits, typed output,
  scoped download hosts and bounded parsing. API credentials remain backend-only.
- Owned configuration library, save/load/repeat, runtime session history,
  measured comparison and JSON export. Idle loading does not submit experiments.
- Independent MjData branches sharing immutable compiled geometry; complete
  integration state snapshots; measured contacts, joint limits, controller
  tracking, failures, goal errors and actual simulation steps.
- Native MuJoCo validation and fresh execution, real pause/resume, live HTTP/WSS,
  replay/export and stale-result invalidation/recomputation after geometry edits.
- Compiled model geometry/initialized pose files for every arm, actual body
  transform rendering and bounded import preview with keyboard orbit/zoom/reset.

Verification executed so far:

- Initial full Windows suite: **189 passed, 1 skipped**, 1534.66 s; Linux sandbox
  test skipped on Windows. Initial deployment image: **190 passed**, 966.126 s.
- Expanded feature suite: **36 passed**, 344.91 s. Native execution/pause/adaptive
  subset: **22 passed**, 184.40 s. Authority/pause/capacity: **27 passed**, 317.56 s.
- Further collision/pacing/preview/cost regression checks passed. Tests cover
  secondary-arm contacts, full bounds after preview reduction, legacy index
  normalization, owner isolation and preserving actual credits on retrieval failure.
- Windows full run during native transition: **195 passed, 1 skipped, 1 failed**,
  1045.51 s. The failing test assumed more than 100 streamed frames; native chunks
  use fewer real frame updates. Its revised check compares delivered state with
  recorded trace/final integration time and passed in the 27-test subset.
- Five Node selection tests passed, covering **1,215 interactions** across 81
  structurally valid legacy combinations. This is not proof of physics success
  for every cross-product of hardware, scene and conditions.
- TypeScript/Vite and production Vercel builds passed. Public OpenAPI matches
  both exported specifications. Existing Three.js bundle/deprecation warnings
  remain; browser error checks and desktop/390 px layout checks were exercised.
- Two host-capacity tests passed under a real **512 MiB Docker limit**, 54.767 s,
  including three native trials on all seven models. Earlier memory check exited
  137 when native execution compiled duplicate mesh models; immutable model
  sharing corrected that. The resource margin remains limited on Free compute.
- Final production-image run **38346284197** on source `ffa94fa`: **198 passed,
  zero failures/errors/skips**, **693.269 s**. The same run repeated the 512 MiB
  capacity checks: **2 passed**, **56.547 s**. JUnit files are saved under
  `artifacts/workspace-linux-release/`.

Measured production evidence:

- Live KUKA UI job `30dd3f6e-172b-4c17-b0c6-7b320931fc7f`: **3/3 validations**,
  fresh execution verified, **45,410 steps**, **51.480 s** wall time. Its report
  downloaded from the real UI. Dragging the blue object changed measured position
  to X 0.492 m/Y -0.195 m and marked previous results stale. Recomputed validations and a fresh execution
  succeeded; the new selected placement error was 1.6 mm.

- Real UR5e job `3b0b974a-c49b-485b-b48e-204390540247`: three validation
  trajectories, independently restored fresh execution, **65,742 physics steps**,
  **526 integration calls**, **1.049 mm** final placement error, **37.404 s** job
  wall time, **5.503 s** process CPU time, **2,161,340 bytes** serialized replay.
  Full HTTP/WSS/replay/invalidation/recomputation journey: **79.795 s**, 12 events.
  Earlier same-seed initial job was 180.258 s; its full verification was 446.499 s.
  These are individual measurements on shared compute, not a guaranteed SLA.
- Actual pause kept production frame sequence 457 and simulation time
  12.40000000000081 unchanged; resume returned HTTP 200.
- Real World Labs jobs completed locally and on production. Public job
  `6c7ed573-d5dc-430e-9364-82a1c454d3dd` reported **230 provider credits**.
  Original collider geometry is parsed; previews use bounded sampled triangles.
  Initial nested NumPy indices rendered blank; flattening and typed preview
  validation fixed the producer and normalize existing records on read.
- Failure boundary experiment `60e38b3e-dc96-4ce9-92b2-c78463d0db7d` returned
  a genuine timeout with 50 integrated steps, eight WSS events and matching replay.
- Local UI saved UR5e and generated-world configurations, ran three real
  validations/fresh execution, persisted reports across reload/server restart,
  and exercised world import, rename, duplicate, recoverable removal and undo.

Limitations and missing features:

- Cloth uses a pre-attached fixture; autonomous cloth grasp acquisition is absent.
  Dual Panda has no coordinated bimanual planner. SCARA is educational, not OEM
  hardware. Added arms use a modeled Panda flange gripper, not certified mounts.
- Sorting is one part with supplied properties, assembly is passive seating,
  insertion is gravity-assisted, and machine tending is a passive bay/door.
  Camera recognition, real machining, fastening, tight-tolerance force insertion,
  multi-part manufacturing and energy accounting are absent.
- Generated/imported rooms use an explicit solid AABB collision proxy beside the
  standard workbench. Full concave scene reconstruction, Gaussian splat/texture
  rendering, animation/skinning/extension-heavy GLTF and USD are absent.
- Object inputs are 40–60 mm and 20–150 g with bounded friction. Valid input is
  not a guarantee of feasible grasp/reach. Search is measured and compute-bounded,
  not a global optimality proof. This host allows eight validation trials per run.
- Workspaces use browser capabilities, not accounts/organizations or cross-device
  identity. Run creation is not HTTP-idempotent; generation is idempotent.
- Render remains **Free**. It can sleep, shared CPU is slow, and SQLite/import data
  can be lost on redeploy/restart. No paid upgrade was activated. Serial container
  tests do not prove concurrency/load capacity. Persistent disk, production queues,
  durable backups, revocation and long-term uptime guarantees remain missing.
- Scientific Discovery stays retired from the product and public API.

Handoff: `docs/WORLD_WORKSPACE_HANDOFF.md`, `FRONTEND_HANDOFF.md`, `openapi.json`,
`frontend/src/generated/api.d.ts` and `scripts/verify_workspace_live.py`.
Historical evidence follows; older Panda-only availability is superseded.

---

# Template picker usability fix (2026-10-13)

Frontend source `12ee3aa` is deployed as Vercel
`dpl_8NukzFtw5CvbBjm6rtGPgXN6CWgV` at https://demo.tryvivacity.com/.
The backend remains on verified source `2bf89e7`; no physics or controller code
was changed. Planned arms and tasks are disabled and labeled Not available yet.
World/task selection now maintains a compatible combination, eliminating the
user-facing robot/gripper/controller-adapter dead end. Panda remains the only
implemented arm; no additional hardware support is claimed.

Executed for this correction: five Node selection tests passed, covering all
135 catalog interactions from the nine runnable combinations. Two backend
catalog/rejection tests passed in 10.98 s with the existing Starlette warning.
TypeScript/Vite and Vercel production builds passed; the existing 913 kB Three.js
chunk warning remains. The full 156-test backend suite was not repeated for this
frontend-only change; its previous verified results are recorded below.

Public browser verification: warehouse, textile/cloth and inspection workcells
loaded through the real backend; cloth pairing and leaving cloth for rigid
handling worked; the inspection world stayed idle. The mass setting persisted
from 20 g to 25 g on apply/reopen, then was restored to 20 g. Keyboard arrows
skip unavailable arms. At 390 px, content width was 375 px with no horizontal
overflow. Six unimplemented choices were disabled, the old adapter message was
absent, and no public console errors were captured. Local 5174 verified picker
interaction only; that origin is not allowed by public-backend CORS.

A fresh public HTTP/WSS diagnostic passed in 11.078 s: eight WebSocket messages,
50 real MuJoCo integration steps, honest timeout, no selected successful branch,
and replay matching the executed trace. This deliberately short diagnostic is
not a new successful pickup claim. Evidence in artifacts/:
template-picker-public-boundary.json and template-picker-public-desktop.jpg,
template-picker-public-mobile.jpg.

# Robotics template release verification (2026-10-13)

This release retires Scientific Discovery from the public UI, schemas and runtime.
The implemented catalog has five arm references, five physical workcell presets
and five task choices. Panda is the actuated arm. Eight rigid handling combinations
and one fixture-assisted textile fold run through existing MuJoCo adapters.
UR5e, KUKA iiwa, SCARA, dual-arm control, machine tending and assembly are gated
reference templates, not implemented controllers. See docs/ROBOTICS_TEMPLATES.md.

Executed locally: all 11 template tests passed in 169.57 s (one dependency warning).
The migrated runtime boundary run passed 61 tests and failed three in 606.67 s;
cloth failed-adapter replay labeling, an observation-envelope assertion and a
wait deadline were corrected. All three repaired checks passed in 98.60 s.
The full Linux deployment-image run 38318104071 on source 2bf89e7 passed
156 tests, zero failures/errors/skips, in 930.151 s. The separate 512 MB check
passed one test in 52.580 s. Both had the existing dependency warning. Evidence:
artifacts/templates-linux-tests/.

TypeScript/Vite build passed, with the existing large Three.js chunk warning.
The live local HTTP/WebSocket demo passed repeated deterministic reaching,
measured collisions, obstacle change/staleness, all-path failure and real cloth
folding. A UI warehouse run completed five real feasible trials and a fresh
pickup execution; a downloaded measured branch has 6,055 integration steps,
53 frames and 1.0705 mm placement error. Actual worker pause/resume was exercised.

Known limits: simplified workcells rather than complete facility twins; Panda
only; pre-attached cloth fixture without autonomous grasp; synthetic semantic
ray sensing rather than real camera perception; bounded host compute, ephemeral
Free-host SQLite, no hardware actuation or production account/billing system.
No ROI, traction, global optimality or universal physical feasibility is claimed.

Public release: backend source `2bf89e7`, Render
`dep-db6me8e7bikc73ai2g50`, frontend source `0bb0b9a`, Vercel
`dpl_7xYiCA4UA2ntSQvLXqBdXAU7kRQs`, https://demo.tryvivacity.com/.
Public template/API/OpenAPI/CORS checks passed; retired science and reference
hardware return 422. A real WSS diagnostic delivered eight sequenced messages,
50 integrated steps and replay identical to its trace; the intentional 100 ms
timeout failed honestly. A later geometry patch invalidated that experiment
and replay and incremented its world revision. This is not a pickup success.

Public warehouse: five measured feasible trials and a fresh successful execution.
Pause/resume controlled the backend. Downloaded validation: 6,055 steps,
53 frames, 12.11 simulated seconds, 1.0712 mm placement error. Displayed completion
was 231.38 wall seconds, including a pause from 134.98 to 208.65 s.
Public cloth: three genuine validation rollouts plus a fresh successful execution;
selected validation has 2,758 steps, 112 frames, 0.9234 mm alignment error and
100% vertex coverage. Displayed completion was 475.60 wall seconds. The Free
host's CPU makes cloth slow; faster or uninterrupted service is not established.

Desktop and 390 px mobile layout, native radio keyboard navigation, reference
gating, template load focus, idle opening and empty viewport text were checked.
The final public browser had zero captured errors. Screenshots:
`artifacts/templates-public-fold.jpg`, `artifacts/templates-public-mobile.jpg`.
Numerical exports and API proof: `artifacts/templates-public-*-branch.json`,
`templates-public-api.json`, `templates-public-boundary.json` and
`templates-public-invalidation.json`. Screen-reader testing and a new automated
axe run were not performed; older browser harness results are historical.

The following records are historical releases, not the current template scope.

# Implementation status — current Render handoff, 2026-10-13

## Current clean tabletop and adaptive pickup release

**Live and verified at https://demo.tryvivacity.com/**. The robotics viewport
has no visible text, target markers, paths, grid or sensor overlays; loading
and errors also appear outside it. Object dragging covers the whole physical
table, inset by object dimensions to keep it supported. Width/depth/height,
mass/weight and friction controls rebuild the actual MuJoCo geometry and
contacts. Search varies grasp yaw, seeded DLS IK retries and joint-space RRT
routes. Physical trial count is adaptive, with measured plateau and host
compute-budget stops disclosed.

Docker CI: **155 passed, zero failures/errors/skips**, one upstream warning,
353.54 s. The separate 512 MB check: **one passed**, 53.25 s. Reports:
`artifacts/adaptive-linux-tests/backend-linux.xml`, `host-memory.xml`.
Final Vercel TypeScript/Vite build passed; the large Three.js chunk warning
remains. Backend source `0353263` is live as Render `dep-db6lh3ff3r2c73crqm4g`;
frontend `dpl_EHwp139FoB9QFLYqEi9p5J6DpaaR` is ready on the custom domain.

The public run screened 256 commands and stopped at five integrated MuJoCo
trials, retaining two feasible outcomes and genuine failed grasps/drops.
Its fastest measured feasible candidate used 180° grasp yaw, 7,398 steps,
14.796 simulation seconds and 8.5498 mm placement error. A separate live
authoritative execution succeeded at 8.5 mm error and zero prohibited
contacts; total public wall time was 4:07.21. The object measured
44 × 56 × 52 mm, 100 g and friction 0.65. Public dragging reached the far
edge (ray estimate `[1.065,0.385]` m), invalidated the result, and did not
start a new job. Desktop and mobile were checked with empty viewport text,
no captured console errors, and no mobile horizontal overflow.

Limits: placement on the table does not guarantee that a fixed Panda can
reach or grasp that point. The planner currently searches top-down yaw
grasps; no base repositioning or arbitrary shape support exists. Carried
object collisions are validated by physical trials. This is best measured
feasibility under a budget, not a global optimum. Perception uses synthetic
MuJoCo semantic depth labels. Free hosting retains its earlier uptime and
ephemeral-persistence limitations. Details: `docs/ADAPTIVE_PICKUP.md` and
`docs/HOSTING_STATUS.md`. Sections below describe earlier releases.

## Bounded 3D pickup drag and 422 repair (2026-10-12)

**Deployed and verified:** the blue cube can be dragged on the rendered table
within X 0.35–0.65 m and Y -0.30–0.30 m. Release rebuilds the MuJoCo world
through the existing environment API and invalidates earlier results. The
preview is labelled as uncommitted; keyboard users can change the same
coordinates through the existing sliders. Exact 0.10 m pickup/placement
separation is accepted by the backend, while closer points are blocked in the
editor with a short alert. A rejected server edit keeps the editor open and
shows a concise error. The drag moves the object between experiments; it is
not itself a robot manipulation simulation.

Backend commit `8cfa7fcd60e5acd01f1075d59eec5de2e2a03212`, Render deploy
`dep-db6fie2jnfac73djg6ag`: Docker CI **139 passed, one warning in 352.77 s**;
the separate 512 MB lab check **1 passed in 55.83 s**. Vercel deployment
`dpl_E7CdpcAXC29sJyiMBNAg5E5wdnzD` serves both public aliases with the same
built JavaScript asset. The production TypeScript/Vite build passed. Local
desktop and mobile browser drags, bounded clamping, invalid-drop feedback,
and stale-result indication were exercised. The public browser accepted a
drag and the screenshot's previously failing 60 mm scene; live `/health`
reported eight physics trials. The subsequent public experiment ran **8/8
actual physics trials**, then a fresh authoritative execution succeeded with
**1.7 mm** placement error and **zero prohibited contacts**. Dragging again
visibly marked those results stale. Exact run outcomes: `docs/HOSTING_STATUS.md`.
The same deployed site completed four SciPy Discovery cycles and displayed
computed model predictions, held-out errors and a complexity-aware final
central-only selection; the measured values are in the hosting report.

Remaining limitation: Render Free can sleep and uses ephemeral SQLite; the
interactive host remains capped at eight physics trials. A separate hosted
5,000-trial audit exists, but visitors cannot request 5,000 on this host.

## Configurable pickup release (2026-10-12)

**Deployed and tested:** the public robotics page lets a visitor set the cube pickup
position, placement position and side length from 40 to 60 mm. Applying conditions
rebuilds the actual MuJoCo geometry without starting an experiment; Start submits
independent physics trials. The frontend asks `/health` for the host capacity and
displays the actual completed trial count and backend event log. On the current
Render Free service, that capacity is **8**, not 5,000. The requested 5,000
visitor-configured trials remain **incomplete** on this 0.1 CPU / 512 MB host.
The separate completed cloud 5,000-trial audit is reproducible evidence of the
backend on a larger runner, not a live per-visitor feature.

- Backend source: `e4d6d2c4f0ad23c4d34c32bd0751a19d3af1c704`; Render deploy
  `dep-db60ej0473hc73clmuo0` succeeded. The public OpenAPI exposes
  `cube_half_size` bounded to 0.02–0.03 m; `/health` reports a limit of 8.
- Frontend: Vercel deployment `dpl_w1tHiBqKWM4bzNmso4iWnjtVXETQ` is ready and
  aliased to `https://demo.tryvivacity.com/` and
  `https://vivacity-investor-demo.vercel.app/`; both returned HTTP 200 with the
  same built JavaScript asset. Its requested budget is 5,000,
  clamped to the live host limit before each session. The production TypeScript
  and Vite build passed (5,125 modules, 6.21 s); the existing large Three.js
  vendor-chunk warning remains.
- Public browser verification: a visitor set the cube to **60 mm**, applied the
  new physical scene, then started explicitly. **8/8 real backend physics
  trials** completed and were feasible. A separate fresh authoritative
  execution reported **1.7 mm** goal error, **zero prohibited contacts**, and
  persisted successfully. The result appeared after about **4:03** of event
  time; reopening Change conditions still showed 60 mm. Captured browser
  console errors: **zero**. This is one measured scene, not a reliability
  guarantee across arbitrary positions or object sizes.
- Local full backend suite: **136 passed, 1 Linux-only skipped**, 439.86 s;
  the added legacy-snapshot check passed separately. The pushed Docker image
  passed **138 tests** in 225.85 s plus the 512 MB lab check (**1 passed** in
  41.74 s). The upstream Starlette deprecation warning remains.

In the earlier configurable-pickup release, repositioning used settings
sliders only. The current release adds direct pointer dragging as described
above. The arm performs physical pickup and placement after Start. Render Free
still sleeps and uses ephemeral storage.

**Current deployment truth:** the UI uses Render Free at `https://vivacity-runtime.onrender.com`
and `https://demo.tryvivacity.com`. This free service sleeps after inactivity and
loses SQLite data on restart. Its true pickup limit is eight physics trials. Latest
release and actual test results: `docs/HOSTING_STATUS.md`. The completed 5,000-trial
hosted backend-image audit is documented in `docs/PHYSICS_5000_VARIED_AUDIT.md`;
it does not measure the current free Render instance. Earlier test/browser tables
below are historical local/prior-release results. A measured slow-CPU pickup execution
timeout is addressed with a tested 300-second host wall deadline. The public
pickup journey was verified on release 2f61389; current Orbital verification
and release evidence is recorded in docs/FINAL_VERIFICATION.md.

The latest Render deployment image passed **135 tests**, plus a separate 512 MB lab test. Windows with bounded numerical threads passed **134 tests with one Linux-only skip**; unrestricted Windows deadline failures remain preserved. Fixed pickup benchmark: **20/20**. Final public adapted Orbital journey passed **12 checks**, including blocked-reactor invalidation and real failed alternatives, with **30,757 actual physics steps** and **1.717717 mm** measured successful placement error. Both public aliases passed real SciPy fits, reload, mobile layout and offline recovery. Current UI uses Start/Stop without video controls; native Pause/Resume remains a tested API capability. A separate hosted backend-image audit completed 5,000 full MuJoCo trials: 4,000 measured successes, 1,000 collision failures, 29,625,840 validation steps, with live cloud logs and persisted records. Exact current evidence, limitations and reproduce commands: `docs/FINAL_VERIFICATION.md`, `docs/HOSTING_STATUS.md`, `docs/PHYSICS_5000_VARIED_AUDIT.md`. API/frontend contracts: `FRONTEND_HANDOFF.md`, `docs/ORBITAL_HANDOFF.md`, `openapi.json` and `docs/openapi.json`.

**Render Free is provisioned:** `https://vivacity-runtime.onrender.com`, with both public frontend aliases connected. Paid activation remains blocked by the payment method requirement despite the existing credits. Free hosting sleeps after 15 idle minutes; SQLite data is ephemeral. Public pickup uses eight real physics trials and rejects oversized jobs. Always-on availability and durable persistence are **not** implemented by this free fallback. The completed 5,000-trial cloud run used the same backend Docker image on a separate hosted runner with 2 GB memory; it did not execute on Render Free. `docs/HOSTING_STATUS.md` records the deployed configuration and executed evidence.

## Working and actually tested

- Shared create/observe/snapshot/fork/apply/simulate/evaluate/commit/replay operations with backend-owned state, unique worlds, reproducibility metadata, independent branches, revision invalidation, persistent lineage/evaluations/history and exports.
- Vendored Menagerie Panda under MuJoCo 3.15.0. Legacy collision-free reaching retains DLS IK and joint-space RRT. New pickup is a free dynamic 50 mm cube grasped by real bilateral finger forces; lift/retention/transport/release/table support/placement are measured. There is no object weld, mocap attachment, kinematic teleport or frontend hand parenting.
- Fixed pickup benchmark: **20 successes / 0 failures**, total **86.5164 s**, physics **3.50–5.45 s/run**; measured final position error **0.0016989113 m**. Actual full-state identical re-execution and independent fork tests pass. Grasp miss/drop/timeout/collision/controller/limit/planning failures remain honest.
- Actual 5,000 distinct timing proposals with cached identical kinematic templates, explicit rejection counts, real shortlisted MuJoCo validation, measured ranking/top-three exports. A chosen successful command executes again in independent authoritative state; only a freshly verified physical final state is committed.
- Bounded leased autonomous sessions create fresh world IDs, seeds and conditions. One physics worker, eight reserved jobs, two active supervision slots, finite cycles, 180 s lease, 30 min session bound and step-boundary cancellation. Expired sessions are stopped, not falsely completed. Restart marks interrupted work failed.
- Session capabilities cover their REST records and both WebSockets; only token hashes are stored. Latest-only measured state is retained for at most 32 experiments; persistent progress supports sequence recovery. No prerecorded main-scene loop/video controls remain.
- SciPy 1.18.1 `solve_ivp`/`least_squares`, blinded synthetic observations, competing fits, chronological holdout, BIC complexity penalty, local Jacobian uncertainty, parameter recovery/control rejection and real displayed `[x,y,0]` predictions. Fresh perturbed/control cycles select different models from executed metrics.
- Actuated Panda carrying a pre-attached bar through a real 7×7 MuJoCo flex fixture, constrained fold, release/settling and measured quality. Separate fixed benchmark **5 successes / 0 failures**, **26.6677 s**, alignment **0.0003588456 m** and coverage **1.0**. Disabled actuators cannot pass.
- Bounded GLB/glTF/ZIP static preview and MJCF/URDF description staging; actual uploads, decoded triangles, transform/persistence/error/unsafe-input checks. Every import reports `physics_ready:false`.
- Real FastAPI requests, sequenced WS progress, live physics WS, bounded queue errors, retries/idempotency, cancellation, persistence/restart, hidden-truth isolation and stale replay/commit behavior.
- Existing React/Three.js brand/workspace preserved: dominant live scene, actual result cards/downloads, one inspector, camera keyboard path, tested 1440/768/375 layouts, measured geometry and numerical paths. Capability-owned sessions replace public frontend jobs.

## Tests executed and actual results

| Check | Actual outcome | Evidence |
| --- | --- | --- |
| Original-code full baseline | 86 passed, 352.52 s | `artifacts/master-baseline.xml` |
| Focused pickup/search | 10 passed, 47.95 s | `artifacts/master-pick-place-tests.xml` |
| API/runtime/supervisor regression | 41 passed, 70.12 s | `artifacts/master-supervisor-tests.xml` |
| Fresh-cycle supervisor checks | 5 passed, 92.93 s | `artifacts/master-autonomy-tests.xml` |
| Full new implementation before final boundary fixes | 98 passed, 256.84 s | `artifacts/master-final-backend.xml` |
| Cube-only collision and expired-session boundaries | 3 passed, 1.96 s | `artifacts/master-boundary-tests.xml` |
| Final full backend suite | **101 passed, 290.66 s; zero failed/errors/skips** | `artifacts/master-release-backend.xml` |
| Fixed real pickup / cloth repetitions | **20/20 / 5/5** | `artifacts/pick-place-benchmark.json`, `artifacts/cloth-reliability.json` |
| Complete local browser journey | Passed; 441 actual state messages, 70 progress messages, zero page errors and zero axe violations in checked scope | `artifacts/master-live-verification.json` |
| Complete public HTTPS/WSS journey | Passed; seven fresh jobs, 666 states / 89 events, zero captured page errors / axe violations | `artifacts/master-public-verification.json` |
| Current aliases after mobile fix | Passed; real fresh fits, no narrow overflow, direct reload, preserved evidence on network loss and recovery, zero unexpected console/page errors | `artifacts/master-public-boundaries.json` |
| Owned local services refreshed | Passed; current runtime on 8000/UI on 5173, real fits/reload/mobile/offline recovery | `artifacts/master-local-boundaries.json` |
| Strict TypeScript / Vite build | Passed; scoped Windows output build 26.98 s, remote Vercel build 3.19 s | CLI execution, deployment record |
| OpenAPI/type generation, Python compilation, pip check | Passed; no broken Python requirements | Root/docs specs and generated TS types |

The backend suite retains one upstream Starlette/httpx TestClient deprecation warning. Failed intermediate checks were repaired and rerun: initial pickup test requested 60 s beyond the API's 40 s bound; a request-only global dependency broke WS injection, fixed with HTTPConnection; the initial axe harness required a proper browser context. A subsequent mobile Discovery check measured 19 px overflow because an accessible hidden SVG inherited full width; a scoped 1 px rule fixed it and both current public aliases passed. The offline harness initially selected a mobile-hidden badge, corrected to the visible notice. These failed attempts are not included as passing verification. Scoped local output avoids a locked historical Windows dist font. Current public-browser results and the isolated post-journey layout correction are recorded in `DEMO_STATUS.md` and `DEPLOYMENT_GUIDE.md`.

## Performance measurements

`PERFORMANCE_REPORT.md` and `artifacts/master-measurements.json` expose actual initialization, planning, physics/fitting, total wall, process CPU, queue wait, steps/integrations, candidate counts, replay bytes and error rates. Under concurrent headless software rendering, two local pickup jobs took **110.475 / 112.733 s**, and the cloth job took **122.782 s**; both include three validations plus fresh execution. Scientific jobs took **1.746 / 0.947 s**, performing **30 / 51** integrations. Recorded payloads were roughly **3.46 / 3.80 / 2.91 MB** for physical jobs and **40.5 / 40.7 kB** for science. No universal latency/frame-rate SLA or randomized success guarantee is asserted.

## Known limitations and remaining risks

- New staged pickup does not yet implement generalized obstacle-detour planning. Enabling blocking geometry may make every candidate fail honestly. Generalized grasp strategy, perception, arbitrary payloads and broad randomized robustness are not established by identical fixed repetitions and two supported condition cycles.
- Cloth is an experimental pre-attached folding-bar/fixed-hinge fixture, not autonomous frictional garment grasping, dual-arm or arbitrary clothing folding. Material parameters are synthetic and uncalibrated.
- Science is restricted synthetic 2D fixed-perturber model comparison with known initial state/location and local Gaussian uncertainty, not interacting moving planets, posterior inference or discovery of a new physical law.
- Imports cannot execute native uploaded robots/worlds; isolated untrusted worker execution is missing. Static mesh previews do not promise every glTF feature. Never treat them as physics-ready.
- Session capabilities are not full account authentication. Legacy public worlds/imports remain public. Per-account/IP quotas, retention/deletion/backups, global disk bounds, deployment tenancy controls and distributed scheduling are incomplete.
- Deterministic policy requires no LLM key. Optional hosted proposal adapter is separated; no configured real hosted call or model-cost telemetry is claimed for this release.
- Current Render Free hosting works within a finite eight-trial budget but is neither always-on nor durable. Paid activation is blocked by the payment-method prerequisite. Linux Docker execution is verified by the 125-test workflow and 512 MB smoke. No unrelated service was changed or paid plan purchased.
- Full screen-reader/user research, every mobile/device combination, field Core Web Vitals, long-duration soak/load testing and cross-platform bitwise determinism remain unverified. Axe/layout checks cover only their executed scope.

## Hook investigation

The historical "Hook failed: hook exited with code 1" came from a Windows-incompatible POSIX/escaped-path wrapper around the Impeccable hook, registered for both PostToolUse and Stop. Available logs cannot identify which registration emitted that specific occurrence. Both wrappers were repaired and four entrypoint invocations returned exit 0; current frontend edits also receive hook feedback. The Python backend never invokes it. Exact diagnostics, backup and limits: `docs/HOOK_DIAGNOSTICS.md` and `artifacts/hook-verification.json`.

## Reproduction

Use the commands in `README.md` and `FRONTEND_HANDOFF.md`. The live browser demonstration script creates new real jobs, not expected-winner fixtures. For exact numerical extraction from its persistent DB, use `scripts.export_master_measurements` and `scripts.export_frontend_examples` with their `--database`/`--proof`/`--output` arguments. Exported capabilities and generating truth are forbidden by the example exporter.

## Manual-start release

The page now waits for Start experiments. Lab switches, reloads and Apply settings do not submit experiments; explicitly staged settings survive reload. Existing active sessions are cancelled on reload and completed evidence stays inspectable. Layout/styles and physics are unchanged. Local browser checks passed (14 checks); production checks passed (15 checks), including zero automatic session submissions, real SciPy control fits, 5,000 screened pickup commands / three validations / fresh successful execution, eventual safe cancellation and mobile layout. The first production harness incorrectly expected synchronous cancellation; it was corrected to wait for the actual stopped state. Source TypeScript/production builds passed (latest local Vite 12.57 s, remote 2.56 s). Proof: artifacts/manual-start-public.json and manual-start-deployment.json. Backend tests were not rerun for this frontend-only release.

## Earlier pause, local 5,000-trial audit and paid Render preparation — 2026-10-11 (historical)

The page waits for Start experiments; settings, lab switches and reload do not
start new work. Pause/Resume controls the actual worker and retains the same
world/experiment and simulator state; Stop cancels running or paused work.
Original layout/styles and measured Three.js geometry remain unchanged.

Full stable-source Windows regression: **119 passed, 410.15 s**, zero failed,
errors or skips. Linux Docker build and the same full suite: **119 passed,
148.34 s**, zero failures, one upstream Starlette warning. Evidence:
`artifacts/pause-final-backend.xml`, `artifacts/render-linux/backend-linux.xml`.
Linux verification used the dedicated private backend repository; no unrelated
frontend code or data was uploaded.

The exhaustive audit actually completed **5,000 independent distinct MuJoCo
pickup trials**, **36,520,171 trial physics steps**, and a fresh selected physical
execution. All 5,000 succeeded in this fixed clear scene; selected placement
error was 0.00165828179949 m. Exact same-engine repeat and immutable parent
checks passed. This is not evidence of arbitrary-scene or cloth robustness.
Proof and performance: `artifacts/physics-5000.json`, `PAUSE_TRIALS_VALIDATION.md`.

Local live UI passed 17 checks, 610 measured frames / 57 progress messages,
zero page errors and zero axe violations in checked scope. First public pause
journey passed pickup/cloth controls and measured exports, then timed out waiting
for an already-completed SciPy fit to pause; it is recorded as failed, not called
complete. The harness now pauses fast science directly after real REST creation
before delivering its creation response to the browser. Public verification
must be rerun after the hosting endpoint is available.

`render.yaml` proposes one paid 1 CPU / 2 GB instance, a persistent 5 GB `/data`
disk, Singapore, exact CORS/WS origins, health checks and manual deployments.
**At this earlier checkpoint, Render was not deployed:** dashboard and GitHub are connected; $100 credits are
verified. Render requires card registration before paid activation. Render TLS/WSS, restart/disk persistence and remote
performance remain unverified. No paid service has been purchased. The current
temporary tunnel stopped resolving and its renewal failed once; this illustrates
why it cannot provide independently durable availability. Instructions and exact
remaining gates: `docs/RENDER_DEPLOYMENT.md`.

Full traces are kept for the best candidates and fresh execution; other trials
keep actions, complete final integration states, metrics and evaluations in a
paged catalog. Cloth remains three real validations plus fresh constrained fold;
science remains two numerical hypotheses. Sessions have one worker/two slots,
a 180 s heartbeat lease, finite cycles and a two-hour bound for exhaustive pickup.
Active jobs do not resume after a server restart. Account auth, lifetime disk
quotas, automated retention/backup restore, load/soak tests and a zero-downtime
architecture remain incomplete. A paid always-running instance is not a 100%
uptime guarantee.
# Final Factory discovery release — 2026-10-14

The current public build is https://demo.tryvivacity.com/ (Vercel deployment
`dpl_3NVSBD53rJK3fznForaNu8ic9Axz`). Its `/`, `/runtime/health` and
`/runtime/openapi.json` routes returned HTTP 200 after promotion. Render deploy
`dep-db7j6u6k1f9s73fv66g0` is Live on backend commit `0ed1e94`; the source
manifest, Docker build and Linux CI passed. The scoped root checkout change is
documented in `docs/FINAL_PRODUCT_AUDIT.md`.

Working and directly verified in this release: a browser-started public
MuJoCo conveyor run completed at 2.100 s simulated time, displayed 43 saved
frames, and published eight descriptive model series with a genuine poor-fit
label for carton height. A separate public run returned all 43 frames in eight
pages of at most seven, without cursor gaps, and a 177,046-byte ZIP containing
matching `discovery.json` plus a 57,643-byte PDF. The local equivalent executed
1,050 MuJoCo steps and produced 43 frames. The production browser logged zero
JavaScript errors; at a 375 px client width it had no horizontal overflow.
The released robotics API sent nine WebSocket events for a completed four-branch
experiment, including collision/planning failures and an execution success.
All four branches were replayable. Changing its obstacle invalidated the old
result, and a new two-branch experiment completed with a selected branch.

Tests actually executed: full Windows Pytest **297 passed, 1 skipped, 1
warning** in 1,298.49 s. The skip is Linux-specific; the warning is the
existing Starlette TestClient/httpx deprecation. Linux GitHub Actions
[run 38529411185](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38529411185)
passed **298 backend tests** across three shards (87 + 102 + 109) and **4/4
hard 512 MiB host checks**. The focused Factory API/discovery/report/paging
suite passed 15 tests. Frontend API/template/settings/numerical/snapshot
checks passed **36**, and TypeScript/Vite and Vercel production builds passed.
The 512 MiB host peaked at its exact memory cap without an OOM kill, leaving
no measured memory headroom for larger simultaneous reports.

Limits: the official interactive Desmos adapter has no authorized production
key or commercial agreement and was not browser-tested. Its local equation
view, MathML, CSV and JSON export remain available; opaque calculator-state
reopen has unit tests only. A 5,000–6,000 experiment-definition campaign and
cross-run causal law discovery are not implemented. Render currently uses a
Free instance with ephemeral SQLite and possible sleep; always-on uptime and
durable storage cannot be claimed. The remaining web-preview chunk is about
901 KiB gzip. This release did not establish a p95 latency or throughput SLO.
