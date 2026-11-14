#!/usr/bin/env python3
"""
build_worship_arrangement.py — acoustic / stripped-back worship backing track.

Modelled on the instrumentation of an acoustic Hillsong-style live set:
fingerpicked acoustic guitar, felt piano + Rhodes, upright-style bass,
cajon and brushes instead of a loud kit, string swells on the chorus,
and a long spacious reverb.

Every sound is synthesised in code here (Karplus-Strong strings, additive/FM
pianos, formant-filtered percussion) — no samples, no sample packs, so the
output is your own production and carries no third-party rights.

The Karplus-Strong technique itself is public domain (1983); the implementation
below is original. Reference repos in tools/ (javascript-karplus-strong,
EKS-string-generator) are unlicensed and are used for study only.

Usage:
    python3 scripts/build_worship_arrangement.py -o public/music/beats/worship-D-72.wav \
        --key D --bpm 72 --bars 12
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

SR = 44100
RNG = np.random.default_rng(11)

MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]
OFFSET = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
          "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def midi_of(name: str) -> int:
    return 12 * (int(name[-1]) + 1) + OFFSET[name[:-1]]


def parse_chord(sym: str) -> tuple[int, bool]:
    """'Em' -> (4, True); 'D/F#' -> (2, False); 'Dsus4' -> (2, False)."""
    s = sym.strip().split("/")[0]
    letter, rest = s[0].upper(), s[1:]
    acc = 0
    while rest and rest[0] in "#b":
        acc += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    is_minor = rest.startswith("m") and not rest.startswith("maj")
    return (OFFSET[letter] + acc) % 12, is_minor


def chord_voicing(sym: str, key_root_midi: int) -> list[int]:
    """Voice a chord symbol as a triad near the key's register."""
    pc, is_minor = parse_chord(sym)
    m = 48 + pc
    while m < key_root_midi - 6:
        m += 12
    while m > key_root_midi + 10:
        m -= 12
    return [m, m + (3 if is_minor else 4), m + 7]


def noise(n: int) -> np.ndarray:
    return RNG.standard_normal(n)


def filt(x, lo=None, hi=None, sr=SR, order=2):
    from scipy import signal
    if lo and hi:
        sos = signal.butter(order, [lo / (sr / 2), min(hi / (sr / 2), 0.99)], btype="bandpass", output="sos")
    elif hi:
        sos = signal.butter(order, min(hi / (sr / 2), 0.99), btype="lowpass", output="sos")
    else:
        sos = signal.butter(order, lo / (sr / 2), btype="highpass", output="sos")
    return signal.sosfilt(sos, x)


# ---------------------------------------------------------------- instruments
def karplus_strong(freq: float, dur: float, sr: int = SR, decay: float = 0.9955,
                   brightness: float = 0.5, damp: float = 0.0) -> np.ndarray:
    """Plucked string via the Karplus-Strong delay line (block-vectorised).

    brightness 0 = soft/muted attack, 1 = bright plectrum.
    """
    n_delay = max(int(sr / freq), 2)
    n = int(dur * sr)
    total = n + n_delay
    y = np.zeros(total)

    # excitation: low-passed noise burst = pick position / softness
    exc = noise(n_delay)
    if brightness < 1.0:
        exc = filt(exc, hi=max(400, brightness * freq * 12 + 300), sr=sr)
    y[:n_delay] = exc / (np.max(np.abs(exc)) + 1e-9)

    b = np.clip(1.0 - brightness, 0.05, 0.95)   # averaging filter mix
    for start in range(n_delay, total, n_delay):
        end = min(start + n_delay, total)
        prev = y[start - n_delay:end - n_delay]
        if start - n_delay - 1 >= 0:
            prev_shift = y[start - n_delay - 1:end - n_delay - 1]
        else:
            prev_shift = prev
        y[start:end] = decay * ((1 - b) * prev + b * prev_shift)

    out = y[:n]
    # string damping toward the end of the note (player lifting off)
    if damp > 0:
        k = int(damp * n)
        if k > 0:
            out[-k:] *= np.linspace(1, 0, k)
    return out


