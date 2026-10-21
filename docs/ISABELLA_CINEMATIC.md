# Isabella Labs: The Impossible Shot

The opening is a 7.500-second, 60 fps, offline-rendered Three.js film. A single authored clock drives the camera, robot poses, metallic cube, architecture, and identity reveal. It is motion design, **not** MuJoCo experiment footage or evidence of a physical grasp. The interactive laboratory and measured experiment results are separate.

## Story and delivery

| Time (s) | Beat | Authored action |
| --- | --- | --- |
| 0.00–0.60 | Ignition | A close view of the machined cube and Panda gripper emerges from darkness. |
| 0.60–1.40 | First transfer | The camera pulls back with the Panda and the cube. |
| 1.40–2.20 | Chain reaction | An enlarged UR5e, a custom parallel-delta mechanism, and an xArm7 receive the same cube in rapid succession. |
| 2.20–3.00 | Impossible setup | The cobot places the cube above a plinth; the cube hangs briefly. |
| 3.00–4.10 | World breaks | The cube descends; floor, walls, ceiling, and large structural slabs shear along authored axes. |
| 4.10–5.10 | Possibility space | The camera passes a single layered alternate workcell with robot and humanoid imagery. |
| 5.10–6.10 | Identity | The geometry aligns to reveal an in-scene **ISABELLA LABS / BY VIVACITY** wordmark. |
| 6.10–7.50 | Handoff | The camera advances through the architecture while a portal mask reveals the already-mounted homepage. |

The four arms use three compiled MuJoCo Menagerie visual meshes (Panda, UR5e, xArm7) and one authored delta mechanism. The alternate scene also uses Unitree H1 visual geometry. The UR5e is enlarged and enclosed to read as a heavier arm; it is not a distinct heavy industrial robot model. Visual mesh license notices are in `frontend/public/vivacity/cinematic-licenses/`; source provenance is in `assets/PROVENANCE.md`. The film's kinematic choreography and impossible architecture are deliberately stylized. The renderer uses no experiment outputs.

The homepage plays the introduction again on reload. Playback starts when the chosen file becomes playable, so network delay is outside the seven-and-a-half-second film. Desktop uses 1440×810 landscape H.264/AAC; portrait uses separately framed 720×1280. Narrow or data-saver devices receive 30 fps lighter renditions. The soundtrack begins muted; Sound, Skip, and Escape are available. Reduced-motion visitors go straight to the homepage. If media fails or cannot start within 2.3 seconds, the homepage becomes usable. The homepage stays mounted underneath and no experiment starts on load.

The film contains 450 frames. The frame at 7.500 seconds is the real homepage, because the final video frame occurs at 7.483 seconds. The portal opens over the last 0.75 seconds. The homepage is reactivated and focused when the media ends. A 15-second wall-clock safety exit handles a decoder that stops advancing. The authored source can be scrubbed at exact timestamps; in development, `/?introDebug=1` exposes a playback scrubber.

## Rebuild and inspect

The four visual mesh manifests and binaries used by the authoring renderer are versioned in `frontend/cinematic/generated/`. Regeneration requires a compatible MuJoCo Menagerie checkout and this repository's Python environment. With Node dependencies, FFmpeg, and the authoring server on port 5181:

```powershell
.venv\Scripts\python.exe scripts\build_isabella_cinematic_audio.py
cd frontend
npx vite --host 127.0.0.1 --port 5181 --strictPort
```

In another terminal:

```powershell
cd frontend
node cinematic\check.mjs
node cinematic\render.mjs preview landscape
node cinematic\render.mjs preview portrait
node cinematic\render.mjs film landscape
node cinematic\render.mjs film portrait
cd ..
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\encode_isabella_cinematic.ps1
.venv\Scripts\python.exe scripts\inspect_isabella_cinematic.py
```

`check.mjs` verifies deterministic seeking and cube position continuity across 451 samples. `inspect_isabella_cinematic.py` extracts the **encoded** frames at 0.30, 0.90, 1.80, 2.60, 3.50, 4.60, 5.60, 6.50, and 7.45 seconds, then writes landscape and portrait contact sheets under `artifacts/isabella-cinema-encoded-*/contact.png`. The true 7.50-second homepage state is captured by the browser test in `artifacts/isabella-cinema-runtime/homepage-after-7_5s.png`.

## Verification and limitations

The source check passed: 451 samples, identical frame after seek, and a maximum cube displacement of 0.206 m between adjacent 60 fps samples. Both main encoded films contain 450 H.264 frames, AAC audio, and report exactly 7.500 seconds via `ffprobe`. The production Vite build passed. The browser regression result and production deployment are recorded in `IMPLEMENTATION_STATUS.md` after release verification.

The cinema is a video-to-DOM handoff with a mask, not a shared live 3D camera. The last encoded frame on its own is dark; the homepage beneath the widening mask supplies the final visual. Heavy-arm scale, contact, depth of field, and architectural mechanics are art-directed rather than physically simulated. A cold or constrained connection can show the homepage before the film if the media load exceeds the 2.3-second fallback. Under slow decoding the 7.5-second media clock can take longer in wall time; the 15-second safety exit favors a usable homepage over a stalled opening.
