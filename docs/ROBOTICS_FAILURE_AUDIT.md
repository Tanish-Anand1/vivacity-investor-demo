# Robotics physical-truth audit — 2026-10-24

This is a forensic record of the current branch, not a certification of every
scenario. The reference commit `8d785b9` exists. The repair branch is
`codex/physical-truth`, forked from `d4446e6` with tracked files clean; 82
files differ between the reference and that starting point. Existing untracked
workspace artifacts were left in place. The verified factory SORT stage and
Panda workcell editor were not replaced.

## Confirmed breaks in the input-to-outcome chain

| Reported symptom | Observed execution path and root cause | Repair or present limit |
| --- | --- | --- |
| Lowering humanoid floor friction had no effect | `HumanoidLab.tsx` sent `floor_friction`; `HumanoidTrialRequest` accepted it; `_scene`/`compiled_model` changed only `floor.geom_friction`. Before repair, an H1 trial at 0.2 and 0.8 had different model hashes but identical frames and 1.0 effective foot contact friction. G1 feet have priority 1 and 0.6 friction; Apollo's explicit sole/floor pairs specify 2.0, overriding both geoms. | `vivacity/humanoids.py` now gives the floor higher priority than robot soles and updates Apollo's explicit pair friction in both source MJCF and the production binary path. Direct MuJoCo probes read the submitted 0.2/0.8 contact coefficient on all three embodiments. Dedicated solver-level regression tests were added. [MuJoCo's contact mixing rule](https://mujoco.readthedocs.io/en/stable/modeling.html#contact-parameters) explains the original discrepancy. |
| G1 appears to carry with one hand | `humanoid_pickup.py::_contact_measurements` requires bilateral force-bearing contact before grasp. `_activate_grasp` then welds the parcel to **only** `right_wrist_yaw_link`; the lift, transfer and lower phases plan only the right hand. The licensed model has actuated fingers, but `_control_vector` leaves them at home targets throughout this task. In single-seed measured 0.2/0.5/1.2 kg trials, right-hand peak normal force rose 128/183/249 N while left-hand peaks stayed roughly 85/85/83 N. | The existing task is a bilateral-contact-gated **single-wrist fixture** pickup. It is not validated bimanual load sharing, dexterous grasping, or whole-body carrying. Its successful parcel placement is real within this simplified constraint. A dynamic dual-hand carton benchmark remains unimplemented. |
| Apollo only moves a bar/rotor | `humanoids.py::_scene` contains a static cabinet shell, one hinged switch and one motorized rotor. `apollo_service.py` gates motor torque on measured hand/switch contact and deflection, then retracts. Its success check does not inspect a door, latch, cartridge, tray, replacement or lock because these bodies do not exist. The integrated Apollo model has collision hand plates but no finger actuators. | This is a physical **switch actuation and motor response probe**, not cabinet servicing. The robot can push the switch; cartridge handling requires a gripper/fixture and a validated multi-phase controller. Do not label the probe as completed maintenance. |
| Physical settings appear visually inert | Before repair, the floor slider changed a model value but not the active H1/G1/Apollo sole contact. Separately, `factory.py` already compiles carton mass, half-size, friction (priority 1) and roller velocity drives; `world_editor.py` rebuilds the Panda workcell after edits and tests contact friction against `mjData.contact`. | The confirmed platform defect was the humanoid sole/floor path. Model values and sampled effective floor-contact friction are now included in humanoid result JSON so an investor can inspect the executed model, not just the slider. Other settings remain bounded to the scenario that exposes them. |
| Local live trial browser checks reloaded mid-run | The Vite dev server watched Playwright's `frontend/test-results-live` traces and screenshots, then sent HMR page reloads while a job was running. This was visible in its log during the first browser run. That run also competed with the full backend suite for CPU and hit 90/120-second wall bounds. | `frontend/vite.config.ts` now ignores Playwright artifact directories. The later serial compiled-model browser rerun passed 3/3 with no artifact-triggered reloads. |
| Live H1 physics took a minute despite fast integration | `HumanoidTrialService._run` flushed SQLite every two frames. A direct H1 trial integrated 3,536 steps in 1.34s, while a local API/browser job took 60.63s inside the callback-heavy simulation. The initial frame was already persisted immediately. | Later frames now flush in batches of 16; ordering and pre-completion streaming tests pass. A comparable browser H1 trial measured 4.06s backend compute wall time and completed in the end-to-end journey. This is a local-volume measurement, not a Render latency guarantee. |

The earlier `8d785b9` SORT result is a reference, not evidence that later
COLLECT, TRANSPORT, PACK, CLOSE, SEAL, LABEL or DISPATCH work. The current
`vivacity/fulfillment.py` intentionally marks every stage after SORT blocked
because no shared-world humanoid carry controller exists. No object is
substituted or teleported to make those stages green.

## Exposed parameter inventory

Categories: **A** reaches the current executed model/controller; **B** was
connected incorrectly and is repaired on this branch; **C** requires a fresh
compiled model/reset and is handled by the owning adapter; **D** is not
supported by that scenario; **E** would be a visual-only value presented as
physical. No category E control was confirmed in the bounded humanoid,
factory or Panda controls inspected here. This does not certify every route in
the application. A scenario may pass despite a parameter's real causal effect;
success alone is not the sensitivity metric.

| Surface and setting | Class | Actual dependency and limit |
| --- | --- | --- |
| Humanoid floor friction | B | MuJoCo floor geom and G1/H1 contact priority; Apollo explicit sole/floor pair; sample actual `mjData.contact.friction`. Single tangential Coulomb coefficient, not independently calibrated static/dynamic friction. |
| G1 parcel mass | A/C | Recompiles or patches body mass and principal inertia in a private `MjModel`; constant parcel dimensions. The rigid grasp fixture can mask natural slip. |
| G1 parcel position and destination | A | Initial free-body qpos and IK/placement target. Source/destination workspaces are bounded. |
| Apollo switch position and stiffness | A/C | Switch body pose and hinge stiffness in a private `MjModel`; target IK recomputed. No cabinet-door or cartridge variables exist. |
| H1 walk distance and motion scale | A | Velocity command/termination goal; 10-actuator recurrent policy integrates in MuJoCo. No running command or payload. |
| Humanoid disturbance | A | Bounded external force on base during 0.4–0.65 s. |
| Humanoid duration/timeout | A | Number of integrated steps; not a material property. |
| G1 dimensions, density, grip strength; Apollo cartridge/latch; H1 payload/slope/turn/running | D | No corresponding humanoid API or verified controller. Do not present these as functional controls. |
| Panda workcell cube mass/density/half-sizes, friction/material, table friction, gravity, gripper force, obstacle pose/size | A/C | `world_editor.py` validates and versions the configuration; `robotics.py`, `physical_properties.py` compile new geometry, inertia, contact and actuator parameters. Editor applies only to the pick/place workcell. |
| Factory carton mass/half-size/friction/start, roller speed, gripper scale | A/C | `factory.py` compiles bodies and drive actuators; each run uses settings from its cell. `realtime_speed` is wall-clock pacing; arrival spacing and sort threshold are controller decisions, not material coefficients. |

Restitution, independently calibrated static/dynamic friction, arbitrary
contact compliance, and arbitrary robot-model edits are not exposed as
supported controls by these scenarios. Friction here is the MuJoCo contact
solver's tangential coefficient. A fixed grasp constraint has no physical
grip-strength setting; adding a slider for it would be misleading.

## Integrated humanoid embodiments and control type

| Model | Executed articulation | Controller | Mechanical limit |
| --- | --- | --- | --- |
| Unitree G1 | 55 DoF, 43 actuators, 49 meshes | Bilateral hand-position IK to establish contact; scripted joint targets under MuJoCo dynamics; then one right-wrist weld fixture | The model has actuated fingers, but this controller does not close them; no validated force-limited grasp or bimanual load-sharing controller. |
| Apptronik Apollo | 40 DoF, 33 actuators, 44 meshes | Stationary right-arm IK and position control; measured hand/switch contact gates a motor | Collision hand plates have no actuated fingers in this integration; no cartridge/door mechanism. |
| Unitree H1 | 16 DoF, 10 actuators, 21 meshes | Pinned matched recurrent walking policy with joint-level PD torque, feedback and native contacts | Tested for a short straight walk only; no turning, carrying or running policy. |

The G1 and Apollo phases are real dynamics under scripted/IK targets, not
learned general-purpose manipulation. H1 uses the pinned policy only for
walking. No evaluated trial is presented as hardware performance.

## Task capability disposition

| Scenario | Current physical operation | Status |
| --- | --- | --- |
| Panda workcell edit/fork/replay | Native collision, mass/inertia, gravity, gripper and versioned scene changes | VERIFIED for the bounded workcell; no arbitrary-world editor claim |
| Factory SORT | Native roller/Panda contact with measured destination arrival | VERIFIED for the bounded three-carton order |
| UR5e precision assembly | Modeled parallel-jaw fixture picks, transfers, releases and seats one part in a passive fixture | PARTIAL as an assembly primitive; no fastening or physical UR gripper claim |
| High-payload arm transfer | No validated payload-transfer controller or grasp in this integration | BLOCKED; catalog says `not_implemented` |
| Delta-arm high-speed sorting | No validated delta model or moving-object interception | BLOCKED; catalog says `not_implemented` |
| Collaborative constrained transfer | No validated moving-obstacle/minimum-clearance controller | BLOCKED; catalog says `not_implemented` |
| G1 parcel placement | Bilateral approach, contact-gated single-wrist fixture, lift, transfer, release, support verification | PARTIAL for physical grasp/manipulation; no genuine load-sharing or locomotion |
| Apollo switch probe | Reach, contact, switch deflection, motor-driven rotor, retraction | PARTIAL as a maintenance primitive; cabinet service NOT TESTED/unsupported |
| H1 threshold walk | Pinned recurrent controller, foot contacts, goal, slip and stable stop | VERIFIED for the bounded course; turning, carrying and running NOT TESTED |
| Fulfillment after SORT | No shared-world controller | BLOCKED; `fulfillment.py` reports blocked stages |

The current fulfillment API exposes `sort → collect → pack → seal → label →
dispatch`; it has no explicit `transport` or `close` task records. Those
missing stages must be modeled before the eight-stage workflow in the
directive can be claimed. `fulfillment.py` derives the sorting state from
physical arrival events and does not advance downstream work on a timer.

## Scenario evaluation contract

| Scenario | Controller and editable inputs | Measured acceptance and observed failure | Executed evidence |
| --- | --- | --- | --- |
| Panda workcell | Damped-least-squares IK, joint-space search and native gripper control; bounded geometry, obstacle, mass, friction, gravity and gripper edits | Contact and goal error, forbidden collision, placement, version/replay consistency; failures include collision and infeasible grasp | `tests/test_world_editor.py` (5), `tests/test_physical_platform.py` (22) in the clean suite |
| Factory SORT | Conveyor and Panda sorting state machine; carton mass/size/friction/start, belt speed, gripper scale | Each sorted carton must physically arrive at its assigned destination; weak-grip runs fail | `tests/test_factory_production.py` (3), `tests/test_fulfillment.py` (2), other factory modules in the clean suite |
| UR5e fixture seating | Staged IK/search/contact controller with modeled parallel-jaw flange; bounded assembly configuration | Measured part seating in the passive fixture; no fastening claim | `tests/test_v_robotics.py` (6) in the clean suite |
| G1 stationary parcel | Bilateral approach IK, position targets and one contact-gated wrist fixture; parcel position, destination, mass, floor friction, disturbance | Bilateral initial contact, lift, released destination support and final pose; 2.0 kg produced a prohibited-contact failure | Browser: 2 nominal/resumed successes, 1 heavy-parcel failure; source and binary physical tests |
| Apollo switch/motor | Arm IK and contact-gated motor; switch lateral pose/resistance, floor friction, disturbance | Hand contact, switch angle, motor shaft travel, arm retraction; 16 N·m/rad did not actuate | Browser: 1 nominal success, 1 high-resistance failure; source and binary physical tests |
| H1 threshold walk | Matched recurrent policy and PD torques; walk distance, floor friction, disturbance | Goal error, foot support/slip, threshold contact and stable stop; 0.2 friction failed in fixed-seed source and binary tests | Browser: 1 nominal success; low-friction failure in `tests/test_humanoid_physics_contract.py` |
| High-payload, delta sorting, collaboration; downstream fulfillment; cabinet servicing; running | No validated controller/world state | No success is emitted for an unimplemented operation | Catalog and fulfillment blocked-state tests only; physical task NOT TESTED |

Counts above are executed examples or test-case counts, not reliability rates
over a randomized campaign. Fixed conditions and a single seed do not
establish field robustness or hardware transfer.

H1's pass criterion uses the 95th percentile of support-foot slip, not the
single largest instantaneous slip sample. Both values are now shown so a
successful run with a larger peak is not mistaken for a hidden failure.

The currently exposed H1 distance and horizontal-disturbance controls have
direct controller/force paths but do not yet have independent parameter-sweep
acceptance tests. The same applies to every permutation of the Panda and
factory editors. These are remaining sensitivity-audit gaps, not evidence that
the controls are inert.

## Acceptance evidence and remaining gates

Independent analytical mechanism tests live in `tests/test_physics_causality.py`:
free fall at two gravity values; equal force with two masses; box dimensions,
native inertia and contact height; equal torque with two inertias; inclined
sticking/sliding with measured solver friction. Existing
`tests/test_physical_platform.py`, `tests/test_world_editor.py` and
`tests/test_factory_production.py` cover bounded gripper force, world
save/restore, contact propagation and factory settings. This does not prove a
force-limited G1 hand grasp: the current G1 uses a weld fixture.

`tests/test_humanoid_physics_contract.py` probes actual sole/floor solver
coefficients for all three robots at 0.2 and 0.8; separately checks Apollo
switch position/resistance, G1 mass and principal inertia, H1 low-friction
trajectory/outcome changes, and G1 loading over 0.2, 1.2 and 2.0 kg. The
2.0 kg run is expected to fail on a measured prohibited contact; a high
mass is not silently turned into a success. The existing world-editor tests
exercise native reset/version and independent forks; the humanoid API tests
exercise persisted results and owner isolation.

Gate 1 (parameter propagation) is repaired for the confirmed humanoid
sole/floor break, with solver-level and controller-level tests. It is not a
claim that every conceivable model property is editable. Gates 2–3 have bounded
stance, reach, contact and parcel-placement evidence, but the pickup remains a
simplified constraint. Gate 4 (dynamic bimanual carton), gate 5 (turn/carry),
gate 6 (cabinet service), gates 7–8 (shared-world fulfillment), and gate 9
(running) are **not complete**. Gate 10's regression checks passed for the
implemented bounded tasks, but the absent task gates cannot be promoted to a
release. The Isaac Lab [whole-body/teleoperation patterns](https://isaac-sim.github.io/IsaacLab/main/source/features/isaac_teleop.html)
are a research reference, not an integrated or validated controller here.

Reproduce the focused mechanism checks with
`\.venv\Scripts\python.exe -m pytest -q tests/test_physics_causality.py tests/test_humanoid_physics_contract.py`.
The final uncontended full backend run on this branch was
`\.venv\Scripts\python.exe -m pytest -q --junitxml=artifacts/physical-truth-final-suite.xml`:
**365 passed, 1 skipped, 1 Starlette/httpx deprecation warning, 0 failed** in
32m15s on this Windows host. The 9 analytical tests, 8 humanoid physical
contract tests, and first-motion persistence regression are included in that
total. The separate focused humanoid selection had **34 passed, 1 warning**.
API transport, template selection and factory settings had **20, 5 and 4
passed**, respectively. Frontend TypeScript and the production Vite build
passed after the final UI change.
The exact JUnit cases are preserved in
`docs/evidence/physical-truth/pytest-final.xml` with only the local machine
hostname redacted.
The skipped test is the Linux syscall sandbox check in
`tests/test_import_physics.py`; this Windows host cannot exercise that kernel
boundary.

An earlier full run that overlapped three heavy browser jobs ended at
**362 passed, 1 skipped, 2 timeout failures** in 45m40s. Those two tests passed
in 45.92s when rerun alone, and the uncontended full rerun passed. The first
browser run had three failures while that same load and Vite artifact reloads
were present. It is not acceptance evidence. Production-binary contact checks
then passed **8/8**. After SQLite batching, focused live/host/pickup tests
passed **21/21**; the final full suite includes the subsequent first-motion
regression. The final serial compiled-model browser journey passed **3/3**
in 1m30s. The browser run persisted six real trials: G1 nominal and resumed
trials succeeded, 2.0 kg G1 failed on prohibited contact; H1 nominal succeeded;
Apollo nominal succeeded and 16 N·m/rad resistance failed to actuate. Backend
compute times for the latter six were 12.97, 4.14, 2.82, 1.15, 1.36 and
6.42s in run order. Browser captures are preserved in
`docs/evidence/physical-truth/`: G1 desktop/mobile replay plus measured H1
and Apollo views. `docs/evidence/physical-truth/trial-summary.json` is a
field-limited export of the six persisted trial records. Full frames remain
in the local SQLite artifact and are available through the replay endpoint.
`docs/evidence/physical-truth/g1-nominal-replay.json.gz` preserves the exact
3,448,471-byte JSON downloaded by Playwright, with 161 measured frames and
SHA-256 `098ebf8dabfea0d391eb90eaf061a6c4fbfbb94ca571f909a48965f7798eb54d`
after decompression. It is evidence of the bounded fixture pickup only.
The production build and live browser journey passed after the final changes.
The browser journey verifies measured frame delivery, replay controls and JSON
export, and the captured robot poses were inspected visually. There is not yet
an automated canvas-to-simulator transform-registration test across every
scene and camera.
This branch has not been deployed.
