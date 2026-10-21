# V-Robotics validation matrix

The source of truth for the first eight columns is [v-robotics-verification.json](v-robotics-verification.json), generated from fresh MuJoCo runs with `python -m scripts.verify_v_robotics`. The browser column comes from the separate [Playwright JSON report](v-robotics-browser-verification.json). `PASS` means the cited check ran successfully; `NOT TESTED` means there is no acceptance evidence. A loaded asset does not imply a completed robot program.

| Program | Model | Kinematics | Dynamics | Controller | Baseline | Failure | Variation | Replay | UI E2E |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Precision assembly / UR5e | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Heavy payload | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |
| High-speed sorting | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |
| Collaborative manipulation | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |
| Humanoid maintenance | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |
| Humanoid terrain | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |
| Humanoid logistics | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED | NOT TESTED |

At the latest successful machine run, precision assembly had a verified selected result with **0.001214604 m** measured placement error and **41,118** total physics steps across three validation branches. All three deliberately weak-grip/high-mass/low-friction branches were `dropped_object`; the 0.30 kg mass-variation run generated three new physical results, one successful and two `grasp_failure`. The machine script took **8.95 s** wall time on this local machine. These are individual simulator runs, not general success rates. MuJoCo version was **3.15.0**, timestep **0.002 s**. The report contains the exact initial state, solver settings and seed for each run.

Commands already executed:

```text
.\.venv\Scripts\python -m pytest tests/test_v_robotics.py -q
  6 passed, 1 warning, 16.01s
.\.venv\Scripts\python -m pytest tests/test_robotics.py tests/test_pick_place.py tests/test_workspace.py tests/test_templates.py tests/test_physical_platform.py tests/test_api.py tests/test_v_robotics.py -q
  122 passed, 1 warning, 255.45s
.\.venv\Scripts\python -m scripts.verify_v_robotics
  precision first eight gates PASS; other six programs NOT TESTED
npm run generate:api
  passed
npm run build
  passed
$env:PLAYWRIGHT_JSON_OUTPUT_FILE='P:\VIVACITY\DEMO-\docs\v-robotics-browser-verification.json'; npx playwright test --config playwright.config.ts e2e/v-robotics.spec.ts --reporter=json
  1 passed; 0 unexpected failures; 192.82s, including replay, export, session protection, mobile axe, stale result and tighter-tolerance rerun
```

The single warning in both pytest runs was the existing Starlette/httpx deprecation warning. This matrix covers the local environment. Cross-solver-version, hardware and public-host reproducibility were not tested by these commands.

## Public-host verification, 2026-10-21

The backend source commit `33adfe4` served the new catalogue with seven programs and ran experiment `4ba6722a-4704-416f-9f43-4b743109c99e` on `https://isabella-labs-runtime.onrender.com`. Two independent physics branches both returned `execution_success`, with **11,320** and **12,481** integrated steps. The selected measured placement error was **0.001214604 m**. The report returned `verified`, a solver model hash, and **95** replay frames. These values were written by `python -m scripts.verify_v_robotics_public` to the local artifact `artifacts/v-robotics-public-live.json`; they are one live experiment, not a reliability estimate. A separate public WSS connection received six persisted events through `completed`.

The frontend release `dpl_GGrz5UW1t4zVkq8hsQiisDqhnrEC` reached Vercel `READY` and was aliased to `https://demo.tryvivacity.com`. The live `/workspace` route showed the seven-program catalogue, loaded the UR5e workcell, streamed three measured validation results and an independent execution, and displayed the persisted assembly report. During the first release, an asset fetch failed and left the canvas blank while the physics job succeeded. The viewer now retries transient geometry requests and offers **Retry 3D view**; a dedicated Playwright failure-injection test passed. After redeployment, the live UR5e geometry rendered on a clean load. The first program-open request also timed out during deployment; a retry succeeded. Cold-start/deployment interruptions therefore remain an operational limitation.
