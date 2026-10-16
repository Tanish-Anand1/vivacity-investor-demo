# Current deployment — 2026-10-11

Latest native-import backend: `69013a8f6b538398a042a4f862638aac50865f20`, live
Render deployment `dep-db5s8hks728c738sccf0`, verified 2026-10-11 22:46 IST.
Exact source passed **135 Linux tests** and a separate **512 MB test**.
Frontend `dpl_9kYzmrxJgMi2mLFmB8fAX8a1bBEX`, immutable
`https://vivacity-demo-qey7nhf4o-tanishs-projects-66633ee2.vercel.app/`, both public
aliases assigned. Public Orbital upload/native probe/configuration/three trials/
fresh delivery/exports/geometry correspondence/mobile/reload and blocked-reactor
replanning passed **12 checks**. Current proof: `docs/FINAL_VERIFICATION.md`,
`artifacts/orbital-public-final.json`. The Orbital-only camera correction leaves
workcell physics and styling unchanged.
The following older release detail is historical where it differs.

## Current hosting status

The frontend at **https://demo.tryvivacity.com/** connects to the live Render API
at **https://vivacity-runtime.onrender.com/**. Alias:
https://vivacity-investor-demo.vercel.app/. Current release and public evidence:
`docs/HOSTING_STATUS.md`.

The deployed Render Free instance uses 0.1 CPU / 512 MB, sleeps after 15 minutes
idle and has ephemeral SQLite storage. Public pickup runs eight real physics trials.
These limits cannot deliver always-on hosting or durable history. The paid upgrade
was blocked by Render's card requirement after the debit card was declined; no
payment action was made. The constrained-host 300-second execution deadline passed
135 Linux tests plus the 512 MB smoke and is deployed. For the final public run, use
`docs/HOSTING_STATUS.md` as the current behavior.

The rest of this file records the earlier temporary-tunnel deployment and is
historical evidence only; it is not the current backend URL.

## Previous temporary deployment evidence

Frontend: **https://demo.tryvivacity.com/**; **https://vivacity-investor-demo.vercel.app/** aliases the same current deployment. Project `vivacity-demo`, scope `tanishs-projects-66633ee2`. Current immutable URL: `https://vivacity-demo-3oxvuhg3m-tanishs-projects-66633ee2.vercel.app`; deployment ID **dpl_yP6WDKC22EMLt2y58rUSHGrdXtBz**. The preceding deployment **dpl_4odWdeqdZ2VGXu7Shcj8uoR7dyWb** ran the complete seven-job journey; the current release adds only the scoped Discovery accessibility-SVG sizing fix, with separate current-alias boundary verification. Physics/runtime revision: `5de72f8`; layout fix: `9788f8e`.

Backend: **https://stayed-oem-founded-son.trycloudflare.com**, health `/health`, Swagger `/docs`, OpenAPI `/openapi.json`. Verified versions: MuJoCo 3.15.0, SciPy 1.18.1. A hidden local persistent Python process on port 8001 and SQLite WAL at `data/public/vivacity.sqlite3` supply actual numerical computation and state. Cloudflare forwards HTTPS/WSS to that process. MuJoCo does not execute in Vercel's static frontend.

## Actual acceptance evidence

`artifacts/master-public-verification.json`: **passed**, seven fresh jobs, 507.741 s, 666 actual state frames, 89 persisted progress messages, no captured page errors, zero axe violations in checked scope. It verifies fresh pickup cycles, real 5,000-proposal/three-validation/fresh-execution counts, exact body poses, three parsed downloads, camera, no video controls, one inspector, blocked-scene failure, stale results/replay, clear-route recovery, actual blinded SciPy/control fits, actual planar predictions, fresh Panda/flex folding and all 49 measured vertices, plus visual upload. Public numerical outputs are in `master-public-measurements.json`; screenshots were inspected.

The subsequent 375 px Discovery check found 19 px overflow from a visually hidden SVG inheriting full width. Restoring its 1 px accessible sizing corrected it without changing physics or visible data. `scripts/check-public-boundaries.mjs` verifies current public aliases with real fresh fits, console capture, direct reload retaining the same session, narrow layout, deliberately unavailable requests retaining evidence, and recovery. Expected simulated offline console errors are recorded separately from unexpected errors. A first harness tried the mobile-hidden connection badge; it was corrected to test the visible offline notice. The failed harness report and original overflow screenshot are retained. Current result: `artifacts/master-public-boundaries.json`.

