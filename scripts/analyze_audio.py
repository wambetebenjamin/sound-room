#!/usr/bin/env python3
"""
analyze_audio.py — diagnostic report for a song before "amplifying" it.

Tells you what is actually wrong (or right) with a track so the enhancement
chain is chosen from evidence, not guesswork.

Usage:
    python3 scripts/analyze_audio.py <audio file> [--json]

Reports: format/loudness/clipping, spectral balance, stereo width,
noise floor, tempo and key.
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import numpy as np
import soundfile as sf

# Krumhansl-Schmuckler key profiles (pitch-class salience for major/minor).
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

BANDS = [
    ("sub", 20, 60), ("bass", 60, 250), ("low_mid", 250, 500),
    ("mid", 500, 2000), ("high_mid", 2000, 4000),
    ("presence", 4000, 8000), ("air", 8000, 16000),
]


def db(x: float) -> float:
    return float(20.0 * math.log10(max(x, 1e-12)))


def analyze(path: str) -> dict:
    y, sr = sf.read(path, always_2d=True, dtype="float64")
    n_samples, n_ch = y.shape
    dur = n_samples / sr
    mono = y.mean(axis=1)

    report: dict = {
        "file": path,
        "sample_rate": sr,
        "channels": n_ch,
        "duration_sec": round(dur, 2),
        "samples": n_samples,
    }

    # ---- levels -------------------------------------------------------------
    peak = float(np.max(np.abs(y)))
    report["peak_dbfs"] = round(db(peak), 2)
    rms = float(np.sqrt(np.mean(mono ** 2)))
    report["rms_dbfs"] = round(db(rms), 2)
    report["crest_factor_db"] = round(db(peak / rms) if rms else 0.0, 2)

    # Clipping: consecutive samples pinned at/near full scale.
    near_full = np.abs(y) >= 0.999
    report["clipped_samples"] = int(near_full.sum())
    report["clipped_percent"] = round(100.0 * near_full.sum() / y.size, 4)

    # ---- loudness (BS.1770 via pyloudnorm) ---------------------------------
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sr)
        report["integrated_lufs"] = round(float(meter.integrated_loudness(y)), 2)
    except Exception as exc:  # pragma: no cover - meter needs >=0.4s audio
        report["integrated_lufs"] = None
        report["loudness_error"] = str(exc)

    # ---- spectral balance ---------------------------------------------------
    mono_f = mono - mono.mean()
    spec = np.abs(np.fft.rfft(mono_f * np.hanning(len(mono_f))))
    freqs = np.fft.rfftfreq(len(mono_f), 1.0 / sr)
    power = spec ** 2
    total = float(power.sum()) or 1.0
    report["band_energy_pct"] = {}
    for name, lo, hi in BANDS:
        m = (freqs >= lo) & (freqs < hi)
        report["band_energy_pct"][name] = round(100.0 * float(power[m].sum()) / total, 1)

    centroid = float((freqs * spec).sum() / (spec.sum() or 1.0))
    report["spectral_centroid_hz"] = round(centroid, 1)
    cum = np.cumsum(power)
    rolloff_idx = int(np.searchsorted(cum, 0.85 * cum[-1]))
    report["rolloff85_hz"] = round(float(freqs[min(rolloff_idx, len(freqs) - 1)]), 1)

    # ---- noise floor / dynamics --------------------------------------------
    frame = int(0.05 * sr)
    if len(mono) > frame * 4:
        n_frames = len(mono) // frame
        frames = mono[: n_frames * frame].reshape(n_frames, frame)
        frame_rms = np.sqrt((frames ** 2).mean(axis=1))
        quiet = float(np.percentile(frame_rms, 5))
        loud = float(np.percentile(frame_rms, 95))
        report["noise_floor_dbfs"] = round(db(quiet), 2)
        # 5th-to-95th percentile spread: for continuous music this is a dynamic-range
        # measure, NOT a signal-to-noise ratio (a loud, unbroken track scores low here
        # without being noisy).
        report["dynamic_range_db"] = round(db(loud) - db(quiet), 2)

    # ---- stereo -------------------------------------------------------------
    if n_ch >= 2:
        l, r = y[:, 0], y[:, 1]
        denom = math.sqrt(float(np.sum(l ** 2) * np.sum(r ** 2)))
        corr = float(np.sum(l * r) / denom) if denom else 0.0
        report["stereo_correlation"] = round(corr, 3)
        mid, side = (l + r) / 2, (l - r) / 2
        side_e, mid_e = float(np.sum(side ** 2)), float(np.sum(mid ** 2)) or 1e-12
        report["side_to_mid_db"] = round(10 * math.log10(max(side_e / mid_e, 1e-12)), 2)
        report["mono_compatible"] = bool(corr > -0.2)
    else:
        report["stereo_correlation"] = None
        report["layout"] = "mono"

    # ---- tempo & key --------------------------------------------------------
    try:
        import librosa
        y_mono = mono.astype(np.float32)
        tempo, _ = librosa.beat.beat_track(y=y_mono, sr=sr)
        report["tempo_bpm"] = round(float(np.atleast_1d(tempo)[0]), 1)

        chroma = librosa.feature.chroma_cqt(y=y_mono, sr=sr).mean(axis=1)
        best = (None, -2.0, None)
        for i in range(12):
            for profile, mode in ((MAJOR, "major"), (MINOR, "minor")):
                rolled = np.roll(profile, i)
                c = float(np.corrcoef(chroma, rolled)[0, 1])
                if c > best[1]:
                    best = (f"{NOTES[i]} {mode}", c, mode)
        report["key_estimate"] = best[0]
        report["key_confidence"] = round(best[1], 3)
    except Exception as exc:
        report["tempo_bpm"] = None
        report["key_error"] = str(exc)

    return report


def diagnose(r: dict) -> list[str]:
    """Turn numbers into plain-language findings."""
    out: list[str] = []
    lufs = r.get("integrated_lufs")
    if lufs is not None:
        if lufs < -18:
            out.append(f"Quiet: {lufs} LUFS (streaming targets ~-14). Needs gain + limiting.")
        elif lufs < -11:
            out.append(f"Healthy loudness: {lufs} LUFS — close to streaming target.")
        else:
            out.append(f"Very hot: {lufs} LUFS — little headroom left, risky for platforms.")

    if (r.get("peak_dbfs") or -99) > -0.1 or r.get("clipped_percent", 0) > 0.001:
        out.append(f"Peaks at {r.get('peak_dbfs')} dBFS / {r.get('clipped_percent')}% clipped samples — "
                   "intersample clipping likely; needs true-peak limiting.")
    if (r.get("peak_dbfs") or -99) < -3:
        out.append(f"Peak only {r.get('peak_dbfs')} dBFS — lots of unused headroom.")

    bands = r.get("band_energy_pct") or {}
    if bands.get("sub", 0) + bands.get("bass", 0) > 60:
        out.append("Bass-heavy: over 60% of energy below 250 Hz — likely boomy/muddy.")
    if bands.get("sub", 0) + bands.get("bass", 0) < 15:
        out.append("Thin low end: under 15% of energy below 250 Hz.")
    if bands.get("air", 0) < 2:
        out.append("Dull top: less than 2% of energy above 8 kHz — needs air/exciter.")
    if bands.get("presence", 0) > 25:
        out.append("Harsh: presence band 4–8 kHz is very strong.")

    corr = r.get("stereo_correlation")
    if corr is not None:
        if corr > 0.95:
            out.append(f"Very narrow: correlation {corr} — almost mono, can be widened.")
        elif corr < 0.0:
            out.append(f"Out-of-phase risk: correlation {corr} — will thin out in mono.")

    dyn = r.get("dynamic_range_db")
    if dyn is not None and dyn < 6:
        out.append(f"Very flat dynamics (5th-95th percentile spread {dyn} dB) — heavily squashed.")

    if not out:
        out.append("No major issues detected — light polish only.")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Audio diagnostic report")
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true", help="print raw JSON only")
    args = ap.parse_args()

    try:
        report = analyze(args.path)
    except Exception as exc:
        print(f"Failed to analyze {args.path}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"\n=== {report['file']} ===")
    print(f"{report['duration_sec']}s · {report['sample_rate']} Hz · "
          f"{report['channels']} ch · {report.get('tempo_bpm')} BPM · {report.get('key_estimate')}")
    print(f"Loudness {report.get('integrated_lufs')} LUFS · peak {report['peak_dbfs']} dBFS · "
          f"RMS {report['rms_dbfs']} dBFS · crest {report['crest_factor_db']} dB")
    print("\nBand energy %:")
    for k, v in (report.get("band_energy_pct") or {}).items():
        print(f"  {k:<9} {v:>5}%")
    print(f"\nSpectral centroid {report.get('spectral_centroid_hz')} Hz · "
          f"85% rolloff {report.get('rolloff85_hz')} Hz")
    if report.get("stereo_correlation") is not None:
        print(f"Stereo correlation {report['stereo_correlation']} · "
              f"side/mid {report.get('side_to_mid_db')} dB")
    print("\nFindings:")
    for line in diagnose(report):
        print(f"  • {line}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
