# Apollo tray clearance and grip investigation — 2026-10-25

**These are failed development trials. They do not qualify full cabinet service.**
The verified application change is `b49552c64aced96b972ee8eba4d410e29fc8a8a1`.
The research overrides below remain separate from the application controller.

## Shipped change

`CabinetConfig` now defines independent `old_tray_surface_height_m` and
`replacement_tray_surface_height_m` values, each bounded to 0.75–1.05 metres.
Their default is 0.99 m, preserving the historical fixture. Each value changes
the corresponding native support, pedestal and retaining walls. The replacement
cartridge starts on its own tray, and the old-cartridge placement evaluator uses
the old tray's height. The cabinet seat stays at its existing height.

The first investigation lowered both trays with an intermediate shared-height
prototype. That trial timed out during the initial door motion. The committed
implementation makes them independent: lowering only the old tray avoids the
previous palm/tray-wall path conflict without changing the replacement station.
This is a declared fixture change before compilation, not removal of collision
geometry or movement of a support during a trial. Its runtime source is archived
separately from the earlier prototype.

## Actual results

There are **2 fresh trials and 18 independent continuations**, all failed, with
**82,540 newly executed native steps** in total. Two continuations stopped after
two steps because a research command used a measured swivel position just beyond
its allowed target range; these are controller errors, not motion acceptance.
The subsequent bounded-reference variants retain those failed records.

All trials request a 1.1-radian opening. The model has zero equality constraints
and zero mocap bodies. Execution uses bounded actuators. Research changes neither
native poses during stepping nor contact, collision, tilt, torque or success
thresholds. There is no successful fallback trajectory.

| Trial | Type | New steps | Final door angle (rad) | Outcome |
| --- | --- | ---: | ---: | --- |
| Both trays lowered | Fresh | 14,180 | 0.306892 | Opening timeout |
| Both trays, measured opening feedback | Continuation | 4,502 | 0.118893 | Opening timeout |
| Old tray lowered; rotating wrist | Fresh | 22,064 | 0.934328 | Lost grip |
| Bounded lead, yaw 0.35 / lead 0.08 | Continuation | 2,694 | 0.763629 | Lost grip |
| Bounded lead, yaw 0.50 / lead 0.08 | Continuation | 2,296 | 0.758542 | Lost grip |
| Bounded lead, yaw 0.65 / lead 0.10 | Continuation | 3,813 | 0.736441 | Prohibited collision |
| Consistent local grasp, yaw 0.50 / lead 0.10 | Continuation | 2,897 | 0.943279 | Lost grip |
| Consistent local grasp, yaw 0.50 / lead 1.00 | Continuation | 4,156 | 0.945980 | Lost grip |
| Consistent local grasp, yaw 0.65 / lead 1.00 | Continuation | 6,001 | 0.892620 | Opening timeout |
| Continuous IK, yaw 0.50 | Continuation | 2 | 0.288802 | Invalid joint target |
| Continuous IK, yaw 0.65 | Continuation | 2 | 0.288802 | Invalid joint target |
| Bounded continuous IK, yaw 0.50 | Continuation | 1,301 | 0.635886 | Lost grip |
| Bounded continuous IK, yaw 0.65 | Continuation | 2,446 | 0.930820 | Lost grip |
| Torso-inclusive IK, yaw 1.00 | Continuation | 977 | 0.478133 | Lost grip |
| Torso-inclusive IK, yaw 0.85 | Continuation | 2,442 | 0.937197 | Lost grip |
| Preload-preserving path, yaw 1.00 | Continuation | 609 | 0.387497 | Lost grip |
| Preload-preserving path, yaw 0.65 | Continuation | 718 | 0.398521 | Lost grip |
| Saturated-servo command preservation | Continuation | 4,142 | 0.951726 | Lost grip |
| Contact-normal-force tracking | Continuation | 3,012 | 0.978423 | Prohibited collision |
| Higher finger-force objective weight | Continuation | 4,286 | 0.938819 | Lost grip |

The fresh old-tray trial took 220.851 s in its execution/planning loop, excluding
model initialization and archival work. It completed 44.128 simulated seconds,
then measured 41.335 N on one loaded-hand pad and 0 N on the other. Root tilt was
0.012599 rad. It passed release, withdrawal and right-arm parking first.