def guitar(freq: float, dur: float, sr=SR) -> np.ndarray:
    x = karplus_strong(freq, dur, sr, decay=0.9965, brightness=0.78)
    # body resonance + pick transient
    body = filt(x, lo=90, hi=5200, sr=sr)
    body = body + 0.25 * filt(x, lo=100, hi=260, sr=sr)
    body = filt(body, lo=150, sr=sr)            # leave the low end to the bass
    n = min(len(body), int(0.004 * sr))
    body[:n] += noise(n) * np.linspace(0.25, 0, n)
    return body * 0.5


def bass(freq: float, dur: float, sr=SR) -> np.ndarray:
    x = karplus_strong(freq, dur, sr, decay=0.999, brightness=0.25)
    return filt(x, lo=35, hi=900, sr=sr) * 0.55


def felt_piano(freq: float, dur: float, sr=SR) -> np.ndarray:
    n = int(dur * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    # slight inharmonicity, like a real string
    for k, amp in ((1, 1.0), (2, 0.42), (3, 0.20), (4, 0.10), (5, 0.05)):
        f = freq * k * (1 + 0.0004 * k * k)
        if f > sr / 2:
            break
        out += amp * np.sin(2 * np.pi * f * t) * np.exp(-t / (dur * (0.55 / k)))
    # hammer felt: soft attack, no click
    out *= np.clip(t / 0.006, 0, 1)
    out[: int(0.02 * sr)] += noise(min(int(0.02 * sr), n))[: min(int(0.02 * sr), n)] * 0.02
    return filt(out, lo=70, sr=sr) * 0.15


def rhodes(freq: float, dur: float, sr=SR) -> np.ndarray:
    n = int(dur * sr)
    t = np.arange(n) / sr
    index = 2.2 * np.exp(-t / 0.22)          # FM index decays -> bell attack
    mod = np.sin(2 * np.pi * freq * t)
    return np.sin(2 * np.pi * freq * t + index * mod) * np.exp(-t / (dur * 0.55)) * 0.15


def cajon_bass(sr=SR) -> np.ndarray:
    n = int(0.28 * sr)
    t = np.arange(n) / sr
    f = 95 * np.exp(-t / 0.02) + 62
    x = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / 0.10)
    x += filt(noise(n), hi=900, sr=sr) * np.exp(-t / 0.012) * 0.5
    return np.tanh(x * 1.4) * 0.5


def cajon_slap(sr=SR) -> np.ndarray:
    n = int(0.13 * sr)
    t = np.arange(n) / sr
    x = filt(noise(n), lo=900, hi=5200, sr=sr) * np.exp(-t / 0.022)
    x += filt(noise(n), lo=180, hi=420, sr=sr) * np.exp(-t / 0.035) * 0.6
    return x * 0.4


def brushes(sr=SR) -> np.ndarray:
    n = int(0.42 * sr)
    t = np.arange(n) / sr
    env = np.clip(t / 0.05, 0, 1) * np.exp(-t / 0.20)      # soft swell, not a hit
    return filt(noise(n), lo=2500, hi=9000, sr=sr) * env * 0.22


