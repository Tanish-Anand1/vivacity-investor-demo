# Factory measurements, version 1

All records use SI units and MuJoCo 3.15.0. Robot positions, velocities, joint
accelerations and actuator joint torques come from `qpos`, `qvel`, `qacc`, and
`qfrc_actuator`. Carton mass, principal inertia and three friction coefficients
come from the compiled model, never from appearance. Free-carton translational
`qacc` is its centre acceleration in world coordinates (centred box inertia).

`state_time_s` is the integrated pose time. `dynamics_time_s` is the most recent
force-solution time, normally one 0.002 s step earlier. Camera snapshots recompute
the force solution at their captured pose. Each contact includes its location,
normal force and contact-frame force rotated into world axes, acting on geom 2.
Forces are MuJoCo soft-contact estimates, not physical sensor measurements.

- Mechanical actuator power: sum of `actuator_force * actuator_velocity` (W).
- Net mechanical work: sum of power × integration timestep (J), including negative work.
- Positive actuator work: sum of each actuator's max(power, 0) × timestep (J).
- Robot work/power: the seven Panda servos plus its finger actuator.
- Carton kinetic energy: ½ m |v|² + ½ ωᵀ I_world ω (J).
- Carton gravitational potential: −m g·(centre − [0,0,−0.8]) (J).

Work uses a left-rectangle integration at every physics step, not just displayed
frames. The accumulated ledger travels with snapshots and forks. No efficiency,
regeneration or drive-electronics model is assumed; electrical energy is null.
Ground-truth pose refresh is independent of display cadence. Contact peaks can
be missed by displayed samples; stored work still includes every integration step.

Sources: [MuJoCo computation](https://mujoco.readthedocs.io/en/stable/computation/index.html),
[API types and units](https://mujoco.readthedocs.io/en/stable/APIreference/APItypes.html),
[Python state access](https://mujoco.readthedocs.io/en/stable/python.html).
