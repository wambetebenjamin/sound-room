# "Benjamin voice" × Amapiano — full-pipeline test

## Source
`benjamin voice.mp3` from the repo's `main` branch — actually OGG, 16 kHz mono,
32.05 s. Male vocal centred on **G2**, ~57% voiced, phrase gaps at 3.3s / 4.7s / 19.7s / 22.9s.

Measured on arrival: −20.48 LUFS, peak −1.24 dBFS, 89% of energy below 500 Hz,
nothing above 8 kHz (16 kHz sample rate caps it there).

## Decisions, and why

| Decision | Evidence |
| --- | --- |
| Bed = `Amapiano-Beatpad/Beat7` | Only loop in **G minor**, matching the vocal's key; chroma correlation 0.63 (2nd best of 12) |
| Tempo 114.8 BPM, no time-stretch | The vocal has no reliable pulse (117.2 vs 125.0 BPM estimates). Beat7's native 114.8 avoids resampling artifacts entirely |
| Corrective EQ on the bed (+2 dB @1.2k/+3k, HP 45 Hz) | All 12 loops are 34–68% sub-bass. This setting scored closest to a target balance of sub 18 / bass 25 / mid 32 / high 7 |
| Sidechain duck 4 dB | Keeps the vocal on top without pumping the whole arrangement |
| Bed widened to 1.45×, vocal untouched | The vocal is mono; widening it would only smear the centre |

Rejected: `Beat5` (D minor) — chroma correlation 0.01, i.e. harmonically unrelated.

## Arrangement
2 bars intro (beat only) · vocal enters on the downbeat at 4.18 s · 2 bars outro. Total 39.11 s.

## Result
−14.57 LUFS · −1.00 dBTP · peak −1.57 dBFS · crest 16.23 dB · correlation 0.845
Vocal sits **+6.1 dB** over the bed (full band) and **+6.4 dB** in the 300 Hz–3 kHz presence band.

## What this exercised
1. `scripts/analyze_audio.py` — loudness, band balance, tempo/key
2. `pitch/key measurement` — pyin f0 tracking + chroma correlation across 12 candidate beds
3. `scripts/build_voice_track.py` — cleaning, arrangement, sidechain mix
4. `scripts/enhance_audio.py` — EQ, compression, true-peak limiting, loudness target
5. `ffmpeg` (via imageio-ffmpeg) — AAC/m4a decoding
6. GitHub Release — the download link

**Not exercised:** Demucs stem separation (`tools/stem-separator`) — pointless on a
mono voice memo with nothing else in it; and MusicGen — too slow/heavy for a 32 s
source on CPU.
