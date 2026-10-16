# Runtime stability release — 2026-10-13

The runtime-unavailable/failed-fetch investigation reproduced a real hosting
failure. Render recorded `Ran out of memory (used over 512MB)` at 17:07 IST.
After restart, stale browser session/world IDs returned 404 indefinitely.
The legacy `vivacity-investor-demo.vercel.app` alias also served an older client.
An HTTP health check alone did not detect these application failures.

## Changes

- Production HTTP requests now use the frontend origin's `/runtime` prefix.
  Vercel forwards them to the fixed Render backend. Capability headers remain
  required; private responses have `Cache-Control: private, no-store`, and
  external-rewrite CDN caching is disabled. Native WSS stays on Render.
- Reads have bounded timeout/retry handling for network and 502/503/504 errors.
  Writes are not retried automatically because a lost response may already
  have changed the world or started a job.
- Missing/inaccessible run references are discarded without discarding physical
  preferences. The client initializes an idle world and requires explicit Start.
  An expired saved configuration may use the already-known physical configuration;
  forbidden configuration access is not bypassed. Lost imported files cannot be
  recreated from a browser preference.
- Docker omits rendering-only geometry on bodies with explicit inertia. All
  collision geometry, explicit contact references, joints, inertias, actuators,
  sites and geometry-derived masses remain. Original detailed frontend mesh assets
  remain unchanged. Set `VIVACITY_HEADLESS_GEOMETRY=0` when exporting display meshes.
- Two native MuJoCo trial workers execute independent MjData states. Candidate
  results are consumed in proposal order; adaptive stopping counts complete batches.
  A single experiment worker still queues separate experiments. Fresh selected
  execution follows measured validation/ranking and remains independently restored.
- Trial records expose actual start/end timestamps; progress and performance
  expose `physics_trial_workers` and measured `peak_parallel_trials`.
  Exhausting the final batch reports a budget/exhaustion reason rather than an
  early plateau. Live candidate frames show one actual trial from each batch.

## Executed evidence

- Final backend source: `1b7f5b98467c9c587f273c78b82e918dd5421f60`.
  [Linux workflow](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38394809042):
  **213 passed**, zero failures/errors/test skips, across three disjoint file
  shards (46 + 103 + 64). JUnit durations: 146.435, 267.494 and 209.719 s.
  Additional actual Docker `--memory=512m --memory-swap=512m` checks:
  **3 passed**, 68.756 s. Reports: `artifacts/runtime-final-linux/`.
- The first full Linux run was **211 passed, 1 failed** (851.62 s). It exposed the
  final-batch stopping-report bug; this failed run is retained in
  `artifacts/runtime-first-linux/`, not counted as a pass.
- Windows targeted geometry/dynamics/parallel/capacity checks: **13 passed**,
  83.42 s. Serial and parallel stopping checks after the correction:
  **5 passed**, 9.06 s. Full/pruned dynamics match for all seven arm models;
  sequential and concurrent native trial evaluations/final states match exactly.
- Frontend transport/response/recovery/preview checks: **19 passed**.
  TypeScript/Vite production build passed. Existing large-chunk warnings remain.
- Bare Panda compiled model buffer: **35,378,160 → 752,688 bytes**;
  mesh vertices **396,791 → 2,247**; bodies and joint dimensions unchanged.
  This is a model-buffer measurement, not total service RSS.
  `artifacts/headless-model-measurements.json` contains executed values.
- Public post-memory-fix concurrent requests: **2 experiments**, **6 validation
  integrations**, **2 fresh successful executions**, **50 concurrent HTTP reads**,
  **61.687 s** total. Actual trial timestamps overlap in each experiment.
  Separate jobs correctly queue (measured waits 27.208 s and 0.014 s).
  `artifacts/runtime-concurrency-live.json` contains measured results.
- Public UR5e HTTP/WSS journey: **3 native validation trials**, fresh successful
  execution, **12 events**, replay/export, geometry invalidation and two new
  integrated alternatives; **70.005 s**.
  `artifacts/runtime-proxy-parallel-live.json` contains measured results.
- Public Panda UI: changed mass to **0.065 kg**, recovered an expired world after
  the real restart, ran **6 native validations**, paused/resumed the actual
  workers, and completed fresh placement. Both socket handshakes returned 101.
  No new physics frames arrived while paused; resumed frames reached `verified`
  at actual simulation time **12.110 s**. A subsequent run stopped during fresh
  execution and showed **Cancelled**, preserving validation evidence.
  Actual JSON export: **53 frames**, **6,055 steps**, **155 full integration-state
  values**, **589,972 bytes**. `artifacts/runtime-ui-export-proof.json` records it.
- Blocking direct Render HTTPS in the browser did not prevent the same-origin
  client from connecting and enabling controls. The temporary block was removed.
  This verifies HTTP independence; WSS still uses Render with HTTP polling fallback.
- Final source `1b7f5b9` is live in Render deployment
  `dep-db721ct9fdbs73eot10g`. A fresh hosted six-trial adaptive experiment passed
  after deployment: **6 integrated trials**, measured peak **2** concurrent trials,
  fresh successful execution, **4 replayable branches / 223 frames**, and the
  correct `host_compute_budget` stopping reason; **26.367 s**.
  `artifacts/runtime-final-budget-live.json` is the executed report.
- Local production preview `/runtime/health` was requested through Vite's actual
  proxy and returned HTTP 200 from the local backend. No local physics experiment
  was run for this preview check. Temporary preview/backend servers were stopped.

## Connecting a frontend

On the deployed website, use the exported `API` constant from `frontend/src/api.ts`:
`https://demo.tryvivacity.com/runtime`. Existing `/health` and `/v1/...` endpoint
paths, payloads and capability headers are unchanged. Do not hardcode an absolute
cross-origin HTTP backend URL in components.

For sockets use `websocketURL`, `liveWebsocketURL` and `liveProtocols` from that
module. These use `wss://vivacity-runtime.onrender.com/v1/experiments/{id}/...`;
Vercel HTTP rewrites are not a WebSocket host. Use the actual measured REST/live
fallback and do not synthesize simulation frames on transport failure.

Local development uses `http://127.0.0.1:8000`; production-build preview forwards
`/runtime` to that local backend, or the configured `VITE_API_BASE_URL`.
Run the backend and `npm --prefix frontend run dev` (or `run preview` after build).

## Limits

Render is still Free: eight full trials per experiment, two bounded native trial
workers, one queued experiment worker, idle suspension and ephemeral SQLite/files.
This release does not provide guaranteed availability, permanent history, or
unbounded parallel compute. Import/provenance persistence requires durable hosting.
No 5,000-trial public run is claimed by this release. Adaptive search is measured
best-so-far, not a proof of global optimality. Existing fixture-assisted cloth,
modeled non-Panda gripper, primary-only dual-arm and simplified-world limitations
remain. No additional paid plan was activated.

Official routing/hosting references:
[Vercel rewrites](https://vercel.com/docs/routing/rewrites),
[Render Free limits](https://render.com/docs/free).
