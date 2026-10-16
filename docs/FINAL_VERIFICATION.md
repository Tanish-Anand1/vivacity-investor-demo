# Final engineering verification — 2026-10-11

This file distinguishes executed evidence from implementation and hosting limits.
The public demo is https://demo.tryvivacity.com/; backend
https://vivacity-runtime.onrender.com. The same high-level runtime runs Panda,
Orbital adaptation, experimental flex folding and SciPy inference.

## Executed test evidence

- Final Linux Docker source `69013a8f6b538398a042a4f862638aac50865f20`:
  **135 passed, zero failed, zero skipped, 351.494 s**. Actual CI run:
  https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38158305693.
  Includes native syscall denial, original Orbital actuator motion, adapted
  physical cargo delivery, export and blocked-layout invalidation tests.
- Separate **512 MB container: 1 passed, 56.313 s**, executing pickup, cloth
  and science under the host's memory limit. This is not proof of indefinite
  availability or arbitrary-upload memory safety.
- Reports: `artifacts/orbital-final-linux/backend-linux-verification/backend-linux.xml`
  and `host-memory-verification/host-memory.xml`.
- Windows import/Orbital regression: **25 passed, one Linux-only skip,
  27.96 s**, `artifacts/orbital-complete-tests.xml`.
- Unrestricted Windows full run under concurrent browser load: **132 passed,
  two supervisor 120-second deadline failures, one Linux-only skip, 729.45 s**.
  Preserve `artifacts/master-final-backend.xml`; do not describe it as passing.
  A separate run with numerical threads fixed at one is recorded independently.
- Bounded-thread Windows rerun: **134 passed, one Linux-only skip, 408.16 s**,
  pytest wall time; JUnit reports **405.798 s**. Report:
  `artifacts/master-final-backend-bounded.xml`. Tests were not weakened and
  supervisor deadlines were not extended to manufacture a passing report.
- TypeScript check and production Vite build executed successfully. Three.js
  vendor bundle remains approximately 933 KB uncompressed; lazy loading reduces
  the initial application bundle. This is a size measurement, not a CWV claim.

## Real robotics and science

Fixed workcell benchmark: **20/20 successful real pick-and-place runs**, zero
failures, 127.9697845 s total locally. Goal error about 1.70 mm with bilateral
grasp, lifting, retention, release and table support. These repeat one fixed
configuration, not 20 independently randomized geometries. Source:
`artifacts/master-final-pickup-20.json` and its recorded trace.

Public baseline (2f61389): eight distinct native physics trials plus fresh
selected execution, 67,488 total steps, wall 269.2703343 s, process CPU
40.3177652 s, goal error 1.749 mm, no prohibited contacts. Replay payload
1,628,759 bytes. Actual downloads and measured Pause/Resume were verified in
that revision. The latest directive removes the UI pause/player controls;
backend native Pause/Resume APIs remain available and tested.

Public flex run: three validations plus fresh physical fold; final alignment
0.923365 mm, vertex coverage 100%, quality 0.969221, clamp error 0.673552 mm,
maximum penetration 1.981481 mm. **Experimental**: Panda carries a folding bar
with seven pre-attached cloth constraints. Autonomous cloth grasp acquisition
is not implemented. It is not ordinary finger grasping of loose fabric.

Public SciPy fits: central-only held-out RMSE 0.3075120601; additional-influence
RMSE 0.00102038844, fitted central parameter 0.9999784517 and perturbing mass
0.1198718478. Actual `solve_ivp`/`least_squares` integration counts and covariance
are in the stored hypothesis evaluations. A separate no-influence control
selected the baseline. This is restricted synthetic 2D inference with a known
perturber location, not discovery of a real planet or a new law.

Public API script passed all nine checks: real HTTP/WSS, deterministic physical
re-execution, failed and successful reach, geometry change/replan, stale commit
rejection, actual all-paths failure, competing fits and unnecessary-mass
rejection. `artifacts/render-live-demo.json`. Both frontend aliases also passed
real fits, narrow layout, direct reload and offline/reconnect checks:
`artifacts/render-final-public-boundaries.json`.

Public cloth/science browser partition passed eight checks, 113 live frames,
27 events, zero page errors, zero axe violations in the checked workspace
scope: `artifacts/render-final-labs-long.json`. Earlier six-minute cloth check
and the composite pickup/cloth click-timeout report remain failures; the
successful partitions do not retroactively turn them into full-suite passes.

## Orbital adaptation

Original fixture really compiled and drove an actuator: 125 steps, 0.5 simulated
seconds, 0.0742063 rad displacement. It has no actuated gripper and is not
task-ready. A checksum-matched adapter replaces the robot with Panda, resizes
cargo, relocates endpoints/reactor and aligns the deck to the validated
workspace. The docking platform is a marked region of the physical deck.
Terrestrial gravity is retained. Original file, source hash and changes are
documented in `fixtures/imports/ORBITAL_SOURCE.md` and `docs/ORBITAL_HANDOFF.md`.

Native local Orbital API: **three independent full native trials plus fresh
execution**, 30,757 total steps (23,725 trial steps), goal error 1.721393 mm,
zero branch failures, wall 9.569583 s, CPU 8.15625 s, planning 0.50832 s,
replay payload 2,790,531 bytes. `artifacts/orbital-local-native-api.json`.

