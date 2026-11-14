#!/usr/bin/env python3
"""
build_original_beat.py — synthesise a complete backing track from code.

Every sound here is generated numerically: no samples, loops, or third-party
audio, so the output is entirely your own production and free of anyone else's
copyright. Elements are a fusion aimed at amapiano / worship-electric / phonk:

  kick · clap · closed+open hats · shaker      (drums)
  log drum (pitch-glide) · 808 sub with drive   (bass)
  electric-piano chords · slow pad              (worship texture)
  bell lead · cowbell                           (phonk / melody)

Usage:
    python3 scripts/build_original_beat.py -o public/music/beats/gm-114.wav \
        --bpm 114.8 --key Gm --bars 20
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

SR = 44100
RNG = np.random.default_rng(7)

SCALES = {
    "maj": [0, 2, 4, 5, 7, 9, 11],
    "min": [0, 2, 3, 5, 7, 8, 10],
}
NOTE_OFFSET = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
               "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def midi(name: str) -> int:
    """'G2' -> midi number."""
    pitch, octave = name[:-1], int(name[-1])
    return 12 * (octave + 1) + NOTE_OFFSET[pitch]


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def env(n: int, attack: float, decay: float, sr: int = SR) -> np.ndarray:
    t = np.arange(n) / sr
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / max(decay, 1e-4))


def noise(n: int) -> np.ndarray:
    return RNG.standard_normal(n)


def lowpass(x, cutoff, sr=SR, order=2):
    from scipy import signal
    sos = signal.butter(order, min(cutoff / (sr / 2), 0.99), btype="lowpass", output="sos")
    return signal.sosfilt(sos, x)


def bandpass(x, lo, hi, sr=SR, order=2):
    from scipy import signal
    sos = signal.butter(order, [lo / (sr / 2), min(hi / (sr / 2), 0.99)], btype="bandpass", output="sos")
    return signal.sosfilt(sos, x)


def highpass(x, cutoff, sr=SR, order=2):
    from scipy import signal
    sos = signal.butter(order, cutoff / (sr / 2), btype="highpass", output="sos")
    return signal.sosfilt(sos, x)


# ---------------------------------------------------------------- instruments
def kick(sr=SR, gain=1.0) -> np.ndarray:
    n = int(0.42 * sr)
    t = np.arange(n) / sr
    f = 132 * np.exp(-t / 0.030) + 47                      # pitch sweep
    phase = 2 * np.pi * np.cumsum(f) / sr
    body = np.sin(phase) * np.exp(-t / 0.16)
    click = highpass(noise(n), 1800) * np.exp(-t / 0.004) * 0.5
    return np.tanh((body + click) * 1.6) * 0.46 * gain


def clap(sr=SR, gain=1.0) -> np.ndarray:
    n = int(0.30 * sr)
    out = np.zeros(n)
    for i, off in enumerate((0.0, 0.008, 0.019)):          # three-tap flam
        s = int(off * sr)
        seg = bandpass(noise(n - s), 1100, 3600) * np.exp(-np.arange(n - s) / sr / 0.035)
        out[s:] += seg * (1.0 - 0.25 * i)
    return out * 0.74 * gain


def hat(open_: bool = False, sr=SR, gain=1.0) -> np.ndarray:
    n = int((0.28 if open_ else 0.055) * sr)
    t = np.arange(n) / sr
    x = highpass(noise(n), 7200) * np.exp(-t / (0.11 if open_ else 0.014))
    return x * (0.36 if open_ else 0.22) * gain


def shaker(sr=SR, gain=1.0) -> np.ndarray:
    n = int(0.07 * sr)
    t = np.arange(n) / sr
    return bandpass(noise(n), 4500, 11000) * np.exp(-t / 0.020) * 0.24 * gain


def log_drum(note_midi: float, sr=SR, gain=1.0) -> np.ndarray:
    """The amapiano signature: a short pitch-glide sine stab."""
    n = int(0.38 * sr)
    t = np.arange(n) / sr
    f0 = hz(note_midi)
    f = f0 * (1.0 + 1.15 * np.exp(-t / 0.026))             # glide down into the note
    phase = 2 * np.pi * np.cumsum(f) / sr
    x = np.sin(phase) * np.exp(-t / 0.15)
    x += 0.25 * np.sin(2 * phase) * np.exp(-t / 0.07)
    return np.tanh(x * 2.0) * 0.34 * gain


def bass808(note_midi: float, sr=SR, gain=1.0) -> np.ndarray:
    n = int(1.5 * sr)
    t = np.arange(n) / sr
    f = hz(note_midi)
    phase = 2 * np.pi * f * t
    x = np.sin(phase) * np.exp(-t / 0.9)
    x = np.tanh(x * 3.2)                                    # phonk-style drive
    return lowpass(x, 180) * 0.20 * gain


def cowbell(sr=SR, gain=1.0) -> np.ndarray:
    n = int(0.20 * sr)
    t = np.arange(n) / sr
    sq = lambda f: np.sign(np.sin(2 * np.pi * f * t))
    x = bandpass(sq(832) + 0.7 * sq(1236), 500, 3200) * np.exp(-t / 0.045)
    return x * 0.34 * gain


def ep_note(note_midi: float, dur: float, sr=SR, gain=1.0) -> np.ndarray:
    """Electric-piano-ish: fundamental + a couple of harmonics, soft attack."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    f = hz(note_midi)
    x = (np.sin(2 * np.pi * f * t) + 0.30 * np.sin(4 * np.pi * f * t)
         + 0.12 * np.sin(6 * np.pi * f * t))
    x *= env(n, 0.012, dur * 0.45) * (1 + 0.15 * np.sin(2 * np.pi * 4.5 * t))
    return x * 0.21 * gain


