# World Labs spatial pipeline

This extends the existing runtime; Gaussian appearance is never used as rigid-body
physics. MuJoCo still computes actions, contacts, motion and outcomes.

## Implemented interfaces

All workspace routes require `X-Workspace-Token` (32–128 URL-safe characters).
Generation submission also requires an `Idempotency-Key`. Tokens are capabilities,
not accounts. They and provider credentials must never enter public reports.

| Method/path | Contract |
|---|---|
| POST `/v1/workspace/captures?filename=view.jpg` | Raw file body, maximum 16 MiB; PNG/JPEG/WebP or MP4/MOV/MKV. Returns capture ID, SHA-256, bytes, kind and validation scope. |
| GET `/v1/workspace/captures` | This capability's capture metadata, never publicly accessible media bytes. |
| POST `/v1/workspace/generations` | Async request, described below; 202 job record. |
| GET `/v1/workspace/generations/{id}` | Persisted stages, input references, error, provider operation and actual reported cost. |
| POST `/v1/workspace/generations/{id}/retry-retrieval` | Polls an existing failed operation; does not submit another paid world. |
| GET `/v1/workspace/worlds/{id}` | Versioned scene, separate representations, input provenance and readiness. |
| GET `/v1/workspace/worlds/{id}/appearance?quality=100k` | Owned SPZ; 100k or 500k only when present. Omit query for legacy/default asset. |
| GET `/v1/workspace/worlds/{id}/geometry` | Preserved original collider GLB, distinct from bounded preview and physics proxy. |
| GET `/v1/workspace/worlds/{id}/thumbnail` | Actual provider thumbnail, protected and cached privately. |
| GET `/v1/workspace/runs` | Saved execution history, actual evaluations and robustness partitions. |
| POST `/v1/workspace/runs/{sid}/measurements` | Object-position comparison against a recorded branch; 201 calculated report. |
| GET `/v1/workspace/measurement-comparisons` | Persisted owned comparisons. |

Example image request (text uses `input_type: "text"`, `inputs: []`):

```json
{
  "prompt": "A compact robotics laboratory with a clear workbench",
  "provider": "worldlabs",
  "model": "marble-1.1",
  "seed": 19,
  "input_type": "image",
  "inputs": [{"capture_id": "<ID returned by captures>", "azimuth_deg": null}]
}
```

`panorama` requires one 2:1 equirectangular image. `multi-image` takes 2–4 images
of the same scene with optional azimuths in degrees. `video` takes one video.
The server prepares a signed provider upload, uploads without the API key on the
storage request, and references the provider media ID in its documented schema.
No arbitrary browser URL fetching or hypothetical Atlas API is implemented.
Local media validation checks container signatures and bounded image dimensions;
full codec/media decoding belongs to the provider and can still fail.

OpenAI proposes a bounded collision specification from the description, with
at most one correction if validation fails. It does not measure material or mass
from the image. Captures describe observations; the returned 3D scene remains
generated/inferred. Invalid outputs are errors, never clamped into fake results.

## Representations and coordinates

- **Visual:** original SPZ color/covariance/spherical harmonics; Spark 2.3.1 in the
  existing Three.js renderer. The raw Marble OpenCV export rotates −π/2 around X
  into runtime Z-up, applies the returned metric scale and ground-plane offset
  over the workcell ground at Z=−0.8 m. Older laboratory export uses its explicitly
  documented manual appearance transform. Provider scale is not hardware calibration.
- **Geometry:** original GLB preserved and hashed. Preview triangles are bounded
  and may be deterministically subsampled. Diagnostics measure finite/indexed
  triangles, bounds, degeneracy, edge topology and winding of that preview.
  Self-intersections and semantic object separation are not checked. Preview
  watertightness never certifies an unexamined high-resolution source.
- **Physical:** user-configured solid box collision proxy beside the standard
  workbench, plus independently specified robot and dynamic object bodies.
  Splats and unvalidated source meshes never become collision surfaces. A solid
  proxy cannot represent the interior of a concave room. Static-environment mass,
  friction and restitution are unknown; configured values are estimates.

## Rendering

