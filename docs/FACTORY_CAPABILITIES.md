# Factory capability report

This report distinguishes implemented behavior from the broader platform ambition.
Release status and exact evidence belong to [FACTORY_STAGE_GATES.md](FACTORY_STAGE_GATES.md).
The API and reproduction commands are in [FACTORY_RUNTIME_HANDOFF.md](FACTORY_RUNTIME_HANDOFF.md).

| Feature | Implemented and exercised | Limits / remaining work |
|---|---|---|
| Focused interface | Factory, workcell, worlds and experiment library; explicit Start; keyboard/view controls and narrow layout | Screen-reader acceptance with a human user and a broader mobile/GPU matrix remain open |
| Factory appearance | Detailed robot meshes, authored machinery, conveyors, shuttle, bins; three render modes and camera views | A tabletop small-carton cell, not a scan of an actual commissioned factory |
| Conveyor motion | Motorized MuJoCo rollers transfer momentum through contacts; real station arrival and stopping | Finite 1–3 carton batches; no unbounded replenishment or teleported cartons |
| Robot manipulation | Panda DLS pose IK, seeded collision-aware routes, actuator control, bilateral grasp, retained lift/transfer and release | One tested factory robot/gripper/controller; bounded carton size, mass and placement |
| Sorting | Contact shuttle routing and bin-floor contact verification; counters derived from events | Classification reads simulator mass; it is not visual material classification |
| Control | Start, checkpoint pause/resume, stop, emergency simulation stop, fresh idle reset | Emergency stop is software simulation control, not certified hardware safety |
| State and persistence | Full native integration state, seed/settings/model metadata, independent data instances, SQLite archives | Single-process worker; Free hosting storage is ephemeral; cross-platform bitwise identity not guaranteed |
| Camera observation | Actual MuJoCo RGB/depth/semantic image, visible/occluded/outside-view result, depth back-projection | Semantic IDs are oracle annotations, not a learned detector; upright-box estimate; confidence unavailable |
| Ground-truth inspection | Native transforms, velocities, masses, inertias, joint state and contacts | Simulator truth and contact-model estimates, not physical sensor readings |
| Physical telemetry | Native torque/contact forces; SI units; object energy; per-step mechanical work with equations | No motor efficiency/electrical consumption model; sampled contact peaks can be missed |
| Engineering analysis | Six graphs, quantity selection, time range/zoom, shared event/sample cursor and 3D replay; CSV/JSON | Display uses saved samples, not every integration step; electrical values remain null |
| Mathematical discovery | Eight measured MuJoCo series, background progressive and final equation fits, chronological holdout metrics, saved provenance, original/fit overlays, model and run comparison, typeset LaTeX/MathML with copy, CSV/Desmos-ready snapshots | Descriptive approximation only; flat holdouts omit unstable R²; official Desmos embed needs an authorized production key and has not been live-tested; 5,000–6,000 definition campaigns are not implemented |
| Benchmarks | Frozen paired conditions/seeds; repeated training and held-out trials; failures, ties and all-fail remain honest | 6–10 serial trials per factory job; small sample, no significance/hardware reliability claim; no 5,000-run factory claim |
| JSON interchange | Strict schema/checksum/software/native-state validation; idle configuration and benchmark import | Raw measured archives are inspection-only; incompatible controller versions must be recreated |
| Reports | Saved-data vector PDF, measured charts, comparison tables and complete ZIP/CSV/JSON | Benchmark PDF details its first recorded trial plus all outcomes; fully tagged accessible PDF remains open |
| Projects | Append-only configuration versions, owned result attachments, comparison and declared creator/team labels | File-based sharing; no authenticated accounts, invitations, roles or live multi-user editing |
| Legacy workcells | Existing seven robot adapters, constrained operations, native parallel trials and REST/WSS retained | Existing declared controller/fixture limits remain; primary-arm dual model is not bimanual control |
| World Labs | Existing owned generation and real spatial assets retained separately from collision/physics | No new live generation is needed for factory acceptance; previous provider evidence is in the spatial release report; no Atlas access claim |
| Hosting | Vercel frontend and Render Docker deployed; real public HTTP/WSS/browser acceptance; two passing 512 MiB runs | Free service sleeps; persistence is ephemeral; exports reach the memory limit; no paid uptime guarantee/disk was activated |

## Evidence mapping

- Native factory model, transport, state/forks, contacts and controller:
  `tests/test_factory.py`, `tests/test_factory_production.py` and
  `tests/test_factory_measurements.py`.
- Actual rendered observations/occlusion and API control/persistence:
  `tests/test_factory_vision.py`, `tests/test_factory_api.py`.
- Repeated measured comparisons, strict interchange, report contents and project
  revisions: `tests/test_factory_benchmark.py`, `tests/test_factory_exchange.py`,
  `tests/test_factory_reports.py`, `tests/test_factory_projects.py`.
- Hosting boundary: `tests/test_host_capacity.py` and
  `tests/test_factory_host_capacity.py`, executed inside Docker with a hard
  512 MiB limit, including actual camera/three-carton/replay/export/report operations.
- Graph quantity/cursor/export contracts: `scripts/test-factory-analysis.mjs`.
- Mathematical fits, owner-scoped persistence and provenance:
  `tests/test_factory_discovery.py`; browser-number formatting:
  `scripts/test-desmos-number.mjs`. API and integration details are in
  [FACTORY_DISCOVERY.md](FACTORY_DISCOVERY.md).
- End-to-end HTTP demonstration: `scripts/demo_factory.py`. Legacy real HTTP/WSS
  and geometry invalidation: `scripts/verify_workspace_live.py`.
- Browser acceptance and inspected report pages: stage-specific
  `artifacts/factory-p0-*` through `artifacts/factory-p11-*` and the stage gate table.

Priority follow-ups: licensed Desmos browser integration and live edit acceptance;
durable managed persistence and authenticated ownership; long-duration bounded
batch execution; hardware/calibration validation; a trained
perception pipeline evaluated separately from simulator annotations. None of these
is required to inspect the currently implemented native simulation evidence.

Final release identities, actual test totals, public timings and corrected gate
failures are in [FACTORY_RELEASE.md](FACTORY_RELEASE.md).
