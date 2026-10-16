# Panda-driven cloth fold: release verification

Date: 2026-10-11. Target: https://demo.tryvivacity.com/. Vercel project `vivacity-demo`, production deployment `dpl_GLZnwgSoBcsGXAS1tNcLViN4waVG`.

## Implemented change

New cloth worlds contain the Menagerie Franka Panda with seven real joint position actuators, gravity compensation, a fixed folding bar and a MuJoCo 7 × 7 flex sheet. The robot carries the pre-attached cloth edge over its fixed hinge, releases its equality constraints and retracts while the sheet settles. The scene contains **no mocap bodies**. During stepping, the controller changes actuator targets and release flags; it never assigns robot positions or cloth vertices.

Each branch records its 71 IK joint waypoints/times, actual robot positions/velocities/controls, body positions/quaternions, cloth vertices, release flags, complete integration states, contact violations, tracking error and fold evaluation. Selection remains based on measured success/alignment/coverage/duration. Disabling actuation is an automated failure control. `legacy_cloth.py` preserves old snapshots, hashes and replay; existing history is not deleted. The UI creates a new arm world when a remembered cloth world has the old fixture configuration.

Scene coordinates: meters, Z-up; initial cloth center `[0.5,0,0.012]`; bar hand-local position `[0,0,0.18]`. The 14 cm fixture stem connects the folding bar to the hand. Both fixture geoms have disabled collision masks, with physical mass and rigid attachment; seven ideal equality constraints transfer motion to the flex. Robot link collisions and excessive penetration remain failure conditions. Rendering uses actual Menagerie meshes and recorded body poses, including WXYZ quaternion conversion, alongside the measured vertices.

## Evidence

- Focused cloth tests: **5 passed**, zero failures/errors/skips, **220.83 seconds** (`artifacts/robot-cloth-targeted.xml`). Includes real deformation, full-state independence/restore, deterministic repeated integration, missing-clamp/timeout failures, numerical search, revision invalidation, disabled-actuator failure and legacy compatibility.
- First complete run: **85 passed, 1 failed**, **414.40 seconds**. The failed robotics API test stopped at its 30-second deadline; its persisted job actually completed successfully in **31.8925 seconds**. The test now allows 120 seconds, preserving its outcome assertions. The complete corrected rerun passed **86 tests, zero failures/errors/skips, 416.81 seconds** (`artifacts/robot-cloth-backend.xml`).
- Executed six-branch test experiment: 5,000 distinct samples; 2,984 geometric rejections; six integrated/feasible branches; **16,585 simulation steps**, **149.13 s job wall**, **141.45 s physics wall**, **132.30 s process CPU**, **4,372,559 replay bytes**. Measured alignment errors **0.4206–1.0690 mm**, vertex coverage 100%. These are measurements, not latency guarantees.
- The live OpenAPI matches `openapi.json` exactly (16 REST paths plus the WebSocket extension). Generated OpenAPI/types, local strict TypeScript/build, dependency check, Python compilation and verification-script syntax passed. Vercel strict build passed; remote bundling **3.43 s**, total remote build **20 s**. The large lazy Three.js vendor chunk remains a recorded warning.
- Custom-origin CORS preflight returned HTTP 200 with exact `https://demo.tryvivacity.com` allow-origin. A real public POST created a Panda cloth world, and GET state returned 49 measured vertices and 12 body transforms.
- The deployed initial scene passed desktop/375 px rendering, reduced-motion context, no horizontal overflow and zero captured page/console errors. Both screenshots were visually inspected: `artifacts/robot-cloth-initial-desktop.png`, `robot-cloth-initial-mobile.png`; machine evidence `robot-cloth-initial-verification.json`.
- Public experiment `920fb43a-edf5-4dad-b01f-f59bf1e416f2` completed through `demo.tryvivacity.com`: 5,000 generated/distinct/screened candidates, 2,984 screen rejections, eight integrated folds, eight measured successes, 22,152 steps and a selected 0.9234 mm alignment error. Its true local-host job wall time was **460.49 seconds** under contention, so the original 360-second verifier timed out while the job kept running. The verifier now allows ten minutes and a targeted replay rerun passed exact final cloth vertices plus Panda body positions and WXYZ orientations, released constraints, three result cards and JSON export (`artifacts/v2-cloth-journey.json`). This is a measured performance limitation, not a claim of seamless low-latency operation.

## Reproduce

From `P:\VIVACITY\DEMO-`:

```powershell
$env:OMP_NUM_THREADS='1'; $env:OPENBLAS_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'
.venv/Scripts/python.exe -m scripts.test_backend -q --junitxml=artifacts/robot-cloth-backend.xml
.venv/Scripts/python.exe -m scripts.export_openapi
npm --prefix frontend run generate:api
npm --prefix frontend run build
powershell -NoProfile -File scripts/restart-public-api.ps1
vercel link --cwd frontend --project vivacity-demo --scope tanishs-projects-66633ee2 --yes
vercel deploy --cwd frontend --prod --yes --scope tanishs-projects-66633ee2 --build-env VITE_API_BASE_URL=https://rid-buffalo-bluetooth-profit.trycloudflare.com
node scripts/check-robot-cloth-initial.mjs
$env:UI_URL='https://demo.tryvivacity.com/'
$env:ARTIFACT_PREFIX='robot-cloth-public'
node scripts/check-v2-public.mjs
```

Use the current URL from ignored `data/public/endpoint.json` if the tunnel has been restarted. Start absent services with `scripts/start-public-demo.ps1`; restart checks process identity and preserves the current tunnel.

## Limits and remaining work

This is one constrained sheet fold, **not autonomous cloth grasp acquisition or general garment folding**. The hinge/opposite edge are pinned; grip attachment is an ideal pre-attached fixture, not frictional grasp validation. Vertex coverage is not area-overlap coverage. There is no calibrated textile material, dual-arm controller or learned folding policy. Reset after committing a released final state before attempting another fold.

Vercel serves the frontend; the real MuJoCo/SciPy API still uses a temporary Cloudflare tunnel to this computer. Keep the machine, API, tunnel and network running. Independent durable backend hosting, multi-user authentication, restart continuation and operational hardening remain incomplete. No hosted LLM was used. Other limitations remain in `DEMO_V2_LIMITATIONS.md`.