def pad_note(note_midi: float, dur: float, sr=SR, gain=1.0) -> np.ndarray:
    n = int(dur * sr)
    t = np.arange(n) / sr
    f = hz(note_midi)
    x = np.zeros(n)
    for det in (-0.95, 0.0, 0.95):                          # detuned stack = width
        x += np.sin(2 * np.pi * (f + det) * t)
    x *= env(n, 0.35, dur) / 3.0
    return x * 0.15 * gain


def bell(note_midi: float, dur: float = 0.9, sr=SR, gain=1.0) -> np.ndarray:
    n = int(dur * sr)
    t = np.arange(n) / sr
    f = hz(note_midi)
    x = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t)
         + 0.25 * np.sin(2 * np.pi * f * 5.4 * t))
    return x * np.exp(-t / (dur * 0.35)) * 0.36 * gain


# ---------------------------------------------------------------- sequencer
class Track:
    def __init__(self, seconds: float, sr: int = SR):
        self.sr = sr
        self.n = int(seconds * sr) + sr
        self.buf = np.zeros((self.n, 2))

    def add(self, sig: np.ndarray, at: float, pan: float = 0.0, gain: float = 1.0):
        i = int(at * self.sr)
        if i < 0 or i >= self.n:
            return
        end = min(i + len(sig), self.n)
        seg = sig[: end - i] * gain
        l = np.cos((pan + 1) * np.pi / 4)
        r = np.sin((pan + 1) * np.pi / 4)
        self.buf[i:end, 0] += seg * l
        self.buf[i:end, 1] += seg * r

    def out(self, seconds: float) -> np.ndarray:
        return self.buf[: int(seconds * self.sr)]


