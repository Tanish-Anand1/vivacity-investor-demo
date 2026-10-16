# World and robotic experiment workspace

Outcome: describe, select or import a world; configure supported hardware and
operations; save a repeatable experiment; inspect actual measured results.

Preserve the existing Panda/cloth adapters, snapshot/fork contract, background
simulation worker, live WebSockets, pause/resume, drag controls and legacy imports.
Do not substitute generated geometry or language-model text for physics results.

1. Extend `vivacity/schemas.py` and workcell scene construction with bounded
   static collision primitives and explicit environment provenance. Render those
   same geometries in `frontend/src/RobotView.tsx`.
2. Add a capability-owned SQLite world/configuration library, prebuilt scene
   definitions, robot/gripper/operation registry and validated resolver. Extend
   `vivacity/api.py`; keep native simulation behind the current Runtime.
3. Add server-only OpenAI structured interpretation and World Labs asynchronous
   generation adapters using official workflows. Persist status, handle restart,
   failures and rate limits. Keys remain backend-only. Missing credentials are
   a visible limitation, not a simulated successful generation.
4. Reuse the bounded import parser. Add explicit scene scale/placement and
   conservative collision-proxy mapping; distinguish original visual triangles
   from simplified collision geometry. Preserve MJCF/URDF native verification.
5. Add Worlds, Robots, Operations and saved Experiments surfaces around the
   existing workspace, using its typography, palette and controls. Configure
   compatible hardware, seeds and bounded trial settings before explicit Start.
6. Add measured comparison/reporting and provenance. Export OpenAPI and frontend
   types; run contract, isolation, provider-error, physics and browser journeys.
7. Commit only scoped changes. Deploy and verify the actual production domain
   once backend and frontend pass checks. Record actual evidence and gaps.

Current implementation: seven actual MuJoCo arm models, thirteen preset workcells,
ten bounded operations, owned world/configuration libraries, actual OpenAI
structured proposals and World Labs generation, explicit imports and collision
proxies, persisted measured reports, and frontend registry/library/setup flows.
Both credentials are configured server-side and excluded from published code.
Real World Labs retrieval, provider failure/retry, real physics in the generated
world, native pickup across all arms, and HTTP/WSS replay were executed. See
WORLD_WORKSPACE_HANDOFF.md and IMPLEMENTATION_STATUS.md for executed evidence
and precise scope/hosting limitations.
Acceptance: a prebuilt or mapped imported scene executes genuine MuJoCo trials;
saved configurations reproduce their seed/scene; provider responses are validated
and failures remain failures; library/config/history ownership is enforced;
loading stays idle; the live UI exposes supported combinations without dead ends.
Unimplemented robot controllers and advanced operations remain clearly unavailable.
