# Isabella Labs by Vivacity — robotics-first release

Date: 2026-10-21. The current homepage is a robotics-led Isabella Labs
experience. A deterministic 7.5-second opening uses three distinct authored
robot-arm silhouettes and two humanoid forms, followed by an identity reveal
and a fade into the already-mounted homepage. The figures are graphic brand
illustrations, not physics output. The opening has a skip button, Escape path,
focus containment, reduced-motion bypass and one-time completion preference.

The new homepage puts a recorded physical workcell beside the central action.
Its two condition buttons show measured weak-grip failure and full-grip
delivery from `scripts/generate_lab_opening.py`. They only inspect a saved
fixture; the application does not start physics on load. `ENTER THE LAB`
opens `/laboratory`, which puts the robotic case first and the SciPy orbital
case second. `/lab` retains the active Factory experiment, `/worlds` and
`/workspace` retain robot-world configuration, and `/discovery` retains the
scientific inference lab. The ordinary frontend labels do not name the robot
physics vendor. The typography uses Google-hosted Instrument Sans, Manrope and
IBM Plex Mono rather than the older local Geist files.

Release verification in this checkout: `npm run build` passed; 28/28 frontend
unit checks passed; the production-bundle Chromium suite passed 12/12 in 3.4
minutes. It exercised both physical failure and success, six independent
backend comparison runs with replay, settings changes, SciPy fitting,
stale-state handling, export and narrow-screen use. Five repeated timed-opening
tests passed in 1.1 minutes. A separate two-route copy audit passed. The
robotic comparison measured 76.1197 s and 4,148/17,083/4,148/17,083/4,148/
17,088 native physics steps. These are case-specific simulated results, not a
hardware reliability claim. The backend itself was not modified in this
release.

The final Vercel production deployment `dpl_FYSpFqYsbyUyrfpwN4Jy2HnqbUGQ`
was READY and aliased to <https://demo.tryvivacity.com/>. The final homepage
and same-origin runtime health returned HTTP 200, and the deployed JavaScript
bundle hash matched the local production build. Direct requests to six UI
routes and runtime health returned HTTP 200 after the first promotion. The
public Chromium suite finished 11/12 in 15.9 minutes. Its only failed check
was a Playwright artifact-directory collision with a simultaneous local run:
the six physical trials finished and produced metrics, but trace cleanup
raised `ENOENT`. With isolated artifacts, that entire live comparison test
passed on the final deployment in 11.3 minutes, including a failed baseline,
six independently restored trials, saved replay and export. It measured
620.3996 s backend wall time, 0/2 versus 2/2 training and 0/1 versus 1/1
held-out deliveries; step counts were 4,147/17,080/4,147/17,080/4,149/
17,088. The final production opening and contrast/accessibility smoke passed
2/2 in 16.6 seconds. The Playwright config now separates local and public
trace directories. GitHub Actions run `39559877403` passed 311 backend tests
and four host-memory checks on the public source commit `06943ae`.

Known limits: the humanoid opening is illustration, not an executable
humanoid model; the homepage condition results are saved evidence, not a new
run; the public Render Free host can sleep and loses SQLite on redeploy; and
the world-preview JavaScript chunk remains roughly 901 KiB gzip. Field LCP,
INP and CLS for this release were not measured.

## Historical scientific laboratory release

Date: 2026-10-21. This section describes the deployed science-led redesign.
The older Factory launch record follows below as historical context.

Isabella Labs now opens as a science and experimentation laboratory by
Vivacity. The homepage presents a **recorded** SciPy orbital inference result,
lets visitors inspect both fitted hypotheses, and links to two executable
disciplines. `/laboratory` is the discipline index, `/discovery` is the new
scientific lab, and `/lab` remains the existing MuJoCo Factory experiment.
No experiment starts on page load. The 7.5-second introduction and broader
robotics routes remain available.

