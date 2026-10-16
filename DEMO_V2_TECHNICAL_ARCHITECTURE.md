# Vivacity V2 technical architecture

The product uses the existing Python 3.12 / FastAPI / SQLite runtime and React / TypeScript / Vite / Three.js frontend. API schemas remain version 1.0; branch downloads use `vivacity.branch/1.0`, imports `vivacity.import/1.0`. Locked library versions and simulator provenance are preserved.

## Shared execution boundary

`vivacity/runtime.py` owns creation, observation, snapshots, independent forks, actions, background simulation, measured evaluation, commit, reset and replay. Simulator-specific state is owned by each adapter. Worlds, experiment settings, immutable parent snapshots, branches, revisions, evaluations and sequenced events persist in SQLite WAL. One simulation worker and eight reservations bound job concurrency. Restarted unfinished jobs are explicitly failed, rather than silently resumed. Commit checks world/experiment/branch ownership, revision, completion and actual success. Environment updates rebuild initial/current state and invalidate old results.

| Adapter | Source of state and results | Scope |
| --- | --- | --- |
| `robotics.py`, backend `mujoco` | Menagerie Panda, MuJoCo integration, contacts, DLS IK and joint-space RRT | Fixed cube/obstacle, collision-free pre-grasp reaching |
| `cloth.py`, backend `cloth` | MuJoCo triangulated flex vertices, equality/clamp state, actual integration | Actuated Panda single fold, fixed hinge/opposite edge, pre-attached folding bar, release/retract/settle |
| `science.py`, backend `scipy` | `solve_ivp`, training-only `least_squares`, held-out residuals/BIC/local uncertainty | Simplified 2D central dynamics with an optional stationary perturber at a known location |

Both MuJoCo adapters serialize `mjSTATE_INTEGRATION`, version, seed, configuration and model hash. This includes controls, warm-start integration information, mocap data and active equality state. Each branch constructs independent `MjModel`/`MjData`. JSON snapshots are not native MJB files. Scientific state contains observations and fitted-model state; hidden generation parameters are removed before the fitting policy can inspect it. No snapshot format is forced onto the other adapter.

## Search and evidence

Robotics V2 requests 5,000 seeded, continuously varied joint paths. Interior waypoint hashes establish actual distinct count. Cheap joint bounds and selected actual MuJoCo FK/contact checks screen these variants; they do not certify the whole path. A diagnostic direct path and a bounded shortlist receive real dynamic integration. Default UI budget is 12 validation episodes. Failed planning with zero integration steps is counted separately from executed rollouts. Successful branches rank by measured executed duration, sampled joint-path length, goal error and candidate index.

New cloth worlds default to `robot_model: "panda"`. The Menagerie arm has seven joint position actuators and gravity compensation. Its fixed folding bar carries seven pre-attached equality constraints; there is no mocap body. DLS pose IK produces 71 joint waypoints for carrying and retracting. During execution only actuator targets and release flags are commanded, never qpos or cloth vertices. Immutable equality anchors are calibrated once at initialization and reproduced on fork. `legacy_cloth.py` preserves old configurations and hashes; the UI starts a fresh arm world when a locally remembered cloth world lacks `robot_model`.

Cloth requests 5,000 distinct clamp height/duration/lateral-offset parameter sets, screens geometric bounds and integrates eight shortlisted episodes by default. Evaluation measures edge alignment RMSE, fraction of moved vertices inside the destination footprint below a height threshold, clamp-constraint residual, excessive penetration, numerical stability and timeout. **Vertex coverage is not area overlap; constraint validity is not autonomous grasp acquisition.** Ranking uses success, alignment, coverage and measured duration. Cloth vertices are never prescribed as animation coordinates.

Scientific hypotheses fit only training observations. The baseline and extra-influence predictions are computed for all observation times; held-out measurements, complexity improvement and identifiability criteria govern selection. Uncertainty is a local least-squares approximation with reported caveats. An optional LLM policy adapter is separated from simulator results; no configured key is required, and deterministic messages are labeled accordingly.

Counters/events are computed from work actually performed. `generated`, `distinct_generated`, `screened`, `rejected`, `fully_simulated`, `physics_attempts`, `planning_failed` and `verified_feasible` have distinct meanings. `fully_simulated` counts completed measured physics-validation episodes with positive step/integration counts, including episodes terminated by a measured failure; it does not mean 5,000 complete successes. API metrics include initialization, planning, integration, queue/job wall time, process CPU time, step counts, replay bytes and adapter errors.

## Frontend and renderer contract

`frontend/src/useRuntime.ts` handles lab-specific persisted IDs, mutation locks, idempotent submission/retry, jobs, WebSocket sequence reconnection and REST history/poll recovery. React lab switching is guarded against stale adapter responses. Progress uses measured event envelopes; complete branch/replay payloads are downloaded at terminal completion, not repeatedly for each branch event. The UI explicitly waits for recorded evidence before enabling new mutations. Terminal WebSocket closure does not trigger an endless reconnect loop. One `TechnicalInspector.tsx` shows a bounded 160-row measured event buffer, preserves scroll position when inspecting older rows and provides persisted failure/history access. The complete event record remains on the server.

