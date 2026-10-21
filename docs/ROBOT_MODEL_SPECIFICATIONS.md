# Robot model specifications

## Executable embodiment: `precision_assembly`

| Field | Implemented value |
| --- | --- |
| Category / ID | Robotic arm / `ur5e` |
| Source | Vendored MuJoCo Menagerie `assets/menagerie/universal_robots_ur5e/ur5e.xml`; original model license at `assets/menagerie/universal_robots_ur5e/LICENSE` (BSD-3-Clause) |
| Structure | Six actuated arm joints with the source model's link geometry, inertia, collision and joint limits; two gripper fingers on a modeled flange |
| End effector | Adapted Panda parallel-jaw hand from `assets/menagerie/franka_emika_panda/`; model license is Apache-2.0. This fixture is **not** an approved UR hardware integration. |
| Actuation | Source model position actuators plus one parallel-jaw actuator. The physics result is measured after every 2 ms solver step. |
| Sensors | Simulator contact sensors for robot, fingers, table, object and obstacle; seven `actuatorfrc` scalar sensors for this program |
| Initial state | Source home keyframe plus open hand and free workpiece at the configured tray pose; full simulator integration state is snapshotted |
| Task | Pick one rigid part from a tray and release it into a passive fixture |
| Constraints | Valid joint limits, prohibited-contact checks, configured elapsed-time limit, stable grasp and retention, placement and orientation tolerances |
| Test suite | `tests/test_v_robotics.py`; `python -m scripts.verify_v_robotics`; Playwright browser test |

Mass and inertia come from the compiled MJCF. The workpiece is a free MuJoCo body, not parented to the gripper during transport. Its mass can be set from 0.02 to 0.30 kg for this operation. Its box half-size is 0.02–0.03 m on each axis. The program accepts arm speed 0.12–0.50 rad/s, yaw −π–π rad, placement tolerance 0.001–0.020 m, and orientation tolerance 0.01–0.40 rad. Server schemas enforce these ranges. The report records the selected model hash and actual solver settings rather than assuming values from product copy.

`actuatorfrc` is reported separately for each actuator. Its scalar units depend on the actuator transmission; the gripper output must not be added to joint torque. The current viewer does not visualize force vectors for the new assembly-specific sensor. The [MuJoCo sensor reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html#sensor-actuatorfrc) defines the sensor used here.

## Remaining requested programs

| Program | Proposed embodiment | Actual status |
| --- | --- | --- |
| `heavy_payload` | High-payload six-axis arm | `not_implemented`: no validated high-payload model/controller/payload transfer |
| `high_speed_sorting` | Delta or verified high-speed sorting arm | `not_implemented`: no moving interception and repeated bin placement. The existing factory carton cell is a separate workflow. |
| `collaborative_manipulation` | Lightweight articulated arm | `not_implemented`: no moving-obstacle/clearance benchmark or collaborative safety claim |
| `humanoid_maintenance` | Biped with balance and standing contact manipulation | `not_implemented` |
| `humanoid_terrain` | Biped with contact gait and fall detection | `not_implemented` |
| `humanoid_logistics` | Biped with walking plus grasp/transport/place | `not_implemented` |

The repository contains other arm and humanoid **assets**. Asset presence does not establish a tested V-Robotics controller, task, or result. The catalog refuses to open those six programs.