The scientific path creates synthetic observations by integrating a bounded
2D Newtonian model with `scipy.integrate.solve_ivp`, fits central-only and
central-plus-stationary-perturber hypotheses with
`scipy.optimize.least_squares`, and compares training BIC and held-out RMSE.
Each fit has its own persisted branch, numerical trace, parameters, local
uncertainty estimate, status, and replay. A changed observation world marks
old results stale while preserving their history. Commit and reset use the
same versioned world contract as robotics. Generator parameters are withheld
from the fitting adapter and public world state. This model is nondimensional,
synthetic, and deliberately restricted; it is not a real astronomical claim.

The fixed-seed recorded homepage preview was regenerated from executable SciPy
code in `scripts/generate-isabella-science-preview.py`. With SciPy 1.18.1,
70 observations and 49 training samples, central-only held-out RMSE was
0.3075121 and the additional-influence model's was 0.0010204. This is a
preview of that saved run, not a fresh simulation triggered by page load.
The 17,121-byte JSON carries both predictions and observations.

Local verification: the full Python suite finished **310 passed, 1 skipped,
1 warning in 25m 43s**. A subsequent focused API/science run, including the
WebSocket assertion added during the full run, finished **27 passed,
1 warning in 1m 32s**. Frontend unit suites finished **5 template,
4 Factory-settings, 19 API tests passed**. TypeScript and the Vite production
bundle passed. The final Chromium suite finished **12 passed in 3.5 minutes**,
including a real six-trial MuJoCo benchmark, both SciPy fits, changed-world
invalidation, commit/reset, replay/export, expired-storage recovery, mobile
reflow, the timed opening and a homepage axe scan with no serious or critical
violations. The benchmark recorded 0/2 versus 2/2 training deliveries and
0/1 versus 1/1 held-out deliveries; its six physics step counts were 4,148,
17,083, 4,148, 17,083, 4,148 and 17,088. This is one fixed-seed simulated
case, not a hardware reliability estimate.

The private runtime source commit `4b45d9e` was deployed to
<https://isabella-labs-runtime.onrender.com/> on Render Free as service
`srv-dbc09mbbc2fs73aqkf60`; the dashboard marked its first deploy
`dep-dbc09mjbc2fs73aqkg20` successful. Public `/health` returned HTTP 200
with `mujoco 3.15.0`, `scipy 1.18.1`, and `cloth 3.15.0` registered.
The live science demonstration submitted two backend jobs, each with two
persisted hypothesis branches and six WebSocket events. Its signal scenario
selected the extra-influence model after measured held-out RMSEs of
0.3075120601 versus 0.0010203884; the control scenario selected central-only
after RMSEs of 0.0039675485 versus 0.0039675485. The prior job became stale
after a changed observation world. A separate public MuJoCo timeout diagnostic
recorded 50 real physics steps, eight WebSocket events, and matching replay.
The public Factory HTTP demonstration then completed a physical delivery
in **17,080 MuJoCo steps** and an intentionally weak-grip failure in
**4,636 steps**. Camera detection, pause/resume, replay, export/import,
PDF and ZIP report generation all passed on the new backend. This was a
separate run from the six-trial browser comparison.

