# Controller design

The executable precision-assembly controller is a bounded staged manipulator controller, not a learned policy. `vivacity/pick_place.py` computes eight tool stages: approach, descend, close, lift, transport, lower, release and retract. MuJoCo starts from the same full saved state for each candidate.

For each target pose, damped least-squares IK searches a valid joint goal. Joint interpolation is checked against contact geometry; when the direct path is obstructed, a seeded joint-space RRT search is attempted. Candidate yaw and lift height vary with the world seed. Position actuators then drive the six arm joints while the gripper actuator opens/closes. Physics steps, not keyframe animation, determine workpiece motion, grip retention, collisions and final pose.

The assembly settings change the actual candidate actions and measured pass condition:

| Control | Meaning | Bound |
| --- | --- | --- |
| `arm_speed_rad_s` | Nominal joint-motion speed for planned stages | 0.12–0.50 rad/s |
| `grasp_yaw_rad` | Base tool yaw for candidate grasp orientations | −π–π rad |
| `placement_tolerance_m` | Maximum evaluated final Cartesian error | 0.001–0.020 m |
| `orientation_tolerance_rad` | Maximum evaluated final workpiece angular error | 0.01–0.40 rad |
| `object_mass_kg` | Workpiece inertial mass | 0.02–0.30 kg |
| `physics.gripper_force_scale` | Scale applied to the modeled gripper effort | 0.05–1.0 |

The runtime distinguishes planning rejection, physical contact/grasp failure, dropped object, joint-limit/controller failure, timeout and operation-goal failure. A candidate is never promoted from a planning result to a completed task without stepping the corresponding MuJoCo branch. Physics execution samples the assembly's `actuatorfrc` outputs every step and records the maximum absolute scalar per actuator. Contact and final-pose checks determine success.

This implementation does **not** provide joint-space velocity control as a user mode, general torque control, real force feedback, adaptive grasp learning, high-speed interception, balance or locomotion. No humanoid controller is marked executable. The adapter boundary remains separate from the common runtime; new embodiments need their own tested controller before catalog status can change.
