# Model-matched locomotion development

This directory is an isolated research environment. No trained policy exists for
the complete tool-equipped embodiments yet. Nothing here is used by the API
image, and no GPU resource has been purchased.

## Native policy contract — executed 2026-10-24

`locomotion_contract.py` and `native_locomotion.py` now provide the CPU reference
for the complete tool-equipped embodiments. The action/observation sizes are
G1 **43/138**, Apollo **36/117**, and H1 **23/78**. The manifest binds named joints,
units, joint ranges, native actuator types, force limits and action scaling to
the compiled-model hash. It does not reuse the ten-actuator H1 mapping.

The actor accepts only explicit joint/IMU observations, a bounded velocity
command and its previous action. Absolute world positions and evaluator contact
measurements do not enter the actor function. Position servos retain their native
force clamps; direct motors receive bounded PD torque commands. Every environment
step advances native MuJoCo through `data.ctrl`. Full integration checkpoints
retain previous actions, settings, model identity and RNG state; an independent
restored world reproduces continuation and can diverge under different actions.

This is **an unloaded, flat-floor training reference, not a walking policy**.
The computed reward never asserts task success. Falls, force/joint-limit
violations and time limits remain explicit outcomes. GPU batching, the actual
learning environment, training, exported-policy parity, terrain/carry/running
tasks and native acceptance cohorts remain open.

