Current product: robotics-only. Templates: GET `/v1/templates` and POST `/v1/templates/resolve`; see `docs/ROBOTICS_TEMPLATES.md`. Supported public backends are `mujoco` and `cloth`. Scientific Discovery is retired.

# Version 1 frontend contract

OpenAPI REST specification: root `openapi.json`, with an identical documentation copy at `docs/openapi.json` (regenerate both with `python -m scripts.export_openapi`). See `FRONTEND_HANDOFF.md` for complete frontend integration and `docs/frontend-examples.json` for actual responses. API schema version is `1.0`; URL major version is `/v1`. All request bodies reject unknown fields and non-finite values. World, state, experiment, branch and replay responses are named Pydantic schemas.

Current master handoff: `FRONTEND_HANDOFF.md`, `docs/master-frontend-examples.json`, `ARCHITECTURE.md`. Historical captures in `docs/frontend-examples.json` describe standalone reaching/science. Current frontend requests contact-driven pickup explicitly and consumes fresh measured states, not replay.

## Autonomous sessions and live state

Current additive controls: POST `/v1/sessions/{id}/pause` and `/resume` use the
same capability and return `pause_requested`, `paused` and `paused_seconds`.
Acknowledged pause freezes the actual worker at a safe boundary; Resume keeps
the same world/experiment/state. No recorded-playback behavior is involved.
`physics_trials:5000` with matching `search_candidates:5000` requests exhaustive
Panda pickup physics. Other backends reject this option. GET
`/v1/experiments/{id}/trials?after=-1&limit=50` exposes every measured trial;
pagination uses returned completion-sequence `next_after`, not candidate index.
Full schemas, execution details and proof scope: `PAUSE_TRIALS_VALIDATION.md`.

POST `/v1/sessions` creates a bounded session; GET `/v1/sessions/{id}` reads status and refreshes its browser lease; POST `/v1/sessions/{id}/stop` requests cancellation. Required `X-Session-Token` is a client-generated 32–128 character random capability. The same capability protects every REST and WS route for that session's worlds/experiments. Only its SHA-256 digest is persisted; response/export records do not reveal it. Reusing the same token/settings is idempotent; conflicting settings return 409. Legacy standalone worlds and imports remain public demo data; this is not account authentication.

POST `/v1/experiments/{id}/cancel` requests asynchronous cancellation. GET and WS `/v1/experiments/{id}/live` expose `{schema_version:"vivacity.live/1.0",experiment_id,world_id,sequence,timestamp_unix_s,stage,frame}` (GET can return null). WS offers `vivacity.live` and `vivacity.token.<capability>` subprotocols, never a secret query string. The persisted-events socket uses the same capability convention. Exact Origin must be allowed for both protocols.

Latest-state stream retains one actual frame per experiment, at most 32 experiments, up to 20 Hz; slow clients skip intermediate frames. Validation branches keep their measured traces but do not drive the main scene. `execute_selected:true` runs a validated chosen command again in independent MuJoCo data, records an `authoritative_execution` branch, streams that fresh state, and commits only a newly successful physical outcome. `result.execution_branch_id`, `execution_evaluation`, and `executed_world_revision` identify it. Self-committed successful results are not stale until another world change. A failed live attempt does not commit a validation prediction.

One physics worker, eight reserved jobs, two active supervised sessions, at most eight cycles (cloth two), 180 s heartbeat lease and 30 min session wall bound constrain active work. New cycles create new seeds/worlds/conditions. Stop/cancel checks every physical integration step; Restart marks interrupted jobs/sessions failed. Expiry is stopped, never successful completion. Disk retention/account quotas remain unimplemented.

## Operations

| Endpoint | Meaning | HTTP |
| --- | --- | --- |
| POST /v1/worlds | Initialize adapter and persist initial/current state | 201 |
| GET /v1/worlds/{id} | Configuration, state, version, seed, lineage, history and evaluations | 200 |
| GET /v1/worlds/{id}/state | Measured structured observation | 200 |
| POST /v1/worlds/{id}/experiments | Persist and queue an isolated experiment | 202 |
| GET /v1/experiments/{id} | Job state, comparison, selected branch, metrics, stale flag | 200 |
| GET /v1/experiments/{id}/branches | Independently initialized candidates and measured outcomes | 200 |
| POST /v1/worlds/{id}/commit | Commit one successful branch from the current revision | 200 |
| POST /v1/worlds/{id}/reset | Restore current environment's initial snapshot | 200 |
| PATCH /v1/worlds/{id}/environment | Replace validated configuration and reset initial/current state | 200 |
| GET /v1/experiments/{id}/replay | Recorded evidence frames, original configuration | 200 |
| WS /v1/experiments/{id}/events | Persisted progress and measured branch outcomes | WebSocket |

