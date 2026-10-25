# Frontend release and free-GPU research evidence — 2026-10-25

This is a verified frontend update and a research checkpoint, not the complete
Physical Truth release. No new paid resources or Fireworks calls were used.
Unrelated files in the main checkout and existing local test reports were preserved.

## Public deployment

- Public URL: https://demo.tryvivacity.com
- Frontend source: `d2519c390962ed6aa5b3cbb68d192db82cf968c7`.
- Production deployment: `dpl_2ddoDynjdVt58puBYK4KGTw7wh9w`.
- Immutable URL: https://vivacity-demo-agsowxzkz-tanishs-projects-66633ee2.vercel.app
- Existing production backend: https://isabella-labs-runtime.onrender.com
- Backend was not replaced by experimental controller code.
- Rollback deployment: `dpl_phwPDqXn5DGE9qT737E6N4qhF1So`,
  https://vivacity-demo-oo03cgchu-tanishs-projects-66633ee2.vercel.app

The contact page now handles an older runtime's capabilities HTTP 404 by showing
the native model preview and explicitly disabling unavailable experiments. HTTP
403 and transport errors remain errors. No simulation begins on page load.

Real browser inspection exposed a second defect: the sample-panel mount/cleanup
callback cleared the chosen benchmark trial. Selecting a successful candidate
therefore immediately returned to the failed baseline. The explicit “Return to
latest” action is now separate from sample cleanup. Trial status, counts, events,
samples, complete-record export and error messages follow the inspected trial.
The original comparison's cell identity remains unchanged. Project attachment also
uses the inspected run ID.

The next production journey (CI 40168620656) passed selected-run identity but
exposed an incomplete export: only the first 400 samples had loaded, ending at
19.550 s while the actual trial continued to 34.160 s. CSV, sampled JSON and
Discovery exports now stay disabled until sample pagination catches up, with a
visible loaded/total count. The failed report is `public-pagination-failure.json`.
Its six physics trials completed honestly: baseline 0/3, candidate 3/3, 63,691
steps, 672.9963 wall seconds. An export failure is still an end-to-end failure.

The strengthened journey asserts the exact selected trial ID in the UI, CSV,
sample JSON and complete run JSON, including its measured final simulation time
and completed status. Presence of a replay slider alone is insufficient evidence.

## Executed evidence

Overlapping suites must not be added together.

| Check | Measured result | Evidence |
|---|---|---|
| Backend image at `a539ecf` | 536 passed, 3 skipped, no failures/errors | `ci/backend-linux-*.xml`; CI 40166797833 |
| Contact/controller/API suite at `efc966a` | 110 passed, 227.899 s | `ci/contact-tests.xml`; CI 40167824005 |
| Contact browser journeys at `efc966a` | Chromium, Firefox, WebKit passed | CI 40167824005 |
| Native locomotion contract at `a539ecf` | 31 passed, 13.640 s | `ci/native-contract.xml`; CI 40166797799 |
| New native root-velocity checks | 8 passed, 0.697 s | `root-velocity-fixed.xml`; these are included in the 31 above |
| Frontend API, template and settings checks at `d2519c3` | 20 + 5 + 4 passed | `frontend-checks.json` |
| Older-runtime and authorization browser regression | 3 passed | `compatibility-browsers.json` |
| Hosted opening on final deployment `d2519c3` | 17 passed, 87.750 s | `opening-final.json`; CI 40169825355 |
| Strengthened final production journey | 2 passed, 780.121 s; replay/CSV/sampled JSON/complete-record identity and mobile checks | `production-final.json`; CI 40169825355 |
| Local production journey before stronger replay assertions | 2 passed, including mobile | `production-before-replay-fix-test.json` |
| Concurrent hosted experiment request | Correctly rejected by the existing single-worker admission limit with HTTP 429; journey failed | `public-first-worker-busy.json` |

The final deployed journey is green at
https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40169825355.
It ran the standalone measured drop and comparison
`7269d2cd-89cb-44b1-b9ee-ed6e3cce3d09` through the real public UI and backend.
All six comparison trials executed: training baseline 0/2, candidate 2/2;
held-out baseline 0/1, candidate 1/1. Comparison wall time was 699.605844 s,
with 63,691 native steps. The selected candidate remained selected throughout
inspection; CSV, sampled JSON and complete run JSON used its actual run ID.
The sampled export passed the final-time check beyond 30 s; the complete record
reported the selected run as completed. Return to latest cleared inspection.
The mobile journey also passed. These 19 browser checks do not establish the
unimplemented Physical Truth scenarios below.

The local production comparison `e02a8a3f-cec5-40a7-8816-b29ec0c4f334`
completed six genuine native MuJoCo runs in 673.799756 wall seconds. Training:
baseline 0/2, candidate 2/2. Held-out: baseline 0/1, candidate 1/1. Measured step
counts were `[4147, 17080, 4147, 17080, 4149, 17088]` (63,691 total).
Successful durations were 34.160 s for training and 34.176 s held out. The initial
standalone baseline failed with `dropped_object`, as measured. This small sample
is not the required full scenario envelope or evidence of hardware reliability.

Independent manual preview verification completed another six-trial comparison,
paused at 31.300 simulated seconds without state advancement, then resumed.
The versioned benchmark definition downloaded through the real browser.
Production mass editing from 0.06 to 0.09 kg changed measured inertia from
0.0000250 to 0.0000375 kg m² per principal axis and potential energy from
0.4862 to 0.7293 J. Zero mass disabled Apply while retaining the valid world.