Performance targets 100k LoD splats and DPR 1; Balanced targets 300k and DPR 1.25;
High fidelity targets 500k and DPR 1.5. Lower-memory/fewer-core devices default
to Performance. Targets are view-dependent SDK budgets, not promises about total
GPU memory. A 100k asset loads first; Balanced/High then decode the 500k asset,
keeping the first scene until replacement is ready. SPZ is decoded from the
response stream and its LoD tree is built by Spark's worker. These are discrete
detail upgrades, not RAD chunk paging. Full-resolution SPZ is not requested.

The original single demand-driven Three.js render loop and owned Spark updates
are preserved. Camera/projection changes and SDK dirty notifications drive sorting
and LoD updates. Cleanup aborts fetches, awaits initialization/readback, removes old
meshes and disposes owned resources. Diagnostics expose actual file bytes, load
time, source/tree counts and Three.js resource counts at load completion; they
are not GPU-memory or universal FPS measurements. Failed higher detail retains
the loaded coarse environment. Failed lazy interface chunks expose a reload action.

## Physical variation and measurements

Enable `variation` on a saved pick-and-place configuration and choose 3–8
`randomization_cycles`. First seed is baseline. Subsequent seeds vary object and
destination positions, mass and friction within validated bounds. Preset material
is changed to custom for varied friction so the requested coefficient actually
reaches MuJoCo. Each configuration creates an independent world and replans.
The final `ceil((cycles−1) × held_out_fraction)` seeds are held out in advance.
This is replanning robustness, not a trained policy evaluation. Descriptive rates
use completed measured configurations; unfinished jobs do not become successes.
All-paths-failed configurations remain failures and appear in failure-region reports.
Suggested follow-up conditions are returned for explicit user execution.

```json
{
  "name": "Position, payload and friction comparison",
  "environment_id": "warehouse",
  "operation_id": "pick_place",
  "trial_mode": "fixed",
  "validation_trials": 3,
  "randomization_cycles": 3,
  "variation": {
    "enabled": true,
    "position_radius_m": 0.025,
    "friction_min": 0.15,
    "friction_max": 1.2,
    "mass_min_kg": 0.04,
    "mass_max_kg": 0.1,
    "held_out_fraction": 0.25
  }
}
```

Saved configuration submission/start and existing experiment REST/WebSocket
messages remain documented in `FRONTEND_HANDOFF.md`. Poll
`GET /v1/sessions/{id}` with `X-Session-Token` to renew the session lease;
there is no `/heartbeat` endpoint. Physics remains server-side and supports two
independent native trial workers on this host.

Measurement request:

```json
{
  "experiment_id": "<owned completed experiment>",
  "branch_id": "<recorded branch from that experiment>",
  "source_label": "Camera tracking after external coordinate registration",
  "source_kind": "user_recording",
  "coordinate_system": "runtime_z_up_m",
  "time_offset_s": 0,
  "samples": [
    {"time_s": 0, "position_m": [0.5, -0.15, 0.026]},
    {"time_s": 1, "position_m": [0.5, -0.15, 0.026]}
  ]
}
```

This returns Euclidean position RMSE/maximum/mean residual, displacement, overlap
duration, matched/excluded samples, predictions and input hash. It interpolates
recorded states at supplied timestamps, excludes non-overlap, and never extrapolates.
Times must increase; at most 1,000 samples. `synthetic_reference` explicitly labels
numerical self-reference checks. Source authenticity, robot/contact alignment,
automatic registration and physical parameter fitting are not implemented.

## Reproduction

```powershell
.venv\Scripts\python.exe -m scripts.run_workspace_server
$env:VITE_API_BASE_URL='http://127.0.0.1:8010'
npm --prefix frontend run dev
.venv\Scripts\python.exe -m scripts.verify_spatial_pipeline --generate
.venv\Scripts\python.exe -m scripts.verify_spatial_pipeline --failure --output artifacts/spatial-failure-local.json
node --experimental-strip-types --test scripts/test-spatial-quality.mjs
```

`--generate` makes a real paid provider request, bounded by the server daily quota.
`--resume --generate` retrieves the operation recorded in ignored verification
state without resubmitting it. The sample capture is an actual virtual-scene render,
not a hardware photograph. The simulator itself never runs inside this HTTP probe.
Use the real production base and socket base for deployment verification.

## Capability boundary

