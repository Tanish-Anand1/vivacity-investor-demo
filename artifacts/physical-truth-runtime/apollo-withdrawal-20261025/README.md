# Apollo native development evidence — 2026-10-25

These are failed development trials, not a complete cabinet service or a
Physical Truth release. The exact application runtime at `a14c619` passes its
component regressions but loses the left-hand grasp during the requested wider
door swing. Production is unchanged.

## What changed and what was measured

`3fd1ae7` adds collision-checked tool clearance and seeded joint-space parking.
`a14c619` starts the wider swing from the measured latch and TCP pose. It removes
the target jump caused by assuming the latch remained pulled by 50 mm while
the other hand was parked. Planning uses independent scratch data; execution
uses bounded native actuators. The model has no equality constraints or mocap
bodies. All trials below requested a 1.1-radian door opening with seed 7,
cabinet front x = 0.65 m, and finger stiffness = 2,400 N/m.

| Full development trial | Steps | Simulation seconds | Wall seconds | Final door radians | Measured failure |
| --- | ---: | ---: | ---: | ---: | --- |
| integrated-release | 12,730 | 25.460 | 231.420 | 0.319173 | collision_free_route_not_found |
| swept-parking | 12,730 | 25.460 | 177.273 | 0.319173 | collision_free_route_not_found |
| rrt-parking | 15,357 | 30.714 | 144.632 | 0.491515 | lost_door_grip |
| measured-hold | 17,529 | 35.058 | 176.087 | 0.307699 | tool_retraction_timeout |
| settled-parking | 18,709 | 37.418 | 184.321 | 0.506544 | lost_door_grip |
| measured-grasp | 19,068 | 38.136 | 335.496 | 0.560305 | lost_door_grip |

The final two trials complete release, withdrawal and right-hand parking.
The last trial enters `open_wide` at simulation time 35.526 s. It ends with
31.199 N on one left pad and 0 N on the other, root tilt 0.007875 rad, and root
speed 0.002403 m/s. Local wall times include planning and runtime work; memory
contention affected the last measurement. They are not production latency or
CPU-only measurements. No nominal or held-out cabinet acceptance rate is claimed.

Five separately identified research continuations restore the same version-8
checkpoint and change actuator-goal feedback on that independent instance.
Their source and parent checkpoint hashes are preserved. Jaw centering alone
loses grip at 0.631479 rad; a slower bounded command retains both contacts but
times out at 0.515302 rad; additional angle lookahead loses grip at 0.689440 rad.
A separate trial declares a longer 45-second phase budget before it starts;
it still times out at 0.413105 rad with both pad loads retained (41.192 N and
25.111 N). It executes 22,502 further steps from the common checkpoint and
takes 218.840 s wall time. This tests the hypothesis that the original timeout
alone explains failure; it does not establish task completion.

The final continuation rotates the wrist by half the commanded door rotation
and follows a rigid door-relative TCP arc, with the original 12-second budget.
It fails `prohibited_collision` at 0.594816 rad, after 1,541 additional steps:
the left palm hits `service_old_tray_wall_-1` at 17.981 N. Both finger loads are
still present. This is a physical path conflict, not a successful grasp-to-goal
trial. Its compute time is 17.363 s.

None of these research continuations changes simulator poses during stepping.
The longer budget is explicitly recorded; contact, collision, torque, posture
and success criteria are unchanged. No variant is application acceptance.

`rotation-ik.json` records nine scratch IK solves, of which eight pass the pose
tolerances. The full-rotation 1.1-radian goal does not pass that solver attempt.
The half-rotation goal does, but its native execution subsequently collides as
described above. Kinematic feasibility is not collision or physics acceptance.

`measured-grasp.png` is a native MuJoCo render of the failed terminal state,
not camera-perception evidence or a live-browser capture.

## Verification

Exact runtime source: `a14c61945c05939fe7e46bea893827060001c254`.
Overlapping suites must not be added together as independent test counts.

