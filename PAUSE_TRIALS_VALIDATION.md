# Real pause/resume and exhaustive pickup trials

The local/default paid Object Pickup client requests one experiment with 5,000 distinct
commands and `physics_trials:5000`. All 5,000 commands, including screening
rejections, are attempted in independent MuJoCo states. Success comes only from
measured grasp, lift, retention, release, table support and placement checks.
The selected successful command is then executed again using the existing
authoritative adapter. A failed fresh execution is reported honestly.

The current Render Free frontend uses `VITE_PHYSICS_TRIALS=8`, and the server
enforces `VIVACITY_MAX_PHYSICS_TRIALS=8`. Those eight commands each undergo real
physics; the current public release does not claim a completed 5,000-trial cloud
run. Current executed cloud evidence and resource limits: `docs/HOSTING_STATUS.md`.

Cloth still uses 5,000 screening proposals and three physics validations plus
fresh execution. Discovery fits two hypotheses using SciPy. The exhaustive
physics option is rejected for cloth, scientific and legacy reaching worlds.
This is a fixed synthetic pickup benchmark, not 5,000 different scenes or a
generalized robot-success guarantee.

## Pause semantics

POST `/v1/sessions/{id}/pause` and `/resume` require `X-Session-Token` and return
`vivacity.session/1.0`. The additive fields are `pause_requested`, `paused` and
`paused_seconds`. A request is acknowledged only at a worker checkpoint. Until
`paused:true`, show “Pausing safely”; afterward show “Simulation paused”. Resume
continues the same world, experiment, candidate and full simulator state.

Native trials check between chunks of at most 128 integration steps (0.256 s
of simulated time). The selected pickup and actuated cloth check every step.
Scientific fitting checks between numerical prediction integrations. An
individual solve_ivp call and initial planning work can finish before pause is
acknowledged. Pause does not rewrite frames or replay a completed trace.

GET the session periodically to maintain its 180-second lease, even while
paused. Stop, lease expiry and shutdown cancel paused work without requiring
Resume. Pause time is excluded from adapter active-wall timeouts; the session
has an absolute two-hour bound for exhaustive pickup and a 30-minute bound for
other modes. The page does not start an experiment on load, reload, settings
application or lab selection. Reload stops an existing active session.

## Measured trial catalog and replay

GET `/v1/experiments/{id}/trials?after=-1&limit=50` returns:

```json
{"schema_version":"vivacity.trials/1.0","completed":1,"items":[{"schema_version":"vivacity.trial/1.0","completion_seq":1,"candidate_index":417,"parent_state_reference":"world:revision:snapshot-sha256","action":{},"engine":"mujoco.rollout/contact-sensors-v1","control_sha256":"command-sha256","final_state":{},"evaluation":{},"performance":{}}],"next_after":1}
```

This illustrates field names, not fabricated experiment results. The actual
records include full eight-stage commands, final `mjSTATE_INTEGRATION` vectors,
measured evaluation and physics step/wall counts. Use returned `next_after` as
the next cursor. It is a database-wide completion sequence, not candidate index;
late lower-index candidates cannot be skipped. Maximum page size is 100.
Session-owned catalogs require the same capability as their experiments.

Full frame traces are retained for the current best three and any preceding
improved best branches, plus fresh authoritative execution. Other trial records
retain their measured final state and reproducible action rather than 5,000
large frame traces. Existing replay/export endpoints expose retained real traces.
The world geometry revision invalidates older catalogs and replay results through
the enclosing experiment's `stale` flag.

Native MuJoCo rollout uses `mjSTATE_FULLPHYSICS`, all `mjSTATE_USER` inputs and
actual warmstart state for each chunk. Full parent/final snapshots remain
`mjSTATE_INTEGRATION`. Diagnostics-only contact sensors do not alter the physical
model/hash. Per-step native sensor forces precede integration by one timestep.
Aggregated prohibited-contact diagnostics report a category and first observed
step; exact pair names are not inferred. Fresh authoritative execution retains
the existing detailed contact classification. Both adapters independently
evaluate physical success; numerical bitwise equality between adapters is not
assumed. Same-engine fixed-state repeat is tested.

