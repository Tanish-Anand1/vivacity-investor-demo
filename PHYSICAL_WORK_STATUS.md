# Physical work and world editor status

Verified locally and in a bounded public release on 2026-10-22. This is a staged implementation, not a claim that the full autonomous fulfillment directive is complete.

## Working now

- The existing MuJoCo Panda factory cell sorts one to three cartons with a contact-driven grip and measured destination-bin arrival. A new capability-owned order ledger maps each item to its carton and advances SORT only after the saved run records all destination contacts and `cartons_sorted` matches the order size. Failed runs do not advance the workflow.
- `/lab` exposes an order panel for a three-item trial or the current factory conditions. It shows live measured progress, item evidence, and explicit blocked reasons for every later stage. The same factory scene and controls remain available.
- The `/workspace` MuJoCo pick-and-place workcell has a typed inspector for object dimensions, density or explicit mass, friction, robot gripper-force scale, gravity, table friction, route obstacle, and static box/cylinder primitives. Changes recompile the native MuJoCo model and increment the world revision. Static primitives can be selected and dragged on the table or edited numerically.
- Native world snapshots are saved in SQLite on create, edit, reset, commit, and restore. The editor supports saved-version restore, session undo/redo, and JSON export. Prior experiments are version-bound and become stale after a configuration change; their saved evidence remains available.
- The table's friction priority is applied to edited worlds so a change to table friction actually changes the MuJoCo cube/table contact coefficient. The default contact configuration is preserved when the table value remains 1.0.
- A saved workcell snapshot compiled by an older scene version now triggers client-side recovery to a fresh world while leaving its server-side world and experiment records intact. The local page was verified to recover from an actual legacy snapshot after the backend restart.

## Not implemented

- One physically shared factory world containing both Panda and a humanoid; humanoid collection from the Panda's sorted items, walking/carrying, packing, carton closure, sealing, label application, dispatch, coordinated multi-robot timing, and running are **not validated controllers**. The order API keeps these stages blocked. A separate stationary G1 pickup-and-placement experiment now passes its bounded MuJoCo acceptance tests with a documented contact-gated rigid grasp; it does not transfer the same sorted object or count as fulfillment. See `docs/HUMANOID_CAPABILITY_AUDIT.md`.
- The world editor is supported for the MuJoCo pick-and-place **workcell**. It is not universal across the factory, humanoid, cloth, imported, or SciPy worlds. It does not add arbitrary dynamic rigid bodies or modify articulated robot topology, actuators, sensors, adhesion, or independent static/dynamic friction.
- Browser undo/redo lasts for the current editor session; the saved-version list remains in SQLite. JSON export is available, but a dedicated re-import of that world-definition format is not implemented.
- Physical results are simulation evidence, not hardware validation or calibrated material measurements.

## API contract

`openapi.json` and `docs/openapi.json` are generated from FastAPI. All requests and responses use JSON.

Fulfillment routes require the same private `X-Workspace-Token` capability as the factory API:

```http
POST /v1/fulfillment/orders
X-Workspace-Token: <your workspace capability>
Content-Type: application/json

{"order_label":"Three-item trial","item_ids":["item_1","item_2","item_3"],"settings":{"carton_count":3,"realtime_speed":8}}
```

Creation returns HTTP 201 with `status: "ready"`, `cell_id`, `initial_state_hash`, and item/task records. `POST /v1/fulfillment/orders/{id}/start` returns HTTP 202 and a `run_id`. `GET /v1/fulfillment/orders/{id}` and `GET /v1/fulfillment/orders` return persisted order views. The underlying physical run is available at `GET /v1/factory/runs/{run_id}`. A completed order reports `status: "sort_completed"`, never full fulfillment.

For the supported workcell, `GET /v1/worlds/{id}/editor` returns entities and property metadata, including units, bounds, dependency explanations, and editability. Writes require the current `expected_revision`:

```http
PATCH /v1/worlds/{id}/editor/properties
Content-Type: application/json

{"expected_revision":0,"entity_id":"surface","property_key":"friction","value":0.25}
```

`POST /v1/worlds/{id}/editor/geometries` accepts `action: "add" | "duplicate" | "delete"`, an optional `entity_id`, and `geometry_type: "box" | "cylinder"`. `PATCH /v1/worlds/{id}/editor/geometry-position` accepts `entity_id: "geometry:<name>"` and a three-number `position`. `GET /v1/worlds/{id}/versions` lists the latest 100 saved versions. `POST /v1/worlds/{id}/versions/{revision}/restore` accepts `{"expected_revision":<current revision>}` and creates a new current revision. Stale writes return HTTP 409; invalid parameters return HTTP 422.

## Verification and next engineering gate

Focused editor tests verify native mass/inertia, geometry dimensions and transform, contact friction, gravity-driven fall, version restore, validation, and persisted HTTP state. Fulfillment tests verify a real successful sort, a real weak-grip failure, capability isolation, and restart persistence. The live local browser created and completed a three-item order with 3/3 measured destination arrivals and 110.236 seconds of integrated MuJoCo simulation time, then displayed blocked downstream stages. The same browser verified add, rotate, drag, undo, and saved-version restore for a static primitive. After restarting the local API on port 8000, the existing `/workspace` page recovered from an incompatible saved physics snapshot and reached **Physics connected**. A fresh production-built preview loaded `/workspace` with no browser console errors. The new automated browser journey checked saved arrival events and completed in 3.6 minutes.

The next gate is a physically stable humanoid pickup-and-transfer controller in a shared MuJoCo factory world. Do not advance COLLECT, PACK, SEAL, LABEL, or DISPATCH until their contacts, carried-object retention, task-state transitions, and failure cases pass automated and browser tests.

Executed checks:

| Check | Actual result |
| --- | --- |
| `python -m pytest -q` | 331 passed, 1 skipped (Linux-only syscall test on Windows), 1 Starlette deprecation warning; 24m 54s |
| `python -m pytest tests/test_world_editor.py -q` after the final friction and duplicate fixes | 5 passed, 1 deprecation warning; 75.09s |
| `python -m pytest tests/test_fulfillment.py -q` | 2 passed, 1 deprecation warning; 27.44s |
| `npm run build` | Passed TypeScript and Vite production build after the final recovery fix. Existing large-bundle warning remains (`WorldPreview` about 2.5 MB before gzip). |
| `npm run test:api`, `test:templates`, `test:factory-settings` | 20, 5, and 4 passed, respectively. |
| `playwright test e2e/physical-work.spec.ts` against the isolated local backend | 1 passed, 3.6m. |

The full-suite run started before the final small table-contact and duplicate-boundary edits. The focused editor run, production build, and browser test were repeated after those edits. The later G1 stationary pickup release is deployed at `https://demo.tryvivacity.com/works`; its live measurements and limits are recorded in `docs/HUMANOID_CAPABILITY_AUDIT.md`. The Render Free backend can sleep and has no durable disk guarantee.