Errors: 404 missing record; 409 failed/stale/mismatched branch commit or conflicting idempotency key; 422 invalid configuration/request/header; 429 bounded job queue full; 503 unavailable worker. Queue/worker responses include `Retry-After: 5`. A worker submission error is persisted as a failed experiment before 503 is returned.

## Safe experiment retries

Send an optional `Idempotency-Key` header with `POST /v1/worlds/{id}/experiments`. Generate one key for each deliberate action and reuse it when retrying that action after a lost/slow response. Keys are 1..128 ASCII letters, numbers, dot, underscore, colon or hyphen. They are scoped to the world ID. The normalized validated request settings are hashed; the same key/settings return the **original experiment ID and current status**, and different settings with the same key return 409. Requests without a key intentionally create separate experiments.

The key mapping is committed with the experiment, queued event and world history in SQLite. Concurrent retry requests and retries after restart cannot create another job. A retry also works when the job queue is full because it needs no new worker slot. Editing/resetting a world does not repurpose a key: the original result is returned with `stale: true`. Use a new key to deliberately compute a new revision or retry a failed job as new work. Keys currently remain for the lifetime of the local database; expiry/retention is not implemented. Browser CORS permits the header for configured origins.

## World state and lineage

MuJoCo snapshots store `mjSTATE_INTEGRATION` via `mj_getState` / `mj_setState`, including controls, solver warmstart, applied forces and other integration inputs. Metadata includes engine version, generated scene/mesh hash, seed, configuration and state bitmask. Each fork loads its own model and `MjData`. No mutable array or configuration list is shared between branches. Reproduction is validated in the pinned Windows/Python environment; cross-platform bitwise equality is not promised.

Branch `parent_state_reference` is world ID + revision + snapshot SHA-256. Each branch exposes its actual action, initial snapshot, final snapshot, sampled trace, evaluation and compute metrics. World history stores experiment IDs and branch relationships. Revision increments on environment edit, commit and reset. Older experiments remain replayable with their original configuration and `stale: true`; their results cannot be committed.

Branch rows, evaluation records, lineage and progress events are persisted together as each branch finishes. A later planner/worker failure retains already completed evidence. Unexpected adapter exceptions become `adapter_failure` with the operation phase and exception type. Such branches have an empty unavailable trace, and their physics timing/step/call counts are `null`; no fabricated counters or frames are supplied. `final_state` is `null` if it cannot be recovered safely. Replay source is `failed_adapter_execution`. Other independent candidates still run. When every branch has an adapter failure, the job ends `failed`. A mixed job may finish `completed` while reporting adapter errors in its performance; clients should display these failures beside the measured results.

## Robotics rendering

### Simulated object localization

For `task:pick_place` in the standard workcell, `GET /v1/worlds/{id}/state`
adds `observation.perception` with schema version `vivacity.perception/1.0`.
An orthographic overhead sensor casts **22,701 actual MuJoCo rays** into the
current scene. A hit is labelled `cube` using MuJoCo's semantic geom ID;
`estimated_xy_m` is the mean of visible cube-hit positions and is never copied
from the configured or true body position. `localization_error_m` compares
that estimate with MuJoCo's true body position for demo evaluation only.
`visible_samples_xy_m` supplies the supporting hit coordinates. If fewer than
four rays see the cube, `detected` is false, estimate/error are null, and the
pickup planner reports `object_not_visible` with zero physics steps. When
detected, the planner targets the ray-derived XY estimate. The camera covers
X `-0.30..1.10` m and Y `-0.65..0.65` m. Valid tabletop pickup/placement centers
are inset from those table edges by object half-width/depth plus 1 mm, with at least `0.10` m between
pickup and placement. An allowed position can still be unreachable or fail
physical grasp; those cases retain genuine failure results.

This is **synthetic simulator semantic-depth sensing**, not RGB vision, a
trained detector, a real camera, or a claim of solved real-world perception.
The sensor runs for state reads and planning, not on every streamed physics
frame. Enabled static obstacles can occlude it; disabled obstacles are ignored.
No ray-scan result is substituted into a recorded physics trace.

The optional `cube_half_sizes: [x,y,z]` sets independent object half-dimensions
(0.02..0.03 m each); absent/null retains `cube_half_size` compatibility.
`cube_mass` is 0.02..0.15 kg and `cube_friction` is 0.05..1.5. Weight derives
from mass and configured gravity; it is not an independent parameter.
Adaptive pickup requests use `adaptive_trials: true`, `physics_trials: 0`
and a host-bounded `physics_budget`. The result's `search.stopping_reason`
records measured plateau, candidate exhaustion or compute-budget stop.
See `docs/ADAPTIVE_PICKUP.md` for the exact search and frontend journey.

