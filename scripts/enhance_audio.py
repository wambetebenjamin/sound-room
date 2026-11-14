#!/usr/bin/env python3
"""
enhance_audio.py — "amplify" a track: corrective EQ, harmonic excitation,
stereo repair, glue compression, then loudness/true-peak normalisation.

The chain is fixed but every stage is parameterised, so the same script can be
re-targeted per song after reading scripts/analyze_audio.py output.

Usage:
    python3 scripts/enhance_audio.py in.mp3 -o out/music/track.wav
    python3 scripts/enhance_audio.py in.mp3 -o out.wav --preset bright
    python3 scripts/enhance_audio.py in.mp3 -o out.wav --target-lufs -14 --ceiling -1.0
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field

import numpy as np
import soundfile as sf
from scipy import signal

DB = 20.0


@dataclass
class Chain:
    """Parameters for the whole enhancement chain."""
    # corrective EQ
    highpass_hz: float = 28.0
    cuts: list[tuple[float, float, float]] = field(default_factory=list)   # (freq, gain_db, q)
    boosts: list[tuple[float, float, float]] = field(default_factory=list)
    air_shelf_hz: float = 9000.0
    air_shelf_db: float = 0.0
    # harmonic excitation (adds perceived level + detail without peak)
    drive_db: float = 0.0
    drive_band_hz: tuple[float, float] = (800.0, 12000.0)
    # stereo
    width: float = 1.0                 # side gain multiplier
    mono_bass_hz: float = 0.0          # fold content below this to mono
    # dynamics
    comp_threshold_db: float | None = None
    comp_ratio: float = 2.0
    comp_attack_ms: float = 20.0
    comp_release_ms: float = 180.0
    # output
    target_lufs: float | None = -14.0
    ceiling_db: float = -1.0


PRESETS = {
    "neutral": Chain(),
    # Balanced: targets ~45-50% below 250 Hz for a bass-forward genre,
    # keeping the log-drum body while opening up the top.
    "amapiano_balanced": Chain(
        highpass_hz=30.0,
        cuts=[(210.0, -2.0, 1.0)],
        boosts=[(2800.0, 2.5, 1.1), (5200.0, 1.5, 1.2)],
        air_shelf_hz=8500.0, air_shelf_db=4.5,
        drive_db=3.0, drive_band_hz=(700.0, 11000.0),
        width=1.2, mono_bass_hz=100.0,
        comp_threshold_db=-22.0, comp_ratio=1.8,
        target_lufs=-14.0, ceiling_db=-1.0,
    ),
    # Aggressive: for a source with almost no top end at all.
    "amapiano_lift": Chain(
        highpass_hz=30.0,
        cuts=[(210.0, -3.5, 0.9), (430.0, -1.5, 1.4)],
        boosts=[(2800.0, 4.0, 1.1), (5200.0, 2.5, 1.2)],
        air_shelf_hz=8500.0, air_shelf_db=6.0,
        drive_db=6.0, drive_band_hz=(700.0, 11000.0),
        width=1.35, mono_bass_hz=110.0,
        comp_threshold_db=-20.0, comp_ratio=2.0,
        target_lufs=-14.0, ceiling_db=-1.0,
    ),
    "bright": Chain(air_shelf_db=4.0, boosts=[(3000.0, 2.0, 1.0)], target_lufs=-14.0),
    "warm": Chain(cuts=[(300.0, -1.5, 1.0)], air_shelf_db=2.0, target_lufs=-14.0),
}


# ---------------------------------------------------------------- biquads
def _biquad(kind: str, sr: float, freq: float, gain_db: float = 0.0, q: float = 0.707) -> np.ndarray:
    """RBJ-cookbook biquad returned as a single SOS row."""
    a_lin = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * freq / sr
    cos_w0, sin_w0 = np.cos(w0), np.sin(w0)
    alpha = sin_w0 / (2 * q)

    if kind == "peak":
        b = [1 + alpha * a_lin, -2 * cos_w0, 1 - alpha * a_lin]
        a = [1 + alpha / a_lin, -2 * cos_w0, 1 - alpha / a_lin]
    elif kind == "highshelf":
        sq = 2 * np.sqrt(a_lin) * alpha
        b = [a_lin * ((a_lin + 1) + (a_lin - 1) * cos_w0 + sq),
             -2 * a_lin * ((a_lin - 1) + (a_lin + 1) * cos_w0),
             a_lin * ((a_lin + 1) + (a_lin - 1) * cos_w0 - sq)]
        a = [(a_lin + 1) - (a_lin - 1) * cos_w0 + sq,
             2 * ((a_lin - 1) - (a_lin + 1) * cos_w0),
             (a_lin + 1) - (a_lin - 1) * cos_w0 - sq]
    elif kind == "lowshelf":
        sq = 2 * np.sqrt(a_lin) * alpha
        b = [a_lin * ((a_lin + 1) - (a_lin - 1) * cos_w0 + sq),
             2 * a_lin * ((a_lin - 1) - (a_lin + 1) * cos_w0),
             a_lin * ((a_lin + 1) - (a_lin - 1) * cos_w0 - sq)]
        a = [(a_lin + 1) + (a_lin - 1) * cos_w0 + sq,
             -2 * ((a_lin - 1) + (a_lin + 1) * cos_w0),
             (a_lin + 1) + (a_lin - 1) * cos_w0 - sq]
    else:
        raise ValueError(kind)
    b = np.array(b) / a[0]
    a = np.array(a) / a[0]
    return np.concatenate([b, a])


def apply_eq(x: np.ndarray, sr: int, chain: Chain) -> np.ndarray:
    sos: list[np.ndarray] = []
    if chain.highpass_hz > 0:
        sos.append(signal.butter(2, chain.highpass_hz / (sr / 2), btype="highpass", output="sos"))
    for freq, gain, q in chain.cuts:
        sos.append(_biquad("peak", sr, freq, gain, q)[None, :])
    for freq, gain, q in chain.boosts:
        sos.append(_biquad("peak", sr, freq, gain, q)[None, :])
    if chain.air_shelf_db:
        sos.append(_biquad("highshelf", sr, chain.air_shelf_hz, chain.air_shelf_db, 0.707)[None, :])
    if not sos:
        return x
    out = signal.sosfiltfilt(np.vstack(sos), x, axis=0)  # zero-phase: no EQ-induced phase smear
    return out.astype(np.float64)


# ---------------------------------------------------------------- dynamics
def compress(x: np.ndarray, sr: int, chain: Chain) -> np.ndarray:
    """Feed-forward peak compressor on a linked stereo detector."""
    if chain.comp_threshold_db is None:
        return x
    thr = 10 ** (chain.comp_threshold_db / 20.0)
    ratio = max(chain.comp_ratio, 1.0)
    att = np.exp(-1.0 / (sr * chain.comp_attack_ms / 1000.0))
    rel = np.exp(-1.0 / (sr * chain.comp_release_ms / 1000.0))

    detector = np.max(np.abs(x), axis=1) if x.ndim > 1 else np.abs(x)
    env = np.zeros_like(detector)
    prev = 0.0
    for i, v in enumerate(detector):
        coeff = att if v > prev else rel
        prev = coeff * prev + (1 - coeff) * v
        env[i] = prev

    over = np.maximum(env / thr, 1e-9)
    gain = np.where(env > thr, over ** (1.0 / ratio - 1.0), 1.0)  # smooth, no hard knee
    return x * (gain[:, None] if x.ndim > 1 else gain)


def excite(x: np.ndarray, sr: int, chain: Chain) -> np.ndarray:
    """Band-limited tanh saturation: adds harmonics in the mids/highs only."""
    if chain.drive_db <= 0:
        return x
    lo, hi = chain.drive_band_hz
    nyq = sr / 2
    sos = signal.butter(4, [min(lo / nyq, 0.99), min(hi / nyq, 0.99)], btype="bandpass", output="sos")
    band = signal.sosfiltfilt(sos, x, axis=0)
    drive = 10 ** (chain.drive_db / 20.0)
    shaped = np.tanh(band * drive) / np.tanh(drive)   # unity-ish small-signal gain
    return x + 0.6 * shaped


def stereo(x: np.ndarray, sr: int, chain: Chain) -> np.ndarray:
    if x.ndim < 2 or (chain.width == 1.0 and chain.mono_bass_hz <= 0):
        return x
    mid = x.mean(axis=1, keepdims=True)
    side = (x[:, 0] - x[:, 1]) / 2.0

    if chain.mono_bass_hz > 0:
        sos_lp = signal.butter(4, chain.mono_bass_hz / (sr / 2), btype="lowpass", output="sos")
        low_side = signal.sosfiltfilt(sos_lp, side)
        side = side - low_side                      # bass stays centred

    side = side * chain.width
    return np.column_stack([mid[:, 0] + side, mid[:, 0] - side])


# ---------------------------------------------------------------- limiting
def true_peak(x: np.ndarray, sr: int, oversample: int = 4) -> float:
    up = signal.resample_poly(x, oversample, 1, axis=0)
    return float(np.max(np.abs(up)))


def limit(x: np.ndarray, sr: int, ceiling_db: float, lookahead_ms: float = 5.0) -> np.ndarray:
    """Lookahead brickwall limiter with a smoothed gain envelope."""
    ceiling = 10 ** (ceiling_db / 20.0)
    peak = np.max(np.abs(x), axis=1) if x.ndim > 1 else np.abs(x)
    if peak.max() <= ceiling:
        return x

    need = np.minimum(ceiling / np.maximum(peak, 1e-12), 1.0)
    la = max(int(sr * lookahead_ms / 1000.0), 1)
    # take the minimum gain over the lookahead window so the limiter pre-empts peaks
    pad = np.pad(need, (0, la), mode="edge")
    win = np.lib.stride_tricks.sliding_window_view(pad, la + 1).min(axis=1)[: len(need)]
    smooth = signal.sosfiltfilt(signal.butter(2, 12.0 / (sr / 2), btype="lowpass", output="sos"), win)
    smooth = np.minimum(smooth, need)  # never exceed the required reduction
    return x * (smooth[:, None] if x.ndim > 1 else smooth)


def loudness(x: np.ndarray, sr: int) -> float | None:
    try:
        import pyloudnorm as pyln
        return float(pyln.Meter(sr).integrated_loudness(x))
    except Exception:
        return None


def true_peak_limit(x: np.ndarray, sr: int, ceiling_db: float) -> np.ndarray:
    """Guarantee the *inter-sample* peak stays under the ceiling.

    A sample-peak limiter alone leaves overshoots that many codecs and platform
    encoders turn into real clipping, so trim by the oversampled peak and re-limit.
    """
    ceiling = 10 ** (ceiling_db / 20.0)
    for _ in range(4):
        tp = true_peak(x, sr)
        if tp <= ceiling:
            break
        x = x * (ceiling / tp)
        x = limit(x, sr, ceiling_db)
    return x


def normalize(x: np.ndarray, sr: int, chain: Chain) -> np.ndarray:
    """Iterate gain -> limit until the requested LUFS is met at a true-peak ceiling."""
    x = limit(x, sr, chain.ceiling_db)
    if chain.target_lufs is None:
        return true_peak_limit(x, sr, chain.ceiling_db)

    for _ in range(6):
        current = loudness(x, sr)
        if current is None:
            return true_peak_limit(x, sr, chain.ceiling_db)
        delta = chain.target_lufs - current
        ceiling = 10 ** (chain.ceiling_db / 20.0)
        tp_ok = true_peak(x, sr) <= ceiling
        if abs(delta) < 0.1 and tp_ok:
            break
        if abs(delta) >= 0.1:
            x = x * (10 ** (delta / 20.0))
        x = true_peak_limit(limit(x, sr, chain.ceiling_db), sr, chain.ceiling_db)
    return true_peak_limit(x, sr, chain.ceiling_db)


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="Enhance / amplify an audio track")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--preset", default="neutral", choices=sorted(PRESETS))
    ap.add_argument("--target-lufs", type=float, default=None)
    ap.add_argument("--ceiling", type=float, default=None)
    ap.add_argument("--no-compress", action="store_true")
    ap.add_argument("--report", action="store_true", help="print before/after numbers")
    args = ap.parse_args()

    chain = PRESETS[args.preset]
    if args.target_lufs is not None:
        chain.target_lufs = args.target_lufs
    if args.ceiling is not None:
        chain.ceiling_db = args.ceiling
    if args.no_compress:
        chain.comp_threshold_db = None

    x, sr = sf.read(args.input, always_2d=True, dtype="float64")
    before = {"lufs": loudness(x, sr), "tp": true_peak(x, sr)}

    # pre-gain: nothing upstream should clip before the limiter
    pk = np.max(np.abs(x))
    if pk > 0.5:
        x = x * (0.5 / pk)

    x = apply_eq(x, sr, chain)
    x = excite(x, sr, chain)
    x = stereo(x, sr, chain)
    x = compress(x, sr, chain)
    x = normalize(x, sr, chain)

    # final safety: hard-trim any residual overshoot from rounding
    ceiling = 10 ** (chain.ceiling_db / 20.0)
    pk = np.max(np.abs(x))
    if pk > ceiling:
        x *= ceiling / pk

    sf.write(args.output, x, sr, subtype="PCM_24")
    after = {"lufs": loudness(x, sr), "tp": true_peak(x, sr)}

    if args.report:
        def fmt(v, unit):
            return f"{v:.2f} {unit}" if v is not None else "n/a"
        print(f"in : {fmt(before['lufs'], 'LUFS')} · true peak {fmt(DB * np.log10(max(before['tp'],1e-12)), 'dBTP')}")
        print(f"out: {fmt(after['lufs'], 'LUFS')} · true peak {fmt(DB * np.log10(max(after['tp'],1e-12)), 'dBTP')}")
    print(f"wrote {args.output} ({len(x)/sr:.2f}s @ {sr} Hz, 24-bit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
