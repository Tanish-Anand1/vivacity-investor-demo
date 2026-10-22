# Vivacity — The One

The Isabella Labs opening is a **7.500-second authored film**, rendered offline from a deterministic Three.js scene. One metallic cube connects a Panda arm, a divided industrial hall, four alternative states, and the Vivacity identity. The verified production deployment is available at <https://demo.tryvivacity.com/>. The homepage and experiment interfaces are preserved.

This is brand cinematography, not experiment footage or proof of a grasp. The arm uses actual MuJoCo forward kinematics over authored joint trajectories. The cube is explicitly attached until release, deliberately suspended, then follows a calculated gravity arc. The architectural transformation is authored. The film does not generate or display scientific results.

## Locked timeline

| Time | Action |
| --- | --- |
| 0.00–0.80 s | Macro approach and gripper closure around the machined cube. |
| 0.80–2.20 s | Pull back into the hall; the hero Panda and three background arms move in staggered synchronization. |
| 2.20–3.05 s | Suspended cube, deliberate silence, then a gravity arc onto the contact plinth. |
| 3.05–4.65 s | A straight seam separates the contiguous hall into the original and three alternate states. |
| 4.65–5.55 s | Hall sections retract; their structural V rails converge on one tip and the cube. |
| 5.55–6.50 s | A physical shutter uncovers the extruded VIVACITY wordmark beneath the rails. |
| 6.50–7.50 s | ISABELLA LABS / BY VIVACITY appears; the rails part and a central mask reveals the mounted homepage. |

`frontend/cinematic/theOneStage.ts` owns the camera keys, materials, lighting, architecture, and choreography. It uses time-aware cubic Hermite camera interpolation with monotone tangent limits. Portrait has its own camera positions, world arrangement, and identity scale. There are no randomized camera or particle effects. The source can seek deterministically to any media time.

The aperture opens from 6.98 to 7.50 seconds. This is a **video-to-DOM transition**, not one camera shared by the film and homepage. The last encoded frame is at 7.483 seconds. At 7.500 seconds the live homepage supplies the image; a final video frame is not a homepage screenshot.

## Runtime and reusable contract

`frontend/src/openingConfig.ts` separates lab identity and media prefix from the shared sequence. `LabOpeningConfig` contains the lab ID, name, subtitle, asset prefix, landing route, accent, camera preset, version, and homepage focus selectors. Only Isabella is implemented. Another lab needs its own authored scene and encodes; changing a string does not create a new film.

`LabOpening.tsx` selects landscape or portrait at mount and uses `object-fit: contain` to preserve composition. Portrait devices at 600 px or narrower, data saver, and slow connection hints select a lighter rendition. Rotating across the aspect breakpoint exits to the homepage instead of swapping shots midway.

- Each play starts muted. **Sound** requires a visitor gesture.
- **Skip intro** and **Escape** reveal and focus the existing homepage.
- Each homepage load, including refreshes, starts the opening again. **Skip intro** or **Escape** dismisses only that playback; it never creates a persistent skip preference.
- `/?intro=replay` explicitly requests playback and remains useful for sharing/reviewing the opening.
- Reduced motion bypasses playback, including explicit replay. Enabling it during playback exits immediately.
- Playback does not depend on browser storage, so storage restrictions cannot block the page or change refresh behavior.
- Homepage input is inert while the film owns focus. Completion restores input, scrolling, and focus. The intro never starts an experiment.
- Metadata arrival requests playback; `canplay` is also supported. A download with no metadata exits after 2.3 seconds. A metadata-ready decoder has a bounded 5 seconds total to start. Media errors and autoplay refusal also exit safely.
- Actual media completion owns the normal ending. A 15-second playback watchdog recovers a stalled decoder. Listeners, timers, and animation callbacks are released on unmount.

Development-only `/?introDebug=1` exposes a film-time scrubber. It is excluded from production. The source authoring page is `/cinematic/` on Vite, not a production application route.

## Assets and provenance

The detailed Panda mesh is the existing compiled Menagerie mesh in `frontend/cinematic/generated/panda.json` and `panda.bin`. Its model revision and Apache-2.0 license are recorded in `assets/PROVENANCE.md` and `frontend/public/vivacity/cinematic-licenses/`. All four arms are Panda instances; the film does not claim to depict four different robot models.

`scripts/build_the_one_poses.py` produces 451 poses from the vendored Panda MJCF. The exporter checks joint limits, self-penetration, and cube attachment. Its output is versioned in `frontend/cinematic/generated/the-one-panda-motion.json`. These checks validate authored kinematics, not dynamic grasp stability.

The 3D wordmarks use Instrument Sans from the official Google Fonts repository: <https://github.com/google/fonts/tree/main/ofl/instrumentsans>. The source TTF, SIL OFL license, and generated outlines are in `frontend/cinematic/fonts/`. The original mechanical soundtrack is generated by `scripts/build_the_one_audio.py`; there is no licensed music sample or external font request in the film player. No paid assets or rendering service were used.

## Reproduce