Positions are meters in MuJoCo's right-handed Z-up frame. Joint values are radians, velocities radians/second, time seconds. Body quaternions are **w,x,y,z**; Three.js constructors ordinarily require **x,y,z,w**, so reorder them. `body_transforms` are world transforms, not parent-relative transforms. Replay frames contain actual measured `qpos`, `qvel`, `ctrl`, simulation time, end-effector coordinates and body transforms sampled every 25 integration steps (50 ms) plus initial/final/failure frames. Contacts are checked every 2 ms even though replay is decimated. UI interpolation between sampled frames is visualization only.

The pre-grasp site is 0.103 m along the hand's local Z axis. Desired rotation matrix is diag(1,-1,-1). In legacy reaching, `target_position` is the pre-grasp goal and the cube has the same XY/Z=0.026 m. In `task:pick_place`, a free dynamic cube starts at `cube_position` and must be grasped/transported/released at `placement_position`; its actual `target` body transform is authoritative. Its half-size is 0.025 m. Table center `[0.4,0,-0.04]`, half-size `[0.7,0.65,0.04]`; ground Z=-0.8. Obstacle size is **half-size**, not full dimensions. Disabling the obstacle changes actual collision masks as well as rendering. The implemented React client serves compiled Panda visual bindings/buffer in `frontend/public/vivacity`; apply compiled local geom poses with actual world body poses, without double-applying raw XML mesh transforms. Never parent the cube to the hand.

Robotics evaluation distinguishes planning, collision, limit, controller, timeout, grasp, dropped-object and cancelled failures from execution success. `planning_feasible` describes geometric checks only. Contacts with robot/environment or non-excluded self bodies are prohibited; the fixed link0/table mount is allowed. Legacy reach requires position error ≤0.02 m and orientation error ≤0.08 rad. New pickup additionally requires real bilateral finger forces, lift/retention, release, final table support, settled object velocity and placement error ≤0.025 m, with no prohibited contact/limit/controller event. Finger-cube grasp contact and cube-table support are intended; carried-cube obstacle/ground impact is prohibited even without robot collision. Infeasible RRT/staged paths preserve honest planning failure with zero integrated steps; a geometric diagnostic is not counted as a completed physics episode. Generalized obstacle-detour pickup remains incomplete.

## Scientific rendering and metrics

Replay frames include observed position, fitted predicted position/velocity, time and a `train`/`heldout` tag. Residuals are predicted minus observed. RMSE is per-coordinate: sqrt(mean(dx²,dy²)). Fits see only the chronological training prefix; predictions are tested against the suffix. Training BIC is chi-squared under known observation noise + k*log(number of training coordinates); the common Gaussian constant cancels in comparison.

The additional mass is selected only if training BIC improves by >6, held-out RMSE improves by >5%, and the fit Jacobian has full rank. Otherwise retain the baseline. If a fit fails numerically, comparison remains incomplete with no selected result. Standard errors are a local Jacobian covariance approximation using known measurement noise; inspect rank, active bounds and caveats. No posterior probability is provided. A weak/noisy experiment may not support a real perturbation; this is a valid outcome.

## Events and reconnect

Connect to `ws://127.0.0.1:8000/v1/experiments/{id}/events?after=0` with the capability subprotocol for session-owned records. Each JSON message has `schema_version`, monotonically increasing `seq`, `kind`, and `details`. Kinds: `queued`, `running`, `planned`, `progress`, `branch_completed`, `completed`, `failed`, `cancelled`. Keep the last `seq` and reconnect with `after=<seq>` to receive missed events. These are persistent job/branch events; the separate live socket supplies current measured state. A terminal event closes 1000; missing/disallowed/unauthorized records close 1008. Events are retained in SQLite and can be read after completion.

## Performance

Without bulk search, the deterministic policy may run **one additional robotics planning round** when no candidate succeeds, IK converged, the starting state is collision-free, and the search budget is below 4000 iterations. Legacy reaching doubles its RRT budget (capped at 4000); every original failure is retained. `followup_settings` and a second `planned` event identify the extra work. Bulk search uses its bounded physics shortlist instead. `search.fully_simulated` counts validation integrations, while aggregate candidate/step measurements also include a fresh selected execution if requested.

World metrics expose initialization wall time. Experiment metrics expose planning, physics and whole-job wall time, process CPU time, queue wait, candidate count, simulation step count, serialized replay bytes and branch failure rate. A rejected candidate is an expected measured outcome, not an infrastructure error. A worker error reports `job_error_rate: 1`. CPU measurements include any concurrent API activity in the same process. Deterministic execution has zero hosted model cost; optional hosted adapter usage/billing telemetry is not implemented.

`adapter_error_count` counts failed adapter boundaries. `measurement_complete: false` means aggregate physics timing, simulation steps and integration calls sum the **available measurements only**; their missing portions cannot be inferred as zero. Branch performance uses nullable counters to make those gaps explicit. `job_error_rate` is 1 for a job containing adapter errors, including a mixed job that completed evaluation; it is 0 for normally measured jobs. Robotics selection and reported ranking both order successful candidates by measured simulated duration, then goal error.