The initial Vercel production deployment `dpl_HkC5AAawBkRtuo2ZcuGGnHcQ8rQZ`
was marked READY and aliased to <https://demo.tryvivacity.com/>. A final
copy correction was promoted as `dpl_iquVohZXZzFFsczTw1PUYeNf7hxC`, also
READY and aliased to the same URL.
Direct `/`, `/laboratory`, `/discovery`, `/lab`, `/runtime/health` and
`/runtime/openapi.json` checks returned HTTP 200. The proxied OpenAPI
advertises `mujoco`, `scipy`, and `cloth`. Seven public Chromium tests
passed in 1.1 minutes, including homepage accessibility, the robotic world
library, the complete scientific journey, mobile layout, and expired-world
recovery. A visual inspection of the production homepage and discovery lab
confirmed the intended content and controls. A separate public Chromium
Factory journey then passed **3/3 tests in 13.1 minutes**. It executed a
fresh baseline failure and six independently restored MuJoCo trials on the
new Render host, inspected a completed trial during the run, replayed a saved
candidate, and exported the comparison. The backend benchmark measured
**706.1039 seconds** wall time, training baseline **0/2** versus candidate
**2/2**, and held-out baseline **0/1** versus candidate **1/1**. Native step
counts were **4,147, 17,080, 4,147, 17,080, 4,149, 17,088**. This verifies
the specific simulated case; it does not establish population reliability.
After the final promotion, six direct site/API routes again returned HTTP 200,
and a targeted public Chromium homepage test passed. The final live homepage,
lab selector and discovery page were visually inspected; the source label
renders without an erroneous dollar sign, the scientific lab loads idle,
and the browser console showed only the known non-fatal Three.js Clock
deprecation warning.

Render Free explicitly warns that the instance spins down after inactivity,
possibly delaying a request by 50 seconds or more. SQLite is ephemeral on
this host. The service is not always-on and does not provide durable history;
the science UI reports expired saved worlds and permits a fresh start.
The production homepage also emitted a non-fatal Three.js Clock deprecation
warning from the retained 3D preview; no browser error was observed in the
inspected route.

## Historical Factory-first launch record

# Isabella Labs by Vivacity — launch evidence

Date: 2026-10-21. Product URL: <https://demo.tryvivacity.com/>. This report separates the recorded homepage presentation from experiments executed by the public runtime.

## Architecture and implemented journey

The frontend is a React/Vite application. `/` is the Isabella Labs homepage; `/lab` is the Factory laboratory; `/worlds` is the existing world library; `/workspace` and `/experiments` retain the broader robotics workspace and saved experiment history. The homepage does not issue simulation-start requests on load. Its first-paint poster is a still of the actual renderer, faded when WebGL is ready. The interactive preview and plan-view path use **recorded MuJoCo body transforms** generated by `scripts/generate_lab_opening.py`; they never populate live results.

The 7,500 ms opening uses one `performance.now()` timeline with deterministic stage intervals, skip/Escape, focus containment, reduced-motion bypass, local completion preference, and resource cleanup. It reveals the already-mounted homepage scene so no second WebGL world is swapped in at the end. The first screen explains the product and provides working **Enter the Lab** and **Watch an Experiment** actions. The latter creates or reloads a one-carton world and starts a fresh production run only after the click.

The laboratory continues to use the existing FastAPI/MuJoCo Factory service, SQLite experiment storage, ownership capability token, validated configuration, saved initial simulator state, native physics worker, and recorded sample pages. Explore presents the failed baseline, a gripper-force intervention, six independent matched training/held-out runs, measured comparison, and pause/stop. Research opens the same cell and records, including world provenance, production settings, recorded traces, numerical plots/fits, saved runs, project versions, and export controls. Completed trials can be inspected while the benchmark worker continues; the selected world and job remain intact. The larger robotics world library, robot models, templates, and existing API remain accessible.

The homepage's one-world comparison is a **recorded preview**, explicitly described as such. Its delivery counts, positions, force scales, and step counts are copied from executed MuJoCo runs. It is not an LLM response, a live experiment, hardware evidence, or a video result. A new baseline and comparison always come from the backend.

## Capability boundary

| Capability | Launch status and evidence |
| --- | --- |
| Isabella opening, homepage, recorded interaction | Implemented; timed, keyboard, reduced-motion, desktop/mobile, visual, Firefox/WebKit and asset-failure checks passed. |
| Guided Factory physics and controlled comparison | Implemented; local and public browser journeys executed real baseline and six independent MuJoCo trials. |
| Inspect, replay, compare and export | Implemented for the flagship Factory run; local and public browser journeys verified saved trial inspection, measured partitions, replay sample seek, CSV download and benchmark-definition export. |
| World library and broader robotics workspace | Preserved; public browser test opened the library, selected a world and loaded `/workspace`. Every arm/task/provider combination was not revalidated in this launch. |
| Provider-assisted world generation and optional Desmos/LLM paths | Existing bounded integrations remain in the product; no provider calls were executed in this launch. Availability depends on server configuration and account quotas. |
| Physical hardware, accounts, guaranteed durable cloud history, per-visitor rate limit | Not implemented or not demonstrated. The global Factory worker bounds concurrent physics, but a visitor can still consume the shared free service for a long batch. |

