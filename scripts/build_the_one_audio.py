"""Render THE ONE's optional, restrained 7.5-second authored soundtrack.

This deterministic sound design is not recorded hardware or simulation output.
The browser opening remains muted until the visitor enables sound. No samples,
network assets or third-party sound libraries are required.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import wave

import numpy as np

RATE = 48_000
DURATION = 7.5
COUNT = int(RATE * DURATION)
TIME = np.arange(COUNT, dtype=np.float64) / RATE
MASTER_GAIN = 3.5
OUT = Path(__file__).resolve().parents[1] / "artifacts/the-one-audio.wav"
CUES = [
    (0.0, 0.8, "grip"),
    (0.8, 2.2, "machinery"),
    (2.2, 3.05, "hush"),
    (3.05, 4.65, "floor_and_architecture"),
    (4.65, 5.55, "converge"),
    (5.55, 6.5, "resolve"),
    (6.5, 7.5, "calm"),
]


def envelope(start: float, end: float, attack: float, release: float) -> np.ndarray:
    """Cosine ramps avoid waveform discontinuities at every cue boundary."""
    onset = np.clip((TIME - start) / attack, 0.0, 1.0)
    tail = np.clip((end - TIME) / release, 0.0, 1.0)
    return np.sin(onset * np.pi / 2) ** 2 * np.sin(tail * np.pi / 2) ** 2


def add(track: np.ndarray, signal: np.ndarray, pan: float | np.ndarray = 0.0) -> None:
    track[:, 0] += signal * np.sqrt((1.0 - pan) / 2)
    track[:, 1] += signal * np.sqrt((1.0 + pan) / 2)


def texture(rng: np.random.Generator, low: float, high: float) -> np.ndarray:
    """Finite, smoothly band-limited noise, synthesized directly with NumPy."""
    frequencies = np.fft.rfftfreq(COUNT, 1 / RATE)
    spectrum = np.fft.rfft(rng.standard_normal(COUNT))
    rise = np.clip((frequencies - low * 0.5) / (low * 0.5), 0.0, 1.0)
    fall = np.clip((high * 1.4 - frequencies) / (high * 0.4), 0.0, 1.0)
    shaped = np.fft.irfft(spectrum * np.sin(rise * np.pi / 2) ** 2 * np.sin(fall * np.pi / 2) ** 2, n=COUNT)
    return shaped / max(float(np.sqrt(np.mean(shaped**2))), 1e-12)


def render() -> np.ndarray:
    rng = np.random.default_rng(20261022)
    stereo = np.zeros((COUNT, 2), dtype=np.float64)
    # Tiny contact detail, never a trailer-style impact or bass drop.
    for start, frequency, amplitude, decay, pan in [
        (0.4, 1320.0, 0.072, 36.0, -0.18),
        (3.05, 620.0, 0.085, 28.0, 0.08),
        (3.05, 298.0, 0.030, 20.0, 0.0),
    ]:
        local = np.maximum(TIME - start, 0.0)
        ring = np.sin(2 * np.pi * frequency * local) + 0.16 * np.sin(2 * np.pi * frequency * 1.73 * local)
        pulse = amplitude * ring * np.exp(-decay * local) * envelope(start, start + 0.3, 0.003, 0.09)
        add(stereo, pulse, pan)

    # Low servomotor movement follows the real arm motion's authored timing.
    local = np.maximum(TIME - 0.8, 0.0)
    motor_phase = 2 * np.pi * (124 * local + 46 * local**2 / (2 * 1.4))
    motor = (0.034 * np.sin(motor_phase) + 0.009 * np.sin(2 * motor_phase)) * envelope(0.8, 2.2, 0.18, 0.28)
    add(stereo, motor, np.clip(-0.23 + local / 1.4 * 0.46, -0.23, 0.23))
    add(stereo, 0.006 * texture(rng, 220, 1250) * envelope(0.8, 2.2, 0.3, 0.3), 0.0)

    # 2.2–3.05 is literal digital silence. The missing sound gives the held
    # cube its tension without suggesting a physical sound measurement.
    architecture = envelope(3.05, 4.65, 0.23, 0.35)
    architecture_pan = np.clip((TIME - 3.05) / 1.6 * 1.1 - 0.55, -0.55, 0.55)
    add(stereo, 0.013 * texture(rng, 150, 950) * architecture, architecture_pan)
    add(stereo, (0.020 * np.sin(2 * np.pi * 182 * TIME) + 0.007 * np.sin(2 * np.pi * 364 * TIME)) * architecture, -architecture_pan * 0.5)

    local = np.maximum(TIME - 4.65, 0.0)
    converge = envelope(4.65, 5.55, 0.28, 0.25)
    # A quiet accelerating overtone resolves into the final open fifth.
    phase = 2 * np.pi * (196 * local + (220 - 196) * local**2 / (2 * 0.9))
    add(stereo, (0.031 * np.sin(phase) + 0.008 * np.sin(2 * phase)) * converge, 0.0)
    add(stereo, 0.004 * texture(rng, 380, 1800) * converge, 0.12)

    resolve = envelope(5.55, 7.5, 0.38, 1.0)
    local = np.maximum(TIME - 5.55, 0.0)
    for frequency, amplitude, pan in [(146.832, 0.055, -0.08), (220.0, 0.036, 0.08), (293.665, 0.022, 0.0), (440.0, 0.006, 0.0)]:
        add(stereo, amplitude * np.sin(2 * np.pi * frequency * local) * resolve, pan)
    # Keep the mix quiet and leave deterministic headroom. No limiter, gain
    # pumping or automatic normalization turns a small detail into an impact.
    stereo *= MASTER_GAIN
    peak = float(np.max(np.abs(stereo)))
    stereo *= min(1.0, 0.46 / max(peak, 1e-12))
    stereo[0] = 0.0
    stereo[-1] = 0.0
    return stereo


def main() -> None:
    stereo = render()
    assert stereo.shape == (360_000, 2)
    assert np.all(np.isfinite(stereo))
    assert 0.02 < np.max(np.abs(stereo)) <= 0.46
    assert np.array_equal(stereo, render()), "Soundtrack must be deterministic"
    hush = stereo[int(2.2 * RATE) : int(3.05 * RATE)]
    assert np.count_nonzero(hush) == 0, "Time-stop must remain silent"
    assert np.all(stereo[[0, -1]] == 0), "Avoid boundary clicks"
    pcm = np.rint(stereo * 32767).astype("<i2")
    assert not np.any(np.abs(pcm.astype(np.int32)) >= 32767), "PCM clipping"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(pcm.tobytes())
    with wave.open(str(OUT), "rb") as verification:
        assert verification.getparams()[:4] == (2, 2, RATE, COUNT)
    report = {
        "output": str(OUT.relative_to(OUT.parents[1])),
        "duration_seconds": DURATION,
        "sample_rate_hz": RATE,
        "channels": 2,
        "sample_frames": COUNT,
        "peak_dbfs": float(20 * np.log10(np.max(np.abs(stereo)))),
        "rms_dbfs": float(20 * np.log10(np.sqrt(np.mean(stereo**2)))),
        "hush_nonzero_samples": int(np.count_nonzero(hush)),
        "cue_rms": {name: float(np.sqrt(np.mean(stereo[int(start * RATE) : int(end * RATE)] ** 2))) for start, end, name in CUES},
        "bytes": OUT.stat().st_size,
        "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
        "checks": "determinism, duration, PCM format, finite samples, headroom, silent hold, click-free boundaries passed",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
