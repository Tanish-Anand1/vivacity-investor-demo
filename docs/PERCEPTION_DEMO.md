# Simulated object localization in the Panda workcell

Verified locally on 2026-10-13 (Asia/Kolkata). The investor journey is: open
Object Pickup, drag the blue cube anywhere in the highlighted tabletop area,
inspect the overhead scan's detected XY and ray count, then click Start
experiments. Each changed position creates a new MuJoCo world revision and
invalidates older results. The arm plans toward the ray-estimated XY, then
executes independent physical pickup trials. The UI keeps the existing layout.

The allowed cube/placement centers are X `0.15..0.80` m and Y
`-0.45..0.45` m, with a minimum 0.10 m separation. This is a bounded
workcell, not arbitrary 3D placement or guaranteed reachability. An overhead
orthographic scan fires 8,181 MuJoCo rays across the area. Cube-labelled ray
hits determine estimated XY; the true body pose is used only to calculate
localization error. The 3D marker and readout show the estimate. An occluded
object yields `object_not_visible`, no estimated position, and a planning
failure with zero integrated steps. No true pose is used to plan when the
sensor cannot see the object.

Local checks:

- Moving the cube in the browser changed the ray estimate from
  `[0.503,-0.150]` m to `[0.747,0.220]` m; the page returned to Ready to
  start and logged no browser errors. Desktop and 390 px mobile layouts were
  inspected. Capture: `artifacts/perception-local-moved.png`.
- A direct MuJoCo pickup from `[0.20,0.40]` m achieved physical grasp and
  placement: `execution_success`, 10,570 integration steps, 2.1 mm final
  placement error. Separate runs from `[0.30,0.00]` and `[0.65,0.35]` m also
  succeeded with 11.2 mm and 2.3 mm final errors respectively.
- At `[0.74,-0.40]` m the sensor detected the cube, but IK failed. Detection
  alone does not imply reachable manipulation.

**Scope:** This is synthetic MuJoCo semantic-depth sensing. Geom IDs provide
perfect class labels. It is neither RGB object detection nor a real camera or
robot perception system. The fixed overhead projection estimates XY on the
table; cube height is known from workcell configuration and current MuJoCo
state. The current staged controller may fail on some visible poses or
obstacle layouts. Such outcomes remain failed branches, not fabricated picks.
The sensor runs for state reads and planning, not continuously during each
streamed integration frame. See `docs/API.md` for its response fields.

Public verification on 2026-10-13: `https://demo.tryvivacity.com/` connected
to the Render backend. A real browser drag moved the cube from estimated
`[0.503,-0.150]` m to `[0.152,-0.160]` m near the arm mount; 30 MuJoCo rays
hit the cube there. After choosing the reachable `[0.20,0.40]` m position,
the deployed browser showed `[0.203,0.400]` m from 25 hits and an explicit
Start submitted eight independent backend physics trials. All eight were
evaluated feasible. A separate authoritative execution achieved measured
grasp and placement with **2.0 mm final error, zero prohibited contacts**;
the UI recorded `Task verified` at 5:19 elapsed wall time. A subsequent
browser drag moved the estimate to `[0.428,-0.380]` m and the UI showed
`World changed · run again` while retaining the old result only as stale
history. No browser console errors were captured. Evidence:
`artifacts/perception-public-success.png` and
`artifacts/perception-public-stale.png`. The reachable sample does not prove
every visible tabletop point can be grasped; the earlier near-mount drag
verified detection and state rebuilding there, not a successful pickup.
