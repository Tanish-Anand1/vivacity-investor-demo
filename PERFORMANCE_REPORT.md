# Executed performance

## Current measured release

| Executed workload | Wall time | Actual physics work | Outcome |
| --- | ---: | ---: | --- |
| Fixed local pickup benchmark | 127.969785 s total | 20 complete executions | 20/20 success |
| Native local Orbital | 9.569583 s | 3 independent trials + fresh execution, 30,757 steps | 1.721393 mm placement |
| Public Render Orbital | 169.474161 s | 3 independent trials + fresh execution, 30,757 steps | 1.717717 mm placement |
| Final public Orbital camera/replan check | 179.380164 s | 3 independent trials + fresh execution, 30,757 steps | Same 1.717717 mm placement |
| Final public blocked reactor | 5.440279 s | 3 collision failures, 384 actual steps | No feasible result |
| Linux deployment-image regression | 351.494 s | 135 executed tests | 135 passed |
| Separate 512 MB lab smoke | 56.313 s | repeated real pickup/cloth/SciPy | 1 passed |
| Bounded-thread Windows regression | 408.16 s | 135 tests collected | 134 passed, 1 Linux-only skip |
| Hosted backend-image varied audit | 894.512 s | 5,000 full MuJoCo trials, 29,625,840 validation steps | 4,000 successes, 1,000 measured collision failures |

Public Orbital CPU **25.381585 s**, planning **6.175765 s**, trial physics
**18.554261 s**, total physics **159.320562 s**, replay **2,790,796 bytes**, branch
failure rate **0**. These measurements include HTTP activity under process CPU
accounting. There are no deterministic-policy model calls or fabricated billed
cost estimates. Source evidence: `artifacts/orbital-public.json`,
`orbital-local-native-api.json` and `docs/FINAL_VERIFICATION.md`.

Render Free has 0.1 CPU / 512 MB and eight full trials maximum. Orbital uses
three. The separate 5,000-trial cloud audit used the same backend Docker image
on a GitHub-hosted runner with a 2 GB memory limit. Its 50 varied configurations
and intentionally blocked controls are documented with [logs and artifact links](docs/PHYSICS_5000_VARIED_AUDIT.md).
Historical 5,000-trial local measurements below remain valid for that fixed-scene
execution, not arbitrary robustness or Render Free performance.

2026-10-11 fixed physical pickup benchmark: 20 executions, 20 successes, total 86.5164 s; physics per execution 3.50–5.45 s; seed planning 0.028825 s. Conditions, per-run durations and step counts are in `artifacts/pick-place-benchmark.json`. No playback is substituted for integration.

Existing backend compatibility baseline: 86 tests, 352.52 s. New pickup/search checks: 10 tests, 47.95 s. Concurrent verification workloads affected wall time; these are observations, not service-level guarantees.

## Actual autonomous browser jobs

Extracted persisted measurements: `artifacts/master-measurements.json`; reproducible exporter: `python -m scripts.export_master_measurements`. These executions ran concurrently with headless SwiftShader rendering on the same Windows machine; software GPU contention substantially increases physics wall time. No latency or frame-rate service-level guarantee is established.

| Lab / cycle | Job wall s | Planning s | Physics / fitting wall s | Process CPU s | Integration steps / calls | Evidence bytes |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| Pickup / 1 | 110.475 | 4.635 | 102.313 | 37.906 | 24,667 steps | 3,459,595 |
| Pickup / 2 | 112.733 | 4.826 | 103.057 | 38.516 | 25,688 steps | 3,804,430 |
| Science / 1 | 1.746 | 0 | 1.067 | 0.563 | 30 solve_ivp calls | 40,519 |
| Science / 2 | 0.947 | 0 | 0.717 | 0.859 | 51 solve_ivp calls | 40,694 |
| Constrained cloth / 1 | 122.782 | 4.355 | 113.135 | 54.563 | 11,032 steps | 2,914,786 |

All five jobs had zero adapter errors and zero measured branch failure rate. These are selected supported scenes, not a general reliability estimate. World initialization timings and per-branch CPU-relevant measurements are also exported. Process CPU includes concurrent requests; selected physical execution wall time includes pacing when enabled.

