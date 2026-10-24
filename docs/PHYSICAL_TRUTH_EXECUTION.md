# Physical Truth execution ledger

Baseline: public production commit `8cea0c708e6be3722616b37b46362b6684c6e459`.
Historical sorting reference: `8d785b9`. Work is isolated from unrelated local files.

Outcome: reproducible, inspectable physical tasks with truthful success and failure
classification, followed by two independently verified production releases.

## Release order and acceptance

The Physical Truth release precedes all opening changes. No existing acceptance
result is evidence for a newly configured model or controller. Every required
scenario needs 20/20 nominal trials, at least 95/100 held-out trials within its
declared envelope, all deliberate failure fixtures, and state/transport/browser
checks. Hardware execution is outside the completion claim.

| Requirement | Current evidence | Release status |
| --- | --- | --- |
| Complete checkpoint, independent controller and simulator forks | New native checkpoint adapter and transactional worker pass local restore/fork/restart tests; legacy services not migrated | Partial |
| All exposed parameter dependencies and causality | New carton mass/density/inertia and solver-contact definitions pass native causality checks; app-wide inventory/UI generation incomplete | Partial |
| Whole-body stabilization and constraints | Wrench kernel v4 includes contact unloading. Complete G1, Apollo and H1 each pass 20/20 nominal, 100/100 held-out and deliberate instability in the bounded six-second stationary probe at cedf837. General reach, collision audit and mobility remain open | Bounded stance verified; broader gate partial |
| Contact-only manipulation and G1 bilateral load sharing | Native-servo baseline and corrected wrench controller v3 each pass 20/20 nominal and 100/100 held-out stationary trials with zero equality constraints. Wrench v4 unloading changes require revalidation; locomotion is not covered | Partial |
| G1/Apollo/H1 model-matched mobility, turns, terrain, carry | H1 short walk only; complete embodiments need training | Open |
| Apollo cabinet, latch, old/replacement cartridge cycle | Passive fixture and force-limited tooling pass component tests. A development controller physically retracts the latch and opens the door about 0.23 rad; full opening, cartridge service and acceptance remain open | Partial |
| Shared-world SORT through DISPATCH | Sorting ledger only | Open |
| Independent H1 running at 2 m/s | No validated running controller | Open |
| RGB-D pose estimation without privileged controller inputs | Separate image/depth estimator passes five rendered-image tests; not driving robot control or validated over the complete envelope | Partial |
| Hardware-transfer manifests, calibration and watchdog procedure | Offline G1 manifest, 382 simulated sensor samples, calibration procedure and fail-closed dry-run watchdog implemented; no transport or hardware validation | Partial |
| Transactional recovery, owner-scoped fork/compare/export | New opt-in contact API passes real HTTP pause/fork/compare/replay/export; abrupt process-exit recovery tested on real small MuJoCo dynamics | Partial |
| Browser journeys, three engines, all failure states | Actual WebGL2/live/pause/fork/compare/replay/export, network interruption, cancellation and final-state reload passed in Chromium, Firefox and WebKit at `3750125`. The WebKit select contrast correction also passed fresh tests and actual mobile screenshot inspection. Full warehouse journey remains open | Partial |
| Paid persistence, backups/restore, full-world capacity | SQLite-consistent backup/restore passes concurrent-WAL tests; paid hosting and complete-world capacity remain open | Partial |
| Production deployment and 24-hour soak | Not started for this release | Open |
| Break the Frame cinematic release | Deliberately deferred until physics release passes | Deferred |

## Active slice

Verified Linux baselines (their source hashes remain part of every report):

- [Deployment-image suite, cedf837](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40088346632): **485 passed, 3 skipped, zero failures**; separate capacity probes 4 + 1 passed. JUnit reports are in `artifacts/physical-truth-runtime/backend-cedf837/`.
- [Complete stationary embodiments, cedf837](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40088346654): each robot **20/20 nominal and 100/100 held-out**, plus correctly rejected deliberate instability. The held-out Wilson 95% interval is [0.9630, 1.0000] for each narrow sampled distribution. Reports and hashes are in `artifacts/physical-truth-runtime/stance-cedf837/`.
- [Corrected constrained G1, 8508e31](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40080972324): wrench controller v3 **20/20 nominal and 100/100 held-out**. Maximum placement error 11.591 mm; minimum steady vertical hand-support share 39.086%; maximum transport force-balance residual 0.004210 N; median CPU time 31.615 s and maximum 33.285 s. Zero equality attachments. Maximum compliant joint-stop penetration was 0.003474 rad, not zero. The complete report and hashes are in `artifacts/physical-truth-runtime/constrained-8508e31/`.
- [Three browser engines, 3750125](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40083924018): live frames, pause, fork, comparison, explicit replay, export, network interruption, cancellation, final-state reload. The corrected WebKit native select was inspected in the actual mobile screenshot.

