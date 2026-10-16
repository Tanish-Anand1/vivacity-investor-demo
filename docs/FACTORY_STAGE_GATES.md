# Autonomous factory: staged delivery

## Working brief

Outcome: operate, inspect and reproduce a physically simulated carton-sorting cell.
The flagship is one coordinated Panda cell with a real conveyor, real contact grasp,
two destinations and traceable measurements. Existing workcell experiments and owned
World Labs assets remain accessible. Nothing starts on page load.

Visual direction: a quiet industrial workstation, warm graphite and aluminum,
one amber operational accent, a large factory view and contextual instruments.
Anti-references: a neon control-room dashboard; a grid of decorative product cards.

## Current inventory and audit (source inspection, 2026-10-13)

| Existing capability | Evidence / decision |
|---|---|
| MuJoCo native robot dynamics, contact pickup, full integration snapshots | Preserve `robotics.py`, `pick_place.py`, native execution and tests. |
| Seven implemented robot adapters, specialized fixture operations | Preserve as advanced workcell choices. Do not present primary-arm dual Panda as bimanual control. |
| Owned configuration history, real branches, exports, live controls | Preserve runtime/supervisor/workspace contracts and capability authorization. |
| World Labs owned generation and SPZ/GLB assets | Preserve independent appearance and collision mappings. |
| Actual state/contact/energy inspection | Extend sampled records rather than invent chart values. |
| Overhead semantic ray scan | Working synthetic depth query, but not an RGB camera pipeline. Keep accurately labeled until the camera stage passes. |
| Factory conveyor, arrival control, coordinated sorting | Missing. Existing sorting is one-part transfer based on simulator properties. |
| Engineering time-series charts, benchmark interchange, PDF/ZIP | Missing as complete product journeys. |
| Authenticated team membership | Missing. Browser capabilities are not user accounts. |

### Redundant or misleading surfaces

- Experiments and Results navigation mount the exact same component.
- Standalone Robots and Operations repeat selections available in the experiment editor.
- Legacy templates repeat the typed configuration workflow.
- The default heading is generic, while the live task is specific.
- The localization paragraph permanently occupies the result panel; it belongs in inspection.
- Appearance quality settings change splat budgets, not the advertised engineering view.
  Preserve their function in world preview; define distinct factory render modes later.
- No evidence of fabricated numeric outputs found in the audited current paths. Missing
  factory/vision/report functions must stay unavailable until their own acceptance gates pass.

## Architecture

FastAPI owns jobs and capability authorization. SQLite stores immutable experiment
records and sampled traces. MuJoCo adapters own model/state/control; Three.js renders
measured transforms. React owns operation controls and selection, not dynamics.
The factory will extend this application with a bounded production controller and
versioned factory records. Visual machine detailing stays separate from collision
geometry. Sampled telemetry, charts, JSON and reports share the same saved data.

## Stage gates

| Stage | Acceptance | Status / evidence |
|---|---|---|
| P0 Focused interface | No duplicate destinations; useful existing selections remain reachable; keyboard/mobile and build pass | Passed: 26 frontend checks; TypeScript/Vite build; local browser navigation + keyboard selection; 390 px reflow without horizontal overflow. `artifacts/factory-p0-desktop.jpg` |
| P1 Factory composition | Detailed existing robot, authored industrial machine assets, distinct render modes; no fake motion; browser review | Passed visual preview: TypeScript/build; browser High fidelity/Performance and keyboard Plan/Overview; no JS errors. Engineering mode awaits P5. `artifacts/factory-p1-fidelity.jpg` |
| P2 Conveyor physics | Motor-driven contacts transport a free carton to station; pause/reset and state reproduction | Passed: 7 physics/API tests, TypeScript; browser Start/Pause (time frozen at 0.350 s)/Resume/arrival (8.650 s)/Reset to idle. Snapshot, owner isolation, emergency stop and restart persistence tested. `artifacts/factory-p2-tests.xml`, `artifacts/factory-p2-browser.jpg` |
| P3 Production workflow | Observe → plan → physical grip → transfer → route → destination events; counters match recorded events | Passed: 10 physics/API tests (including 3 physical deliveries across both lanes, weak-grip failure and cancellation); 26 frontend checks; TypeScript/build; compiled browser Start/Pause/Resume → 3/3 deliveries at 109.902 s. `artifacts/factory-p3-tests.xml`, `artifacts/factory-p3-browser.jpg` |
| P4 Observations | Actual rendered camera, semantic detection/occlusion, world estimate compared to ground truth; no invented confidence | Passed locally: 5 API/camera tests, TypeScript/build; compiled browser moved carton to Y=-0.400 m → image estimate -0.399 m, then Y=-0.940 m → outside view. Actual occlusion tested with physical occluder. `artifacts/factory-p4-tests.xml`, `artifacts/factory-p4-browser.jpg` |
| P5 Physical records | Timestamped state, contacts, actuator outputs, derived work/power with equations and missing-data semantics | Passed: 11 physics/measurement/production tests, TypeScript/build, compiled browser force vectors and ground-truth units; pause holds state time 0.400 s and force time 0.398 s. `docs/FACTORY_MEASUREMENTS.md`, `artifacts/factory-p5-tests.xml` |
| P6 Analysis | Recorded graphs, units, cursor/range/zoom/export and synchronized replay; values match data | Passed: 4 analysis tests; 3 sample/API checks and 1 real production event-sample integration check; TypeScript/build; compiled browser event/keyboard cursor, zoom, 390 px reflow and CSV download. All 812 exported time/power/force rows exactly matched SQLite. `artifacts/factory-p6-*` |
| P7 Benchmarks | Defined task, repeated seeded trials, controlled/held-out comparisons, failures preserved | Passed: 7 real benchmark/API tests (88.43 s), TypeScript/build; browser six-trial comparison with 3 baseline successes and 3 weak-grip failures, failed-trial replay, live trial pose, pause at 17.100 s and stop. `artifacts/factory-p7-*` |
| P8 Interchange | Strict versioned JSON round-trip, incompatible input rejection, reproducible configuration | Passed: 2 integration tests including exact native state and 300-step equality after import, owner/size/version/units/checksum rejection; TypeScript/build; browser download and file import leaves cell idle at 0.000 s. `schemas/factory-exchange.schema.json`, `artifacts/factory-p8-*` |
| P9 Reports | Saved-data PDF/ZIP, legible charts/tables, matching metrics and inspected pages | Passed: real production PDF/ZIP integration (20.18 s), exact CSV/JSON comparison, TypeScript/build; all 7 benchmark PDF pages visually inspected; browser PDF/ZIP downloads; all 6 archived trial records exactly match SQLite. `artifacts/factory-p9-*` |
| P10 Projects | Useful versioned organization and creator attribution; no false authenticated identity claims | Passed for project notebooks: integration test covers immutable versions, conflict detection, ownership, restart and attributed PDF (4.93 s); TypeScript/build; browser create/save/load/attach benchmark/download attributed report, physics remains idle. `artifacts/factory-p10-*` |
| P11 Release | Full regression, browser journey, live deployment check and capability report | Passed for the declared factory scope: 289 Linux tests; two separate 4/4 hard 512 MiB runs; 31 frontend checks; local/Vercel builds; public HTTP success/failure, six-trial benchmark, native WSS and geometry invalidation; final public browser idle/start/pause/resume/delivery/replay/camera/import/PDF/mobile checks. [Release evidence and limits](FACTORY_RELEASE.md). |