`RobotView.tsx` uses the compiled geometry assets in `frontend/public/vivacity`: `robot-geometry.json` and `robot-meshes.bin`. Body transforms and quaternions come from recorded MuJoCo frames; MuJoCo WXYZ is converted to Three.js XYZW. Robot/cloth/science use Z-up. Science remains `[x,y,0]` even in its orbitable 3D viewer. Cloth uses 49 measured vertices, compiled triangle indices and actual Panda body poses. New sheets are centered at world `[0.5,0,0.012]` meters; the bar is fixed at hand-local `[0,0,0.18]`. Its measured quaternion rotates both bar and fixture stem. The arm uses the same Menagerie geometry asset cache as the reaching workcell. Imported glTF preserves its Y-up convention and applies uploaded node transforms before previewing. Camera centering/zoom and motion interpolation are display operations, never additional simulation.

`usePlayback.ts` automatically selects/loops a successful current result using recorded timestamps. Interaction pauses motion. Reduced motion disables autoplay. Failed/stale results do not autoplay. Each top-three card downloads its own complete actual branch action, parent/final state, frames, evaluation, hash/seed/timestamps and metrics. Fewer than three successes remain fewer than three cards.

## Import boundary

`vivacity/imports.py` decodes static GLB/glTF triangle data into a trusted preview representation. It supports float32 VEC3 positions, unsigned indices, scene transforms and embedded buffers or manifest-relative ZIP resources. Extensions, skinning, animations, sparse/normalized geometry and external references are rejected. Materials/textures are not rendered from uploads. Limits: 16 MiB uploaded, 32 MiB expanded, 64 ZIP entries, 100 expansion ratio, 100k decoded vertices/triangles, hierarchy/accessor limits, 100 saved imports and 128 MiB saved JSON.

ZIPs are never extracted. Symlinks, encryption, duplicate/path-traversal names and unsupported entrypoints are rejected. UTF-8 MJCF/XML and URDF receive structural/numeric inspection with entities/DTDs/includes/plugins prohibited. They are not compiled or executed. This is data-only staging, **not an OS-isolated native simulation worker**. General robot conversion, physical configuration and imported-native execution require future implementation.

## REST/WebSocket integration

Use `openapi.json` and generated `frontend/src/generated/api.d.ts` as the REST contract. Existing create/get/state/experiment/branches/commit/reset/environment/replay endpoints remain. `GET /v1/experiments/{id}/events?after=<seq>` recovers persisted events; WS at the same path streams versioned envelopes and closes after completed/failed. Browser origins are checked against the same explicit allowlist as CORS. Export: `GET /v1/experiments/{id}/branches/{branch_id}/export`.

Imports: raw file bytes via `POST /v1/imports?filename=<basename>`, not multipart. The response gives `visual_only` or `configuration_required`, always `physics_ready:false`. `GET /v1/imports/{id}` retrieves metadata; `/preview` retrieves validated triangles when supported. Sample imports are in `fixtures/imports`. A ZIP manifest is exactly `{"entrypoint":"assets/scene.gltf"}`.

## Hosting and reproduction

Vercel hosts the built frontend. MuJoCo/SciPy run in a dedicated Python process, not Vercel functions. `scripts/start-public-demo.ps1` starts an owned hidden local API on 8001 with a persistent SQLite path and explicit Vercel CORS, then verifies a Cloudflare quick tunnel. Its child environment uses single-thread numerical-library settings and removes optional hosted LLM credentials. Process identities/logs/endpoint are recorded under ignored `data/public`. `restart-public-api.ps1` restarts only the identity-matching API and preserves the tunnel URL; its external readiness check was executed. `stop-public-demo.ps1` checks identity before stopping owned services; public shutdown is not part of live-release verification. This tunnel depends on this machine and is temporary; an independently provisioned authenticated persistent host is still required for a durable release.

```powershell
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\python -m scripts.test_backend -q --junitxml=artifacts/v2-final-backend.xml
.\.venv\Scripts\python -m scripts.export_openapi
Set-Location frontend
npm run generate:api
npm run build
npm run test:e2e
Set-Location ..
powershell -NoProfile -File scripts/start-public-demo.ps1
# Use the returned HTTPS API URL:
vercel link --cwd frontend --project vivacity-demo --scope tanishs-projects-66633ee2 --yes
vercel deploy --cwd frontend --prod --yes --build-env VITE_API_BASE_URL=<returned-api-url>
```

Follow `DEMO_V2_TEST_RESULTS.md` for actual evidence, and `DEMO_V2_LIMITATIONS.md` for the distinction between implemented and incomplete work.