def build(bpm: float, key: str, bars: int, sr: int = SR) -> np.ndarray:
    if key.lower().endswith("min"):
        root_name, quality = key[:-3], "min"
    elif key.lower().endswith("maj"):
        root_name, quality = key[:-3], "maj"
    elif key.endswith("m") and len(key) > 1:
        root_name, quality = key[:-1], "min"
    else:
        root_name, quality = key, "maj"
    root = midi(root_name + "3")
    scale = [(root + i) for i in SCALES[quality]]

    beat = 60.0 / bpm
    bar = 4 * beat
    step = beat / 4                                        # 16th
    total = bars * bar
    tr = Track(total + 2, sr)

    def deg_to_midi(d: int) -> int:
        """Scale degree -> midi, carrying octaves when d goes past the 7th."""
        return root + SCALES[quality][d % 7] + 12 * (d // 7)

    # i - VI - III - VII  (Gm - Eb - Bb - F in G minor): anthemic, worship-friendly
    prog = [0, 5, 2, 6]

    def chord_of_bar(b: int) -> list[int]:
        d = prog[b % 4]
        return [deg_to_midi(d + j) for j in (0, 2, 4)]      # root, third, fifth

    # ---- arrangement map: pads-only intro, groove, breakdown, big finish
    groove_start = 2
    breakdown = max(groove_start + 4, bars - 6)
    for b in range(bars):
        t0 = b * bar
        full = b >= groove_start
        is_break = breakdown <= b < breakdown + 2

        # pad every bar (the worship bed) — sustained across the whole bar
        for k, m in enumerate(chord_of_bar(b)):
            tr.add(pad_note(m + 12, bar * 1.05), t0, pan=(-0.5 + 0.5 * k), gain=1.0)

        # electric piano chord stabs
        for hit, g in ((0.0, 1.0), (2.5, 0.65)):
            for k, m in enumerate(chord_of_bar(b)):
                tr.add(ep_note(m + 12, 1.1), t0 + hit * beat, pan=(-0.3 + 0.3 * k), gain=g)
        if full and not is_break:
            tr.add(ep_note(chord_of_bar(b)[0] + 12, 0.5), t0 + 3.5 * beat, pan=0.2, gain=0.5)

        if not full:
            continue

        # drums
        for pos in (0.0, 2.0, 2.75):
            tr.add(kick(), t0 + pos * beat, gain=1.0)
        if is_break:
            tr.add(kick(), t0 + 3.5 * beat, gain=0.7)
        for pos in (1.0, 3.0):
            tr.add(clap(), t0 + pos * beat, pan=0.05, gain=0.9)
        for i in range(8):                                 # 8ths, slight swing
            pos = i * 0.5 + (0.06 if i % 2 else 0.0)
            if is_break and i % 2:
                continue
            tr.add(hat(), t0 + pos * beat, pan=0.25, gain=1.0 if i % 2 == 0 else 0.7)
        tr.add(hat(open_=True), t0 + 3.5 * beat, pan=0.2, gain=0.9)
        for i in range(16):                                # shaker 16ths
            tr.add(shaker(), t0 + i * step, pan=-0.35, gain=0.8 if i % 2 else 1.0)

        # log-drum bassline (amapiano)
        pattern = [(0.0, 0), (0.75, 0), (1.5, 2), (2.25, 0), (3.0, 1), (3.5, 4)]
        for pos, deg in pattern:
            if is_break and pos not in (0.0, 2.25):
                continue
            tr.add(log_drum(deg_to_midi(deg) - 12), t0 + pos * beat, gain=1.0)

        # 808 sub on the downbeat of the finish
        if b >= breakdown:
            tr.add(bass808(root - 24), t0, gain=0.9)

        # cowbell (phonk accent) — sparse, on the "and" of 2
        if b % 2 == 1:
            tr.add(cowbell(), t0 + 1.5 * beat, pan=0.3, gain=0.8)

        # bell lead: pentatonic-ish phrase in the last section
        if b >= breakdown:
            for pos, deg in ((0.5, 0), (1.25, 2), (2.0, 4), (3.25, 2)):
                tr.add(bell(scale[deg] + 12, 0.9), t0 + pos * beat, pan=-0.15, gain=0.85)

    audio = tr.out(total)
    from enhance_audio import _biquad
    from scipy import signal as _sig
    shelf = _biquad("peak", sr, 3000.0, 4.0, 0.8)[None, :]
    audio = _sig.sosfiltfilt(shelf, audio, axis=0)
    # gentle bus glue: soft-knee saturation + DC removal
    audio = np.tanh(audio * 1.1) * 0.9
    audio -= audio.mean(axis=0, keepdims=True)
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio *= 0.75 / peak
    return audio.astype(np.float64)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--bpm", type=float, default=114.8)
    ap.add_argument("--key", default="Gm")
    ap.add_argument("--bars", type=int, default=20)
    args = ap.parse_args()

    audio = build(args.bpm, args.key, args.bars)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    import soundfile as sf
    sf.write(args.output, audio, SR, subtype="PCM_24")
    dur = len(audio) / SR
    rms = float(np.sqrt(np.mean(audio ** 2)))
    print(f"wrote {args.output} · {dur:.2f}s · {args.bpm} BPM · {args.key} · "
          f"{args.bars} bars · RMS {20*np.log10(max(rms,1e-12)):.1f} dBFS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
