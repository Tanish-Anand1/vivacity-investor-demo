# Historical audit notice — superseded on 2026-10-22

The measurements below describe the **previous** 19-actuator Menagerie H1
open-loop gait probe and Apollo switch-only probe. They are preserved as
historical failure evidence. The current bounded tasks use a matched
10-leg-actuator Unitree H1 policy, an Apollo contact-gated machine cycle, and
live persisted frames. Current outcomes and limitations are in
[`IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md) and the current API
contract is in [`FRONTEND_HANDOFF.md`](../FRONTEND_HANDOFF.md).

---

# Humanoid capability audit — stationary G1 milestone

Date: 2026-10-22. Evidence is the checked-in MuJoCo Menagerie models, compiled
MuJoCo state, executed experiments, and `tests/test_humanoid_pickup.py`. This
is a **simulation** audit; none of these results validates physical hardware.

## Embodiments actually present

The imported robot assets are pinned in this repository. Their licenses are
included under `assets/menagerie/<model>/LICENSE` and with the frontend visual
exports. Counts below were read from compiled `MjModel` instances after adding
the Vivacity scenes. Total mass includes the robot body masses and the parcel
where one is present; it is not a manufacturer payload rating.

| Model | License | `nq` / `nv` / actuators | Limited joints | Bodies / geoms / sensors | Initial base Z | Manipulation and contact surface |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Unitree G1 with hands | BSD-style bundled license | 57 / 55 / 43 | 43 | 46 / 112 / 4 | 0.790 m | 14 actuated finger joints; bilateral hand collision geoms; left/right ankle-roll foot contact bodies |
| Apptronik Apollo | Apache 2.0 | 40 / 39 / 32 | 33 | 38 / 85 / 4 | 1.016 m | Collision hand plates but no independently actuated fingers; left/right foot bodies |
| Unitree H1 | BSD-style bundled license | 26 / 25 / 19 | 19 | 21 / 62 / 0 | 0.980 m | No actuated hand fingers or onboard sensors in this imported model; ankle contact bodies |

Each model has a floating root, hip/knee/ankle leg chains, torso and shoulder/
elbow arm chains, collision geoms, bounded joint ranges, a standing keyframe,
and body mass/inertia parameters in MJCF. G1's four sensors are torso and
pelvis angular velocity and linear acceleration; Apollo has four IMU channels;
H1 has no sensor channels in this import. The current controller reads MuJoCo's
privileged object/body state and contact forces. **It does not use a camera,
object detector, or onboard state estimator.** The G1 task state monitor
uses base height/orientation, joint positions, solved hand contact forces,
parcel pose/velocity, support contacts, and prohibited contacts.

G1 is the flagship because it is the only integrated model with actuated
fingers and the initial bimanual contact probe already reached a parcel. The
local [Menagerie G1 model documentation](https://github.com/google-deepmind/mujoco_menagerie/tree/main/unitree_g1)
describes a simplified simulation model and standing keyframe. Apollo's
existing hand-plate switch actuation remains valid for that narrow task. The
H1 gait probe falls; it is not a walking policy.

## Controller compatibility decision

- [HugWBC](https://github.com/InternRobotics/HugWBC) publishes a whole-body
  research/training stack built around Isaac Gym/CUDA and H1-style policy
  embodiments. No model-matched, tested G1 policy is present here.
- [OpenHLM](https://github.com/OpenHLM-project/OpenHLM) offers G1 whole-body
  research code, but its policy/server path depends on heavyweight model
  checkpoints, TensorRT/GPU runtime, and retargeting assumptions that are not
  satisfied by this CPU-hosted Menagerie scene.
- [ULTRA](https://github.com/Sirui-Xu/ULTRA) uses an Isaac Gym training and
  sim-to-sim workflow; its released code does not supply a validated policy
  for this exact asset and warehouse task. The recent
  [Workhorse paper](https://arxiv.org/abs/2610.09117) has not released a
  controller that can be run here.

No external learned policy was imported. The implemented first milestone uses
damped least-squares bilateral hand IK, MuJoCo joint position actuators, and a
finite-state controller with measured transition conditions. It is a bounded
stationary manipulation controller, **not** dynamic whole-body control or
locomotion. Leg/torso position actuators hold the standing keyframe while base
height/tilt and collisions are checked. A model-matched walking policy or
whole-body force controller, validated retargeting and foot-contact tests, and
substantially more compute are required before walking/carrying can be called
operational.

## Physical pickup contract

One G1 stands beside a source table and a separate destination support stand.
A free parcel starts on the source. The controller reads its actual simulated
pose, computes left and right hand IK targets, then executes position commands
through the model's actuators. It does not set the robot root pose or parcel
pose during the trial.

The imported hands cannot retain this carton through a reliable pure-friction
pinch. The task model therefore contains a **disabled MuJoCo weld** between
the right wrist and parcel. It activates only after both hand sides show
normal contact forces of at least 2 N for ten consecutive 0.002-second steps.
At that instant, the weld's rest translation and quaternion are set to the
measured relative transforms. The baseline activation produced **0.0 m pose
jump**. The weld stays active during lift/transfer/lowering and is explicitly
deactivated before final support and velocity are evaluated. This is a
contact-triggered rigid-grasp approximation, not dexterous grasp physics.

The controller progresses through approach, lift, transfer, lower, settle,
release. Each transition requires the previous phase's measured condition
(bilateral forces, lifted height, transfer proximity, lowering height,
pre-release destination proximity). Durations only bound actuator ramps and
timeouts. Failure is recorded if contact, lift, stance, collision, joint
limit, release, or final stable support checks fail. Destination error and
support are read from MuJoCo state. Every job deep-copies the compiled model,
so changing the weld rest pose does not mutate other jobs; full integration
state and sampled body transforms are stored for replay.

API: `POST /v1/robotics/humanoids/experiments` with `action: "pickup_place"`,
`robot_id: "unitree_g1"`. `parcel_mass_kg`, `floor_friction`,
`parcel_xy_m`, and `destination_xy_m` alter real model or initial state.
Invalid robot/position configurations return HTTP 422. A valid but physically
infeasible configuration completes with `task_success: false` and a specific
`failure_reason`. Jobs use the existing owner-scoped SQLite trial store and
`GET .../{id}/replay` endpoint. The browser uses the exact exported scene
geometry and recorded body transforms.

## Validation matrix

`PASS` means the stated **bounded simulation** case passed a test; it says
nothing about hardware or general reliability.

| Capability | Status | Evidence / boundary |
| --- | --- | --- |
| G1 MJCF load, articulation, sensors, keyframe | PASS | `tests/test_humanoids.py`; compiled model counts above |
| G1 stationary bilateral contact and joint control | PASS | `test_g1_contact_gated_grasp_lift_place_release_and_replay` |
| Contact-gated rigid-grasp pickup, lift, place, release | PASS | Default 0.5 kg episode, 4,000 MuJoCo steps, 0.946 m peak parcel Z, final destination support, weld inactive at end |
| Initial and final integration state, replay determinism, branch isolation | PASS | Two fixed-configuration runs had identical frames/states; cached parent weld state unchanged |
| Valid failure: absent grasp and unreachable parcel | PASS | Motion scale 0: no bilateral grasp; x=0.95 m: IK rejects before physics execution |
| Mass and destination variation | PASS | 0.2 kg and 1.2 kg placed; changed destination produced a different measured parcel pose |
| Heavy parcel 2.0 kg | FAIL | Prohibited robot/fixture contact observed; task recorded failure, not completion |
| G1 walking and carrying | BLOCKED | No validated footstep/whole-body locomotion controller for this exact model/world |
| Shared-world Panda-to-G1 handoff | BLOCKED | Standalone G1 task has a separate `MjModel` and parcel, not the same sorted item's state |
| Packing, closing, sealing, labeling, dispatch | BLOCKED | Depends on shared-world transfer, task-specific fixtures/controllers and measured stage gates |
| G1 running | BLOCKED | No validated running gait/policy; cannot infer from standing manipulation |
| Apollo switch actuation | PASS | Existing nominal contact-and-hinge test, separate from pickup |
| H1 terrain traversal | FAIL | Existing controller probe falls in its tested terrain trial |
| Onboard perception / hardware transfer | NOT TESTED | Object pose is privileged MuJoCo state; no camera estimator or hardware control |
| Local desktop and narrow-screen browser pickup journey | PASS | Playwright on both Vite development and production-preview builds submitted physics jobs, inspected success/failure, replayed, exported a measured JSON record, and found no page exception or horizontal overflow |
| Public deployment | PASS for the bounded G1 task and robot probes | The public domain submitted real jobs, returned persisted replay frames, and passed the browser pickup journey on 2026-10-22; production limits are below |

The full local backend suite on 2026-10-22 passed **336 tests, with 1 skip**
and one upstream Starlette/httpx deprecation warning. After the final
controller cleanup, the focused humanoid suite passed **13/13**. Frontend
API-transport checks passed **20/20**, the production build passed, and the
production-preview Playwright pickup journey passed **1/1**. The baseline pickup measured
4,000 steps / 8.0 s simulated time, 3.47 s physics compute on the local
machine, minimum base Z 0.790 m, maximum tilt 0.056 rad, final parcel
`[0.584, -0.394, 0.690]` m, and destination-center error 0.108 m. These are
single-trial observations, not benchmark reliability or calibrated warehouse
metrics. Some parcel placements within the exposed range may fail, and that
failure is shown. A separate fixed-seed, held-out variation run over 12
bounded configurations produced **11 successes and 1 measured no-grasp
failure**. The observed fraction was 11/12; the exact 95% binomial interval
is **[0.615, 0.998]**. That wide interval and the narrow sampled domain do
not justify a general reliability claim. The configurations and per-trial
outcomes are in `artifacts/humanoid-pickup-variation.json`. Browser
captures from the local run are `artifacts/humanoid-pickup-replay-desktop.png`
and `artifacts/humanoid-pickup-replay-mobile.png`.

## Public release verification — 2026-10-22

The Vercel frontend is live at `https://demo.tryvivacity.com/works` and proxies
the Render runtime through `/runtime`. Render reports backend commit `017e6d3`
live. The production image precompiles the original Menagerie scenes with
MuJoCo 3.15.0 during its Docker build and loads independent `.mjb` models for
each request. The G1 binary retains the full collision and visual model.
Apollo's server binary uses MuJoCo `discardvisual` to omit visual-only meshes;
the browser retains the original full-resolution mesh bundle. A paired local
trial confirmed identical Apollo joint frames, switch contact count, and
successful switch actuation with and without visual-only meshes. The frontend
model hash still describes the same source MJCF, assets, parameters, and
MuJoCo version.

| Live case | Measured outcome |
| --- | --- |
| G1 0.5 kg pickup on final backend revision | Success; 4,000 physics steps, 161 replay frames, 25.61 s backend compute, 0.1217 m destination-center error, stable destination support, exact replay-frame equality |
| G1 2.0 kg pickup on preceding binary-loader revision | Honest `prohibited_robot_contact` failure; 1,888 steps, 77 replay frames, no destination support, exact replay-frame equality |
| G1 2-second reach probe | `parcel_not_transported`; 1,000 steps, 129 hand/parcel contact samples, 41 replay frames |
| Apollo 2-second switch probe | Success; 400 steps, two hand/handle contact samples, 41 replay frames |
| H1 2-second terrain probe | Honest `fall`; 1,000 steps, 3,470 foot/terrain contact points across steps, 41 replay frames |

The live Playwright pickup journey passed **1/1** on the public domain. It
submitted the default and heavy-parcel jobs, inspected their opposite
outcomes, scrubbed replay, exported the measured JSON, checked the narrow
layout, and recorded no page exception. Two public opening tests passed:
the actual encoded 7.5-second film handed off to the homepage without
starting physics, and refresh replayed the opening after a skip. The API
summary is `artifacts/humanoid-live-final.json`; the success/failure pair is
`artifacts/humanoid-live-verification.json`. Production browser captures are
`artifacts/humanoid-pickup-live-desktop.png` and
`artifacts/humanoid-pickup-live-mobile.png`.

Both final Linux Docker-image CI runs passed: the
[private runtime run](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/39788360536)
and the
[public source run](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/39788391967).
In each run, the three full-suite shards reported **154 + 115 + 70 = 339 passed,
3 skipped**. The separate free-host memory check passed **4/4** in each run.
The logs report one upstream warning per shard; no tests failed.

The host remains **Render Free** (512 MB memory, shared 0.15 CPU). It can sleep
after inactivity, delay the first request, and lose ephemeral SQLite data
across restarts or redeploys. No always-on or durable-history claim is made.
The local Windows process measured approximately 755 MB after XML compilation
versus 229 MB after loading the exact G1 binary. Render Free does not expose
application memory metrics, so those are local measurements, not production
RSS. The production Docker build outputs 114.3 MiB for G1, 0.1 MiB for the
headless Apollo physics model, and 49.2 MiB for H1.
