# Robotics validation — 2026-10-11

Current checkpoint reran the fixed workcell **20 times: 20 successes, zero
failures, 127.9697845 s locally**. Evidence: `artifacts/master-final-pickup-20.json`.
This is fixed-scene repeatability, not randomized robustness.

The supplied Orbital original was physically probed but cannot grasp its cargo.
The explicit Panda adaptation passed three real native trials plus fresh
execution on Render: **30,757 steps, 1.717717 mm final goal error, zero prohibited
contacts**, verified bilateral grasp, lifting, retention, release and deck
support. Wall **169.474161 s**, process CPU **25.381585 s**; no recording substitutes
for that fresh execution. Browser compared live cargo transforms against the
rendered scene and parsed the downloaded evidence. Detailed limitations/source
changes: `docs/ORBITAL_HANDOFF.md`. Actual results: `artifacts/orbital-public.json`.
All **135 Linux deployment-image tests** passed; full evidence and preserved
Windows failures are in `docs/FINAL_VERIFICATION.md`.

Earlier benchmark sections below retain their own release scope.

Phase 1 is verified at the adapter and persistent-runtime boundaries. `task: pick_place` is additive; absent/`reach` preserves old Menagerie scene hashes and reaching behavior.

The cube has a free joint, 60 g mass and finite friction. The Panda's existing tendon actuator closes its actual collision pads. No cube weld, mocap, mesh parenting, object pose assignment during execution or artificial lift is used. Arm gravity compensation is a documented simulated controller aid. Approach, descent, close, lift, transport, lower, release and retract are actual actuator commands integrated at 2 ms.

Success requires bilateral force-bearing finger contacts, physical lift, retained contacts during transport, release, table support, final position error below 25 mm, low final object velocity, and no prohibited contact/controller/limit/timeout failure. This synthetic Coulomb-contact workcell is not hardware calibrated. Candidate screening is kinematic and does not imply task success.

Executed fixed benchmark: **20/20 successful**, **0 failures**, **86.5164 s total wall time**, per-rollout physics **3.50–5.45 s**, measured cube peak height **0.1767568 m**, final error **0.00169891 m**. These identical fixed-state repetitions demonstrate executed reproducibility, not statistical robustness to disturbances. Evidence: `artifacts/pick-place-benchmark.json` and `artifacts/pick-place-benchmark-trace.json`. Command: `.venv/Scripts/python.exe -m scripts.benchmark_pick_place --runs 20`.

New checks: **10 passed in 47.95 s** (`artifacts/master-pick-place-tests.xml`): free body/actual grasp/lift/transport/place; exact full-state fork/re-execution; physically missed grasp; deliberately released/dropped object; timeout; blocked geometry; parent validation; persistent branch export; obstacle invalidation; existing hierarchical search. An earlier run had nine passes and a test-request validation failure (60 s exceeds the API's 40 s bound); the corrected request was rerun.

Original compatibility baseline: **86 passed in 352.52 s**, one upstream Starlette/httpx deprecation warning (`artifacts/master-baseline.xml`). This baseline process imported pre-change code; it is historical compatibility evidence, not a complete post-change regression run.

Stored 5,000-rejection diagnosis: local experiment `16ed3913-5608-4161-9263-d5ce1c6d5583` used obstacle center `[.5,.1,.3]`, half-size `[.35,.35,.3]`, and recorded 5,000 kinematic collisions. Public experiments `ed4cd922-04d4-4dbc-88a3-a35213e5098e`, `70809bf3-ebc6-4206-ab3b-d8a6d9d776b4`, `fd9f9c5f-dca9-4233-9c89-42851b84ad56` used target `[.7,.41,.22]` and had no usable seed path. None recorded positive-step physics or a success. Bulk sampling now stops when seed planning fails, exposes seed diagnostics, and retains one honest diagnostic rollout. The prior count of thousands of rejected variants was wasted work, not evidence of thousands of physics trials.

Phase 2 additionally verifies two fresh pickup worlds with seeds 7 and 8, changed pickup/placement positions and successful fresh authoritative execution in each. A 5,000-plan search checks distinct commanded speeds and close/release dwell across eight IK/collision-screened height templates, then integrates three validation candidates and the winner again. Geometry checks are reused for identical templates; 5,000 full physics episodes are never claimed. Recorded traces, live sequence values, committed simulator state and validation counts are asserted by `tests/test_supervisor.py`.

Final full regression: **101 passed, 290.66 s, zero failed/errors/skipped**, `artifacts/master-release-backend.xml`. It includes a cube/obstacle collision classification check even when the robot itself is clear, and honest stopped status for expired lease/wall bounds. Those refinements do not change the verified fixed pickup controller or benchmark geometry. Public release verification is recorded in `DEMO_STATUS.md` after deployment.

Current public browser journey passed two fresh pickup cycles, exact measured body poses, three real evidence downloads, changed-obstacle stale results/replay, a genuine all-paths-failed scene and fresh successful clear-route computation. It verified three physics validations plus a separate fresh selected execution in each supported case. Source: `artifacts/master-public-verification.json`; measured outcomes/performance: `artifacts/master-public-measurements.json`.

Remaining: generalized obstacle-avoidance pickup detours and broad randomized robustness. Fixed unobstructed pickup and supported changed-condition cycles are verified; general manipulation is not claimed.