Apollo wide-door development revealed that a release request must remove the old
handle's predicted support from the optimizer. Wrench v4 adds explicit contact
unloading while retaining all native collision geometry. Its focused native
separation test and the three complete-stance cohorts pass. The new constrained
G1 contact cohort is still running. V3's report is preserved rather than
relabeled as v4 evidence. Additional uncommitted Apollo development is not
covered by these baselines.

The maximum measured stance tilt was 0.01849 rad for G1, 0.02712 rad for
Apollo and 0.00286 rad for H1. Maximum per-trial p95 loaded-foot slip was
0.000455, 0.000542 and 0.004948 m/s respectively. These stationary samples
are not hardware reliability estimates or acceptance for the requested courses.

The isolated stationary native-servo G1 slice now has measured frictional contacts,
full-state checkpoints, a durable owner-scoped worker, real HTTP verification and
replay renders. Production still uses the historical fixture task. Do not replace
its UI or enable the research API by default until the required controller and
frontend gates pass. See `CONTACT_EXECUTION_HANDOFF.md` for the exact local contract.
The separate complete-embodiment development slice is documented in
`COMPLETE_EMBODIMENT_DEVELOPMENT.md`. Its fixture probes must not be described as
completed cabinet service or model-matched locomotion.

Only actuator commands may drive robot joints during a trial. Initial conditions
and independent planning scratch states may set positions before execution.
No attachment, kinematic object motion, or overwritten root pose may count as
contact-based load support.

## Dependencies and spending

GPU training and paid persistent hosting require a concrete instance quote and
spending ceiling approved before purchase. No paid resource has been provisioned
for this release. Training dependencies must remain outside the runtime image.

The latest user constraint is **zero spend** (2026-10-24). There is no funded GPU
or budget to activate the prior Runpod proposal. The free Colab compatibility
notebook is prepared; its execution and resource availability must be verified.
Paid hosting and training remain unfulfilled release requirements, not implied
authorizations. The following paid quote is retained only as historical context.

Runpod sign-in is complete. The observed 2026-10-24 quote is one A40 with 48 GB
VRAM, 43 GB RAM and 9 vCPU: $0.59/hour compute plus $0.007/hour container disk
(50 GB, no persistent volume). The first requested approval is a $2 ceiling for
at most two hours of exact-model compatibility probes, not full training.
Account balance is $0.00 and payment setup is pending. The operator must monitor
the resource externally; the tested stop-request guard is not a provider billing
cap. See `training/README.md` for the reviewed dependency lock and exact command.

## Evidence policy

Reports retain failures, parameters, simulator/controller/model identities, source
hashes, seeds and reproduction commands. `artifacts/physical-truth-runtime` holds
executed evidence and its generated summary. The nominal G1 carton was placed
3.209 mm from its target; its minimum steady vertical hand-load share was 44.609%.
These are local measurements for a stationary 8 cm transfer, not general carrying
or hardware performance. The held-out position envelope is only 1 cm wide.

Six negative fixtures were executed: low friction → `grip_slipped`; weak fingers
→ `insufficient_grip_contact`; 20 kg carton → `lift_not_clear`; distant source
→ `unreachable_target`; 150 N disturbance → `prohibited_collision`; short budget
→ `task_timeout`. These are measured failure classifications, not independent
certification of their inferred root causes.

Earlier whole-body attempts remain failed evidence. The new experimental
`constrained_bimanual.py` and `wrench_dynamics.py` preserve the original native
actuator gains, velocity bias, force limits and model hash. They optimize joint
acceleration, actuator forces and contact-dimensional wrenches with support,
friction, joint and fixture-clearance constraints. They do not provide complete
self-collision avoidance or validated general stabilization.

One development nominal trial completed 9,510 native steps with minimum steady
hand share 43.952%, placement error 7.063 mm and no actuator torque-limit excess.
Five development corner trials passed. These are development results, not the
required acceptance sample. A subsequent 20-trial nominal run passed 19 and failed
one with `MaxTime` under concurrent browser load. That run remains failed; the
100 held-out trials were not completed. The revised solver uses 150 iterations
and one solver thread instead of a scheduling-dependent 250 ms cutoff. The worker
retains its separate 120-second computation budget. New source hashes require a
separate acceptance report.

