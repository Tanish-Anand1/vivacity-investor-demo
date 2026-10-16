# Staged factory release — 2026-10-14

Public application: https://demo.tryvivacity.com/.
The implementation was built and checked as P0–P10 slices; the release gate is
tracked in [FACTORY_STAGE_GATES.md](FACTORY_STAGE_GATES.md). The capability
inventory is [FACTORY_CAPABILITIES.md](FACTORY_CAPABILITIES.md), and exact API,
setup, replay and frontend instructions are in
[FACTORY_RUNTIME_HANDOFF.md](FACTORY_RUNTIME_HANDOFF.md).

## Release identity

- Workspace implementation: `e99c0e2`, with exchange-control fix `a1040d4`, on `codex/investor-workspace`, following
  the eleven individually recorded P0–P10 commits.
- Backend: `d94a401858fffd3b54a1bbae53f7b6cc634a834f`, fast-forwarded to the
  existing private runtime repository's main branch; no force push.
- Render deployment: `dep-db78nt59fdbs73d98a7g`, existing Free service,
  reported live after 1m18s. No paid instance or disk was activated.
- Vercel deployment: `dpl_GCf4MA9t8UzE4kWCmfTJkU1NADfb`.
  Both production aliases serve identical HTML. The immutable deployment URL
  is protected by Vercel SSO; public acceptance uses the production domain.
- Deployed OpenAPI exactly matches all 77 paths and schemas in `openapi.json`.
- Machine-readable identities: `artifacts/factory-release-identity.json`.

## Executed regression

The exact deployed backend passed **289 tests**, zero failures, errors or skips,
in its Linux Docker image. Shards: 112 / 398.867 s, 108 / 331.729 s,
69 / 198.601 s. CI run:
https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38456925509.
JUnit evidence is under `artifacts/factory-linux-final/`.

Two independent hard **512 MiB, no-swap** acceptance runs each passed all four
tests (115.863 s and 140.228 s). They exercised every legacy arm, parallel legacy
trials, a three-carton factory batch, camera capture during production, history,
replay, complete JSON, PDF, ZIP and a subsequent camera capture. Native cgroup
OOM and OOM-kill counters remained zero. Peak cgroup usage reached 512 MiB during
archive generation, so this is a tested capacity boundary, not spare capacity
for arbitrary concurrency. Evidence: `artifacts/factory-memory-final/` and the
`memory/` subdirectory of the final Linux evidence.

**31 frontend checks passed** after fixing the deployment packaging boundary.
TypeScript, local Vite and Vercel production builds passed. A generated frontend
layout copy is checked for exact equality with the native layout source.
The large lazy world-preview chunk remains approximately 901 KiB gzip;
Three.js is approximately 263 KiB gzip. No universal frame-rate claim is made.

## Failures found and corrected during the gate

- Initial constrained Linux runs were killed with exit 137. Large traces were
  repeatedly parsed as one SQLite JSON value, retained in live memory and copied
  during serialization/hashing. Records now use indexed summaries and paged
  SQLite samples, retain at most 100 pending samples, and stream JSON archives
  and canonical hashes. Completed native buffers are released between jobs;
  software camera resources and allocator arenas are bounded.
- A closed browser could leave a paused job occupying the worker indefinitely.
  Owned summary/control reads renew a lease; an unattended pause stops after
  two minutes while preserving recorded data. Active-client behavior was tested.
- One functional test used a 20-second wall deadline that expired after physical
  delivery while the shuttle was finishing. Its wait budget is now 60 seconds;
  native controller deadlines and physical acceptance criteria were unchanged.
- The first Vercel build could not import layout JSON outside `frontend/`.
  The deployable generated copy and exact consistency test fixed the boundary;
  the subsequent production build passed. The old investor alias was explicitly
  pointed to the same verified deployment as the custom domain.
- All root commits in this release completed successfully. CRLF notices are Git
  line-ending warnings; they did not prevent committing or running the backend.
- Public visual inspection found 18-pixel-high export buttons and cramped file
  controls. The scoped fix uses 44-pixel controls, explicit spacing and a stacked
  mobile layout. TypeScript/build and actual desktop/mobile browser checks passed.

## Public acceptance

`scripts/demo_factory.py` completed against
`https://demo.tryvivacity.com/runtime`; all physics ran on Render:

