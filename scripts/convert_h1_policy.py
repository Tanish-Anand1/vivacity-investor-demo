"""Convert and independently verify Unitree's pinned H1 TorchScript weights.

Torch is needed for this one-time development command, never on the Render
runtime. It is intentionally absent from requirements-lock.txt.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import numpy as np
import torch

from vivacity.h1_policy import H1Policy, SOURCE_TORCH_SHA256, WEIGHTS, _weights


SOURCE = WEIGHTS.with_suffix('.pt')


def main():
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest != SOURCE_TORCH_SHA256:
        raise ValueError(f'Unitree checkpoint hash mismatch: {digest}')
    reference = torch.jit.load(str(SOURCE), map_location='cpu').eval()
    tensors = {name: tensor.detach().numpy().astype(np.float32)
               for name, tensor in reference.named_parameters()}
    np.savez_compressed(WEIGHTS, **tensors)
    _weights.cache_clear()
    candidate = H1Policy()
    rng = np.random.default_rng(20261022)
    maximum_error = 0.
    with torch.no_grad():
        for obs in rng.normal(0, .5, size=(256, 41)).astype(np.float32):
            expected = reference(torch.from_numpy(obs).unsqueeze(0)).numpy().reshape(-1)
            actual = candidate.act(obs)
            maximum_error = max(maximum_error, float(np.max(np.abs(expected-actual))))
    if maximum_error > 1e-4:
        raise AssertionError(f'NumPy LSTM disagrees with TorchScript: {maximum_error}')
    print(f'policy_sha256={hashlib.sha256(WEIGHTS.read_bytes()).hexdigest()} '
          f'max_abs_error={maximum_error:.8g} observations=256', flush=True)


if __name__ == '__main__':
    sys.exit(main())