An actual unauthenticated public request to a session-owned world returned **403**. Successful capability-bearing HTTP/WSS is exercised by the browser journeys. OpenAPI has **21 REST paths** and two explicit WebSocket message schemas. The full backend suite passed **101/101** before release. Strict TypeScript and local/remote Vite builds passed; current remote build 2.54 s. The lazy Three.js chunk remains approximately 933 kB / 249 kB gzip; no latency/frame-rate SLA or full load/soak claim is made.

## Reproduce this temporary deployment

From the repository root in PowerShell, using existing authenticated CLIs and preserving unrelated projects:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-public-demo.ps1
# When the tunnel is already running but backend source changed:
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/restart-public-api.ps1
vercel link --cwd frontend --yes --project vivacity-demo --scope tanishs-projects-66633ee2
vercel deploy --cwd frontend --prod --yes --scope tanishs-projects-66633ee2 --build-env VITE_API_BASE_URL=https://stayed-oem-founded-son.trycloudflare.com
# Use the newly returned immutable URL, not an old example, for the investor alias:
vercel alias set NEW_IMMUTABLE_URL vivacity-investor-demo.vercel.app --scope tanishs-projects-66633ee2
```

The custom domain is attached to this Vercel project and is assigned by production deploy. If the quick-tunnel hostname changes, use `data/public/endpoint.json`'s actual `apiUrl` for the build environment and verification. Do not copy example IDs/hosts into an unverified new deployment. Never commit `.env.local`, CLI credentials or capabilities. The scripts record PID, creation time, executable and command marker and stop only matching owned processes. `restart-public-api.ps1` preserves the current tunnel hostname and DB; interrupted jobs/sessions become honest failed records. Check for active visitors/jobs before restarting. Starting an already healthy process does not reload changed Python source.

Current public verification commands:

```powershell
$env:UI_URL='https://demo.tryvivacity.com/'
$env:API_URL='https://stayed-oem-founded-son.trycloudflare.com'
$env:PROOF_PREFIX='release-check'
$env:CHECK_CONDITIONS='1'
node scripts/check-master-live.mjs
# Check both canonical aliases, including console/reload/offline behavior:
$env:UI_URL=$null
node scripts/check-public-boundaries.mjs
```

The first command creates genuine new physics and scientific experiments and can take several minutes on software graphics. Do not run multiple heavy verification suites simultaneously on the presentation machine. The second performs cheap real SciPy fits. Captured capabilities remain local to their browser contexts, not artifacts. Explicit CORS permits both deployed origins and known local dev origins; WS uses the same Origin allowlist and session-capability subprotocol.

## Durable-hosting blocker and prepared container

**This is a working temporary investor deployment, not independently durable cloud infrastructure.** The backend depends on this computer, its network and the tunnel. Railway authenticated provisioning was attempted and refused: **"Your trial has expired. Please select a plan to continue using Railway."** No unrelated `uber-telegram-bot` service was repurposed, no paid plan purchased and no cloud volume claimed.

`Dockerfile` and `railway.toml` are prepared for a provisioned Python host; `.dockerignore` excludes secrets, Git, node modules, temporary DBs/artifacts and frontend from the build context. The image defaults to `VIVACITY_DATABASE=/data/vivacity.sqlite3`, creates `/data`, declares a volume and constrains numerical thread pools. Use one Uvicorn process with platform `PORT`. Mount a real persistent volume at `/data`, allow exactly the deployed frontend origins through `VIVACITY_CORS_ORIGINS`, terminate HTTPS/WSS and expose `/health`. **Docker build/run is unverified** here: the Docker Desktop Linux daemon socket is unavailable. These files are preparation, not evidence of a deployed Linux image.

A durable public service still needs provisioned compute/volume, verified Linux dependency/model execution, authentication/tenancy for all endpoints, request/disk/upload quotas, backups/retention, TLS/WSS/proxy timeouts, structured monitoring and load/soak tests. Current capability isolation protects session-owned worlds, but standalone worlds/imports remain public demo data. Never upload confidential content or advertise unlimited concurrency. Active work is bounded to two supervision sessions, one physics worker, eight job reservations, finite cycles, 180 s heartbeat lease and 30 min session wall bound.

## Preserve state and recover safely

Use SQLite's online backup API for a consistent backup while WAL is active; copying only the main SQLite file during writes is unsafe. Retain compiled-model assets and engine versions with exported integration states. Old reaching/cloth snapshots remain readable through their dedicated adapters; cross-version or model-hash mismatches fail rather than silently reconstructing different physics.

Frontend rollback is reversible by assigning the two demo aliases to a verified prior immutable Vercel deployment. Inspect Vercel history and its recorded acceptance evidence first; do not delete a project or change the company site. Backend rollback requires a consistent DB backup and explicit schema/state compatibility review. Shutdown/restart may fail active jobs honestly; it must not manufacture completion.
