# Evaluation

Robotics: damped least-squares pose IK, direct candidate and seeded collision-aware joint-space RRT alternatives. Collision checking includes obstacle, table, target, ground and non-excluded robot self contacts. All paths execute in independent MuJoCo states, including the diagnostic direct path if planning detects collision. Dynamic execution is monitored at each integration step; replay records sampled actual transforms and joints. Success requires no prohibited contact, no limit violation, finite stable controller state and final position/orientation tolerances.

Science: fit training observations only using solve_ivp and bounded least_squares. Evaluate held-out predictions and training BIC. Require improved predictive error and complexity support before choosing the extra mass. Report failed optimization, parameter bounds and Jacobian uncertainty explicitly. Recovery and false-positive tests cover both a nonzero and zero mass.