## Genuine search and resource boundaries

Each pickup cycle generated **5,000 distinct timed commands**, with eight height/IK/contact templates reused where geometry is identical. Every command receives timing/horizon validation; signature uniqueness and catalog digest are measured. Three shortlisted commands were actually integrated and all three validated successfully in these cases. The chosen command then ran again as a **fourth independent authoritative execution**. `result.search.fully_simulated` counts validation branches; `performance.candidate_count` and total steps include that fresh execution. These fields must never be relabeled as 5,000 full physics episodes.

The cloth cycle generated/screened 5,000 proposals: **2,984 rejected, 2,016 screening passes, three actual validation rollouts and three verified feasible folds**, plus fresh selected execution. Proxy screening does not establish dynamic success. Top-three ordering is computed from actual branch evaluations; exports carry those exact actions, states, frames, metrics, engine/configuration hashes and seeds. An unavailable seed path in legacy reaching now terminates bulk variation honestly rather than presenting thousands of unusable paths as useful work.

One physics worker, an eight-job reservation bound, two active session slots, at most eight cycles (two for cloth), a 180 s heartbeat lease, step-boundary physical cancellation and 32 latest-frame entries limit active compute. A job still stores complete branch evidence in SQLite; lifetime database/upload quotas, retention, distributed worker scheduling and comprehensive abuse controls are **not implemented**. Multi-visitor capacity remains intentionally small.

The complete local browser journey took **392.73 s**, received **441 live states / 70 persisted progress messages**, and checked 1440/768/375 px layouts, exact measured transforms and numerical geometry, downloads, keyboard camera, zero captured page errors and zero axe violations. This is journey verification, not a complete screen-reader or real-user performance study.

## Current public release

The complete actual HTTPS/WSS journey at `https://demo.tryvivacity.com/` passed in **507.741 s**, receiving **666 live states / 89 progress messages**, with no captured page errors and zero axe violations in its checked scope. It created seven fresh jobs, including a blocking condition and clear-route recovery; no recorded result was substituted. Evidence: `artifacts/master-public-verification.json`, `artifacts/master-public-measurements.json` and its screenshots/three downloads.

Public pickup whole-job times were **103.575 / 102.346 s** for the two fresh cycles and **110.882 s** after clearing the obstacle. The blocked job took **3.875 s**, integrated **zero steps**, selected no branch and honestly preserved planning failures. Scientific jobs took **0.953 / 0.514 s** with **30 / 51** actual integrations. The constrained cloth job took **109.183 s**, including **11,032 actual integration steps** across three validations plus fresh selected execution. These measurements include software-rendering contention and tunnel request overhead; they are not a scale or low-latency claim.

The subsequent scoped Discovery accessibility layout fix passed a fresh local production build in **45.41 s** under machine contention and remote Vercel build in **2.54 s**. Both current aliases passed fresh numerical fitting, 375 px layout, reload and offline/reconnect checks with zero unexpected console/page errors. Two deliberate offline console failures are categorized separately (`artifacts/master-public-boundaries.json`). The seven-job physics proof precedes that isolated style fix; no physical code changed afterward.

## Executed exhaustive pickup audit — 2026-10-11

`artifacts/physics-5000.json`: 5,000 unique positive-step trials, 36,520,171
trial steps; 36,526,335 total including fresh execution. Job elapsed 3,956.263 s,
trial physics wall 2,853.498 s, process CPU 2,111.328 s, planning 2.633 s.
Replay payload 1,432,169 bytes; compact trial storage 46,764,032 bytes.
All 5,000 succeeded in the fixed unobstructed scene; no generalized success-rate
claim follows. Selected fresh placement error 1.6583 mm. Exact native repeat and
immutable-parent checks passed. Concurrent browser/API activity affected these
local timings. No cloud performance or billed LLM cost is inferred.

Linux Docker full suite passed 119 tests / 148.34 s on a GitHub-hosted runner.
This measures verification, not Render request latency or physics throughput.
