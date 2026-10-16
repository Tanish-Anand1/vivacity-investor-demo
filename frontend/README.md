# Vivacity live investor workspace

React/TypeScript/Three.js frontend for the persisted FastAPI runtime. Current integration and exact Claude Code commands are in the root `FRONTEND_HANDOFF.md`. Preserve this client; do not rebuild its scaffold or replace real computation with fixtures.

## Local development

With the current Python backend running at `http://127.0.0.1:8000`:

```powershell
npm ci
npm run generate:api
npm run build
npm run dev
```

The UI runs at `http://127.0.0.1:5173`. `VITE_API_BASE_URL` defaults to local port 8000; configure an HTTPS API for a deployed HTTPS frontend. Backend CORS must permit the exact UI origin for HTTP and WebSockets. Secrets never belong in `VITE_` variables. Stop script-owned old services before reinstall/restart on Windows; `scripts/stop-demo.ps1` checks process identity. Build to a fresh scoped output directory if an old font remains locked.

## Current real browser checks

With both services running, from this directory:

```powershell
$env:UI_URL='http://127.0.0.1:5173/'
$env:API_URL='http://127.0.0.1:8000'
$env:PROOF_PREFIX='frontend-live'
$env:CHECK_CONDITIONS='1'
npm run test:e2e
```

This executes the root `scripts/check-master-live.mjs` against actual running services. It changes only requested cycle counts for bounded verification: two pickup/science cycles and one cloth cycle. Every candidate, integration, fit and selected execution remains real. It checks exact measured poses/vertices/numerical geometry, result selection without replay, three actual JSON downloads, keyboard camera, narrow widths, axe, imports and optional blocked/clear obstacle recovery. Allow several minutes with software graphics. Outputs are written under root `artifacts`; captured capability tokens are not exported.

Install Chromium under root `data/playwright` if absent: set `PLAYWRIGHT_BROWSERS_PATH` to that absolute directory, then `npx playwright install chromium`. The script keeps browser temp files on the project drive. `test:e2e:legacy` preserves the preceding V2 runner; playback expectations in those historical tests do not describe current acceptance.

## Lifecycle and physical rendering

`api.ts` owns transport and capability headers/subprotocols. `useRuntime.ts` owns idempotent session initialization, one-second heartbeat/poll recovery, sequenced progress, latest-only live states, safe stop/apply/reset and evidence inspection. Session IDs/capabilities and selected lab are saved locally; stored simulator evidence remains authoritative on the server. Stop cancels backend computation, not a video. No `usePlayback.ts`, replay clock, timeline, Play/Pause or canned trajectory exists in this UI.

Validation candidates start from independent restored states. The scene stays initialized during validation, then moves from fresh authoritative execution messages. Completed result cards inspect real validations; clicking one does not substitute its trace in the main scene. Science renders computed paths and observations with chronological train/heldout splits. Cloth renders actual MuJoCo flex vertices while the actuated Panda moves its explicitly pre-attached bar fixture.

MuJoCo coordinates are right-handed Z-up meters; quaternions are WXYZ and must be reordered to Three.js XYZW. Body transforms are world poses, not local FK. Compiled mesh vertices already include their mesh-frame transforms; use local geom bindings without reapplying raw XML transforms. Dynamic cube pose always comes from `target` body measurements, never hand parenting. Half-size obstacle dimensions become twice the size in Three.js. Uploaded glTF preview uses Y-up. Camera/grid/light actions do not alter physics.

Compiled Panda geometry is in `public/vivacity/robot-geometry.json` and `robot-meshes.bin`; provenance/licenses are adjacent and in root `assets`. Client type generation reads exported OpenAPI. UI labels the wrapper Viva Physics and credits actual MuJoCo/Menagerie/SciPy scope. Deterministic policy is not presented as hosted LLM reasoning.

Read root `DEMO_STATUS.md`, validation reports and `DEPLOYMENT_GUIDE.md` for measured outcomes and remaining limits: generalized pickup obstacle detours, arbitrary garments, native import workers, account authentication/retention and independent durable hosting remain incomplete or blocked.
