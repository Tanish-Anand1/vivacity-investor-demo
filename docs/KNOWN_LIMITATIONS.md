# Known limitations and unfinished work

1. **Only one of seven V-Robotics programs is executable.** The six remaining entries have no task-specific model/controller/environment acceptance test and are visibly `not_implemented`. Existing robot or humanoid assets elsewhere in the repository do not change this status.
2. **The UR5e hand is a modeled Panda parallel-jaw flange.** It is a useful physical simulation fixture, not a manufacturer-approved tool mount, calibrated gripper or validated payload rating.
3. **Assembly is passive fixture seating.** There is no tight-tolerance insertion, force-guided assembly, fastening, tactile sensing, grasp synthesis across arbitrary part geometry, or real hardware validation.
4. **The accessible parameter range exceeds the proven-success envelope.** A user can request 0.30 kg and low friction/low force; the simulator may genuinely fail. The UI and API retain failed branch evidence.
5. **The solver is deterministic only within controlled local conditions.** Saved integration state, model hash, seed and version support local replay. Bitwise identity across MuJoCo versions, CPU types, operating systems, GPUs or altered solver settings is not promised.
6. **Sensor outputs have actuator-dependent units.** `actuatorfrc` peak scalars are measured per actuator. The gripper scalar is not physically comparable to a joint torque without interpreting its transmission. No mechanical work or energy total is claimed.
7. **The receiving fixture is an addition to the existing desktop world.** A dedicated `precision_assembly_cell` library entry and purpose-built industrial scene are not yet available. The current desktop ID is reported honestly by the API.
8. **Search is bounded and heuristic.** DLS IK and joint-space RRT may miss a feasible trajectory. Candidate success is measured by dynamics; no global optimality or fixed 5,000-rollout guarantee is claimed.
9. **No humanoid balance or locomotion.** Rendering a humanoid asset would not create an executable humanoid experiment. No such UI action is enabled.
10. **Deployment is a separate verification boundary.** Local tests and local browser checks do not prove that a production backend has these changes or that production compute will stay awake. Record live release verification before claiming availability at a public URL.

The next engineering milestone is a purpose-built heavy-payload model and force-limited transfer controller with one passing and one failing physical experiment. The existing stage should first pass its browser E2E and release checks. The full seven-program specification remains open.