Local opening runs initially gave 16/17 twice: first a playback timeout under
heavy memory contention, then Chromium `ERR_NO_BUFFER_SPACE` when loading a
module. The isolated playback repeat passed 3/3. All reports are preserved;
hosted execution passed the full 17-test suite. Its lightweight-film test measured
7.500 s media duration, 7.5425 s wall playback and zero simulation-start requests. A browser holding the previous
deployment's asset graph hit a missing old chunk during promotion; the existing
Reload workspace action recovered the page. No claim of zero deployment churn
or measured real-device dropped-frame targets is made.

## Actual free-GPU work

An available Google Colab Tesla T4 (15,360 MiB) was used without a purchase. The
complete G1, H1 and Apollo models were compiled unchanged. Dependencies are pinned
in `training/requirements-gpu-lock.txt`. Model, contract and source hashes are in
each report. Reports explicitly retain `task_success: false` and no trained policy.

The probe found and corrected an actual CPU sensor-frame mismatch: `mjOBJ_BODY`
uses the inertia frame, while orientation/projected gravity used body axes.
`mjOBJ_XBODY` now supplies the matching body angular velocity. Eight randomized
native MuJoCo tests verify the equivalent free-root velocity transformation.
The state selector also now uses MuJoCo's `Data.where`, preserving Warp's shared
contact workspaces instead of leaking a batched tracer through a generic tree map.

| Probe | Result |
|---|---|
| Initial controller probe (`control-batch-*`) | H1/Apollo observation parity failed; G1 hit `UnexpectedTracerError`. Failures retained. |
| Corrected two-world H1 | Short parity/independence/repeat/frozen-state probe passed; 200 timed physics steps, 531.807 steps/s. |
| Corrected two-world Apollo | Short probe passed with JAX backend; 200 timed steps, 6.507 steps/s; 7,504,924,672 peak host-memory bytes. |
| Corrected two-world G1 | Native parity passed; exact GPU repeatability and bitwise independence checks failed. |
| Deterministic Warp opt-in | G1 and H1 each exceeded the 350-second subprocess budget. Neither is a pass. |
| Eight-world G1 | 8,000 timed steps, 3,870.886 steps/s; no fall within the two-second probe; exact repeat difference 9.6043e-10. Overall strict probe failed. |
| Eight-world H1 | 3,600 timed steps, 3,436.272 steps/s; all eight untrained worlds fell at 450 steps (0.9 s); exact repeat difference 1.7462e-10. Overall strict probe failed. |

The GPU discrepancies are tiny floating-point differences, but exact checks were
not weakened to turn red reports green. Deterministic Warp compilation is an
explicit optional probe. This is experimental training infrastructure; no
locomotion policy was trained, deployed or accepted. Native CPU task acceptance
is still required independently of future GPU training results.

The downloaded complete GPU archive was verified before extraction:
`b3833e94abfc99a43310711418329a3e92ef3e6e3eeafbabe4c18988815833a6`
(1,089,798 bytes). The compact individual reports, including every failure, are
retained under `gpu/`. Full resolver logs and source snapshots remain locally in
`data/frontend-release-20261025/gpu-control-evidence.tar.gz`.

## Evidence integrity

`manifest.json` hashes the committed Git blob bytes. Git may convert text line
endings in a Windows checkout; verify against `git show HEAD:<repository-path>`
(or normalize CRLF to LF for these UTF-8 text files). PNG hashes use raw bytes.

## Reproduce

In the repository's isolated Python environment:

```powershell
python -m pytest --noconftest training/native_tests -q
```

In the pinned Linux GPU environment, using a bounded subprocess:

```bash
python -m training.mjx_probe --robot h1 --batch-size 2 --transitions 10 --output h1.json
python -m training.mjx_probe --robot g1 --batch-size 8 --transitions 100 --output g1-eight.json
python -m training.mjx_probe --robot h1 --batch-size 8 --transitions 100 --output h1-eight.json
# Opt-in compilation can exceed the measured free-GPU budget:
python -m training.mjx_probe --robot g1 --warp-deterministic --output g1-deterministic.json
```

Public verification runs sequentially to respect the backend worker limit:

```powershell
gh workflow run frontend-release.yml --ref codex/physical-truth-runtime
```

The workflow runs the real opening suite and native production experiment
journey, and retains reports/screenshots without uploading authorization headers.

Rollback, only if required:

```powershell
vercel promote https://vivacity-demo-oo03cgchu-tanishs-projects-66633ee2.vercel.app --yes --scope tanishs-projects-66633ee2
```

## Gates still open

Apollo's full cabinet/cartridge cycle; complete-model walking, turning, terrain,
carrying and H1 running; the single-world eight-stage warehouse; perception-driven
task control; app-wide parameter and scenario acceptance; and qualifying durable
hosting with restart/capacity evidence and a 24-hour soak. The free production
service's one-worker rejection, ephemeral storage and possible sleep remain
limitations. Fireworks inference credits do not establish those capabilities.

The cinematic refinement remains deferred. This frontend deployment must not be
presented as completion of those unpassed Physical Truth gates.

Implementation references: [MuJoCo state-selection issue](https://github.com/google-deepmind/mujoco/issues/3377),
[Warp 1.17 deterministic execution](https://github.com/NVIDIA/warp/blob/v1.17.0/docs/user_guide/execution_and_performance/deterministic_execution.rst).
These references explain the APIs; the measured results come from the executed
reports retained here.
