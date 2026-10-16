# Recorded branch export 1.0

`GET /v1/experiments/{experiment_id}/branches/{branch_id}/export` returns an attachment with schema identifier `vivacity.branch/1.0`. Its Pydantic/OpenAPI schema is `BranchExport`.

It contains the actual independent parent and final state, original configuration, simulator version, seed, model/configuration hashes, chosen actions, recorded frames, evaluated outcome, constraint violations, measured performance and submission/branch-completion Unix timestamps. IDs must belong to the requested experiment; mismatches return 409, missing records 404. Failed branches can also be exported for inspection.

MuJoCo state is a JSON numerical serialization of the `mjSTATE_INTEGRATION` vector with configuration/version/model hash and state-spec metadata. It is not a native `.mjb` binary model or simulator checkpoint file. Restore through the pinned adapter after checking version and hash. Frames are sampled observations, not complete integration snapshots at every timestep. Scientific state contains public observations/assumptions and fitted parameters, never hidden generating mass. Configuration hash is SHA-256 of the runtime's compact JSON encoding.

The renderer interpolates stored poses/positions only. Looping resets presentation to the original recorded parent without rerunning physics. A finite sampled joint path length is an efficiency proxy, not measured energy. The entire raw export should be retained if another developer needs to reproduce a branch; the UI displays only a few metrics.
