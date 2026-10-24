# Model-matched locomotion development

This directory is an isolated research environment. No trained policy exists for
the complete tool-equipped embodiments yet. Nothing here is used by the API
image, and no GPU resource has been purchased.

The first gate is whether the exact native models can execute through MJX, with
unchanged contact geometry, actuator properties and tooling. `preflight.py` uses
the pinned MuJoCo Playground adapter and records the model hash, installed
versions, memory, compilation time and actual native/MJX integration differences.
It is deliberately a short compatibility probe, not a stability or mobility test.

On Linux, in a separate Python 3.12 virtual environment:

```sh
python -m pip install -r training/requirements.in --report resolver.json
python -m pip check
python -m pip freeze > requirements-linux.txt
JAX_PLATFORMS=cpu python -m training.preflight --robot h1 --steps 3 --output data/h1-mjx-preflight.json
```

The CPU GitHub workflow runs the same probe for G1, Apollo and H1. Its artifacts
record success or the actual exception. A timeout is a failure. If the exact
model is unsupported or too expensive, investigate before selecting a training
backend; do not silently remove tooling or collision constraints.

Before paid training: finish the model-matched observation/action contract,
task/reward/termination and randomization environment, inference export/parity,
bounded training command and checkpoint recovery; then profile and present a
concrete instance/storage quote, duration and spending ceiling for approval.
Training and the required native CPU mobility acceptance are separate gates.

Primary references: [MuJoCo MJX](https://mujoco.readthedocs.io/en/stable/mjx.html)
and [MuJoCo Playground](https://github.com/google-deepmind/mujoco_playground).