The local browser journey passed ten checks, 235 measured live frames, ten
events: original readiness, actual native motion, no auto-start, independent
physics and fresh delivery, exported states/contacts/provenance, rendered cargo
matching live transforms, one inspector, no player controls, keyboard camera,
mobile/axe scope and idle reload. `artifacts/orbital-local-final.json`. An earlier
browser run was cancelled by a development hot update; its failed report is
retained. The production journey is measured separately after rollout.

Public Orbital on source 69013a8 also passed all ten checks: **426 measured
frames, ten events, zero page errors, zero axe violations in the tested scope**.
Actual job: three native trials plus fresh selected execution; **30,757 steps**,
**1.717717 mm delivery error**, bilateral grasp/lift/retention/release/deck support,
no prohibited contacts. Wall **169.474161 s**, CPU **25.381585 s**, planning
**6.175765 s**, native trials **18.554261 s**, total physics **159.320562 s**,
replay **2,790,796 bytes**. `artifacts/orbital-public.json` and downloaded
`artifacts/orbital-public-branch.json`; actual screenshot `orbital-public-verified.png`.

Render deployment `dep-db5s8hks728c738sccf0` is live at source 69013a8. Vercel
release `dpl_9kYzmrxJgMi2mLFmB8fAX8a1bBEX` serves both demo aliases. Live OpenAPI
exactly matches exported `openapi.json`/`docs/openapi.json` (26 REST paths plus
documented WebSocket extensions). No unrelated frontend work was reset.

The nine-check live HTTP/WSS/re-execution/replan/all-fail/SciPy/control script
also passed again against the new 69013a8 release:
`artifacts/orbital-release-live-demo.json`. Its blocked scene genuinely reports
no solution, and its no-influence control genuinely selects central-only.

Final Orbital-only camera correction was visually inspected and deployed.
The production rerun passed **12 checks**, **428 measured frames**, **17 events**,
zero page errors and zero axe violations in the checked scope. It additionally
changed the reactor through the UI, verified stale results and no auto-start,
then ran **three real collision failures (128 steps each)** with no selected
result. Final successful job wall **179.380164 s**, CPU **26.848431 s**, physics
**168.256571 s**, planning **7.024571 s**, unchanged **1.717717 mm** goal error and
**30,757 steps**. Blocked job wall **5.440279 s**, 384 total steps. Reports and
actual screenshot: `artifacts/orbital-public-final.json`, its `-branch.json` and
`-verified.png`. Original public ten-check proof is retained separately.

Both aliases were then verified on the final camera release, with actual SciPy
fits, session-preserving reload, 375 px layout, retained offline evidence and
reconnection. No unexpected console/page errors were captured; intentional
offline errors are recorded separately. Current result:
`artifacts/orbital-final-aliases-boundaries.json`.

## Remaining limits and operational risks

- Render **Free**, 0.1 CPU / 512 MB, eight full trials maximum. It sleeps after
  15 idle minutes and may take 50 seconds or more to wake. SQLite is ephemeral
  across restarts/redeploys; there is no persistent disk. Paid compute/disk is
  blocked by the payment-method prerequisite. Credits do not remove it.
  No always-on claim, durability claim, fake keepalive or card workaround.
- Historical 5,000-trial result is real local evidence, not cloud verification.
  Current cloud budget is eight; Orbital uses three actual trials. Screened
  candidate counts never imply full physics execution.
- Generic visual imports stay visual-only. Generic MJCF/URDF capability probes
  do not automatically supply a manipulation controller. Only the supplied
  Orbital checksum has a configured task adapter. Native plugins and generated
  composite/flex/heightfield assets are excluded from native probes.
- Linux native probes have CPU/address-space/file/process/network constraints;
  Windows permits only the exact trusted fixture. This restricted data importer
  is not a general arbitrary-code execution platform or independently audited
  multi-tenant production sandbox.
- Fixed pickup and Orbital are constrained staged manipulation. General pickup
  routing around arbitrary obstacles, spacecraft dynamics, automatic semantic
  robot task discovery, hardware control, distributed workers, account identity,
  billing and calibrated real-world cloth handling are not implemented.
- Bounded existing supervisor changes conditions between cycles and genuinely
  recomputes; Orbital starts one manually requested bounded experiment. No
  unbounded continuous Orbital supervisor is claimed.
- No comprehensive human screen-reader study, field CWV measurement or
  broad randomized-manipulation reliability claim.

## Reproduction

Run backend with Python 3.11+ and the pinned lock file; Linux Docker uses Python
3.12. On Windows, numerical thread limits also avoid uncontrolled BLAS overhead:

```powershell
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
.venv/Scripts/python.exe -m pytest -q --junitxml=artifacts/backend-check.xml
.venv/Scripts/python.exe -m uvicorn vivacity.api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
$env:VITE_API_BASE_URL='http://127.0.0.1:8000'
$env:VITE_PHYSICS_TRIALS='8'
npm --prefix frontend install
npm --prefix frontend run dev
```

Use `scripts/demo.py` for reach/replan/science; `scripts/demo_orbital.py` for the
supplied native import and actual delivery; `scripts/check-orbital-live.mjs`
for the browser journey. Explicit `API_URL`, `UI_URL` and `PROOF_PREFIX` select
local or public verification. API examples/geometry/WS/export formats are in
`FRONTEND_HANDOFF.md`, `docs/ORBITAL_HANDOFF.md` and exported `openapi.json`.