| Capability | Status |
|---|---|
| Text and single-image generation, persistence and owned retrieval | Implemented; single-image executed live in this release |
| Multi-image, panorama and video request/upload/UI contracts | Implemented adapters; further live-provider validation required for each modality |
| 100k→500k appearance upgrades and Spark view-dependent LoD | Implemented; browser verification recorded below |
| Original generated collider and actual provider thumbnail | Implemented; retrieved and byte-hashed |
| Preview geometry topology/normals/bounds evidence | Partially implemented; source self-intersection and semantic segmentation unavailable |
| Collision mapping and real robot execution | Implemented conservative proxy/workcell; automatic concave room twin unavailable |
| Seeded position/mass/friction experiments and held-out rates | Implemented; genuine independent MuJoCo executions |
| Object-trajectory measurement comparison | Implemented calculations; supplied real hardware validation required |
| Robot/contact demonstration alignment and automatic calibration | Unavailable |
| Orientation/clutter/initial-joint/visual randomization | Not included in this variation workflow |
| Atlas reconstruction/generation service | Unavailable through the verified public API contract; future adapter access required |
| Durable production accounts and always-on hosting | Unavailable on current capability-based Render Free deployment |

## Verification evidence

Final backend revision `fcfb6f6cc415a7ca664e5557dfa634c1ad146384` passed **261/261 Linux tests** with zero failures, errors or skips, plus **3/3 hard 512 MiB checks**. [Executed CI run](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38426776786); JUnit evidence is in `artifacts/spatial-final-linux/`. Shards executed 92/75/94 tests in 311.464/195.438/347.953 seconds; memory checks took 67.914 seconds. Windows spatial/schema/workspace checks passed 67/67; earlier changed-area checks passed 86/86. All 26 frontend transport/selection/quality checks and TypeScript/Vite/Vercel builds passed.

Public verification on this backend revision executed three independent physical configurations, nine candidate trials plus fresh authoritative executions: **74,867 simulation steps**, 75.585 seconds aggregate experiment wall time, peak two independent physics workers in every experiment. All three configurations succeeded, including the single held-out seed. This is a three-configuration demonstration, not a statistically established success rate. Replay returned 250 frames; native WSS delivered 12 events. A separate weak-grip run genuinely failed all three configurations and retained those failure regions; it returned 104 replay frames and nine WSS events. Recorded self-reference measurement comparison returned position RMSE 0 m; this verifies interpolation, not hardware alignment.

The browser submitted a real image generation and saved world `aec0bc04-e661-45ab-a3c6-ed764963f446`, operation `a18240bf-21fd-49e7-89c0-56ff06650462`, with the actual provider-reported 1,580 credits. Its image was our virtual warehouse render, explicitly described as such. Input SHA-256, provider media ID, collider evidence and separate uncalibrated physics mapping are recorded in `artifacts/spatial-public-generation.json`. A separate local image generation, owned original collider/100k/500k/thumbnail byte hashes and actual physics executions are in `artifacts/spatial-live-local.json`.

The first local and first public generation attempts failed during OpenAI scene validation, without a World Labs submission or fake world. The reproduced issue was fixed by putting position/size/dimension bounds into the provider's structured schema and retaining one bounded correction. A fresh real OpenAI call passed (`artifacts/spatial-provider-schema-live.json`), followed by successful browser generation. A local verification-client connection interrupted polling once; it resumed the recorded operation without submitting a new paid generation.

Public HTTP uses the actual same-origin rewrite, WSS connects directly to Render, and all **55 OpenAPI paths** match `openapi.json`. A 5 MiB container-signature upload crossed the public rewrite and was persisted with its real byte count. It was deliberately a container-boundary test, not a valid decoded video or successful video generation.

Rendering audit found and fixed hidden active previews and recursive idle collection. The corrected LoD signature includes SDK generator/mapping versions, and teardown awaits sorting plus the public LoD worker barrier. One idle local measurement observed 0.112 seconds of browser main-thread task time over 79.527 seconds, 0.042 seconds script time and a 17,075,236-byte JS heap at the final sample. Those figures are device-specific and exclude total GPU/worker memory. Generation mode had zero mounted canvases. The public generated environment rendered with the real Panda; gallery framing now uses an interior eye height anchored to the aligned workcell ground rather than outlier splat bounds. Large Spark/Three bundles remain a cold-load cost (~901 KiB/~262 KiB gzip).

