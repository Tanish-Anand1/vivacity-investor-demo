# Environment specifications

## Precision assembly cell

`precision_assembly` is the only executable V-Robotics environment. It uses the existing `desktop` workcell plus task-specific geometry assembled in `vivacity/scene.py`. The catalogue maps it to `environment_id: desktop`; `precision_assembly_cell` in the project brief describes the intended dedicated cell, which is not a separate world-library ID yet.

All positions are world-frame metres in a right-handed Z-up scene. The table top is `z = 0`. The default workpiece centre is `[0.5, -0.15, 0.026]`; the fixture centre is `[0.5, 0.18, 0.026]`. A 0.025 m half-size gives a nominal 0.05 m box. Four static tray rails surround the pickup, and four static rails bound the fixture pocket. The workpiece has a free joint and contact geometry. There is a ground plane below the table and a movable rectangular obstacle in the base workcell.

The receiving fixture is **passive**. Containment is checked from the MuJoCo-computed workpiece pose against the pocket geometry; settling, release, velocity, angular alignment, gripper contact, and forbidden contacts contribute to the measured outcome. This is a one-part placement/seat experiment. There is no peg insertion, fastening, adaptive force-guided fitting, or machine operation.

The visible source tray and destination fixture are real collision geoms in the same compiled model as the arm and object. Changing task configuration creates a new world revision and invalidates prior results. The raw model hash and world revision appear in the experiment report. Rendered frames use MuJoCo body and geom transforms; visual interpolation cannot change the evaluation.

The six other planned worlds have no V-Robotics environment implementation or task test. See [Robot model specifications](ROBOT_MODEL_SPECIFICATIONS.md) and [Validation matrix](VALIDATION_MATRIX.md). A pre-existing generic warehouse scene is not a substitute for any of them.
