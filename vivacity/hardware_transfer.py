"""Offline transfer contract. This module has no robot transport or SDK.

The gate validates commissioning messages and emits dry-run decisions. It is not
a safety controller, physical E-stop, or evidence of hardware compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class JointEnvelope:
    names: tuple[str, ...]
    lower_rad: tuple[float, ...]
    upper_rad: tuple[float, ...]
    rate_limit_rad_s: tuple[float, ...]

    def __post_init__(self):
        n = len(self.names)
        if not n or len(set(self.names)) != n:
            raise ValueError('unique joint names required')
        arrays = [np.asarray(v, dtype=float) for v in (self.lower_rad, self.upper_rad, self.rate_limit_rad_s)]
        if any(a.shape != (n,) or not np.isfinite(a).all() for a in arrays):
            raise ValueError('finite per-joint limits required')
        if np.any(arrays[0] >= arrays[1]) or np.any(arrays[2] <= 0):
            raise ValueError('invalid joint envelope')

    def position(self, values):
        value = np.asarray(values, dtype=float)
        if value.shape != (len(self.names),) or not np.isfinite(value).all():
            raise ValueError('finite ordered joint vector required')
        if np.any(value < self.lower_rad) or np.any(value > self.upper_rad):
            raise ValueError('joint command outside commissioning envelope')
        return value


class DryRunCommandGate:
    """Fail-closed, explicit arming and latching watchdog for adapter development."""
    version = 'vivacity.hardware-dry-run/1'

    def __init__(self, envelope: JointEnvelope, manifest_sha256: str, *, watchdog_s=.1):
        if len(manifest_sha256) != 64 or any(c not in '0123456789abcdef' for c in manifest_sha256):
            raise ValueError('manifest SHA-256 required')
        if not .01 <= watchdog_s <= .5:
            raise ValueError('watchdog must be between 10 and 500 milliseconds')
        self.envelope = envelope
        self.manifest = manifest_sha256
        self.watchdog_s = watchdog_s
        self.armed = False
        self.sequence = -1
        self.last_time = None
        self.position = None
        self.fault = None

    def arm(self, now_s, measured_positions, *, manifest_sha256, operator_acknowledged=False):
        if not operator_acknowledged or manifest_sha256 != self.manifest or not math.isfinite(now_s):
            raise ValueError('matching manifest and explicit dry-run acknowledgement required')
        position = self.envelope.position(measured_positions)
        self.armed, self.fault = True, None
        self.position = position.copy()
        self.last_time = float(now_s)
        self.sequence = -1

    def _disable(self, reason):
        self.armed = False
        self.fault = reason
        return {'mode':'dry_run', 'operation':'disable', 'reason':reason,
                'hardware_command_sent':False}

    def tick(self, now_s):
        if not math.isfinite(now_s):
            return self._disable('invalid_clock')
        if not self.armed:
            return self._disable(self.fault or 'not_armed')
        if now_s < self.last_time:
            return self._disable('clock_reversed')
        if now_s-self.last_time > self.watchdog_s:
            return self._disable('command_watchdog_expired')
        return {'mode':'dry_run', 'operation':'await_command', 'hardware_command_sent':False}

    def accept(self, *, sequence, timestamp_s, positions, now_s):
        status = self.tick(now_s)
        if status['operation'] == 'disable':
            return status
        if (not isinstance(sequence, int) or isinstance(sequence, bool) or sequence <= self.sequence
                or not math.isfinite(timestamp_s) or timestamp_s > now_s or timestamp_s < self.last_time):
            return self._disable('invalid_command_order')
        if now_s-timestamp_s > self.watchdog_s:
            return self._disable('stale_command')
        try:
            value = self.envelope.position(positions)
        except (ValueError, TypeError):
            return self._disable('invalid_joint_command')
        interval = timestamp_s-self.last_time
        if np.any(np.abs(value-self.position) > np.asarray(self.envelope.rate_limit_rad_s)*interval+1e-9):
            return self._disable('command_rate_exceeded')
        self.sequence, self.last_time, self.position = sequence, float(timestamp_s), value.copy()
        return {'mode':'dry_run', 'operation':'validated_position_reference',
                'sequence':sequence, 'positions_rad':value.tolist(), 'hardware_command_sent':False}


def validate_sensor_replay(records, joint_names):
    """Validate recorded proprioception only; never label simulated frames hardware."""
    previous, count = -math.inf, 0
    for frame in records:
        if frame.get('schema_version') != 'vivacity.recorded-proprioception/1':
            raise ValueError('unknown sensor replay schema')
        if frame.get('provenance') not in ('native_mujoco_simulation', 'recorded_hardware_unvalidated'):
            raise ValueError('explicit sensor provenance required')
        if frame.get('joint_names') != list(joint_names):
            raise ValueError('sensor joint mapping mismatch')
        t = frame.get('timestamp_s')
        if not isinstance(t, (int, float)) or not math.isfinite(t) or t <= previous:
            raise ValueError('strictly ordered sensor timestamps required')
        for key in ('position_rad', 'velocity_rad_s'):
            values = np.asarray(frame.get(key), dtype=float)
            if values.shape != (len(joint_names),) or not np.isfinite(values).all():
                raise ValueError('invalid recorded joint vector')
        previous, count = t, count+1
    if not count:
        raise ValueError('sensor recording is empty')
    return {'samples':count, 'last_timestamp_s':previous, 'hardware_validation':False}