The furthest terminal angle was 0.978423 rad in a continuation, **not a pass**.
The negative finger hit the broad latch crossbar at 16.084 N, exceeding the
unchanged 2 N prohibited-contact threshold. The normal-force objective did not
solve grip retention. The saturated-servo variant also failed: its recorded TCP
error grew to 58.9 mm while the weaker finger closed without maintaining contact.
These observations point to coupled grasp/tracking failure; they do not establish
a complete diagnosis or a validated replacement controller.

Wall times in the continuation reports exclude checkpoint loading and initial
IK. They are local measurements under memory contention, not hosting latency or
complete compute-cost measurements. No nominal or held-out cabinet success rate
is claimed from these selected development runs.

## Verification of the application change

Overlapping suites must not be added as independent test counts.

- [Linux deployment image](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40163889334): **536 passed, 3 skipped**, zero failures/errors. Shards contain 184, 159 and 196 tests. Separate 512 MB probes: 4 general/factory and 1 humanoid check passed.
- [Apollo component tests](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40163889325): **67 passed**, zero failures/skips, 229.721 s.
- [Contact integration and browsers](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40163889319): **110 passed**, zero failures/skips, 114.602 s. Chromium, Firefox and WebKit jobs passed.
- [ARM64 preflight](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40163889262): passed; this is architecture verification, not a provisioned durable host.
- Local native cabinet mechanism tests: **21 passed in 10.397 s**, including independent height causality, actual support force, unchanged other-tray geometry and invalid-value rejection.
- OpenAPI and generated frontend types were regenerated together; `git diff --check` passed.

The WebKit journey executes 9,510 native steps, measures 5.882 mm G1 placement
error, and rejects a changed-condition trial as `grip_slipped`. Its 18 checks
include live frames before completion, pause, independent fork, comparison,
explicit replay, export, reload, network recovery, cancellation and mobile
reflow. The actual mobile screenshot was inspected. This verifies the existing
bounded G1 contact page, not an Apollo cabinet or warehouse journey.

## Preview and release boundary

The free preview API at <https://vivacity-physical-truth-preview.onrender.com>
serves the new schema. Current real GETs returned HTTP 200 from `/health`
(1.045 s) and `/openapi.json` (0.467 s); the latter includes both new bounded
tray fields. These are reachability/contract checks, not a live cabinet run on
that 512 MB host. A real `/v1/robotics/contact/capabilities` GET returned
`enabled: false`; experimental contact task execution is disabled there.

The production website/backend were not replaced. The free preview has no
qualified durable storage or 24-hour soak and is not the full release. No paid
resources or Fireworks calls were activated in this work.

## Evidence and reproduction

`index.json` records report, source, parent-checkpoint and native-model hashes,
frame counts and outcomes. Gzipped reports retain every recorded measured frame;
the two checkpoint archives retain full integration/controller/task/RNG state at
phase boundaries. A frame alone is not a complete resumable checkpoint.

Research source files are byte-preserved via the local `.gitattributes`. Runtime
sources are in the corresponding `*-runtime-sources.json.gz`. The earlier
shared-height prototype predates the verified application commit; use its exact
archived source if reproducing it. Do not silently restore it as the current
model. The 257 MB compiled models remain local and are identified by hash; they
are not committed. Native MJB continuation requires matching MuJoCo and model
hashes. Reports are inspected without those binaries.

From the isolated worktree, using the existing Python 3.12.10 / MuJoCo 3.15.0:

```powershell
$env:PYTHONPATH='.'
$env:OPENBLAS_NUM_THREADS='1'
$python='P:/VIVACITY/DEMO-/.venv/Scripts/python.exe'
& $python -m pytest tests/test_cabinet_mechanism.py -q
& $python artifacts/physical-truth-runtime/apollo-tray-research-20261025/old-tray-swing-source.py --height .89 --yaw-fraction .5 --output data/reproduce-old-tray/report.json
```

The fresh research command returns exit code 1 for the measured failed task.
Continuation scripts refer to the local original `data/physical-truth-oct25/`
paths. Extract their named checkpoint archive to that location and use the
matching compiled model before running them. Their process exit code is not the
acceptance result: inspect `state.status`, `state.success` and `state.failure`.

`failed-door-terminal.png` is a static native render reconstructed from the
last measured qpos/qvel frame of the normal-force variant. It is not a restored
controller state or camera-perception result. The recorded report remains the
source of force measurements. `render_failed_frame.py` records this distinction.

Remaining gates: complete cabinet exchange/retention/closure; complete-model
locomotion, terrain, carrying and H1 running; eight-stage shared warehouse;
RGB-D-driven task control; app-wide parameter/acceptance coverage; durable
no-cost hosting, recovery and 24-hour soak. The opening release remains deferred.
