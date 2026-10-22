"""Unitree H1 recurrent walking policy inference without a runtime Torch dependency.

Weights are converted from the pinned Unitree TorchScript checkpoint by
``scripts/convert_h1_policy.py``. Every trial constructs a new Policy instance,
so LSTM memory cannot leak between independent experiments.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
from pathlib import Path

import numpy as np


WEIGHTS = Path(__file__).resolve().parents[1] / 'assets/unitree_rl_gym/h1/policy/motion.npz'
SOURCE_TORCH_SHA256 = '44a0fbceb81f3877833ae9a398d039bea1759cb0d3c8188181013885f70589eb'
SOURCE_COMMIT = '276801e46c5d433564f24658bac64f254b7d2d4b'
DEFAULT_ANGLES = np.asarray([0, 0, -.1, .3, -.2] * 2, dtype=np.float32)
KP = np.asarray([150, 150, 150, 200, 40] * 2, dtype=np.float32)
KD = np.asarray([2, 2, 2, 4, 2] * 2, dtype=np.float32)
ACTION_SCALE = .25
CMD_SCALE = np.asarray([2., 2., .25], dtype=np.float32)


@lru_cache(maxsize=1)
def _weights():
    with np.load(WEIGHTS, allow_pickle=False) as archive:
        tensors = {name: np.asarray(archive[name], dtype=np.float32) for name in archive.files}
    expected = {
        'actor.0.weight': (32, 64), 'actor.0.bias': (32,),
        'actor.2.weight': (10, 32), 'actor.2.bias': (10,),
        'memory.weight_ih_l0': (256, 41), 'memory.weight_hh_l0': (256, 64),
        'memory.bias_ih_l0': (256,), 'memory.bias_hh_l0': (256,),
    }
    if {key: value.shape for key, value in tensors.items()} != expected:
        raise ValueError('H1 policy tensor shapes do not match the pinned controller')
    return tensors


@lru_cache(maxsize=1)
def policy_hash():
    return hashlib.sha256(WEIGHTS.read_bytes()).hexdigest()


class H1Policy:
    def __init__(self):
        self.weights = _weights()
        self.hidden = np.zeros(64, dtype=np.float32)
        self.cell = np.zeros(64, dtype=np.float32)

    def act(self, observation):
        obs = np.asarray(observation, dtype=np.float32)
        if obs.shape != (41,) or not np.isfinite(obs).all():
            raise ValueError('H1 policy requires 41 finite observations')
        w = self.weights
        gates = (w['memory.weight_ih_l0'] @ obs + w['memory.bias_ih_l0'] +
                 w['memory.weight_hh_l0'] @ self.hidden + w['memory.bias_hh_l0'])
        sigmoid = lambda x: 1. / (1. + np.exp(-np.clip(x, -80, 80)))
        ingate = sigmoid(gates[:64])
        forgetgate = sigmoid(gates[64:128])
        cellgate = np.tanh(gates[128:192])
        outgate = sigmoid(gates[192:])
        self.cell = forgetgate * self.cell + ingate * cellgate
        self.hidden = outgate * np.tanh(self.cell)
        intermediate = w['actor.0.weight'] @ self.hidden + w['actor.0.bias']
        intermediate = np.where(intermediate > 0, intermediate, np.expm1(intermediate))
        return w['actor.2.weight'] @ intermediate + w['actor.2.bias']


def gravity_in_body(quaternion):
    """Unitree deploy_mujoco.py observation convention for projected gravity."""
    qw, qx, qy, qz = quaternion
    return np.asarray([2*(-qz*qx+qw*qy), -2*(qz*qy+qw*qx),
                       1-2*(qw*qw+qz*qz)], dtype=np.float32)


def observation(data, command, previous_action):
    obs = np.zeros(41, dtype=np.float32)
    obs[:3] = data.qvel[3:6] * .25
    obs[3:6] = gravity_in_body(data.qpos[3:7])
    obs[6:9] = np.asarray(command, dtype=np.float32) * CMD_SCALE
    obs[9:19] = data.qpos[7:17] - DEFAULT_ANGLES
    obs[19:29] = data.qvel[6:16] * .05
    obs[29:39] = previous_action
    phase = (float(data.time) % .8) / .8
    obs[39:41] = [np.sin(2*np.pi*phase), np.cos(2*np.pi*phase)]
    return obs