## Reproduce verification

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.venv/Scripts/python.exe -m pytest -q --junitxml=artifacts/pause-runtime-regression.xml
.venv/Scripts/python.exe scripts/verify-physics-iterations.py
$env:UI_URL='http://127.0.0.1:5175/'
$env:API_URL='http://127.0.0.1:8002'
node scripts/check-pause-live.mjs
```

The exhaustive audit executes all 5,000 real trials, checks independent parent
references, unique commands, positive steps, complete final states and measured
step totals, then repeats the selected native command exactly. It writes
`artifacts/physics-5000.json` only after its assertions pass. Local SQLite evidence
is `data/run/physics-5000.sqlite3`. The browser test verifies the default 5,000
request, freezes/resumes actual native state and stops that partial run; its
second pickup is explicitly bounded to eight real trials for smoke testing. It
also pauses/resumes fresh execution, cloth and SciPy. This distinction is
recorded in browser proofs; a partial public run is not called 5,000 completed
trials.

## Actual executed results — 2026-10-11

Final stable-source full suite: **119 passed**, zero failed/errors/skips,
410.15 s (JUnit suite time 409.708 s), one upstream Starlette TestClient warning.
Evidence: `artifacts/pause-final-backend.xml`. An intermediate test started before
an idempotency repair was imported failed once; the final unchanged-source full
rerun passed. TypeScript and local production build passed, Vite 19.52 s;
Vercel remote build passed, 3.95 s. Existing bundle warning remains.

**Full audit passed:** 5,000 distinct commands, 5,000 positive-step independent
trials, 36,520,171 trial integration steps; 36,526,335 including fresh selected
execution. All 5,000 were feasible in this fixed unobstructed scene. This does
not establish success under arbitrary obstacles or materials. Fresh selected
placement error: 0.00165828179949 m. Immutable parent and exact selected
same-engine repeat passed. Job elapsed 3,956.263 s; audit 3,970.799 s; trial
physics wall time 2,853.498 s; stored trial records 46,764,032 bytes; replay
payload 1,432,169 bytes. Source: `artifacts/physics-5000.json` and its local DB.

Local live UI passed 17 checks in 536.19 s, 610 actual physics frames and 57
progress messages, zero page errors/axe violations in checked scope. Evidence:
`artifacts/pause-local.json`. First public run passed robotics/cloth control and
real exports but timed out waiting for a fast scientific fit to acknowledge
pause; persisted science evidence actually completed. The harness now requests
science pause immediately through REST after session creation before delivering
the response to the browser. This reduces the completed-fit timing race;
subsequent public outcomes are recorded separately, not retroactively changed.

Linux deployment image also built and passed all 119 tests in 148.34 s. Final
manifest-preserving package passed source integrity, rebuilt and passed all 119
again in 269.17 s. Reports: `artifacts/render-linux/backend-linux.xml` and
`artifacts/render-linux-final/backend-linux.xml`. Neither run deploys a Render
service or establishes cloud uptime. Render preparation and deployment blockers:
`docs/RENDER_DEPLOYMENT.md`.

## Deployment preflight and slow local browser diagnostic

The live HTTP/WebSocket demonstration passed again on the current local API:
`artifacts/render-preflight-summary.json` and the complete responses in
`artifacts/render-preflight-live.json.gz`. It measured failed/successful reaches,
exact reruns, environment invalidation, stale commit rejection, replanning,
all-paths-fail behavior, SciPy held-out predictions and unnecessary-mass
rejection. A separate direct API pickup completed eight native trials plus a
fresh contact-validated execution in 17.417 s, with 67,488 actual integration
steps and 1.749 mm placement error: `artifacts/native-api-diagnostic.json`.

An additional local browser attempt failed its six-minute wait for ten initial
trials, before testing pause. Seven successful trials and one cancelled trial
were actually persisted; 207 measured live messages arrived and no page errors
were recorded. This failure is retained in `artifacts/pause-local-final.json`;
it does not replace the earlier complete 17-check pass. Trial wall times during
that browser run were 24–60 s, versus 0.355–0.676 s in the direct API diagnostic.
The underlying contention cause has not been isolated. The control journey now
waits for two genuine trials before pause and two additional trials after resume,
because throughput is verified separately by the completed exhaustive audit.
This smaller sample does not claim 5,000 browser-driven trials finished.

The subsequent run passed six checks, including native worker pause/resume,
same-world continuation, measured trials, Stop and interactive camera controls.
It then failed on an Undici `UND_ERR_SOCKET` connection reset while reading the
bounded second session. The API remained healthy; the server also logged a
Windows Proactor `WinError 10054`. This is not a complete browser pass:
`artifacts/pause-local-control.json`. The harness now retries only transport
errors of idempotent GETs (at most twice) and records each retry; HTTP/contract
failures still fail immediately and mutations are not retried. Syntax was
checked, but the complete journey with this retry repair still needs execution
against the provisioned Render service.

Disk-compatible deployment revision `7d899a2` passed all 119 Linux tests again,
JUnit suite time 146.820 s, zero failures/errors/skips:
`artifacts/render-linux-deployment/backend-linux.xml`.