## Measured evidence

Regenerating the fixed-seed preview produced a weak-grip `dropped_object` failure after **4,148** MuJoCo steps and a full-grip completed delivery after **17,083** steps. The resulting JSON contains **27** and **100** transform samples and is **170,225 bytes**, SHA-256 `231af237c5781955754b6a75ab8a76e842c32e2ba59c695a45119f127c777339`. The first-paint WebP poster is **26,392 bytes** and is not used for results.

In the final locally exercised guided journey, the baseline failed with `0 of 1 delivered`. Six matched backend trials produced training baseline **0/2**, training intervention **2/2**, held-out baseline **0/1**, and held-out intervention **1/1**. The benchmark took **77.766 seconds** wall time in that run. Native step counts were **4,148, 17,083, 4,148, 17,083, 4,148, 17,088**. These values describe the seeded simulated experiment and do not estimate hardware reliability or statistical significance.

## Verification

| Boundary | Actual result |
| --- | --- |
| Backend full suite | **297 passed, 1 skipped**, one upstream Starlette/httpx deprecation warning, in 26m 53s. |
| Frontend unit suites | **5 template, 4 Factory settings, 19 API tests passed**. |
| TypeScript and production bundle | `npm run build` passed; no new runtime dependency. The existing Three vendor chunk is about 980 KB minified / 263 KB gzip; the existing world-preview chunk is about 2.53 MB / 901 KB gzip. |
| Browser, local Chromium | **8 passed in 3.6 minutes**. The opening, homepage, keyboard path, reduced motion, mobile reflow, world-library selection, missing-asset recovery, physical failure, matched benchmark, interim inspection, replay, and CSV/export API were exercised. |
| Automated accessibility | Homepage axe scan found **no serious or critical WCAG 2 A/AA or 2.2 AA violations**. This is not a substitute for full assistive-technology testing. |
| Public backend health | `https://demo.tryvivacity.com/runtime/health` returned HTTP 200 before the Isabella deployment. Post-deployment verification is recorded below. |

The prior public Factory release completed a live baseline, but its six-trial benchmark was only **3/6 after 6.2 minutes** on the Render Free host; the public browser test timed out before the batch finished. The UI now exposes completed trial evidence during a long run. Do not interpret local completion time as the public-host latency.

### Final browser suite

`npx playwright test --config playwright.factory.config.ts --output test-results/final-local --reporter=list` completed with **8 passed (3.6m)** after the first-paint poster and route checks. Captured screenshots cover the opening at five timestamps, desktop first viewport, comparison section, and narrow layout. The desktop and narrow screenshots were visually inspected: the live Three.js workcell rendered behind the homepage, typography and actions remained legible, and the narrow layout had no horizontal overflow. A public Chromium screen recording was captured and inspected at several timestamps; its page produced no uncaught JavaScript errors. The local recording is at `frontend/test-results/isabella-recording/isabella-opening-cut.webm` (7.36 seconds; not part of the deployed bundle).

### Production release

The final Vercel deployment `dpl_2rYBAe8emo8y2qU5WF4x8vpG6N23` was marked `READY` and aliased to <https://demo.tryvivacity.com/>. Direct `GET` checks for `/`, `/lab`, `/worlds`, `/runtime/health`, and the scene poster returned HTTP 200. **Five** Chromium tests against the final alias passed (opening, accessible homepage controls, world-library selection with `/workspace` URL, reduced-motion/mobile navigation, and asset failure recovery). A one-off public Chromium lab measurement found first-contentful-paint/LCP samples of **828/828 ms** at 1440×900 and **676/692 ms** at 390×844 on this machine and connection. These are single lab samples, not field Web Vitals. The full public-host physics journey result is recorded below after its run.

