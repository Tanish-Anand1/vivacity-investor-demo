# Physical Truth execution ledger

Baseline: public production commit `8cea0c708e6be3722616b37b46362b6684c6e459`.
Historical sorting reference: `8d785b9`. Work is isolated from unrelated local files.

Outcome: reproducible, inspectable physical tasks with truthful success and failure
classification, followed by two independently verified production releases.

The current branch also routes Apollo's experimental latch-and-door primitive
through the G1 transactional worker. Three new tests passed in two local runs:
2/2 covered full-state restore and real HTTP live/pause/fork/cancel/replay, and
1/1 completed a real HTTP partial-door trial with measured latch and door motion.
The API result sets `cabinet_service_complete: false`. This does not change the
wide-door, cartridge-service, warehouse or production release gates below.
The cabinet friction parameter now reaches every native fixture/cartridge service
surface instead of leaving the door, handle and trays at their default. Nine
cabinet mechanism tests pass locally, including the new compiled-contact check.
After the fixture source changed, the combined Apollo adapter and original door
regression passed 12/12 in 297.57 seconds. The existing generic checkpoint/API
regression passed 11/11 in 129.58 seconds, and the frontend build passed.
At `5c270e7`, the Linux deployment-image suite passed **508/511 tests with 3
skips**, zero failures or errors; the isolated Apollo suite passed **39/39** and
the contact suite passed **98/98**. These runs verify that commit, not the
subsequent wide-door development changes. The complete release gates remain open.

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
| Contact-only manipulation and G1 bilateral load sharing | Native-servo baseline and corrected wrench controllers v3/v4 each pass 20/20 nominal and 100/100 held-out stationary trials with zero equality constraints. V4 source hashes match the current implementation; locomotion is not covered | Partial |
| G1/Apollo/H1 model-matched mobility, turns, terrain, carry | H1 short walk only; complete embodiments need training | Open |
| Apollo cabinet, latch, old/replacement cartridge cycle | Passive fixture and force-limited tooling pass component tests. A development controller physically retracts the latch and opens the door about 0.26 rad, but a right-pad/crossbar collision stops the wide trial before cartridge service | Partial |
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

- [Deployment image, 9591541](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40102744073): **502 passed, 3 skipped, zero failures/errors**; separate 512 MB host checks 4 + 1 passed. Reports: `artifacts/physical-truth-runtime/backend-9591541/`.
- [Deployment image, 5c270e7](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40108497076): **508 passed, 3 skipped, zero failures/errors** across three shards. The JUnit suites reported 129, 166 and 216 tests. Separate constrained-host checks passed. This verifies the Apollo execution adapter and friction change before later controller development.
- [Apollo components, 5c270e7](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40108497010): **39 passed**, zero skips/failures, 133.905 s. [Contact integration, 5c270e7](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40108497012): **98 passed**, zero skips/failures, 147.779 s; its Chromium, Firefox and WebKit jobs also passed. These are component/contact checks, not full cabinet or warehouse acceptance.
- [Apollo components, 9591541](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40102744097): **33 passed**, zero skips/failures, 77.732 s. Includes native partial-door success and negative fixtures, swivel torque/overload, collision routing, IK and checkpoint independence. This is not wide-service acceptance. Report: `artifacts/physical-truth-runtime/apollo-9591541/`.
- [Contact integration, 9591541](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40102744206): **97 native checks passed** in 161.907 s; Chromium, Firefox and WebKit each passed the 18-check actual browser journey. The three runs each executed 9,510 steps and measured 5.882 mm placement error. The mobile WebKit screenshot was inspected. Reports: `artifacts/physical-truth-runtime/contact-9591541/`.
- [Native locomotion contract, a31613c](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40102370744): **23 passed**, zero skips/failures, 16.402 s. New complete-embodiment mappings, sensor-only actor inputs, bounded native actions, measured failure/reward and checkpoint continuation. No trained policy or mobility acceptance. Report: `artifacts/physical-truth-runtime/native-contract-a31613c/`.

- [Latest deployment-image suite, 1eedec9](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40095423157): **495 passed, 3 skipped, zero failures**; separate capacity tests 4 + 1 passed. The three skips concern frontend visual asset files excluded from the backend image. Reports: `artifacts/physical-truth-runtime/backend-1eedec9/`.

