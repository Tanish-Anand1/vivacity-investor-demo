# Current scope: robotics-only templates

Scientific Discovery is retired. `templates.py` publishes capability readiness and resolves supported selections into existing MuJoCo robot/cloth adapters. No alternative arm controller is implied by a reference catalog entry. The template picker creates idle worlds; actual execution still requires Start. See `docs/ROBOTICS_TEMPLATES.md` and `IMPLEMENTATION_STATUS.md` for current acceptance evidence. The following records earlier architecture milestones; old Discovery verification is historical.

# Vivacity master implementation

## Native import boundary and Orbital adapter

Current implementation/evidence: `docs/FINAL_VERIFICATION.md`. The runtime now
owns `ImportService` beside experiment persistence. Uploads remain data-only
until an explicit verification request queues one disposable native probe on
the bounded shared executor. Scoped VFS assets, process resource limits and
Linux syscall denial precede compilation; no service secrets are inherited.
Windows restricts native probes to the exact trusted supplied fixture.

`vivacity/orbital.py` is a trusted, checksum-checked scene adaptation inside
the existing `PickPlaceBackend`. It preserves the shared snapshot/fork/action/
simulation/evaluation lifecycle; it does not execute arbitrary XML in the web
process. Configured worlds and exports retain `scene_profile`, source import
reference/hash, mechanical changes and actual geometry. The original robot's
motion probe never proves grasp capability. Only measured full task execution
can verify delivery. Generic robot task discovery remains incomplete.

The Orbital UI submits three actual native trials and fresh selected execution,
streams real `/live` and `/events` states, supports explicit cancellation and
geometry changes, and stops polling after completion. It starts no job on load.
Main UI controls are Start/Stop; native Pause/Resume remains in the API.

Existing FastAPI/SQLite adapters and React/Three.js client are retained. MuJoCo 3.15.0 supplies dynamics; SciPy supplies robotics rotation mathematics. Pinned dependencies remain in `requirements.txt` and frontend lockfile.

Runtime operations remain create/observe/snapshot/fork/apply/simulate/evaluate/commit/replay. `RobotAdapter` dispatches persisted robotics configurations between legacy reaching and new contact-driven pickup. Both use full `mjSTATE_INTEGRATION`, independent `MjData` and reconstructed scene/version/mesh hashes. SQLite preserves branch lineage, actions, measured traces, evaluations and idempotent jobs. A bounded one-worker executor runs simulations outside HTTP handlers.

Source audit: `vivacity/{runtime,robotics,pick_place,cloth,templates,search,storage,schemas,api,agent,imports}.py`; frontend runtime, scenes, playback and result/inspector/import components; existing API/physics/templates/search/reliability tests; architecture/API/handoff/status/release documentation. Git checkpoint: `codex/master-build-checkpoint` at `4a1d405`. Unrelated untracked partial verification artifacts were preserved.

New phase-1 code is isolated in `vivacity/pick_place.py`; old scene reconstruction is preserved. See `ROBOTICS_VALIDATION.md` for executed evidence.

Phase 2: `Supervisor` owns at most two leased sessions and one pending experiment per session. The shared one-worker simulation executor remains bounded to eight reservations. A session runs at most eight cycles (cloth capped at two), uses new world IDs/seeds and records conditions. A 180-second browser heartbeat lease and 30-minute session wall bound stop unattended work. Stop/cancel interrupts robotics/cloth at physics-step boundaries. Restart marks interrupted jobs/sessions honestly failed. Successful selected physical plans execute again in an independent simulator and persist their actual live outcome; no recorded trace drives execution.

Session capabilities are client-generated random tokens; only SHA-256 digests are stored. All REST and both WebSocket routes for session-owned worlds check that capability. HTTP uses `X-Session-Token`; WebSockets offer `vivacity.live` and `vivacity.token.<token>` subprotocols. No token appears in URLs, branch exports or result records. Legacy explicitly public demo worlds remain public; this is capability isolation, not account authentication, billing or comprehensive abuse protection.

Live state is latest-only, one measured frame per job and at most 32 jobs retained in memory. `/v1/experiments/{id}/live` offers REST recovery and an independent WebSocket at up to 20 Hz. Physics runs at 500 Hz; optional worker pacing makes selected execution visible without substituting frontend physics. Validation branches retain measured traces in SQLite; the scene remains initialized during validation and consumes fresh states only during authoritative execution. Persisted event messages use the existing sequenced progress WebSocket, with batched search counts. They are separate from transient live frames.

Executed phase-2 checks: 41 API/runtime/supervisor regression tests passed in 70.12 s; a subsequent five-test supervisor run passed in 92.93 s and additionally verifies two physically successful, different-condition pickup cycles. Evidence: `artifacts/master-supervisor-tests.xml`, `artifacts/master-autonomy-tests.xml`. An initial request-only global dependency broke WebSocket injection; changing it to `HTTPConnection` and explicitly authenticating sockets fixed both regressions before the passing run.

Final verification: 101 backend tests passed in 290.66 s, including object-only prohibited impacts and stopped status for expired bounds. The complete public seven-job journey passed with 666 actual state frames and 89 persisted events. A later isolated Discovery SVG sizing fix passed current-alias numerical/console/reload/offline/mobile checks; no physical code changed. Local 8000/5173 services were refreshed and checked; auxiliary verification services were stopped without affecting the public host or unrelated local service. Current evidence, versioned endpoints and operational limitations: `DEMO_STATUS.md`, `FRONTEND_HANDOFF.md`, `DEPLOYMENT_GUIDE.md`.