Each row advances only after its tests and actual browser boundary pass. A failure
keeps that row open. Test fixtures may simplify conditions, but the UI must state
the tested physical scope. A successful trial alone does not validate a benchmark.

## Risks and constraints

Current public Render Free host sleeps and has 512 MiB memory. Persistent local
SQLite is not durable across deployment. Rendering cameras must fit that budget.
The Panda gripper supports small cartons within its opening and tested payload;
this is a tabletop sorting cell, not an uncalibrated claim about shipping cartons.
No hardware performance, electrical consumption or production uptime is inferred.

## Verification plan

Run narrow tests at each gate, then integration checks against real HTTP and the
actual local browser. Inspect desktop/narrow layouts, keyboard controls, faults,
idle/restart behavior, assets and console errors. Save reports/screenshots under
`artifacts/factory-*`. Run full regression and public acceptance before release.

P3 scope: finite 1–3 carton batches, one carton handled at a time. Classification currently reads simulator mass; no camera inference claim. Lateral shuttle uses a position actuator and contact friction. Failed grip/routing/timeouts remain failed. Dev HMR lost a stale lazy module; the production build passed the browser journey.

P4 scope: manual synchronized RGB/depth/semantic capture, camera is overhead 320×240. The centre estimate assumes an upright configured box; semantic IDs are simulator annotations, not a trained detector. Host GPU/software-render support remains a P11 release gate.

P6: old records select the nearest stored event sample; new production runs retain exact event-time samples (integration tested). Chart/viewport/ground-truth inspection share a cursor. CSV/JSON chart exports contain currently loaded backend samples; full experiment interchange follows in P8.

P7 scope: bounded paired serial trials (6–10 per job), immutable seeded definitions and separate held-out positions. One worker limits memory; this is not a hardware reliability estimate. Every failed/stopped trial remains inspectable.

P8 scope: configuration and benchmark definitions are importable. Complete run JSON exports include all saved samples, states, events and metrics but are inspection-only; imported measurements cannot become verified executions. Import provenance is retained verbatim. Compatibility uses engine/NumPy/controller/assets/layout hashes and exact reconstructed initial state. Cross-architecture bitwise equivalence beyond these checks is not guaranteed.

P9: PDFs draw vector charts and a recorded geometry plan, not browser screenshots. The benchmark report analyzes the first recorded trial plus all condition/held-out outcomes. Missing legacy version metadata stays unavailable. ZIP records are written one trial at a time and temporary archives are cleaned after download. PDF text is searchable; a fully tagged accessible PDF is not yet provided. ReportLab flowables/graphics follow https://docs.reportlab.com/reportlab/userguide/ch5_platypus/ and https://docs.reportlab.com/reportlab/userguide/ch11_graphics/.

P10 scope: browser-capability-owned project notebooks, immutable versions, result comparison and portable file sharing. Names are self-reported. Authenticated accounts, team invitations/roles and live multi-user editing remain unimplemented and are explicitly described in the interface.