- [Deployment-image suite, cedf837](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40088346632): **485 passed, 3 skipped, zero failures**; separate capacity probes 4 + 1 passed. JUnit reports are in `artifacts/physical-truth-runtime/backend-cedf837/`.
- [Complete stationary embodiments, cedf837](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40088346654): each robot **20/20 nominal and 100/100 held-out**, plus correctly rejected deliberate instability. The held-out Wilson 95% interval is [0.9630, 1.0000] for each narrow sampled distribution. Reports and hashes are in `artifacts/physical-truth-runtime/stance-cedf837/`.
- [Corrected constrained G1, 8508e31](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40080972324): wrench controller v3 **20/20 nominal and 100/100 held-out**. Maximum placement error 11.591 mm; minimum steady vertical hand-support share 39.086%; maximum transport force-balance residual 0.004210 N; median CPU time 31.615 s and maximum 33.285 s. Zero equality attachments. Maximum compliant joint-stop penetration was 0.003474 rad, not zero. The complete report and hashes are in `artifacts/physical-truth-runtime/constrained-8508e31/`.
- [Constrained G1 v4, cedf837](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40088346604): **20/20 nominal and 100/100 held-out**. Maximum placement error 11.773 mm; minimum steady hand-support share 39.026%; maximum steady force-balance residual 0.003293 N; compliant joint-stop penetration 0.003473 rad. Zero equality attachments; maximum actuator torque fraction 1.0. Median CPU time 43.320 s, maximum 44.354 s. Held-out Wilson 95% interval [0.9630, 1.0000], for this bounded simulation distribution only. Full report and hashes: `artifacts/physical-truth-runtime/constrained-cedf837/`. All three browser journeys passed at that revision.
- [Three browser engines, 3750125](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40083924018): live frames, pause, fork, comparison, explicit replay, export, network interruption, cancellation, final-state reload. The corrected WebKit native select was inspected in the actual mobile screenshot.

Apollo wide-door development revealed that a release request must remove the old
handle's predicted support from the optimizer. Wrench v4 adds explicit contact
unloading while retaining all native collision geometry. Its focused native
separation test and the three complete-stance cohorts pass. The new constrained
G1 v4 contact cohort has now passed independently. V3's report is preserved
under its own source identity. Experimental Apollo wide-opening development is
not covered by these baselines.

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
notebook has now executed on a T4. Three-step numerical comparisons passed
for H1/G1 with MJX-Warp and Apollo with MJX-JAX. Apollo's unchanged margin is
unsupported by Warp; that failed attempt remains in the evidence. H1 has a
reported multi-contact limitation, requiring longer regressions. No policy was
trained. All files and their archive checksum were verified locally, then the
disposable runtime was disconnected. See `training/README.md` and
`artifacts/physical-truth-runtime/colab-t4-fa47720/`.
Paid hosting and training remain unfulfilled release requirements, not implied
authorizations. The following paid quote is retained only as historical context.

