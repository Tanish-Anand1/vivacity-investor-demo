"""Reference outputs from Unitree's pinned TorchScript recurrent checkpoint."""

import hashlib

import numpy as np
import pytest

from vivacity.h1_policy import H1Policy, SOURCE_TORCH_SHA256, WEIGHTS, policy_hash


def test_numpy_lstm_matches_pinned_torchscript_reference_sequence():
    assert hashlib.sha256(WEIGHTS.with_suffix('.pt').read_bytes()).hexdigest() == SOURCE_TORCH_SHA256
    assert len(policy_hash()) == 64
    observations = np.random.default_rng(20261022).normal(0, .5, size=(2, 41)).astype(np.float32)
    expected = np.asarray([
        [-.060636, -1.650595, -1.042884, 1.354806, 3.748222,
         .757129, 2.250786, -3.198258, .911356, -.699302],
        [-.336962, .835161, .202251, -.237421, .691229,
         -.209612, 2.177228, -1.426266, 1.589370, .718124],
    ], dtype=np.float32)
    policy = H1Policy()
    actual = np.stack([policy.act(obs) for obs in observations])
    np.testing.assert_allclose(actual, expected, atol=1e-5, rtol=0)
    fresh = H1Policy()
    np.testing.assert_allclose(fresh.act(observations[0]), actual[0], atol=1e-6)
    with pytest.raises(ValueError, match='41 finite'):
        fresh.act(np.full(41, np.nan))