def strings(freq: float, dur: float, sr=SR) -> np.ndarray:
    """Bowed string: harmonic stack + vibrato + bow noise + slow swell."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    vib = 1 + 0.0035 * np.sin(2 * np.pi * 5.2 * t + RNG.uniform(0, 6))
    out = np.zeros(n)
    for k in range(1, 13):
        f = freq * k
        if f > sr / 2 * 0.9:
            break
        out += (1.0 / k) * np.sin(2 * np.pi * f * np.cumsum(vib) / sr + k)
    bow = filt(noise(n), lo=1500, hi=6000, sr=sr) * 0.03
    env = np.clip(t / 0.45, 0, 1) * np.clip((dur - t) / 0.6, 0, 1)   # slow in/out
    return (out * 0.11 + bow) * env


def pad(freq: float, dur: float, sr=SR) -> np.ndarray:
    n = int(dur * sr)
    t = np.arange(n) / sr
    x = np.zeros(n)
    for det in (-0.7, 0.0, 0.7):
        x += np.sin(2 * np.pi * (freq + det) * t)
    x *= np.clip(t / 0.6, 0, 1) * np.clip((dur - t) / 0.8, 0, 1) / 3
    return x * 0.12


# ---------------------------------------------------------------- space
def reverb(x: np.ndarray, sr: int = SR, seconds: float = 2.4, wet: float = 0.26) -> np.ndarray:
    """Synthetic hall: exponentially decaying decorrelated noise IR."""
    from scipy.signal import fftconvolve
    n = int(seconds * sr)
    t = np.arange(n) / sr
    ir = np.empty((n, 2))
    for ch in range(2):
        ir[:, ch] = noise(n) * np.exp(-t / (seconds * 0.32))
    ir[: int(0.02 * sr)] *= np.linspace(0, 1, int(0.02 * sr))[:, None]   # pre-delay fade
    ir /= np.max(np.abs(ir))
    wet_sig = np.column_stack([fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)])
    return x * (1 - wet) + wet_sig * wet * 2.2


# ---------------------------------------------------------------- arrangement
class Bus:
    def __init__(self, seconds: float, sr: int = SR):
        self.sr, self.n = sr, int(seconds * sr) + sr * 3
        self.buf = np.zeros((self.n, 2))

    def add(self, sig: np.ndarray, at: float, pan: float = 0.0, gain: float = 1.0):
        i = int(at * self.sr)
        if i < 0 or i >= self.n:
            return
        e = min(i + len(sig), self.n)
        seg = sig[: e - i] * gain
        self.buf[i:e, 0] += seg * np.cos((pan + 1) * np.pi / 4)
        self.buf[i:e, 1] += seg * np.sin((pan + 1) * np.pi / 4)


DEFAULT_FORM = [("intro", 4), ("verse", 8), ("chorus", 8), ("verse", 8),
                ("chorus", 8), ("bridge", 4), ("chorus", 8), ("outro", 4)]


def build(key: str = "D", bpm: float = 72.0, bars: int | None = 12, sr: int = SR,
          chords: list[str] | None = None,
          form: list[tuple[str, int]] | None = None) -> np.ndarray:
    if key.lower().endswith("min"):
        root_name, quality = key[:-3], "min"
    elif key.lower().endswith("maj"):
        root_name, quality = key[:-3], "maj"
    elif key.endswith("m") and len(key) > 1:
        root_name, quality = key[:-1], "min"
    else:
        root_name, quality = key, "maj"
    scale = MAJOR if quality == "maj" else MINOR
    root = midi_of(root_name + "3")

    def deg(d: int, octave: int = 0) -> int:
        return root + scale[d % 7] + 12 * (d // 7) + 12 * octave

    def chord(d: int) -> list[int]:
        return [deg(d), deg(d + 2), deg(d + 4)]

    prog = [0, 4, 5, 3]                     # I - V - vi - IV  (D A Bm G in D)

    if chords:
        # explicit progression from a chord chart (progressions are not copyrightable;
        # the chart's lyrics and melody are the publisher's and are never reproduced here)
        seq = [chord_voicing(c, root) for c in chords]
        chord_of_bar_fn = lambda b: seq[b % len(seq)]
    else:
        chord_of_bar_fn = lambda b: chord(prog[b % 4])
    # ---- song form: which section each bar belongs to, and where it sits inside it
    if form is None:
        form = DEFAULT_FORM if bars is None or bars > 12 else [("intro", 2), ("verse", max(1, bars // 2 - 2)),
                                                               ("chorus", max(1, bars - bars // 2 - 2)), ("outro", 2)]
    section_of_bar, bar_in_section = [], []
    for name, n in form:
        section_of_bar.extend([name] * n)
        bar_in_section.extend(range(n))
    bars = len(section_of_bar)

    beat = 60.0 / bpm
    bar = 4 * beat
    total = bars * bar
    bus = Bus(total + 4, sr)

    for b in range(bars):
        t0 = b * bar
        section = section_of_bar[b]
        bis = bar_in_section[b]
        is_last = b == bars - 1
        # the progression restarts at each section boundary so verses land on the tonic
        ch = chord_of_bar_fn(bis)
        # energy builds across the song: last chorus is the biggest moment
        energy = 1.12 if (section == "chorus" and b > bars * 0.75) else 1.0
        if section == "bridge":
            energy = 0.85 + 0.08 * bis

        def add(snd, tm, pan=0.0, gain=1.0):
            bus.add(snd, tm, pan=pan, gain=gain * energy)
        bass_note = ch[0] - 12

        # ---- fingerpicked acoustic guitar (always present)
        arp = [ch[0], ch[2], ch[1] + 12, ch[2], ch[0], ch[2], ch[1] + 12, ch[2]]
        for i, m in enumerate(arp):
            pos = i * beat * 0.5
            g = 0.85 if i % 4 == 0 else 0.62
            add(guitar(hz(m), min(2.2, bar * 0.7), sr), t0 + pos, pan=-0.45, gain=g)
        # second pass, slightly late and duller = natural double-track width
        for i, m in enumerate(arp):
            add(guitar(hz(m), 1.8, sr), t0 + i * beat * 0.5 + 0.008, pan=0.5, gain=0.42)

        # ---- felt piano / Rhodes
        for hit, g in ((0.0, 1.0), (2.0, 0.8)):
            for k, m in enumerate(ch):
                # root stays low for body, upper voices move up an octave for clarity
                note = m if k == 0 else m + 12
                add(felt_piano(hz(note), 2.6, sr), t0 + hit * beat, pan=-0.15 + 0.12 * k, gain=g)
        if section in ("chorus", "outro"):
            for m in ch:
                add(rhodes(hz(m + 12), 1.6, sr), t0, pan=0.3, gain=0.7)
        if section == "chorus":
            add(felt_piano(hz(ch[2] + 12), 1.4, sr), t0 + 3.0 * beat, pan=0.1, gain=0.6)

        # ---- upright-style bass
        if section in ("verse", "chorus"):
            for pos, g in ((0.0, 1.0), (2.0, 0.85), (3.5, 0.7)):
                add(bass(hz(bass_note), 1.5, sr), t0 + pos * beat, gain=g)

        # ---- cajon + brushes instead of a drum kit
        if section in ("verse", "chorus"):
            for pos in (0.0, 2.0):
                add(cajon_bass(sr), t0 + pos * beat, gain=1.0)
            for pos in (1.0, 3.0):
                add(cajon_slap(sr), t0 + pos * beat, pan=0.1, gain=0.9)
            for pos in (1.5, 3.5):
                add(cajon_slap(sr), t0 + pos * beat, pan=0.15, gain=0.45)
            for i in range(8):
                add(brushes(sr), t0 + i * beat * 0.5, pan=-0.3,
                        gain=0.85 if section == "chorus" else 0.55)

        # ---- strings and pad swell on the chorus
        if section == "chorus":
            for m in ch:
                add(strings(hz(m), bar * 0.98, sr), t0, pan=-0.55, gain=0.9)
                add(strings(hz(m + 12), bar * 0.98, sr), t0 + 0.01, pan=0.55, gain=0.5)
            for m in ch:
                add(pad(hz(m + 12), bar * 1.05, sr), t0, pan=0.0, gain=0.8)
        elif section == "outro":
            for m in ch:
                add(pad(hz(m + 12), bar * 1.05, sr), t0, pan=0.0, gain=0.9)

    audio = bus.buf[: int(total * sr)]
    from enhance_audio import _biquad
    from scipy import signal as _sig
    audio = _sig.sosfiltfilt(_biquad("highshelf", sr, 4000.0, 4.0, 0.707)[None, :], audio, axis=0)
    audio = reverb(audio, sr, seconds=2.4, wet=0.26)
    audio -= audio.mean(axis=0, keepdims=True)
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio *= 0.8 / peak
    return audio


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--key", default="D")
    ap.add_argument("--bpm", type=float, default=72.0)
    ap.add_argument("--bars", type=int, default=12)
    args = ap.parse_args()

    audio = build(args.key, args.bpm, args.bars)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    import soundfile as sf
    sf.write(args.output, audio, SR, subtype="PCM_24")
    print(f"wrote {args.output} · {len(audio)/SR:.2f}s · {args.bpm} BPM · {args.key} · {args.bars} bars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
