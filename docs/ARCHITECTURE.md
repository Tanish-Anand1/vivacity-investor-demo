# Architecture

FastAPI -> bounded single-worker job executor -> shared Runtime -> Backend protocol -> MuJoCo or SciPy. SQLite stores versioned JSON worlds, snapshots, experiments, branches and events. Jobs persist before submission; interrupted jobs are marked failed on startup. A world revision changes on geometry edits, reset and commit. Revision checks prevent stale branch commits. SQLite transactions serialize mutations; branches restore independent data and never share writable simulator state.

Adapters implement create_world, observe, snapshot, fork, apply_action, simulate, evaluate, commit and replay. Raw serialized states differ. MuJoCo uses mjSTATE_INTEGRATION, model configuration, engine version and model hash. SciPy uses observations, initial conditions and the fitted model state. API responses never include the generation-only hidden parameter configuration.

One local process and one worker are supported. Local trusted demo API; no multi-tenant authorization or distributed job leasing is claimed.

Experiment submission uses an immediate SQLite transaction to persist the optional per-world idempotency key, request fingerprint, experiment, queued event and history together. A reused key retrieves the original job before requesting queue capacity. Keys survive restart and never change meaning after a world revision changes. No-key submissions retain the existing new-experiment behavior.

Branch execution catches adapter boundary exceptions separately from storage/worker errors. It records failed evidence honestly, then continues independent candidates. Completed branch rows, lineage, evaluations and events share one transaction, preserving partial progress if a later job operation fails. Job terminal status and terminal events commit atomically. WebSocket delivery reads status before draining events, preventing a terminal commit from being skipped between an empty event query and socket closure.

Reference: [SQLite transactions](https://www.sqlite.org/lang_transaction.html) and [FastAPI header parameters](https://fastapi.tiangolo.com/tutorial/header-params/).
