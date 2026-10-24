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
| Whole-body stabilization and constraints | Experimental inverse dynamics passes pendulum constraints but fails the G1 task; alternate QP solver loses retention | Failed gate |
| Contact-only manipulation and G1 bilateral load sharing | Stationary native-servo baseline passes 20/20 nominal and 100/100 held-out trials, with zero equality constraints and continuous retention checks; whole-body controller not accepted | Partial |
| G1/Apollo/H1 model-matched mobility, turns, terrain, carry | H1 short walk only; complete embodiments need training | Open |
| Apollo cabinet, latch, old/replacement cartridge cycle | Physical switch demonstration only | Open |
| Shared-world SORT through DISPATCH | Sorting ledger only | Open |
| Independent H1 running at 2 m/s | No validated running controller | Open |
| RGB-D pose estimation without privileged controller inputs | Separate image/depth estimator passes five rendered-image tests; not driving robot control or validated over the complete envelope | Partial |
| Hardware-transfer manifests, calibration and watchdog procedure | Not yet validated as a package | Open |
| Transactional recovery, owner-scoped fork/compare/export | New opt-in contact API passes real HTTP pause/fork/compare/replay/export; abrupt process-exit recovery tested on real small MuJoCo dynamics | Partial |
| Browser journeys, three engines, all failure states | Prior release checks cannot validate new capabilities | Open |
| Paid persistence, backups/restore, full-world capacity | SQLite-consistent backup/restore passes concurrent-WAL tests; paid hosting and complete-world capacity remain open | Partial |
| Production deployment and 24-hour soak | Not started for this release | Open |
| Break the Frame cinematic release | Deliberately deferred until physics release passes | Deferred |

## Active slice

The isolated stationary native-servo G1 slice now has measured frictional contacts,
full-state checkpoints, a durable owner-scoped worker, real HTTP verification and
replay renders. Production still uses the historical fixture task. Do not replace
its UI or enable the research API by default until the required controller and
frontend gates pass. See `CONTACT_EXECUTION_HANDOFF.md` for the exact local contract.

Only actuator commands may drive robot joints during a trial. Initial conditions
and independent planning scratch states may set positions before execution.
No attachment, kinematic object motion, or overwritten root pose may count as
contact-based load support.

## Dependencies and spending

GPU training and paid persistent hosting require a concrete instance quote and
spending ceiling approved before purchase. No paid resource has been provisioned
for this release. Training dependencies must remain outside the runtime image.

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

The constrained whole-body controller is explicitly unsuccessful. Its original
QP stops on nonconvergence; a research-only Clarabel adapter progresses farther
but loses retention. Increasing the objective's requested normal load to 25 N per
hand also failed, as did a subsequent increase in torque-reference objective
weight from 0.01 to 1. None is substituted for the native-servo result.

No new GPU training, paid resource activation, production deployment, 24-hour
soak or opening modification has occurred. This ledger is not a completion
certificate.
