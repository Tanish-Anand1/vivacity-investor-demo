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
drone = .06 * (np.sin(2 * np.pi * 55 * TIMES) + .32 * np.sin(2 * np.pi * 110 * TIMES))
add_stereo(left, right, drone * envelope(0, 7.5, .7, 1.2), 0)

for hit, pitch, pan, strength in [
    (.16, 715, -.72, .23), (.46, 850, -.35, .17), (.78, 1040, .1, .14),
    (1.22, 610, .48, .16), (1.84, 780, -.25, .14), (2.44, 940, .52, .17),
    (4.18, 720, -.45, .16), (4.35, 830, 0, .12), (4.53, 940, .45, .16),
    (5.82, 320, 0, .26),
]:
    local = TIMES - hit
    decay = np.exp(-np.maximum(local, 0) * (14 if hit < 5.8 else 6))
    ring = np.sin(2 * np.pi * pitch * np.maximum(local, 0)) + .35 * np.sin(2 * np.pi * pitch * 1.63 * np.maximum(local, 0))
    sound = np.where((local >= 0) & (local < .7), ring * decay * strength, 0)
    add_stereo(left, right, sound, pan)

for start, duration, low, high, pan in [(1.06, 1.35, 95, 190, -.35), (1.7, 1.12, 140, 265, .38), (2.68, .8, 110, 380, 0)]:
    local = np.maximum(TIMES - start, 0)
    frequency = low + (high - low) * np.clip(local / duration, 0, 1)
    phase = 2 * np.pi * (low * local + (high - low) * local**2 / (2 * duration))
    signal = .052 * np.sin(phase) * envelope(start, duration, .16, .23)
    add_stereo(left, right, signal, pan)

noise = RNG.normal(0, 1, COUNT)
filtered = sosfilt(butter(3, [180, 1800], btype="bandpass", fs=RATE, output="sos"), noise)
swells = .028 * filtered * envelope(2.54, .78, .48, .15)
add_stereo(left, right, swells, .1)

for frequency, amount in [(110, .11), (164.81, .065), (220, .043), (329.63, .025)]:
    local = np.maximum(TIMES - 5.9, 0)
    note = amount * np.sin(2 * np.pi * frequency * local) * envelope(5.9, 1.6, .15, .63)
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
