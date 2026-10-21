# Experiment protocols

## Run the verified slice

On Windows PowerShell from the repository root:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn vivacity.api:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/workspace`, choose **Browse programs → Robotic arms → Precision assembly → Open experiment**, then **Start experiments**. The UI shows candidate outcomes and a persisted verification report with JSON export. Change conditions to alter mass, force scale, speed, yaw or tolerances; apply settings and start another run. Previous results become stale after a world change.

`GET /v1/robotics/programs` returns seven typed entries. Only `precision_assembly` has `status: executable` and `default_configuration`. The workspace configuration resolves through the existing session/world API, which enforces bounds and creates a fresh world. `GET /v1/robotics/experiments/{id}/report` returns the selected branch's initial/terminal state, candidate evaluations, live-run evaluation when present, model hash, solver configuration, world revision, seed, events, measured performance, and replay/export paths. Session-owned worlds require the `X-Session-Token` capability header. The generated [OpenAPI specification](../openapi.json) is the transport contract.

The experiment runs are asynchronous. A completed candidate branch records its own initial snapshot, action, trace, contacts, final state, evaluation and timing. The separate authoritative execution branch can add one branch beyond the requested validation count. `GET /v1/experiments/{id}/branches`, `/replay`, `/events` and `/branches/{branch_id}/export` inspect the persisted evidence. Live WebSockets are `/v1/experiments/{id}/live` and `/events`; session worlds use `vivacity.live` and `vivacity.token.<token>` subprotocols. Replay is a recorded trace, not a re-simulation. The report's `verified` value requires a successful measured physics branch, not an HTTP 200.

## Acceptance scenarios executed locally

The real-run script creates a nominal 0.15 kg part, a weak-grip/high-mass/low-friction failure case, and a 0.30 kg mass variation. It checks an actual MuJoCo model, successful seating, actual simulation steps, branch independence, replay and persisted export. The tests also cover unreachable targets and a tighter 1 mm tolerance that rejects placement. The browser journey tests catalogue availability, configuration, a completed run, JSON export, mobile accessibility and a changed condition. See the machine-readable [verification output](v-robotics-verification.json) and [matrix](VALIDATION_MATRIX.md) for precise results.

The three local runs are controlled examples, not a reliability estimate. The current UI lets the runtime choose bounded candidate counts and resource limits; it does not prove exhaustive optimality or 5,000 fully simulated alternatives for this program.

For a read-only check of the catalogue, use `GET https://demo.tryvivacity.com/runtime/v1/robotics/programs`. To submit a new real experiment against the public backend and store a concise measured artifact, run `python -m scripts.verify_v_robotics_public --base https://isabella-labs-runtime.onrender.com`. That command consumes public-host compute; it is not a health probe. The production backend currently runs on a Render Free instance, so cold starts and non-durable local persistence remain possible.