- [Deployment image](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40127257731): 524 passed, 3 skipped, zero failures/errors. Separate constrained-host probes: 4 general/factory + 1 humanoid passed.
- [Apollo component tests](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40127257656): 55 passed, zero skips/failures, 232.506 s.
- [Contact integration and browsers](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40127257696): 98 native tests passed, 216.819 s; Chromium, Firefox and WebKit jobs passed.
- [ARM64 image preflight](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40127257772): passed; no host was provisioned and no 24-hour soak occurred.
- Local withdrawal/routing/IK: 21 passed in 2.16 s. The measured-grasp native regression passed separately.
- `replay-check.json`: 6,338 additional native steps from the parked-hand
  checkpoint reproduce the final qpos, qvel, controls, time and outcome exactly.
  `reproduced: true` and `task_success: false` deliberately mean different things.

Executed JUnit files are retained in `tests/` in this evidence directory.
Runtime source and report hashes are recorded in `index.json` and the reports.
The repeated backend and contact/browser workflows also passed at `9b8b4a2`,
which adds the exercised checkpoint CLI and evidence without changing the
runtime, frontend or regression-test source. See the execution ledger for links.
The downloaded WebKit journey records 18 checks, 9,510 native steps, 5.882 mm
placement error and a correctly rejected `grip_slipped` trial. Its mobile
screenshot was inspected: the native scene, cancelled final state, parameter
controls and history are visible. This verifies the bounded G1 contact page,
not an Apollo cabinet or warehouse browser journey.

## Reproduction

Use the isolated branch and its installed dependencies. On this PC, Python is
`P:/VIVACITY/DEMO-/.venv/Scripts/python.exe`; the worktree is
`C:/Users/Tanish Anand/.codex/worktrees/physical-truth-runtime/DEMO-`.
The measured environment used Python 3.12.10 and MuJoCo 3.15.0.

Run from the worktree root in PowerShell:

```powershell
$env:PYTHONPATH='.'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$python='P:/VIVACITY/DEMO-/.venv/Scripts/python.exe'
& $python scripts/verify_apollo_door.py --front-x .65 --finger-stiffness 2400 --opening-angle 1.1 --checkpoints --output data/apollo-reproduction/report.json
```

Exit code 1 is the expected honest outcome of the current physical trial. The
verifier saves the report, native compiled model, exact controller-source
archive and full checkpoints even for that failure. These are not just qpos:
they include integration state, mutable model state, controller memory, task
phase, RNG state, model identity, world version and frame cursor.

Use the generated report to select the compiled binary and a checkpoint:

```powershell
$report=Get-Content data/apollo-reproduction/report.json -Raw | ConvertFrom-Json
$model=Join-Path 'data/apollo-reproduction' $report.model_file
$park=$report.checkpoints | Where-Object phase -eq 'park_right' | Select-Object -First 1
$checkpoint=Join-Path 'data/apollo-reproduction' $park.file
& $python scripts/replay_apollo_checkpoint.py --checkpoint $checkpoint --model $model --expected-report data/apollo-reproduction/report.json --output data/apollo-reproduction/replay-check.json
```

This verifier returns zero only when the terminal native state and outcome are
reproduced. It refuses mismatched model, controller or source provenance and
does not migrate older checkpoints. It does not emit display frames during
continuation, so it compares physics and task outcome rather than creating a
new replay cursor history. Cross-platform bitwise identity is not claimed.

## Artifact format and limits

`index.json` identifies each report, hashes, outcome and phase transitions.
Each `*-sources.json.gz` is a JSON map of source filename to exact source text.
Each `*-checkpoints.json.gz` is a JSON map of relative checkpoint filename to
its serialized full checkpoint. The last two complete runs have checkpoint
bundles. Each `*.json.gz` trial report contains actual frames, controls,
measurements, final controller state and failure classification. Standard
Python `gzip.decompress` and `json.loads` read these files.
The research override source files are archival provenance records; their
original relative source/checkpoint/model directory layout must be restored
in an isolated checkout to execute them. The commands above reproduce the
current application controller, not all historical research variants.

The compiled model hash is
`192c7e6acc3f52aac147a2498f77dca8609df526e4202343e5a10d1ce6691463`.
Its roughly 257 MB MJB is retained in the local trial directory and omitted
from Git. Regeneration requires the pinned model assets and matching native
runtime. A source change requires a fresh trial; an older checkpoint must not
be relabeled to bypass the compatibility check.

Full cartridge exchange and closure, model-matched mobility/running, the shared
warehouse, perception-driven control, complete acceptance coverage and durable
hosting remain open. No release or opening-animation work is justified by
these component results alone.