- Run `837e5175-6a37-40bb-94db-cd1c1e516ea8`: actual grasp, lift, transfer,
  release, transport and bin-floor delivery; 17,080 integration steps,
  34.160 simulated seconds, 695 stored samples, 125.402 wall seconds and
  17.244 worker CPU seconds. Planning took 0.697 wall seconds; physics integration
  took 36.285 wall seconds. The free host did not sustain real-time execution.
- Run `60afcec8-28df-4977-9593-59aa91a50241`: actual weak-grip lift failure,
  zero deliveries, 4,636 steps, 9.272 simulated seconds and 28.902 wall seconds.
- Benchmark `e0d968ad-1c93-4930-bf06-0e1b14d15f70`: six independent trials,
  65,145 native steps and 482.340 wall seconds. Two training baseline successes
  and two candidate lift failures selected baseline; the separate held-out
  baseline succeeded and held-out weak-grip candidate failed. All failures remain
  in the record. This is a six-trial demonstration, not statistical validation.
- Actual rendered RGB/depth/semantic observation, acknowledged frozen pause,
  resume, replay, complete JSON and identical initial-state idle import passed.
  The first 400-sample replay page was 5,976,609 bytes.
- Public PDF: six pages, 99,990 bytes; all six pages visually inspected without
  clipping. ZIP: 1,652,180 bytes, containing PDF, README, strict definition,
  complete native JSON and sampled CSV. Evidence and runnable sample report:
  `artifacts/factory-public-http/`; page overview:
  `artifacts/factory-public-report-pages.jpg`.

`scripts/verify_workspace_live.py` also passed against public HTTPS and native
WSS. Experiment `c9cec373-2cb3-4672-b1c6-113f888a0897` ran three validations and
a fresh successful physical placement (1.062 mm goal error). It received 12
WebSocket events and a real live frame at 14.062 s, downloaded replay/native
state, changed geometry, confirmed old-result invalidation and executed two new
physics branches. The journey took 59.685 wall seconds. Evidence:
`artifacts/factory-public-legacy.json`.

Public browser checks include idle reload at 0.000 s, applying changed conditions,
strict idle import, actual camera detection at estimated Y=-0.399 m versus truth
Y=-0.400 m, busy-state recovery, 390-pixel reflow without horizontal overflow,
44-pixel export controls, visible keyboard focus and one active factory canvas.
The existing World Labs warehouse rendered and switching to Generate removed
all canvases. No new paid provider generation was performed for this release.
The final production browser run `fd4ca1a7-a5e6-4ba1-85fb-0932663a215e`
completed one physical delivery at 34.160 s. Pause held exactly 7.000 s across
inspection, then Resume continued the same execution. Selecting the lift event
replayed 9.188 s in the viewport, charts and ground-truth panel: carton height
0.197 m and measured gripper force 2.500 N. The engineering PDF downloaded through
the actual UI. Browser console inspection returned no JavaScript errors.
Reset created an idle cell for the next explicit Start.

Render's application-log filter returned all six `factory_trial` entries with
the same run IDs, conditions, outcomes and step counts as the saved benchmark.
They are preserved verbatim in `artifacts/factory-public-render-trials.jsonl`.
Browser evidence includes `factory-public-replay.jpg`,
`factory-public-export-mobile.jpg`, `factory-public-mobile.jpg` and
`factory-public-browser-verification.json` under `artifacts/`.

## Operational limits

This is one tested Panda sorting cell, 1–3 cartons and 6–10 serial benchmark
trials. Contact manipulation, transport, motion and measurements are native
MuJoCo calculations. The camera is genuinely rendered, but semantic IDs are
simulator annotations; there is no trained detector or invented confidence.
Project notebooks have capability ownership and self-reported attribution,
not authenticated multi-user team collaboration. Raw measurements are not
importable as verified executions. There is no hardware-calibrated reliability
or electrical-energy claim.

Render Free sleeps and its SQLite/files are ephemeral. Important runs must be
exported. A hard process loss may discard up to 99 not-yet-flushed samples;
interrupted runs do not claim a final native state or implicit resume.
Long-run, multi-user and report/simulation stress beyond the declared acceptance
sequence remains unverified. Durable storage, authenticated ownership and more
compute are the first operational improvements before broader use.