Separate Firefox 157 and Playwright WebKit 27.2 public smoke checks reached the homepage, rendered the WebGL scene, switched to the measured weak-grip preview, played and paused recorded samples, and showed no horizontal overflow or uncaught page errors. Both first viewports were visually inspected. A physical Safari installation and its platform-specific behavior were not tested.

### Full public-host physics journey

An isolated Playwright journey **passed (1 test, 12.2 minutes)** against <https://demo.tryvivacity.com/> and the Render backend. It covered a fresh failed baseline, six independently restored MuJoCo trials, inspection of a completed trial while later trials ran, the measured training/held-out comparison, replay of a saved candidate, CSV download, and the benchmark-definition export endpoint. The public benchmark reported training baseline **0/2**, candidate **2/2**, held-out baseline **0/1**, candidate **1/1**, with native step counts **4,147, 17,080, 4,147, 17,080, 4,149, 17,088**. One public batch measured **669.292 seconds** backend wall time; the complete browser journey took **12.2 minutes**. Slight native step differences from local Windows results are reported rather than concealed; reproducibility is scoped to fixed simulator/runtime conditions, not bit-for-bit cross-platform identity. This long browser session began before the final route, intro-focus and asset-error updates; the Factory physics code and backend were unchanged, and the affected final-alias paths/states were tested separately in five public Chromium checks.

A separate public route smoke used the live controls to traverse `/lab` → `/settings` → `/worlds` → `/import` → `/worlds` without uncaught page errors. A focused public browser test additionally waited for the saved world configuration panel after choosing a world, verifying that navigation did not merely show the workspace shell before persistence finished.

An earlier public run completed the same six trials but Playwright failed while disposing its trace because a simultaneous smoke test had cleaned the shared artifact directory. The physics results had completed; rerunning with a separate output directory resolved the test-runner collision and produced the passing result above.

## Known limits and risks

- Results are simulated with an idealized MuJoCo model and constrained controller. No physical robot, safety certification, or deployment reliability is claimed.
- The public Render Free backend can cold-start. Its SQLite files are on ephemeral storage; runs can be lost after a restart or deploy. There is one global Factory worker, which bounds concurrent physics jobs but also creates a queue/busy state. Per-visitor rate limiting and durable account-based history are incomplete.
- The flagship matched comparison uses a small sample. It may fail, tie, or select the baseline under different conditions. The UI must report those outcomes honestly. No general 5,000-iteration campaign is part of this journey.
- WebGL startup is hidden by a static poster, but the 3D renderer and world-preview bundle remain substantial. Asset failure now announces the degraded preview while preserving recorded measurements. Lab performance on low-end phones, full Safari/Firefox task journeys, and screen-reader interaction beyond the automated scan require further verification. A six-trial public batch completed, but its roughly 11-minute latency on Render Free is unsuitable for a short live investor walkthrough without a faster host or smaller explicitly labelled batch.
- Descriptive fitted relationships in Research are not causal physical laws. Desmos embedding requires its configured API key; measured built-in plots and LaTeX remain available without it. Optional providers are not used as a physics engine.

## Reproduce locally

From the repository root after installing `requirements-lock.txt` into `.venv` and running `npm ci --prefix frontend`:

```powershell
.\.venv\Scripts\python.exe scripts\generate_lab_opening.py
.\.venv\Scripts\python.exe -m scripts.test_backend -q
cd frontend
npm run test:templates
npm run test:factory-settings
npm run test:api
npm run build
npx playwright test --config playwright.factory.config.ts
```

The Playwright config starts FastAPI on port 8002 and Vite preview on port 5176. The full browser suite executes real physics and takes several minutes locally; the public host is slower.
