# Model-matched locomotion development

This directory is an isolated research environment. No trained policy exists for
the complete tool-equipped embodiments yet. Nothing here is used by the API
image, and no GPU resource has been purchased.

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
when no GPU is configured. No successful Warp execution is claimed yet.

Before paid training: finish the model-matched observation/action contract,
task/reward/termination and randomization environment, inference export/parity,
bounded training command and checkpoint recovery; then profile and present a
concrete instance/storage quote, duration and spending ceiling for approval.
Training and the required native CPU mobility acceptance are separate gates.

Primary references: [MuJoCo MJX](https://mujoco.readthedocs.io/en/stable/mjx.html)
and [MuJoCo Playground](https://github.com/google-deepmind/mujoco_playground).

## First paid GPU pilot: prepared, not provisioned

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
