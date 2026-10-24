# Complete embodiment and cabinet development

This is an offline development slice. It does not replace the production tasks,
assign a locomotion policy, or establish the full Physical Truth acceptance gate.

## Models and tooling

`vivacity/humanoid_embodiments.py` compiles the licensed native G1 with hands,
Apollo, and complete H1 models. The resulting actuator counts are 43, 36 and 23.
Apollo and H1 include two visible custom simulated parallel grippers. These are
not manufacturer-approved hardware. Each tool has 0.49 kg of modeled mass, two
independent prismatic fingers, a 0–210 mm opening, bounded position commands and
40 N maximum force per finger by default. Native contact, inertia and force
limits remain active. No equality constraint, adhesion or mocap body supports
an object.

The source Apollo wrist/hand assembly retains its original declared inertia;
the tool is an additional assembly. H1 retains its complete articulated arms.
The old ten-actuator H1 walking policy is incompatible with this 23-actuator
embodiment and is never assigned to it.

Manifests include compiled binary identity, native joint and actuator mapping,
force/command bounds, robot mass, tooling and explicit initial-pose corrections.
Source G1 thumb references exceeding their joint limits are brought inside those
limits at initialization. Source foot surfaces are placed 0.1 mm above the floor
at initialization. These corrections precede execution; no controller overwrites
a root or object position during physics stepping.

## Passive cabinet

`vivacity/cabinet_mechanism.py` contains a passive door hinge, spring-return latch,
strike pocket, guide rails, shelf, spring-return retention bar, old and replacement
free-body cartridges, and two physical trays. A visible latch button and the
retention button must be displaced through contact. There are no door, cartridge
or latch actuators in the fixture itself.

The two cartridge identities never change. The mechanism indicator measures the
replacement cartridge's seating and orientation plus latch, door and retention
positions. It is not a complete service-success predicate: robot stability, old
cartridge placement, collision history and the service sequence are still needed.

Bench tests use explicit force-limited moving rams and documented external test
loads. These tests prove fixture behavior, not an Apollo controller. They test
locked-door resistance, contact release, excessive spring resistance, blocked
and released extraction, physical settling, invalid geometry and full-state
restore. Gripper bench tests demonstrate frictional lift, release and failure at
very low friction, weak finger force and excessive payload.

## Standing controller

`vivacity/stance_control.py` uses the constrained native wrench solver with
embodiment-specific reference weights, center-of-mass feedback, upright-body
feedback, foot tasks and bounded support acceleration. Predictions are not
accepted as measurements. Native root height, tilt, loaded-foot slip, contact
force and joint-limit observations independently evaluate every probe.

The six-second probe contains standing, a small shoulder excursion, a bounded
0.2-second horizontal disturbance and settling. It is not a walk, a full cabinet
reach, a carrying test or hardware validation. Early development attempts fell
or became infeasible; the first H1 initialization also left its soles about
11.6 mm above the floor. Those attempts are not successful evidence.

Reproduce local checks from the repository root:

```powershell
python -m pytest tests/test_cabinet_mechanism.py tests/test_simulated_tooling.py tests/test_humanoid_embodiments.py -q
python -m scripts.verify_complete_stance --robot h1 --nominal 20 --held-out 100 --failure-fixtures --output data/h1-stance-acceptance.json
python -m scripts.verify_complete_stance --robot apollo --nominal 20 --held-out 100 --failure-fixtures --output data/apollo-stance-acceptance.json
python -m scripts.verify_complete_stance --robot g1 --nominal 20 --held-out 100 --failure-fixtures --output data/g1-stance-acceptance.json
```

The nominal samples are deterministic repetitions. Held-out settings vary floor
friction from 0.6 to 1.0, shoulder excursion from −0.09 to −0.07 rad and disturbance
from 10 to 20 N. This narrow declared distribution cannot establish general
stabilization or manipulation reliability. Sample counts and the report's
`acceptance_passed` field are authoritative; a small development run is not a
120-trial acceptance.

## Open work

The complete cabinet sequence, force-aware insertion, collision-clearance
planning, full parameter/failure audit, model-matched locomotion, running,
shared-world fulfillment, RGB-D-driven control, API/UI integration for these new
tasks, production hosting and release verification remain open. The opening
release remains deferred. No paid training or hosting has been purchased.
