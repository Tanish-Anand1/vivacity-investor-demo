# Tabletop object manipulation and adaptive search

The Object Pickup viewport contains the measured Panda, dynamic object,
table and configured physical obstacle. Labels, sensor readings, path lines,
targets and camera controls have been removed from inside the 3D scene.
The measured sensor summary appears in the results column. Camera keyboard
controls remain available: arrows to orbit, plus/minus to zoom, R to reset.

Dragging covers the actual beige table: X -0.30..1.10 m, Y -0.65..0.65 m.
Object centers are inset by the object's half-width/depth plus 1 mm so the
complete object stays on the table. If a drag overlaps the placement point,
the placement point is moved 18 cm sideways within the table to preserve a
meaningful transport task. Applying changes increments the world revision;
previous results become stale. No experiment starts on page load.

Change conditions exposes independent width/depth/height (40..60 mm), mass
(20..150 g), weight derived using 9.81 m/s², and sliding friction (0.05..1.5).
These values set the MuJoCo box geometry, body mass and contact friction.
The object's contact priority ensures its friction setting is actually used
against the table and fingers instead of being masked by maximum mixing.
The range reflects the current Panda gripper/controller; arbitrary shapes,
materials and dimensions are not supported.

The simulator's overhead semantic-depth sensor casts 22,701 actual MuJoCo
rays across the whole tabletop. Visible object hit coordinates provide its
estimated XY. Simulator geom IDs supply synthetic class labels. This is not
RGB vision or real-world camera perception. The true XY is used only to
measure localization error, not to set the planner's target.

## Planner and measured stopping

The backend tries eight yaw/lift templates, damped least-squares pose IK
with seeded retry configurations, and joint-space RRT for blocked segments.
Every accepted RRT edge is checked against MuJoCo robot collision geometry.
Carried-object collisions are measured in physics execution; geometric
screening does not certify their absence over every routed transport path.
Native physics trials and fresh authoritative execution share the same
routed stage-command interpolation. Physics contacts, bilateral finger
forces, lift/retention, release, table support and final placement error
determine success. A planning check does not establish grasp success.

The UI requests `adaptive_trials: true`, `physics_trials: 0`, a 256-command
screening catalog and a host-dependent physical compute budget (at most 12
in the client). It no longer requests an exact trial count. After at least
five attempted candidates, three attempts without a material improvement
in successful measured duration stop the search; material means 1% or
50 ms, whichever is larger. The fastest successful candidate remains the
selection even when a smaller gain does not reset the stopping patience.
Other stop reasons are exhausted feasible candidates or the host compute
budget. Search metrics disclose actual attempts, integrated trials, steps,
feasible outcomes and `stopping_reason`.

```json
{
  "adaptive_trials": true,
  "physics_trials": 0,
  "search_candidates": 256,
  "physics_budget": 8,
  "max_simulation_seconds": 40,
  "execute_selected": true
}
```

Submit this to `POST /v1/worlds/{id}/experiments`; the session API accepts
the same adaptive flag and forwards it. `physics_budget` must not exceed
the host's advertised `max_physics_trials`. Fixed-count trial requests are
retained for audit compatibility. Session leases, cancellation, pause and
simulator timeouts continue to apply.

This is a bounded search for the best measured feasible candidate, not a
proof of a global optimum. Placement anywhere on the table does not imply
that a fixed Panda can reach it: positions inside the mount, outside its
reach, or blocked by collision geometry can be physically impossible.
Such cases retain genuine planning/physics failures and no selected winner.

## Executed checks

Before release, local tabletop/property integration checks confirmed a
dragged estimate at `[1.017,0.381]` m and the opposite edge at
`[-0.099,-0.617]` m. A UI edit rebuilt the actual MuJoCo box with half-sizes
`[0.022,0.028,0.026]` m, mass `0.10` kg and friction `0.65`. The clean
viewport was inspected in the browser. The focused perception/pickup tests
passed 26 checks; later routing, actual contact-friction and adaptive checks
passed five checks. Full Docker and public release results are recorded in
`docs/HOSTING_STATUS.md`. The public run stopped at five integrated trials,
retained two feasible outcomes and genuine failures, then completed a separate
authoritative pickup at 8.5 mm error with zero prohibited contacts. All 155
Docker tests and the separate 512 MB host test passed. The final release also
keeps loading/error messages outside the viewport. Public proof artifacts are
listed in the hosting status.
