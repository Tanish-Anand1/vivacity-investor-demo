"""Synthesize an optional, deterministic 7.5-second mechanical sound design.

The opening autoplays muted. A visitor can explicitly enable this soundtrack.
It is authored audio, not a recording of robot hardware or physics output.
"""

from __future__ import annotations

from pathlib import Path
import wave

import numpy as np
from scipy.signal import butter, sosfilt

RATE = 48000
DURATION = 7.5
COUNT = int(RATE * DURATION)
TIMES = np.arange(COUNT) / RATE
RNG = np.random.default_rng(197)
OUT = Path(__file__).resolve().parents[1] / "artifacts/isabella-cinema-audio.wav"


def envelope(start: float, duration: float, attack: float, release: float) -> np.ndarray:
    local = TIMES - start
    return np.where(
        (local >= 0) & (local < duration),
        np.minimum(1, np.maximum(0, local / attack)) * np.minimum(1, np.maximum(0, (duration - local) / release)),
        0,
    )


def add_stereo(left: np.ndarray, right: np.ndarray, signal: np.ndarray, pan: float) -> None:
    left += signal * np.sqrt((1 - pan) / 2)
    right += signal * np.sqrt((1 + pan) / 2)


left = np.zeros(COUNT)
right = np.zeros(COUNT)
drone = .045 * (np.sin(2 * np.pi * 48 * TIMES) + .23 * np.sin(2 * np.pi * 96 * TIMES))
add_stereo(left, right, drone * envelope(1.9, 2.22, .75, .16), 0)

for hit, pitch, pan, strength in [
    (.59, 965, -.68, .27), (1.39, 625, .35, .21),
    (1.68, 835, -.18, .15), (1.9, 1120, .18, .13),
    (2.19, 770, .6, .19), (3.36, 118, 0, .48),
    (3.55, 540, -.46, .17), (3.82, 470, .42, .16),
    (5.18, 290, -.3, .12), (5.72, 430, .3, .11),
]:
    local = TIMES - hit
    decay = np.exp(-np.maximum(local, 0) * (14 if hit < 5.8 else 6))
    ring = np.sin(2 * np.pi * pitch * np.maximum(local, 0)) + .35 * np.sin(2 * np.pi * pitch * 1.63 * np.maximum(local, 0))
    sound = np.where((local >= 0) & (local < .7), ring * decay * strength, 0)
    add_stereo(left, right, sound, pan)

for start, duration, low, high, pan in [(0.62, .78, 88, 170, -.35), (1.4, .8, 135, 290, .38), (3.38, .72, 55, 115, 0)]:
    local = np.maximum(TIMES - start, 0)
    frequency = low + (high - low) * np.clip(local / duration, 0, 1)
    phase = 2 * np.pi * (low * local + (high - low) * local**2 / (2 * duration))
    signal = .052 * np.sin(phase) * envelope(start, duration, .16, .23)
    add_stereo(left, right, signal, pan)

noise = RNG.normal(0, 1, COUNT)
filtered = sosfilt(butter(3, [180, 1800], btype="bandpass", fs=RATE, output="sos"), noise)
swells = .045 * filtered * envelope(3.34, .76, .12, .43)
add_stereo(left, right, swells, .1)

for frequency, amount in [(110, .1), (164.81, .055), (220, .036), (329.63, .018)]:
    local = np.maximum(TIMES - 6.16, 0)
    note = amount * np.sin(2 * np.pi * frequency * local) * envelope(6.16, 1.34, .22, .53)
    add_stereo(left, right, note, 0)

stereo = np.stack([left, right], axis=1)
peak = np.max(np.abs(stereo))
stereo = np.clip(stereo * min(.68 / peak, 2.2), -1, 1)
OUT.parent.mkdir(parents=True, exist_ok=True)
with wave.open(str(OUT), "wb") as output:
    output.setnchannels(2)
    output.setsampwidth(2)
    output.setframerate(RATE)
    output.writeframes((stereo * 32767).astype("<i2").tobytes())
print(f"{OUT}: {DURATION}s / {RATE}Hz / peak {np.max(np.abs(stereo)):.3f}")
