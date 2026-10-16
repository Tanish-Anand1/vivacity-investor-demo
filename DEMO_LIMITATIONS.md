# Demo limitations

The runtime and frontend are a local investor demonstration. Read `IMPLEMENTATION_STATUS.md` for actual verification evidence, not a production-readiness claim.

## Robotics

- Collision-free **reaching** is implemented. Grasp contact validation, gripping, lifting, placement, hardware control and sim-to-real safety are not implemented.
- The cube and obstacle are fixed bodies. Repositioning the obstacle rebuilds configuration; the arm does not push a movable rigid-body obstacle.
- Pose IK and finite-budget joint-space RRT can fail to find a path that exists. Physics can reject a geometrically feasible path. Neither method is a guarantee of safe industrial motion.
- The frontend uses actual compiled mesh vertices/geom bindings and measured world body poses. It linearly interpolates positions and slerps rotations between replay samples. Interpolation is presentation, not a new physics integration or a collision proof between samples.
- Backend contacts are checked every 2 ms; replay samples are approximately 50 ms apart plus initial/final/failure frames. Red markers identify contact-involved **body origins**. Exact contact-point coordinates/normals are not returned by the current API.
- Camera, light, material roughness and floor grid are rendering choices. They do not change physical geometry, state or evaluation. The asset export supports this pinned Panda workcell; other robot models need another export/renderer contract.
- Replay includes joint velocities and all recorded body poses, but the UI does not provide a force/torque plot, collision-geometry overlay, on-screen mesh picking or a hardware controller.

## Science

- Synthetic noisy 2D test-particle observations, a fixed central body, a stationary external influence, known initial conditions and known candidate perturber location. Nondimensional units; no real telescope data, body recoil or moving-planet inference.
- Two predefined hypotheses and bounded SciPy least-squares fits. No discovery of new physical laws, hypothesis synthesis, full Bayesian posterior, calibrated discovery probability or automatic real observation acquisition.
- Uncertainty is a local linearized covariance approximation. Active bounds, limited data, one optimization initialization and model misspecification limit its interpretation. A computed fit is distinct from a supported hypothesis.
- Generation-only mass/central values are discarded before persistence/selection. Investors can choose an explicit synthetic generation scenario, but the policy fits public observations only. The optional influence marker displays **fitted** mass at a declared location.
- Follow-up refinement is a visible deterministic proposal for a new perturbed synthetic dataset. It is user-triggered, not autonomous scientific discovery.

## Agent and API operation

- The UI uses the deterministic policy and needs no paid key. Optional hosted proposals require backend `OPENAI_API_KEY` and `OPENAI_MODEL` and `policy: llm` through the API. The hosted transport is contract-tested; live provider use, billing and latency remain unverified. The UI does not configure secrets or claim LLM reasoning.
- No experiment cancellation. API statuses are queued/running/completed/failed. A completed job may have no successful candidate. The UI cannot show a genuine “cancelled” state because the backend does not support one.
- One loopback process, SQLite and one bounded worker. No multi-tenant authentication, public deployment isolation, distributed job leases, billing, storage retention, automatic interrupted-job resume, multi-process Uvicorn operation or full load benchmark.
- Reset retains history. Storage/events grow over repeated demos. The frontend stores IDs/sequences/preferences locally and refetches evidence; it has no fabricated offline fallback.
- Submission retry uses a persistent per-world idempotency key. Environment edits and commit/reset are not idempotent mutation endpoints; a lost response should be recovered by reloading the world, rather than blindly repeating the edit.
- Polling supplements WebSockets; reconnection is not evidence of cancellation or a new simulation. The app does not report a numeric completion percentage that the backend cannot measure.

## Browser and performance scope

- The live Vercel URL is backed by a temporary Cloudflare quick tunnel to the local Python process. It will stop when that tunnel or process stops; Railway deployment was blocked by the account's expired trial. This is not a durable production deployment.

- Tested environment: Windows, Python 3.12, local Chromium, the committed npm/Python locks and this workcell. Cross-browser Safari/Firefox, touch hardware, real screen-reader output, remote internet deployment, mobile GPU stability and cross-platform bitwise simulation equivalence are unverified.
- WebGL2 is required for the robot viewport. A render-error message preserves access to evidence if unavailable. Static robot meshes are about 6.4 MB; Three/R3F code is a separate lazy chunk. Loading and rendering depend on hardware/network/memory.
- Measured frame timing is a local sampled result, not a guaranteed frame rate. On-demand idle rendering reduces CPU pressure; replay follows elapsed time and may skip displayed intermediate samples on slow hardware. The saved trace remains available for scrubbing.
- Keyboard camera orbit/zoom/reset, laboratory controls, sliders and timeline are supported. Automated axe scans and keyboard checks do not establish complete accessibility or a full WCAG conformance audit. No screen-reader usability study was performed.
- First-run npm/browser installation hit a full C: drive. Task-local cache/temp paths on the project drive solved installation; unrelated files were not deleted. The service needs adequate available memory/disk for reliable presentation.

Before public release: add authentication/deployment isolation and retention controls, broaden scenario and browser/hardware coverage, validate accessibility with assistive technologies, and measure sustained concurrency in a controlled environment.