At zero new spend, Render Free cannot qualify for the requested persistent,
always-available release: it spins down after idle time and cannot attach a
persistent disk ([Render Free limitations](https://render.com/docs/free)).
Oracle's [Always Free A1 allowance](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
advertises 2 OCPUs, 12 GB RAM and free block storage; availability depends on
the account's home region and idle instances can be reclaimed. MuJoCo 3.15.0
publishes a Linux ARM64 wheel. The branch-triggered
`.github/workflows/arm64-host-preflight.yml` built the unchanged deployment
image on a free public-repository ARM64 runner at `9776587` and executed
**30/30 native smoke tests** inside its 8 GB container limit, with zero failures
or skips ([run 40112768362](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40112768362)).
This establishes architecture compatibility only. It does **not** establish
production-host capacity, a provisioned Oracle account, durable recovery,
memory headroom under the complete-world workload or a 24-hour soak. No
qualifying no-cost host has yet been demonstrated.

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

The first Linux cabinet regression at `fa47720` failed two of 25 tests: the
wide-tooling changes had altered the existing partial-door plant and feedback.
The partial path now retains its original latch reach, tool orientation and
controller, while a wide request keeps the distinct experimental embodiment.
It never substitutes the partial goal when a wide trial fails. Native trial R31
then completed 8,132 steps, retracted the latch 52.347 mm and reached a door
angle of 0.229296 rad, with root speed 0.001085 m/s. There were zero equality
constraints or mocap bodies. This is one successful partial-door trial; the
Linux regression rerun at `0b8f00d` then passed **26/26 tests** in 134.663 s,
including the nominal partial door, weak-tool instability, stiff-latch rejection,
checkpoint independence and the no-substitution check for wide requests.
JUnit: `artifacts/physical-truth-runtime/apollo-0b8f00d/apollo-components.xml`.
The wide-service acceptance remains open.

### Later cabinet research record

Native attempts R38--R53 are retained as 16 differing development experiments,
not a statistical acceptance cohort. None completed the requested wide opening.
R53 used the 0.65 m fixture, 2,400 N/m finger servos capped at 40 N, a 300 N/m
latch and a 1.1 rad requested opening. It executed 12,581 native steps in
102.130 seconds of local compute, then failed from latch resistance/retention
at 25.162 seconds of simulation. Measured latch retraction was 24.568 mm,
door angle 0.004643 rad and root tilt 0.034798 rad. Neither cartridge moved to
its service destination. There were zero equality constraints or mocap bodies.

The trace and source snapshot are retained in
`artifacts/physical-truth-runtime/apollo-development-review/`; the larger native
model is retained in the local development evidence directory. The review JSON
records per-attempt parameters, actual outcomes, source hashes and report hashes.
Missing older source archives are marked null rather than asserted verified.
Right-hand preload persists in R53, but left-hand retention still fails. This
blocks wide-door acceptance, cartridge-service composition and deployment.
The final local cabinet/mechanism/tooling/IK/routing/checkpoint regression run
passed **35 tests in 193.91 s**, with no failures or skips. This includes the
preserved partial-door nominal and negative cases. Its JUnit report is
`artifacts/physical-truth-runtime/apollo-final-regression-tests.xml`.

The next wide-tooling controller trial used the same 0.65 m fixture, 40 N
fingers at 2,400 N/m, 300 N/m latch and a requested 1.1 rad opening. Reducing
only the wide-tooling stance reference penalty from 10 to 1 let real contact
retract the latch to 38.706 mm, but the door-opening IK initially failed from
the contact-displaced arm state. The previously commanded whole-body pose was
a feasible scratch-planning seed; no live pose was overwritten. A regression
using the measured arm/root configuration verifies this local-minimum retry.

With that retry and a measured-pose right-hand release, one native trial
reached the `release_right` phase after 11,551 steps. The door angle was
0.258087 rad on entering release; the latch had reached 51.4 mm during the
preceding open phase. The trial then **failed** `prohibited_collision` when the
opening right pad struck the physical latch crossbar at 8.949 N. Final door
angle was 0.241583 rad and final latch retraction 26.136 mm. There were no
attachments or kinematic body writes. A bounded 20 mm retreat was also tried;
it hit the same crossbar at 9.665 N and was removed. Wide opening, cartridge
exchange and acceptance are still open. Reproduce this development condition
with `python scripts/verify_apollo_door.py --front-x .65 --finger-stiffness 2400
--opening-angle 1.1 --output <report.json>`; the verifier preserves the failed
result and source/model hashes.
The current compiled model is
`192c7e6acc3f52aac147a2498f77dca8609df526e4202343e5a10d1ce6691463`;
it has zero equality constraints and zero mocap bodies. Its controller is
`vivacity.apollo-cartesian-contact/6-experimental`. After this controller
change, local `tests/test_apollo_door.py` passed **10/10 in 214.00 s** and
`tests/test_apollo_execution.py` passed **3/3 in 236.96 s**. Linux regression at
`9776587` passed **509/512 backend tests with three skips**, **98/98 contact
tests**, and the Chromium, Firefox and WebKit contact journeys; the ARM64
deployment-image preflight passed **30/30 native smoke tests**.

A checkpoint taken at native step 11,083 allowed release candidates to start
from the same measured integration state. A 40 mm outward and 30 mm lateral
right-hand goal with a 45 mm finger command avoided the crossbar and reached a
transient zero right-pad force at simulation time 23.228 s. Native geometry
distance showed the negative pad was still only **0.959 mm** from the handle.
The old force-only predicate would have treated this as release; the current
primitive also requires **5 mm signed separation** from the grasp surfaces.
`tests/fixtures/apollo_transient_release.json` retains the exact measured
MuJoCo positions and model hash for this regression. Subsequent tested
withdrawal paths either struck the latch link or remained within 0.032 mm of
the handle at timeout; none passed. Shortening both right pads, or only the
positive pad, lost the negative pad's handle contact before latch completion,
so both geometry edits were reverted. These are failed development trials,
not accepted cabinet service or released controller paths.
The local Apollo door/execution suite passed **14/14 in 590.40 s** with the
separation check. After limiting signed-distance queries to unloaded hands,
the focused separation/checkpoint checks passed **2/2 in 37.66 s**. The exact
code revision `483a25f` passed [510/513 Linux backend tests with three skips](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40116822856),
[41/41 Apollo component tests](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40116822908),
[98/98 contact tests and all three browser engines](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40116822816),
and [30/30 ARM64 native preflight tests](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40116822847).
An exact-code full wide-door trial then failed `prohibited_collision` after
11,551 native steps at 23.102 s of simulator time. The right-pad/crossbar force
was 8.949 N. Momentary right grip force was zero, but right-pad/handle signed
clearance was only **0.011 mm**, so the new release guard did not advance the
phase. Local compute time was 122.10 s; the verifier returned exit code 1 as
designed for a failed physical trial. The report remains local at
`$TEMP/vivacity-apollo-postguard/report.json`; it is not a release artifact.

## Subsequent integration findings

The `fa47720` WebKit journey failed an observation GET with `ECONNRESET`;
Chromium and Firefox passed. At `1eedec9`, idempotent test observations
allow two connection-reset retries using Playwright's built-in option.
HTTP failures and simulation-start mutations are not retried. The first
failed run remains recorded. The rerun at `1eedec9` passed all three browser
journeys, each with 18 checks, and 97 native checks. Each completed trial
executed 9,510 steps with 5.882 mm placement error. The WebKit mobile
screenshot was inspected. Reports: `artifacts/physical-truth-runtime/contact-1eedec9/`.


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

