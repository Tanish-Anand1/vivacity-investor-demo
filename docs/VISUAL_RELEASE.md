# Vivacity visual correction

The workspace opens on a real World Labs warehouse appearance and an idle,
measured Panda workcell. Experiments start only when the user requests them.
The robot, gripper and movable part use MuJoCo body transforms. Appearance is
not a prerecorded video or a fabricated physical outcome.

## Asset pipeline

The earlier renderer flattened the provider collider into sampled gray
triangles. It was displaying collision data as the finished world. World Labs
returns separate colored Gaussian splats in SPZ format. The corrected pipeline
retains those bytes and renders their colors, opacity, covariance and spherical
harmonics using Spark 2.3.1. Gaussian appearance has baked lighting; it is not
an automatically relightable PBR facility model.

Provider documentation: [asset outputs](https://docs.worldlabs.ai/api),
[SPZ coordinates](https://docs.worldlabs.ai/api/rendering-spz),
[Spark](https://sparkjs.dev/docs/).

The new warehouse was actually generated with `marble-1.1`:

- Provider world: `1eec9556-2690-44db-aaf5-08cc57e31997`.
- Operation: `b3f64ac6-556f-4331-99e3-2f4b4ff234fc`.
- Reported provider cost: **1,580 credits**.
- SPZ bytes: **7,421,219**; 500,000 splats.
- Provider scale: `1.7335340976715088`.
- Provider ground offset: `1.0082917213439941`.
- Original color data is rendered; the collider is retained separately.

The earlier laboratory export is 4,829,370 bytes and omits provider scale
metadata. Its curated visual scale and ground alignment are explicit in
`vivacity/visual_catalog.json`; they are not inferred physical measurements.
When metadata exists, centers and Gaussian sizes use the reported scale.
The documented raw OpenCV rotation is applied separately, followed by conversion
into the runtime's Z-up coordinates. The old Y-up export uses its explicit
legacy calibration.

Standalone validated GLB uploads now retain their original embedded resources.
The frontend's GLTFLoader preserves node transforms, UVs, PBR materials and
embedded textures. Static OBJ/STL and older imports retain the existing triangle
preview. External network textures, animation, skins and GLTF extensions remain
unsupported and are rejected by the server parser. ZIP visual material bundling
is not added in this release.

## API addition

`LibraryWorld.appearance` is optional; existing simulation contracts are retained.
It describes `format: spz | glb`, quality, semantics and metric-scale provenance.
Curated appearances contain a `url` relative to the frontend origin. Generated
and imported appearances contain no signed provider URL.

```http
GET /v1/workspace/worlds/{world_id}/appearance
X-Workspace-Token: <existing browser workspace capability>
```

The response is the actual binary asset, with private caching and `nosniff`.
SPZ uses `application/octet-stream`; GLB uses `model/gltf-binary`. The backend
validates ownership before serving or retrieving bytes. Provider credentials
and signed storage URLs stay on the backend. Missing/invalid assets produce
an error; the renderer does not replace a failed World Labs world with boxes.

## Rendering and interaction

- One React Three Fiber loop owns each viewport; Spark does not start another
  animation loop. Its asynchronous updates are owned and awaited before GPU
  target disposal. Empty/loading splat collections are cleared without sorting
  nonexistent targets.
- Camera reset updates the existing controls and camera; it does not remount
  the Canvas. Source bounds guide framing; SPZ interior cameras remain near the
  provider capture origin rather than moving outside a room because of outliers.
- Orbit, right-button pan, wheel zoom and keyboard arrows/+/minus/R remain
  available. Reset camera is outside the scene image.
- Object dragging, change conditions, actual run/pause/resume/stop, measured
  results, downloads, API replay and execution logs retain their runtime paths.
- The four-stage configuration panel shows environment, robot, operation or
  experiment parameters. It no longer shows all controls at once.
- The catalogue keeps model preview, name, manufacturer, DOF, nominal payload
  and reach visible. Runtime scope and manufacturer references are secondary.
- Warehouse and laboratory are the curated visual environments. Other existing
  presets remain available under **Show simplified collision fixtures**.
- The workbench is an authored beveled tabletop and slotted extrusion frame;
  its top surface matches the existing MuJoCo table. Trim and legs are appearance
  details, not additional validated collision bodies.

## Physical limits

The rendered warehouse racks and laboratory cabinetry are visual context.
Physics uses the independently declared standardized workbench and collision
primitives. Generated concave facilities are still represented by an explicitly
mapped conservative box, not a complete reconstructed collision twin. This
release does not claim otherwise. Only two polished environments are curated;
automotive, cleanroom and other full facility assets are not delivered.

Hardware nominal payloads are manufacturer reference values, not evidence that
the demo supports those payloads. Existing object/control bounds still apply.
Cloth remains fixture-assisted; dual Panda still executes with its primary arm.
Render Free can sleep and its SQLite filesystem is ephemeral. No hosting tier
or billing change is made by this visual release.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts/run_workspace_server.py
```

In a second terminal:

```powershell
$env:VITE_API_BASE_URL='http://127.0.0.1:8010'
cd frontend
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort
```

Build: `npm --prefix frontend run build`.
Contract export: `python scripts/export_openapi.py`, then
`npm --prefix frontend run generate:api`.
Scoped checks: `python -m pytest tests/test_visual_assets.py tests/test_imports.py tests/test_workspace.py -q`.
Real provider verification: `python scripts/verify_visual_generation.py` creates
one actual paid-credit generation. `--resume` only retrieves the recorded job;
it never submits a replacement generation.

Release evidence and production verification are appended below after execution.

## Executed checks (2026-10-13)

- Linux release image: **201 passed, 0 failures/errors/skips**, 854.882 seconds.
- Same image constrained to 512 MiB: **2 passed**, 65.424 seconds.
- Source: backend commit `4a6595801f112df76647d248d89d60c2e5c0f835`.
- GitHub run: `38380104648`; exact JUnit files in `artifacts/visual-linux-release`.
- Windows workspace/import/visual regressions: **60 passed**, 133.91 seconds.
- Frontend selection checks: **5 passed**; response boundary checks: **4 passed**.
- Eight consecutive laboratory/warehouse switches: no new Runtime.exceptionThrown
  events after the renderer fix; both appearances subsequently rendered.
- Actual GLB upload/map/download/render via the UI: embedded colored texture
  rendered; no new browser exception. Its 1,616-byte material fixture is an
  import verification asset, not a fabricated generated environment.
- Local real Panda workcell execution: 5 physical validations completed; measured
  best placement error 1.1 mm, with grasp and retention verified.
- Robot catalogue selection initialized a real UR5e world in the warehouse.
  Four contextual stages remain available; selection does not start experiments.
- Width 390 emulation: no horizontal document overflow after the navigation gap
  fix; one Canvas, primary controls measured 44 px high. This is a browser-width
  check, not a physical phone or screen-reader certification.
- Build and type checks passed. Spark's WASM/renderer chunk remains roughly
  899 KiB gzipped plus the separate Three vendor chunk; a Vite chunk-size warning
  remains. Three's Clock deprecation warning remains in the dependency stack.

The restart check also exposed a client bug: a legitimate JSON null from the
optional live-state endpoint was classified as an unreadable response. The
response parser now distinguishes null from malformed JSON, with four executed
regression checks.

## Production verification

Backend Render deploy `dep-db709l7f3r2c73cp4bm0`, source `4a65958`, is live.
The frontend is live at https://demo.tryvivacity.com/. Final Vercel deployment
is `dpl_3e8iQH1bMyjDhtBtvRHSZ24NqUsq`, frontend source `a1df0d4`.

Real UR5e HTTP/WSS verification used experiment
`9f46fe0e-c87c-4db3-9d3f-1a6b7612fb42`: three measured validations, successful
fresh execution, twelve event messages, validated replay/export, invalidation
and new physics computation. Total probe wall time was 74.781 seconds; replay
was 2,311,295 bytes. Both public SPZ assets matched their original bytes and
SHA-256 hashes exactly.

A fresh production load showed Ready to start without an experiment. Production
Panda Start, Pause, Simulation paused, Resume and Task verified completed five
real validations. Best displayed measured placement error was 1.1 mm. The
browser error log was empty. Alternative results now keep their metrics compact
until selected. Visual generation explicitly uses the verified Marble 1.1 model
and discloses its consumption of provider credits.

Evidence: `artifacts/visual-public-runtime.json`, `visual-public-assets.json`,
`visual-real-generation.json`, JUnit reports and production screenshots.

Final production checks also exercised alternative-result expansion and keyboard
orbit/pan followed by camera reset. `visual-public-final.jpg` shows the completed
live workspace. The final code release is committed; unrelated untracked work
was preserved.
