#!/usr/bin/env bash
# Execute only after the exact Pod, hourly quote and pilot cap are approved.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${RUNPOD_POD_ID:?Run inside the approved pilot Pod}"
: "${VIVACITY_PILOT_DEADLINE:?Set the approved absolute Unix deadline before setup}"
command -v runpodctl >/dev/null
# Fail before installations if the CLI version does not expose the stop command.
runpodctl pod stop --help >/dev/null
mkdir -p data/gpu-pilot
nohup python3 -m training.runpod_guard --pod-id "$RUNPOD_POD_ID" \
  --deadline "$VIVACITY_PILOT_DEADLINE" --journal data/gpu-pilot/guard.jsonl \
  >data/gpu-pilot/guard.log 2>&1 </dev/null &
GUARD_PID=$!
sleep 1
kill -0 "$GUARD_PID"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export XLA_PYTHON_CLIENT_PREALLOCATE=false JAX_PLATFORMS=cuda
python3 -m venv /tmp/vivacity-gpu-pilot
PY=/tmp/vivacity-gpu-pilot/bin/python
"$PY" -m pip install -r training/requirements-gpu-lock.txt --report data/gpu-pilot/resolver.json
"$PY" -m pip check
"$PY" -m pip freeze > data/gpu-pilot/installed.txt
nvidia-smi > data/gpu-pilot/gpu.txt
git rev-parse HEAD > data/gpu-pilot/commit.txt
status=0
for robot in h1 g1 apollo; do
  timeout 1200 "$PY" -u -m training.preflight --robot "$robot" --steps 3 \
    --implementation warp --output "data/gpu-pilot/$robot.json" || status=1
done
tar -czf data/gpu-pilot-evidence.tar.gz -C data gpu-pilot
printf 'Probe exit status: %s. Export data/gpu-pilot-evidence.tar.gz now.\n' "$status"
printf 'The guard remains active. Verify Pod stop externally, then terminate the empty pilot Pod.\n'
exit "$status"
