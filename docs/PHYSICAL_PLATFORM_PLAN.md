# Physical experimentation platform implementation plan

2026-10-13. Preserve the deployed React/Three.js/FastAPI runtime.

## Audit and decision

Verified in source and the deployed workspace: seven native robot models,
independent MuJoCo state branches, bounded parallel execution, contact-driven
pickup, live state rendering, capability ownership, replay/export, and saved
configurations. OpenAI interpretation already precedes World Labs generation;
these are not disconnected providers. Two curated colored environments exist.
Other worlds are explicitly simplified collision fixtures. Imported room meshes
use conservative proxies; they are not reconstructed collision twins.

Missing: configurable gravity/air, a physical material registry, measured
engineering overlays, and an analytical benchmark report. The current workspace
is usable but gives its results panel more emphasis than investigation tools.

MuJoCo remains the primary engine. Isaac would add a large GPU deployment and a
second state contract without resolving these immediate gaps. No engine switch.

## Outcome and acceptance

An investor can load the existing industrial world, select verified hardware,
configure physical conditions, execute actual contact-driven trials, inspect
measured interactions, compare saved runs and download reproducible evidence.
Reload must stay idle. Normal view remains free of technical overlays.

## Ordered implementation

1. P0: versioned bounded physics settings and eight material presets; apply them
   to compiled MJCF before hashing. Preserve integration state and immutable
   geometry caching. Use native MuJoCo fluid forces, not frontend animation.
2. P0: reproducible analytical/controlled validation cases, actual numerical
   errors, solver/version provenance and an ownership-protected report endpoint.
3. P1: Explore/Generate/Import library navigation with actual existing previews,
   readiness and Enter workspace; expose real generation stages/specification.
4. P2/P3: measured object/joint/contact state, optional force/velocity/COM overlays,
   contextual inspection panel, camera presets and compact time/status controls.
5. P4: preserve existing comparison/history/export; include physical conditions
   in saved configurations and replay; document every unsupported phenomenon.
6. Verify schema bounds, deterministic forces/state, native execution, benchmarks,
   frontend types/tests, live browser controls, repeated world switches and errors.
   Ship only after relevant checks; verify the public deployment separately.

## Limits and risks

Material values are explicit illustrative presets, not calibrated measurements.
MuJoCo Coulomb contact does not expose separate static/dynamic coefficients;
contact damping is not an exact restitution coefficient. Its ellipsoid fluid
model is a simplified aerodynamic approximation, not CFD or buoyancy.
No vacuum/adaptive/three-finger controller, conveyor simulation, new unverified
robot assets, real-world calibration or motor electrical energy will be claimed.
Render Free still imposes eight trials, idle sleep and ephemeral storage.

## Visual direction

An industrial instrument: charcoal surfaces, existing restrained pale-teal
accent, precise tabular measurements, generous immersive view, contextual tools.
Avoid generic dashboard cards and decorative glowing/gradient interfaces.
Preserve existing typography, detailed meshes and owned Spark lifecycle.