Use the repository's existing Python and Node environments. Font rebuilding also needs two build-only packages; they are not backend runtime dependencies:

```powershell
.venv\Scripts\python.exe -m pip install fonttools==4.67.0 skia-pathops==0.9.2
.venv\Scripts\python.exe scripts\build_the_one_poses.py
.venv\Scripts\python.exe scripts\build_the_one_font.py
.venv\Scripts\python.exe scripts\build_the_one_audio.py
cd frontend
npm ci
npx vite --host 127.0.0.1 --port 5181 --strictPort
```

Keep the authoring server running. In another PowerShell terminal, from the repository root (FFmpeg/ffprobe must be on PATH):

```powershell
cd frontend
node node_modules/typescript/bin/tsc --project tsconfig.cinematic.json
node cinematic/check.mjs
node cinematic/render.mjs preview landscape
node cinematic/render.mjs preview portrait
node cinematic/render.mjs film landscape
node cinematic/render.mjs film portrait
cd ..
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\encode_the_one.ps1
cd frontend
npm run build
npx playwright test --config playwright.opening.config.ts
```

The browser suite starts an isolated production preview on port 5178. The opening does not require a Python backend. To inspect the compiled app manually:

```powershell
# From frontend; use a different free port if the tests are running.
npx vite preview --host 127.0.0.1 --port 5178 --strictPort
node cinematic/verify-live.mjs http://127.0.0.1:5178/
node cinematic/record.mjs
node cinematic/check-high-renditions.mjs
```

Open `http://127.0.0.1:5178/?intro=replay`. Run the verification commands in a second terminal while preview stays running. They make real HTTP requests without replacing the films. The recorder captures both lite renditions and the actual homepage handoff; the high-rendition check decodes both 60 fps films. Passing the deployed URL is a separate release verification step, not evidence that this local candidate is deployed.

Build the review sheets after actual browser homepage captures:

```powershell
.venv\Scripts\python.exe scripts\inspect_the_one.py --require-homepage `
  --homepage-landscape artifacts/the-one-browser-home-landscape.png `
  --homepage-portrait artifacts/the-one-browser-home-portrait.png
```

The first eight tiles decode the delivered MP4 at 0.40, 1.40, 2.65, 3.65, 4.40, 5.10, 6.00 and 6.90 seconds. The ninth is the actual browser homepage after media time 7.50. Missing browser evidence produces an explicitly pending tile and fails `--require-homepage`; a dark video frame is never substituted for the working application.

## Encodes and evidence

| File in `frontend/public/vivacity/` | Resolution | Frames / rate | Bytes |
| --- | --- | --- | --- |
| `the-one-isabella-landscape.mp4` | 1440×810 | 450 / 60 fps | 5,095,243 |
| `the-one-isabella-portrait.mp4` | 720×1280 | 450 / 60 fps | 3,977,039 |
| `the-one-isabella-landscape-lite.mp4` | 960×540 | 225 / 30 fps | 1,346,537 |
| `the-one-isabella-portrait-lite.mp4` | 540×960 | 225 / 30 fps | 1,445,615 |

All four files are H.264/AAC, fast-start, and exactly 7.500 seconds according to ffprobe. The soundtrack is 48 kHz stereo, peak −11.75 dBFS with no clipping. Offline frame capture took 34.845 seconds for landscape and 35.257 seconds for portrait on this machine; those are render times, not client playback or backend performance claims.

Current test totals, initial failure history, and release status are in `IMPLEMENTATION_STATUS.md`. Evidence includes `artifacts/the-one-source-check.json`, `artifacts/the-one-browser-tests.json`, encoded contact sheets, and browser journey recordings. The initial failed test artifact is preserved alongside the subsequent corrected run.

The initial Vercel release `dpl_AE2ojDarMpsouHFfPSirfBnL1GJV` was superseded on
2026-10-22 by `dpl_He1JeBQxtrqdQi1f5M8fHL18V897`, now assigned to
`demo.tryvivacity.com`. On the live site, a browser check with standard motion
enabled confirmed the film appears on load, **Skip intro** dismisses it for that
visit, and a subsequent full refresh starts the film again. The check's
browser-reported media time was already greater than zero on both loads. The
browser originally had reduced motion enabled; that preference was restored
after verification, and the site correctly bypasses autoplay while it is set.
The prior release's production health, mobile, and full-playback checks are
recorded in `IMPLEMENTATION_STATUS.md` and the `artifacts/the-one-live-*` files;
they were not repeated for this playback-policy-only change.

## Limits

The world is stylized machined architecture rendered by Three.js, not a photorealistic Blender/Cycles film. MuJoCo supplies arm kinematics; it does not simulate the suspended cube, architecture, or logo. The film-to-homepage mask does not establish shared physical continuity with the homepage workcell. Media duration is exact; network and decoder delays can extend wall time or trigger safe early exit. Real Safari/iOS and Firefox acceptance is not yet established. Existing large application chunks and backend availability are outside this opening-only change. No new full physics regression is claimed.
