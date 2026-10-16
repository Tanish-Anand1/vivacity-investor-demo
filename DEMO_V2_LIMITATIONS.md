# Vivacity V2 limitations

## Implemented and verified at the adapter boundary

Shared persistent runtime operations, independent full-state branches, real MuJoCo reaching/cloth integration, real SciPy training/held-out inference, honest failure handling, revision invalidation, measured replay, deterministic policy, bounded background jobs, REST/WebSockets, search counters, ranked actual successes and versioned branch exports. Static supported GLB/glTF imports are decoded/previewed; safe description/bundle staging persists validation records. See the final test report for the exact UI/deployment checks completed.

## Partial functionality

- **Object Pickup is reach-only.** The Panda reaches a pre-grasp pose. The cube is a fixed target. No frictional grasp, lift, placement, movable-cube dynamics or grasp contact validation exists. The UI says so.
- **Cloth is a constrained single-fold fixture.** A 7 × 7 inextensible flex mesh uses a fixed hinge/opposite edge and seven pre-attached ideal pre-attached clamp constraints. The fixture stem/bar collision masks are disabled; robot-link contacts and cloth penetration are evaluated. A real actuated Panda carries a fixed folding bar, releases the cloth and retracts. It has actual deformation and settling, but no grasp acquisition, calibrated textile bending/stretch model, dual-arm manipulation or general folding policy. Coverage is a measured vertex fraction, not area overlap. Valid constraints do not prove a frictional robot grasp.
- **Science uses simplified 2D physics in a 3D viewer.** Initial conditions and stationary perturber location are known; mass/central strength are fitted. Synthetic noise, local covariance, held-out predictions and model complexity are measured. The demo neither infers an arbitrary planet orbit nor discovers a new physical law. Mass may be unidentifiable at adverse noise/horizon settings; the simpler model can win.
- **Import Tier 1 is static supported triangle preview.** Materials, textures, animation, skinning, compression extensions, sparse/normalized geometry and unsupported primitive types are not imported. External resources are prohibited; embed buffers or use a manifest ZIP.
- **Import Tier 2 is staging only.** MJCF/URDF is structurally inspected without native compilation. Arbitrary imported assets cannot be run. OS-isolated native workers, complete inertia/collision/controller validation, conversion and task criteria remain necessary. This gap is visible, and `physics_ready` stays false.
- Search screens 5,000 distinct variants but integrates only the reported shortlist. Screening is cheaper and incomplete. No continuous collision-safety proof or global planner optimality is claimed. Robot path length is sampled joint-space displacement, not energy.

## Not implemented or not verified

Authentication/authorization or private multi-user worlds; durable independent cloud hosting; distributed workers/restart continuation; GPU/renderer compatibility across devices; presentation-machine latency guarantees; arbitrary uploaded-robot execution; autonomous grasping/placement/general cloth folding; real observation ingestion; hosted LLM calls in this verification; full screen-reader usability review. A passing axe scan is not proof of universal accessibility. Jobs are one-process CPU work, not horizontally scalable infrastructure.

## Operational risks

The public demo API is unauthenticated and intended for a controlled presentation. CORS is an explicit browser allowlist, not authentication. A bounded queue protects simulation concurrency but is not a complete abuse-control system. Do not expose secrets or private scenes. SQLite/import files persist locally; quota cleanup requires an administrator. Simultaneous browser/software-rendering and scientific work changes measured latency. Larger Three.js assets can be slow on constrained networks or software GPUs. Framework deprecation/build warnings are recorded, not hidden.

Vercel serves the frontend independently, but a Cloudflare quick tunnel to this computer is temporary. It stops working when its process, API, network or computer stops, and its URL can change on restart. Railway provisioning was previously blocked by an expired trial; no paid infrastructure was purchased. A durable deployment requires a provisioned Python host, persistent volume/backups, access controls, observability and capacity testing. Do not describe the temporary demonstration as a durable production system.