Run without installing any GPU or training framework:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -m pytest --noconftest training/native_tests -q
```

The Windows run passed **23 native contract tests**. In the combined run with
the six cabinet route/tool component checks, **29 tests passed in 130.03 s**.
Evidence: `artifacts/physical-truth-runtime/native-contract-route-tests.xml`.
Those component checks do not establish that Apollo completes cabinet service.

## Current spending constraint: zero

On 2026-10-24 the user clarified that there is no budget and no existing funded
GPU. The Runpod proposal below is historical and **not approved for activation**.
Do not add funds, select paid accelerators, upgrade hosting or assume that owning
a payment card authorizes a charge.

`colab_compatibility.ipynb` is the free-runtime alternative. Its source is pinned
to `fa47720a2437fed8687648e6f37f399d36af8987`. It uses a separate virtual environment,
original collision geometry, a 30-minute subprocess budget and unique evidence
directories. No Drive mount, SSH, external serving, quota workaround or purchase
is involved. The notebook was executed on a free T4; evidence is recorded below.
Use only an available free T4 with standard RAM. Download the evidence and
disconnect afterward. A free runtime is not guaranteed, and this notebook is a
compatibility probe rather than a trained controller or production host.

## Executed free T4 probe — 2026-10-24

The signed-in Colab session allocated a Tesla T4 (15,360 MiB, driver 580.82.07),
Python 3.13.16 and standard host RAM. No compute units or paid resource were
purchased. The disposable runtime was disconnected and deleted after the report
was exported and its SHA-256 verified locally.

| Exact model | GPU implementation | Three-step comparison | Max absolute qpos difference | Max absolute qvel difference |
| --- | --- | --- | --- | --- |
| H1 | MJX-Warp | Passed | 4.584055e-8 | 1.693091e-6 |
| G1 | MJX-Warp | Passed | 1.329925e-5 | 2.915475e-3 |
| Apollo | MJX-JAX | Passed | 1.114830e-7 | 1.440514e-6 |

Differences use the model's mixed coordinate/velocity units, not a single linear
pose-error unit. Each run spans only 6 ms of simulation. Geometry, actuator
parameters and compiled-model hashes remained unchanged. This is an initial
compatibility result, not stability, locomotion, batched training or throughput
acceptance.

Apollo's original Warp trial **failed** on its non-zero contact margin with
MULTICCD. That rejection is retained in `apollo.json`; no margin was removed.
H1 Warp warns that capsule/cylinder pairs currently produce at most one contact.
Apollo JAX reported a CUDA autotuning-timer warning. These limitations require
longer contact regressions and batch profiling before training.

`artifacts/physical-truth-runtime/colab-t4-fa47720/evidence.tar.gz` contains all
four attempts, compiled-model manifests, package resolver/freeze records and
complete command logs. `selected-backends.json` identifies the three passing
implementations; the original `summary.json` correctly remains `all_passed:false`.
Archive SHA-256: `4697aaf1f81996dd69c72962b57bbe86302bac87e468cc689a805bc74291928f`.

The initial Colab environment omitted `ensurepip`. The notebook now creates a
stdlib virtual environment without pip and uses pip's documented
[`--python` target-interpreter option](https://pip.pypa.io/en/stable/topics/python-option/)
without changing Colab's installed packages. Native browser downloads did not
complete in this session; the optional text-export cell transferred only the
public simulation archive, with its byte count and SHA-256 checked on receipt.

The installed Linux dependency lock was produced by the actual
[preflight run](https://github.com/Tanish-Anand1/vivacity-investor-demo/actions/runs/40083924085)
at `3750125`. Dependency installation and `pip check` passed. Model execution did
not: MJX-JAX rejected G1 cylinder/mesh and H1 cylinder/box collision pairs. Apollo
hit an int32/int64 contact-index mismatch with x64 enabled. The float32 Apollo probe passed three native/MJX steps at `f07a75c`; this is
compatibility only. G1 still reports unsupported cylinder/mesh collision. The
GPU resolver then exposed Warp 1.18 versus the MJX 3.15 extra's required 1.17
pin. Selecting Warp 1.17 alone then failed Playground's newer 1.18 minimum.
The current lock selects the upstream Playground revision `8450aec0` that
explicitly adopted Warp 1.17, paired with MJX 3.15. At `c76abe1`, CI run
`40089372132` passed installation, `pip check` and the CUDA dependency dry run.
Apollo's three-step native/MJX comparison passed (maximum qpos difference
1.12e-7; maximum qvel difference 1.97e-6). G1 and H1 still fail on the original
unsupported CPU collision pairs. The probe calls the public `mjx.put_model` directly,
retaining overflow warnings and avoiding that older Playground wrapper's
standalone `mujoco_warp` import. Original geometry is preserved.

The first gate is whether the exact native models can execute through MJX, with
unchanged contact geometry, actuator properties and tooling. `preflight.py` uses
the pinned MuJoCo Playground adapter and records the model hash, installed
versions, memory, compilation time and actual native/MJX integration differences.
It is deliberately a short compatibility probe, not a stability or mobility test.

On Linux, in a separate Python 3.12 virtual environment:

```sh
python -m pip install -r training/requirements-linux-lock.txt --report resolver.json
python -m pip check
python -m pip freeze > requirements-linux.txt
JAX_PLATFORMS=cpu python -m training.preflight --robot h1 --steps 3 --output data/h1-mjx-preflight.json
```

The CPU GitHub workflow runs the same probe for G1, Apollo and H1. Its artifacts
record success or the actual exception. A timeout is a failure. If the exact
model is unsupported or too expensive, investigate before selecting a training
backend; do not silently remove tooling or collision constraints.

The supported candidate for the unsupported collision pairs is MJX-Warp. GPU
extras are separately resolved through `requirements-gpu.in`. On an approved
NVIDIA instance the probe accepts `--implementation warp`; it fails explicitly
when no GPU is configured. The actual T4 results below now establish a short
Warp comparison for H1/G1 and a separate JAX comparison for Apollo.

Before paid training: finish the model-matched observation/action contract,
task/reward/termination and randomization environment, inference export/parity,
bounded training command and checkpoint recovery; then profile and present a
concrete instance/storage quote, duration and spending ceiling for approval.
Training and the required native CPU mobility acceptance are separate gates.

Primary references: [MuJoCo MJX](https://mujoco.readthedocs.io/en/stable/mjx.html)
and [MuJoCo Playground](https://github.com/google-deepmind/mujoco_playground).

## Historical paid GPU proposal — not approved

This section is historical. Do not execute it under the current zero-spend constraint.

Observed in the signed-in Runpod dashboard on 2026-10-24: one A40 (48 GB VRAM,
43 GB host RAM, 9 vCPU), $0.59/hour compute plus $0.007/hour for a 50 GB
non-persistent container disk. The UI rounds the total to $0.60/hour. No volume
or recurring reservation is selected. Account balance is $0.00; payment setup
and explicit cost approval are outstanding. Never include payment details here.

The proposed first pilot is **compatibility only**, at most two hours from Pod
deployment: $1.194 at the displayed component rates, before any applicable tax.
Request a $2 total spending ceiling and re-check the actual quote before launch.
This does not authorize or estimate the full training campaign.

`gpu_pilot.sh` installs the resolved CUDA lock in a separate venv, compares three
real MJX-Warp steps for each complete embodiment to native MuJoCo, and archives
the reports. Keep native geometry, masses and tooling unchanged. A failed probe
blocks training. The seven local budget-guard tests pass; provider shutdown has
not been exercised because no Pod has been provisioned.

Before setup, record the actual deployment time and set
`VIVACITY_PILOT_DEADLINE` to its Unix timestamp plus 7200 seconds, then run:

```sh
bash training/gpu_pilot.sh
```

The background guard checks its Pod ID against `RUNPOD_POD_ID` and requests
`runpodctl pod stop` at that fixed deadline. It is a best-effort operational
guard, **not a provider-enforced billing cap**. Monitor externally throughout;
stop earlier when the probe finishes or fails. Export
`data/gpu-pilot-evidence.tar.gz` before stopping, because the container disk is
ephemeral. Verify the stopped state in Runpod, then terminate this disposable
pilot Pod. CLI acknowledgement alone is not proof that billing stopped.
