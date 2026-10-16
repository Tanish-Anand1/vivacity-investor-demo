# Vivacity product and launch audit — 2026-10-14

This is an evidence-based inventory for the current Factory-focused release.
Historical results in other files describe earlier commits and are not a
current acceptance gate. The source of truth is the saved backend experiment;
browser charts and reports are derived views.

| Capability | Status | Current evidence / boundary |
| --- | --- | --- |
| MuJoCo Factory conveyor and physical production | Implemented and tested | Existing production controller and contact outcomes are covered by the backend suite; a fresh local conveyor completed 1,050 native steps and 43 frames. This run tested transport, not grasp/placement. |
| Progressive equation discovery | Implemented and tested | Background worker fits recorded MuJoCo scalar samples at 25 samples and on finalization. Eight final quantities, chronological holdout and poor-fit status were observed in a browser-started local run. |
| Desmos-compatible expressions and measured exports | Implemented and tested | Backend fit tests, frontend decimal/snapshot tests, CSV/JSON and live browser visualization. |
| Official interactive Desmos embed and saved-state reopen | Implemented but not fully tested | Adapter uses the documented Graphing Calculator API, including `getState`/`setState`; no authorized commercial browser key is configured, so the vendor UI and import interaction cannot be accepted live. The fallback graph and equations remain available. |
| PDF and ZIP fit provenance | Implemented and tested | Real local MuJoCo run generated a PDF with fitted equations and held-out metrics and a ZIP with the matching persisted `discovery.json`. |
| Live replay pagination | Implemented and tested | Regression test crosses SQLite and in-memory sample pages without duplicates or cursor skips. HTTP playback was exercised in seven-frame pages. |
| Legacy Factory settings editability | Implemented and tested | Missing old X/Y draft fields now fill from current defaults; a local browser loaded the old cell with editable values and applied a new one-carton condition. Original saved records are not rewritten. |
| 5,000–6,000 experiment-definition campaigns | Not implemented | Existing physics-trial limits and small controlled benchmarks are different features. No campaign scheduler, queue, cancellation/recovery protocol or 5,000-definition acceptance run exists. |
| Worker parallelism at campaign scale | Not implemented | Native trials are bounded in the existing runtime; this is not a measured high-throughput campaign system. |
| Cross-run causal law discovery | Not implemented | Per-run fitted trajectories and one joint association are descriptive. Mass/force and speed/throughput claims require controlled variation and repeats. |
| Hardware validation and electrical energy | Not implemented | Results are small-carton MuJoCo simulations; energy is mechanical work, and camera labels are simulator annotations. |
| Account authentication and durable multitenancy | Partially implemented | Factory endpoints use opaque owner capability tokens. There is no user-account system or organization isolation. |
| Always-on durable production hosting | Blocked by external credentials or infrastructure | The existing Render Free service can sleep and has ephemeral SQLite. It cannot guarantee uptime or cross-deployment persistence. |

The official [Desmos v1.12 API](https://www.desmos.com/api/v1.12/docs/index.html?lang=en)
documents the calculator state methods. Its [API terms](https://www.desmos.com/api-terms)
require the appropriate commercial agreement for a public commercial embed.
No trial key is substituted for production.

The frontend build still emits a large lazy world-preview chunk (about 901 KiB
gzip). The focused checks and current release status are recorded at the top
of `IMPLEMENTATION_STATUS.md`. No p95 throughput, GPU utilization, 5,000-job
capacity or hardware cycle-time claim is supported by this release.
