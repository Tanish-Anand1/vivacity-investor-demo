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

### Contact-operated Apollo door development

`vivacity/apollo_door.py` adds an independent controller/task checkpoint for a
stationary door primitive. A bounded Cartesian integral feeds the constrained
whole-body actuator controller. Actual contact, root stability, tool forces,
latch displacement and door angle decide phase transitions. Execution never
overwrites robot, door or object poses. The compiled model has zero equality
constraints and zero mocap bodies.

The nominal development fixture is 0.75 m ahead of the world origin, with a
300 N/m latch spring and 40 N maximum actuator force per finger. The robot
approaches, inserts its tools around the visible handle/button, closes the
fingers, retracts the latch, and opens the door about 0.23 rad. This is only a
partial door opening; `cabinet_service_complete` remains false. The old and
replacement cartridges are not exchanged by this primitive.

```powershell
python -m pytest tests/test_apollo_door.py -q
python -m scripts.verify_apollo_door --output data/apollo-door-development.json
python -m scripts.verify_apollo_door --finger-force 1 --output data/apollo-weak-tool.json
python -m scripts.verify_apollo_door --latch-stiffness 4000 --output data/apollo-stiff-latch.json
```

Reports include actual qpos/qvel, body transforms, forces, phase events, source
hashes and a companion compiled MJB for rendering that exact model. Negative
commands return nonzero. The first weak-tool attempt became unstable before
grasping; an excessive-latch-resistance attempt lost retention and contacted the
crossbar. These are retained failures, not successful service evidence. Current
changes stop a stalled latch earlier and preserve the first failure observed.

### Training isolation

The native reference contract is now implemented in
`training/locomotion_contract.py` and `training/native_locomotion.py`.
G1 has 43 actions / 138 observations, Apollo 36 / 117, and the complete H1
23 / 78. It binds named joints, native actuator limits and compiled-model hashes.
Actor inputs are explicit proprioceptive sensor arrays, not a simulator object.
The Linux contract suite passed 23 tests at `a31613c`, including actual stepping,
deliberate falls, terminal-state freezing and independent checkpoint continuation.
This is the CPU reference for subsequent model-matched learning. No learned
weights, batched training environment, export parity or validated mobility is
provided by that contract. Training and acceptance remain separate open gates.

### Wide-door experiments and control corrections

The experimental Apollo model adds a visible 0.10 kg tool rotor with a bounded
native 3 Nm drive and +/-1.65 rad travel. Manufacturer arm limits are retained.
There are no equality attachments, mocap supports or execution-time pose writes.
Its native bench checks include rotation, overload and degree/radian compilation.

The approach uses seeded bidirectional RRT with sampled collision clearance.
The live trial still evaluates actual prohibited contact and stability. Routing
now preserves all coordinates outside the selected planning joints; an earlier
implementation checked the initial values but returned unchecked goal values
for them. The new regression exercises that discrepancy with native geometry.

Wide-task phase changes preserve commanded gripper preload. A measured finger
position compressed against an object is not an unloaded servo target. Angular
feedback memory is checkpointed and validated; root tilt excludes heading.
Swivel angle, speed and torque are included in measurements and failures.

These changes are research, not full-service acceptance. Earlier horizontal
pinch and wrist variants failed from collisions, reachability or grip loss.
The nearer 0.65 m fixture has reachable cartridge poses in independent IK, but
that is not proof of a collision-free dynamic service cycle. Current trial
reports retain all failed outcomes, frames, exact sources and native models.
The partial 0.25 rad fixture keeps its historical plant/control semantics.

```powershell
python -m pytest --noconftest tests/test_cabinet_route.py tests/test_cabinet_tooling.py tests/test_apollo_door.py -q
python -m scripts.verify_apollo_door --front-x .65 --finger-stiffness 2400 --opening-angle 1.1 --output data/apollo-wide-development.json
python -m pytest --noconftest training/native_tests -q
```

The wide-development command is expected to return nonzero while its gate is
failing. It never substitutes the verified partial-opening target.

### MJX compatibility

`training/README.md` describes an exact-embodiment MJX compatibility preflight.
It does not assign the old H1 policy to the new model, train a policy, provision
a GPU or establish locomotion. Training dependencies remain outside the runtime
image. Concrete cost approval is still required before paid resources.

### Remaining requirements

The complete cabinet sequence, force-aware insertion, collision-clearance
planning, full parameter/failure audit, model-matched locomotion, running,
shared-world fulfillment, RGB-D-driven control, API/UI integration for these new
tasks, production hosting and release verification remain open. The opening
release remains deferred. No paid training or hosting has been purchased.