Evidence: `artifacts/spatial-live-public-final.json`, `artifacts/spatial-failure-public-final.json`, `artifacts/spatial-upload-boundary.json`, `artifacts/spatial-public-openapi.json`, browser screenshots and acceptance record. Multi-image/panorama/video provider contracts passed isolated tests; each still needs its own full live generation. Source self-intersection checks, automatic segmentation/calibration, hardware prediction and Atlas access remain unavailable.

## Public investor journey and release identity

The public browser created a world from an uploaded virtual warehouse image,
loaded the actual generated splats and real Panda model, saved a named variation
configuration, explicitly started the experiment, paused/resumed native execution,
and exported recorded physics. Loading/reloading stayed idle. The clock remained
exactly 6.694 s across the acknowledged pause. The three generated-world conditions
completed with 3/3, 2/3 and 2/3 feasible candidate validations, followed by three
successful fresh executions; placement errors were 1.062/1.098/2.958 mm. This run
integrated 74,855 steps. Its wall time includes the deliberately long pause.
Actual executed masses were 0.060/0.092194/0.082964 kg and sliding friction was
1.000/0.560639/1.111149. Comparison rows now show each executed condition, rather
than repeating the initial run mass. Full evidence: `artifacts/spatial-public-ui-run.json`
and `artifacts/spatial-public-ui-export.json`.

Five repeated public warehouse/laboratory switches completed without JavaScript
errors. At 500k load completion, geometry count stayed at two and texture counts
were 9–11; these are load-time resource samples, not total-memory certification.
Performance, Balanced and High fidelity were exercised. A deliberately blocked
500k download preserved its real coarse splats; unblocking and changing quality
retrieved 500k and cleared the warning. The test initially exposed a stale warning,
which was fixed and rechecked. Mobile/reduced-motion testing at 390×844 measured
390 px document width with the Enter workspace action available. Test emulation
and network blocks were cleared. The remaining cold-load bundle cost is documented
above. No claim is made about every GPU/device or long-duration memory behavior.

A frontend release while an old tab retained old lazy chunk URLs triggered the
new recovery boundary; Reload workspace recovered and the saved server run remained
accessible. The final release is verified after reload. Normal world switching had
no errors; deliberate network/release faults are distinguished from normal operation.

Backend source: `fcfb6f6cc415a7ca664e5557dfa634c1ad146384`, Render deployment
`dep-db75f60m7kps73c3b4ng`, Live (53.2 s deployment). Frontend source `6e01c10`,
Vercel deployment `dpl_fw4Z5Wf9EvtAHgewwxfkfdr5XmSx`; exact identities and final
matching-HTML verification are in `artifacts/spatial-release-identity.json`.
The final live result screenshot is `artifacts/spatial-public-final.jpg`.
Both public aliases return identical HTML and the live 55-path contract matches
the exported specification. The public workspace was reset to 0.000 s with Start
available; old results are explicitly marked as belonging to the previous state.
Render Free still sleeps and loses local files on deployment;
this release does not create paid always-on or persistent-disk hosting.

## Sources checked

Generation/upload/asset formats follow the [official World API](https://docs.worldlabs.ai/api)
and [prepare-upload contract](https://docs.worldlabs.ai/api/reference/media-assets/prepare-upload).
LoD/stream inputs follow [SplatMesh](https://sparkjs.dev/docs/splat-mesh/) and
[SparkRenderer](https://sparkjs.dev/docs/spark-renderer/).
The [real-to-sim research](https://www.worldlabs.ai/blog/real-to-sim-to-real),
[world-model taxonomy](https://www.worldlabs.ai/blog/taxonomy-of-world-models),
[Spark announcement](https://www.worldlabs.ai/blog/spark-2.0),
[World API announcement](https://www.worldlabs.ai/blog/announcing-the-world-api),
[3D-as-code article](https://www.worldlabs.ai/blog/3d-as-code) and
[Atlas research](https://www.worldlabs.ai/blog/atlas) inform the boundaries above;
they are not evidence that Vivacity implements their research capabilities.