Local concurrent browser/controller testing encountered memory pressure: about
270 MB free on an 8 GB PC. Those interrupted checks are not passes. The dedicated
`physical-truth-contact.yml` workflow executes native gates and the real browser
journey on standard public-repository runners, without production credentials or
deployment steps. Its completed reports, not its configuration, determine status.

No new GPU training, paid resource activation, production deployment, 24-hour
soak or opening modification has occurred. This ledger is not a completion
certificate.

## Apollo wide-opening development, 2026-10-24

The wide-opening path is an experimental CLI task, not a public capability or a
completed service operation. Its left gripper uses a visible quarter-turn rigid
mount, a distinct embodiment identity and a new compiled-model hash. The tooling
manifest records its native parent transform and actual finger-servo stiffness.
Old complete-embodiment and partial-door reports do not certify this plant.

An offline diagnosis of trial R29 found a redundant arm pose that reaches the
same requested latch position with 0.15 rad joint reserves. The opt-in bounded
IK solver keeps the original damped solver for existing callers. Planning only
touches scratch data; it neither moves the live robot nor certifies contact.

Native R30 still failed `latch_resistance_or_retention_failure`: the latch moved
18.839 mm against a requested 50 mm, and both grippers lost one contact. Door
angle was 0.005343 rad. There were zero equality constraints and zero mocap
bodies. This is failed evidence, not a cabinet-opening result. Loaded wrist
control, full door opening, extraction, replacement, closure and acceptance
remain open.

The 14 native tooling/mechanism checks passed locally in 6.61 seconds, including
stiffness causality, force caps, weak grip, overload, latch resistance and native
restore. Larger local Apollo test runs were interrupted under memory pressure;
they are not passes. The isolated `apollo-cabinet.yml` workflow runs the actual
partial-door, IK and mechanism regressions in the deployment image on Linux.
Its executed result is required before accepting these changes.

## Subsequent integration findings

- The first Linux all-backend run failed one low-friction negative-test assertion.
  The native simulation rejected the trial for insufficient grip contact rather
  than the Windows slip classification. Stronger evidence checks exposed that
  an upward ejection can produce clearance without a controlled lift. The test
  now checks missing bilateral grip and absence of supported holding; clearance
  is not treated as successful manipulation. This correction passed the subsequent 484-test suite at 3750125.
- Completed-history loading fetches the last persisted frame directly. Explicit
  Replay remains the only operation that starts recorded motion.
- Checkpoint metadata and cached scene reads no longer decompress the full model.
  The owner boundary remains enforced before metadata or geometry is returned.
- New cabinet bench tests exercise locked-door contact, latch release and excess
  resistance, retention, free cartridge extraction and native restore. Added
  gripper tests cover frictional lift/release, low friction, weak grip and overload.
- The complete H1 requires a distinct 23-actuator model and policy. Its new tool
  crossbars need an abducted initial arm posture to clear the hips. This geometry
  correction is explicit; the old ten-actuator walking policy is not reused.
- An unactuated retention spring legitimately decelerated faster than the
  controller's constant-acceleration braking barrier. Wrench kernel v2 applies
  that barrier to driven joints; passive stops remain in native MuJoCo. A native
  regression reproduces the prior infeasibility and verifies passive settling.
# Linux joint-limit audit, 2026-10-24

The deployment-image run at `8df5d91` failed the complete G1 model's initial
thumb limits (89 focused tests passed; one failed). A separate Linux diagnostic
at `1d938e9` reproduced the cause: tuple membership between MuJoCo's native
joint enums and NumPy integers returned false for a hinge. The same expression
also skipped predictive joint-stop constraints in both experimental inverse
dynamics implementations. Native MuJoCo stops still existed; the optimization
barriers were not active. Previous Linux trials therefore cannot certify those
controller constraints, regardless of their measured task outcome.

The correction explicitly converts joint types and constants to Python integers,
bumps controller versions, and tests a fast approaching slider that must command
at least 6.25 m/s² of braking before the native stop. The prior constrained cohort
completed 20/20 nominal and 100/100 held-out physical outcomes before cancellation
was attempted; those outcomes do not establish the missing optimization barrier.
The prior complete-stance cohort was cancelled as superseded (108 Apollo samples,
113 G1 samples, and a completed 121-sample H1 report were retained). These reports
are historical development evidence, not current acceptance. Fresh Linux cohorts
are required for the corrected controller and compiled model identities.

The Linux model audit at `8508e31` passed all three complete embodiments, with
both G1 thumb positions correctly bounded at ±1.0472 radians. The local braking,
inverse-dynamics, and embodiment regression suite passed 23 tests in 27.52 s.

