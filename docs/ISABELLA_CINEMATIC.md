# Isabella Labs opening film

The homepage opening is a 7.5-second, 60 fps, pre-rendered Three.js film. It uses one continuous, deterministic camera path through an authored robotic workcell. Its robot motion, shared object, branching imagery, and soundtrack are **motion design**. They are not MuJoCo experiment output or evidence of a grasp. The interactive lab and its recorded measurements remain separate.

## Shipped behavior

- `/` plays the film on every page load and reload, including when a previous visit wrote the old intro-complete storage flag. Other routes do not play it.
- Desktop/wide screens receive a 1440×810 H.264/AAC file; portrait screens receive a separately composed 720×1280 file. Both contain 450 frames and last 7.500 seconds. Browser data-saver or a reported 2G/3G connection selects a lighter 30 fps rendition at 960×540 or 540×960. The soundtrack starts muted and can be enabled by the visitor.
- Escape or **Skip intro** opens the homepage immediately. The two visible controls stay keyboard-accessible while the homepage is inert. Focus moves to the homepage main element at completion.
- Reduced-motion visitors enter the homepage directly. If playback fails or media cannot become playable within 2.3 seconds, the homepage appears rather than remaining behind a blank film surface.
- The final camera move reveals the actual homepage through a 0.5-second spatial wipe. The homepage and its recorded-scene poster are mounted underneath throughout; the expensive live 3D preview starts after the film finishes. No extra loading page is inserted.

## Models and provenance

Four arm visual models are compiled from this repository's MuJoCo Menagerie assets: Franka Panda, KUKA iiwa 14, UFactory xArm7, and Universal Robots UR5e. See `assets/PROVENANCE.md` and the matching license texts in `frontend/public/vivacity/cinematic-licenses/`.

The Unitree G1, Unitree H1, and Berkeley Humanoid visual models were compiled from `google-deepmind/mujoco_menagerie` at revision `cda5236f98383f6fbaa4820c6b18dba892cd087f`; their BSD-3-Clause licenses are included in the same license directory. The film export includes visual geometry only. It does not bundle those model source files into the browser build.

## Rebuild

With this repository's Python environment, Node dependencies, FFmpeg, and a checkout of `google-deepmind/mujoco_menagerie` at revision `cda5236f98383f6fbaa4820c6b18dba892cd087f` containing the three humanoid folders:

```powershell
$menagerie='C:\path\to\mujoco_menagerie'
.venv\Scripts\python.exe scripts\build_isabella_cinematic_assets.py --menagerie $menagerie
.venv\Scripts\python.exe scripts\build_isabella_cinematic_audio.py
cd frontend
npx vite --host 127.0.0.1 --port 5181 --strictPort
node cinematic\render.mjs preview landscape
node cinematic\render.mjs preview portrait
node cinematic\render.mjs film landscape
node cinematic\render.mjs film portrait
cd ..
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\encode_isabella_cinematic.ps1
```

Run the Vite authoring server in a separate terminal while rendering. The renderer's output is under `artifacts/isabella-cinema-*`. The encoding script uses FFmpeg at 60 fps with `libx264`, `yuv420p`, AAC 128 kbps, `-t 7.5`, and `-movflags +faststart`, then derives the smaller renditions. Authoring geometry lives in ignored `frontend/cinematic/generated/` and is not deployed. No runtime WebGL context is created by the opening.

## Visual QA

The eight mandatory inspection frames are in `artifacts/isabella-cinema-preview-{landscape,portrait}/` at 0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, and 7.5 seconds. `contact.png` in each directory provides an overview. Browser acceptance tests verify film decoding, source selection, elapsed duration, reload behavior, keyboard/sound/skip, a blocked-media fallback, and the homepage handoff.

## Known creative limits

The reflective-object passage and branch duplication are authored geometric cues, not ray-traced mirror imagery or physics outcomes. The four arm actions are deliberately choreographed; they are not controlled by the lab planner. The homepage itself is unchanged by this release, so the film-to-home transition uses a spatial wipe rather than a shared live 3D camera. The film is intentionally available only for the intro and is not a substitute for the interactive simulation.

The media clock is exactly 7.500 seconds, while wall-clock handoff depends on browser startup and decoding. Local headless Chrome measurements ranged from 7.65 to 8.29 seconds. The runtime favors showing the film's ending over cutting a delayed decode; if the file cannot become playable within 2.3 seconds, it reveals the homepage early.
